"""ECHONET device connector and coordinator."""

import asyncio
import logging
import os
import time
from functools import partial
from importlib import import_module
from typing import Any
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pychonet import ECHONETAPIClient
from pychonet.echonetapiclient import EchonetMaxOpcError
from pychonet.lib.epc import EPC_SUPER
from pychonet.lib.epc_functions import _hh_mm

from .const import (
    CONF_BATCH_SIZE_MAX,
    CONF_FORCE_POLLING,
    CONF_ENABLE_SUPER_ENERGY,
    DOMAIN,
    ENABLE_SUPER_ENERGY_DEFAULT,
    ENL_OP_CODES,
    ENL_SUPER_CODES,
    ENL_SUPER_ENERGES,
    MISC_OPTIONS,
    TEMP_OPTIONS,
    USER_OPTIONS,
)

from .config_flow import ErrorConnect
from .sharp import sharp_command, sharp_raw, sharp_value

_LOGGER = logging.getLogger(__name__)

# Batch size constants for ECHONET protocol
MAX_UPDATE_BATCH_SIZE = 10
MIN_UPDATE_BATCH_SIZE = 3
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

# How often to poll STATMAP (push-covered) EPCs as a reconciliation
# fallback, in seconds. These EPCs are normally served entirely by INF
# push notifications and excluded from the regular poll batches — this
# interval bounds how long a dropped/missed INF can leave HA state stale.
# Default matches the low end of the 5-15 min range suggested for
# balancing traffic reduction against staleness risk on lossy UDP networks.
STATMAP_RECONCILE_INTERVAL = 300

# Silence threshold before marking entities unavailable.
# A single failed poll does not immediately cause unavailability — the host
# must have been completely silent (no packets received by pychonet) for
# this duration. Matches pyhems' RuntimeMonitor threshold.
ACTIVITY_TIMEOUT = 300  # 5 minutes

# Per-host semaphore to serialise poll cycles across all ECHONETConnector
# instances sharing the same host IP. Embedded ECHONET devices have limited
# UDP stacks and can drop frames if polled concurrently. A semaphore(1) ensures
# only one instance polls a given host at a time — others wait their turn rather
# than piling up requests. This gives embedded firmware breathing room and
# naturally staggers requests without any fixed time delays.
# Shared across all ECHONETConnector instances via a module-level dict.
_host_semaphores: dict[str, asyncio.Semaphore] = {}


def regist_as_inputs(epc_function_data):
    """Check if EPC function data should be registered as input entity.

    Args:
        epc_function_data: The EPC function data to check.

    Returns:
        True if the EPC should be registered as an input (Switch, Select, or Time).
    """
    if epc_function_data:
        if type(epc_function_data) == list:
            if type(epc_function_data[1]) == dict and len(epc_function_data[1]) > 1:
                return True  # Switch or Select
            if callable(epc_function_data[0]) and epc_function_data[0] == _hh_mm:
                return True  # Time
        elif callable(epc_function_data) and epc_function_data == _hh_mm:
            return True  # Time
    return False


def regist_as_binary_sensor(epc_function_data):
    """Check if EPC function data should be registered as binary sensor.

    Args:
        epc_function_data: The EPC function data to check.

    Returns:
        True if the EPC should be registered as a binary sensor.
    """
    from pychonet.lib.epc_functions import (
        DICT_30_ON_OFF,
        DICT_30_OPEN_CLOSED,
        DICT_30_TRUE_FALSE,
        DICT_41_ON_OFF,
    )

    if epc_function_data:
        if type(epc_function_data) == list:
            if epc_function_data[1] in (
                DICT_41_ON_OFF,
                DICT_30_TRUE_FALSE,
                DICT_30_ON_OFF,
                DICT_30_OPEN_CLOSED,
            ):
                return True
    return False


class DeviceTimeoutError(Exception):
    """Exception to indicate the device did not respond."""

    pass


class ECHONETConnector(DataUpdateCoordinator[dict]):
    """EchonetAPIConnector is used to centralise API calls for Echonet devices.

    API calls are aggregated per instance (not per node!)

    This class extends DataUpdateCoordinator to manage ECHONET device data updates,
    providing built-in polling and caching capabilities while maintaining all
    existing bespoke logic for batch requests, quirks, and callbacks.
    """

    def __init__(self, instance: dict, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the ECHONETConnector coordinator.

        Args:
            instance: The ECHONET device instance configuration dictionary.
            hass: The Home Assistant instance.
            entry: The config entry for this integration.
        """
        import pychonet as echonet

        # Calculate a unique name for this coordinator using string formatting
        # to avoid nested quote issues in f-strings
        display_name = self._get_display_name(instance)

        # Initialize as an DataUpdateCoordinator - the base class handles polling and caching
        super().__init__(
            hass,
            _LOGGER,
            name=display_name,
            update_method=self._async_update_data,
            update_interval=MIN_TIME_BETWEEN_UPDATES,  # Set via startup() based on MIN_TIME_BETWEEN_UPDATES
        )

        # Store original instance config for reference
        self._instance_data = instance

        # Initialize self.data for DataUpdateCoordinator with correct type hinting - this will be populated with EPC code keys in _make_update_flags_full_list()
        self.data: dict[int, Any] = {}

        # Core connector attributes - preserved from original implementation
        self.hass = hass
        self._entry = entry

        # Device identification
        self._host = instance["host"]
        self._eojgc = instance["eojgc"]
        self._eojcc = instance["eojcc"]
        self._eojci = instance["eojci"]
        self._uid = instance.get("uid")
        self._uidi = instance.get("uidi")
        self._name = instance.get("name")

        # Manufacturer and product identification for quirks matching
        self._manufacturer = None
        self._host_product_code = None
        if "manufacturer" in instance:
            self._manufacturer = instance["manufacturer"]
        if "host_product_code" in instance:
            self._host_product_code = instance["host_product_code"]

        # The node profile can identify a network adapter rather than the
        # appliance. Resolve supported object-specific models during startup.
        self._object_product_code = None
        self._quirk_product_code = self._host_product_code

        # ECHONET property maps from configuration
        self._ntfPropertyMap = instance["ntfmap"]
        self._getPropertyMap = instance["getmap"]
        self._setPropertyMap = instance["setmap"]

        # Operation codes mapping for this device type
        self._enl_op_codes = ENL_OP_CODES.get(self._eojgc, {}).get(self._eojcc, {})

        # Update management - batch requests and flags
        self._update_flag_batches: list[list[int]] = []
        self._update_flags_full_list: list[int] = []
        self._singleton_poll_epcs: list[int] = (
            []
        )  # EPCs polled individually due to quirk

        # STATMAP (push-covered) EPCs, batched separately from the normal
        # poll list and only requested occasionally as a reconciliation
        # fallback in case an INF notification was dropped or missed.
        # See _make_batch_request_flags() for how this is populated.
        self._statmap_flag_batches: list[list[int]] = []
        self._last_statmap_reconcile: float = 0.0

        # Callbacks for push notifications and option updates
        self._update_callbacks: list[callable] = []
        self._update_option_func: list[callable] = []

        # User configurable options (fan modes, swing modes, temperature ranges, etc.)
        self._user_options: dict[str, Any] = {}

        # Get API instance from Home Assistant data store
        self._api: ECHONETAPIClient = hass.data[DOMAIN]["api"]

        # Register update callbacks with the API for push notifications
        self._api.register_async_update_callbacks(
            self._host,
            self._eojgc,
            self._eojcc,
            self._eojci,
            self.async_update_callback,
        )

        # Create the pychonet Factory instance for this device type
        self._instance = echonet.Factory(
            self._host, self._api, self._eojgc, self._eojcc, self._eojci
        )

    def _get_display_name(self, instance: dict) -> str:
        """Generate a display name for the coordinator.

        Args:
            instance: The ECHONET device instance configuration dictionary.

        Returns:
            A formatted display name for the coordinator.
        """
        if instance.get("name"):
            return f"ECHONET {instance['name']}"
        return (
            f"ECHONET {instance['host']}-{instance['eojgc']}"
            f"-{instance['eojcc']}-{instance['eojci']}"
        )

    async def startup(self):
        """Complete initialization of the connector/coordinator.

        This method performs one-time setup including:
        - Loading device-specific quirks
        - Initializing user options from config entry
        - Building update flag lists and batch configurations
        """
        import pychonet as echonet
        from homeassistant.const import PERCENTAGE
        from pychonet.HomeAirConditioner import (
            ENL_AIR_HORZ,
            ENL_AIR_VERT,
            ENL_AUTO_DIRECTION,
            ENL_FANSPEED,
            ENL_SWING_MODE,
        )

        entry = self._entry

        _LOGGER.debug(
            f"Starting ECHONETLite {self._instance.__class__.__name__} instance for "
            f"{self._eojgc}-{self._eojcc}-{self._eojci}, manufacturer: {self._manufacturer}, "
            f"host_product_code: {self._host_product_code} at {self._host}"
        )

        # Load device-specific quirks
        await self._discover_sharp_model()
        await self._load_quirk()

        # Initialize default user options for fan and swing modes
        self._user_options = {
            ENL_FANSPEED: False,
            ENL_AUTO_DIRECTION: False,
            ENL_SWING_MODE: False,
            ENL_AIR_VERT: False,
            ENL_AIR_HORZ: False,
        }

        # Apply user-configurable options from config entry
        for option in USER_OPTIONS.keys():
            if entry.options.get(USER_OPTIONS[option]["option"]) is not None:
                option_value = entry.options.get(USER_OPTIONS[option]["option"])
                if isinstance(option_value, list) and len(option_value) > 0:
                    self._user_options[option] = option_value
                else:
                    self._user_options[option] = False

        # Apply temperature range options from TEMP_OPTIONS defaults (or config values)
        for option in TEMP_OPTIONS.keys():
            if entry.options.get(option) is not None:
                self._user_options[option] = entry.options.get(option)
            else:
                self._user_options[option] = TEMP_OPTIONS[option].get("default")

        # Apply miscellaneous options
        for key, option in MISC_OPTIONS.items():
            if entry.options.get(key) is not None:
                self._user_options[key] = entry.options.get(key, option.get("default"))

        # Build the full list of EPC codes to update
        self._make_update_flags_full_list()
        self._update_option_func.append(self._make_update_flags_full_list)

        # Configure batch request flags for efficient polling
        self._make_batch_request_flags()
        self._update_option_func.append(self._make_batch_request_flags)

        _LOGGER.debug(f"UID for ECHONETLite instance at {self._host} is {self._uid}.")
        if self._uid is None:
            self._uid = f"{self._host}-{self._eojgc}-{self._eojcc}-{self._eojci}"

    async def async_setup_data_fetch(self) -> dict[int, Any]:
        """Fetch initial data during setup using best-effort mode.

        Unlike _async_update_data, this method skips batches that time out
        rather than raising DeviceTimeoutError. This allows setup to complete
        even when a device silently drops requests for certain EPCs, trusting
        the coordinator's regular polling to fill in the gaps.

        Returns:
            A dictionary of EPC codes and their current values.
        """
        _LOGGER.debug(
            "Setup data fetch (best_effort) for %s-%s-%s-%s",
            self._host,
            self._eojgc,
            self._eojcc,
            self._eojci,
        )
        # Pass include_ntf=True so poll_pychonet uses the full EPC list
        # including STATMAP EPCs. This warms pychonet's _state cache for all
        # EPCs so push notification reads via no_request=True return real values.
        return await self.poll_pychonet(
            no_request=False, best_effort=True, include_ntf=True
        )

    async def _discover_sharp_model(self) -> None:
        """Read the air cleaner's model, not its HW-A04 node-profile model."""
        if self._manufacturer != "Sharp" or (self._eojgc, self._eojcc) != (0x01, 0x35):
            return
        # Never enable a model quirk from a node-profile match alone.
        self._quirk_product_code = (
            None if self._host_product_code == "FPS42Y" else self._host_product_code
        )
        self._object_product_code = None
        if 0x8C not in self._getPropertyMap:
            return
        try:
            semaphore = _host_semaphores.setdefault(self._host, asyncio.Semaphore(1))
            async with semaphore, asyncio.timeout(10):
                raw = await self._instance.getMessage(0x8C)
        except TimeoutError:
            _LOGGER.debug("Sharp object model lookup timed out at %s", self._host)
            return
        # pychonet 2.8.1 eagerly decodes object EPC 8C to a string.
        if not isinstance(raw, str) or not 1 <= len(raw) <= 12:
            return
        model = raw.rstrip("\x00 ")
        if model == "FPS42Y":
            self._object_product_code = model
            self._quirk_product_code = model

    @property
    def is_sharp_fps42y(self) -> bool:
        """Whether this Sharp air-cleaner object reports the supported model."""
        return (
            self._manufacturer == "Sharp"
            and self._object_product_code == "FPS42Y"
            and (self._eojgc, self._eojcc) == (0x01, 0x35)
        )

    async def async_set_sharp_fan_mode(self, option: str) -> None:
        """Set a calibrated preset; actual F3 (not A0) distinguishes the modes."""
        await self.async_set_sharp_setting("mode", option)

    async def async_set_sharp_setting(self, key: str, value) -> None:
        """Write only validated fields and publish actual GET, never ACK state."""
        if (
            not self.is_sharp_fps42y
            or 0xF3 not in self._getPropertyMap
            or 0xF3 not in self._setPropertyMap
        ):
            raise HomeAssistantError("Unsupported Sharp appliance")
        try:
            payload = sharp_command(key, value)
        except (ValueError, TypeError) as err:
            raise HomeAssistantError("Unsupported Sharp setting") from err
        semaphore = _host_semaphores.setdefault(self._host, asyncio.Semaphore(1))
        async with semaphore:
            try:
                async with asyncio.timeout(15):
                    if not await self._instance.setMessage(
                        0xF3, int.from_bytes(payload, "big"), pdc=27
                    ):
                        raise HomeAssistantError(
                            "Sharp did not acknowledge the command"
                        )
                    for _ in range(3):
                        await asyncio.sleep(0.5)
                        try:
                            # getMessage returns raw bytes and requires a GET
                            # response; update() alone can decode stale cache
                            # when pychonet's request queue is busy.
                            state = await self._instance.getMessage(0xF3)
                            power = await self._instance.getMessage(0x80)
                            speed = await self._instance.getMessage(0xA0)
                        except TimeoutError:
                            continue
                        if not (
                            isinstance(power, bytes)
                            and len(power) == 1
                            and isinstance(speed, bytes)
                            and len(speed) == 1
                        ):
                            continue
                        # Publish raw GET responses directly. Cache decoding
                        # after SET may otherwise read the optimistic command.
                        actual = {
                            0xF3: sharp_raw(state),
                            0x80: {0x30: "on", 0x31: "off"}.get(power[0]),
                            0xA0: {
                                0x41: "auto",
                                0x31: "low",
                                0x35: "medium",
                                0x37: "high",
                            }.get(speed[0]),
                        }
                        self.async_set_updated_data({**(self.data or {}), **actual})
                        if sharp_value(actual, key) == value:
                            return
            except TimeoutError as err:
                raise HomeAssistantError(
                    "Sharp setting verification timed out"
                ) from err
        raise HomeAssistantError("Sharp did not confirm the requested setting")

    async def _async_update_data(self) -> dict[int, Any]:
        """Fetch the latest data from the ECHONET device.

        Returns:
            A dictionary of EPC codes and their current values.

        Raises:
            UpdateFailed: If device is offline or update fails.
        """
        # Acquire the per-host semaphore before polling. This ensures only one
        # ECHONETConnector instance polls a given host at a time, giving embedded
        # devices breathing room between requests. Other instances on the same host
        # wait their turn rather than sending concurrent bursts.
        if self._host not in _host_semaphores:
            _host_semaphores[self._host] = asyncio.Semaphore(1)

        async with _host_semaphores[self._host]:
            try:
                _LOGGER.debug(f"Polling ECHONETLite Host {self._host}: %s")
                new_data = await self.poll_pychonet(no_request=False)
                # Merge with existing data so skipped batches retain their
                # cached values rather than disappearing from coordinator.data.
                # This matches 3.9.0 behaviour where self.data.update() was
                # used rather than replacing the entire dict each cycle.
                merged = {**(self.data or {}), **new_data}
                return await self._maybe_reconcile_statmap(merged)

            except EchonetMaxOpcError as ex:
                # Memory Pressure Control (MPC): Device rejected batch size, adjust and retry
                # 1. Adjust batch size
                batch_size_max = self._user_options.get(
                    CONF_BATCH_SIZE_MAX, MAX_UPDATE_BATCH_SIZE
                )
                batch_data_len = max(
                    ex.args[0], MIN_UPDATE_BATCH_SIZE, batch_size_max - 1
                )

                if batch_data_len >= batch_size_max:
                    raise UpdateFailed(
                        f"MPC Error: Device at {self._host} rejected batch even at minimum size."
                    )

                # 2. Persist new batch size
                self._user_options[CONF_BATCH_SIZE_MAX] = batch_data_len
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    options={
                        **self._entry.options,
                        CONF_BATCH_SIZE_MAX: batch_data_len,
                    },
                )

                # 3. Rebuild and retry — semaphore still held
                self._make_batch_request_flags()
                try:
                    new_data = await self.poll_pychonet(no_request=False)
                    merged = {**(self.data or {}), **new_data}
                    return await self._maybe_reconcile_statmap(merged)
                except Exception as err:
                    _LOGGER.error(
                        "Failed to process ECHONETLite polling notification: %s", err
                    )
                    raise UpdateFailed(f"Retry failed after MPC adjustment: {err}")

            except DeviceTimeoutError as err:
                # Check if host has been active recently via pychonet.
                # pychonet tracks last received packet per host across ALL
                # traffic — GET responses, INF notifications, anything.
                # If any packet arrived within ACTIVITY_TIMEOUT, serve cached
                # data rather than marking unavailable — transient failures
                # under network load should not flash entities unavailable.
                last = self._api.last_activity(self._host)
                if last is not None:
                    elapsed = time.monotonic() - last
                    if elapsed < ACTIVITY_TIMEOUT:
                        _LOGGER.debug(
                            "ECHONETLite %s-%s-%s at %s poll failed but host "
                            "was active %.0fs ago — serving cached data",
                            self._eojgc,
                            self._eojcc,
                            self._eojci,
                            self._host,
                            elapsed,
                        )
                        return self.data or {}
                elapsed_str = f"{(time.monotonic() - last):.0f}s" if last else "never"
                _LOGGER.warning(
                    "ECHONETLite %s-%s-%s at %s has been silent — last activity: %s",
                    self._eojgc,
                    self._eojcc,
                    self._eojci,
                    self._host,
                    elapsed_str,
                )
                raise UpdateFailed(f"Offline: {err}")

            except UpdateFailed:
                raise

            except Exception as err:
                # Catch-all to surface unexpected exceptions with full traceback.
                # Without this, unhandled exceptions silently set last_update_success=False
                # with no indication of what went wrong.
                import traceback

                _LOGGER.error(
                    "Unexpected error polling %s-%s-%s at %s: %s\n%s",
                    self._eojgc,
                    self._eojcc,
                    self._eojci,
                    self._host,
                    err,
                    traceback.format_exc(),
                )
                raise UpdateFailed(f"Unexpected error: {err}") from err

    async def _maybe_reconcile_statmap(self, merged: dict[int, Any]) -> dict[int, Any]:
        """Occasionally re-poll STATMAP EPCs as a fallback for missed INF.

        STATMAP EPCs are normally served entirely by push notifications and
        excluded from the regular poll batches. Since ECHONET Lite INF is
        sent over UDP with no delivery guarantee, an occasional dropped or
        misprocessed notification can otherwise leave HA state stale
        indefinitely. This polls those EPCs directly, but only once every
        STATMAP_RECONCILE_INTERVAL seconds, so the traffic savings of the
        STATMAP-pruning optimisation are preserved.

        A timeout here is treated as best-effort: it must not fail the
        overall coordinator update, and the reconciliation clock still
        advances so a momentarily unreachable device doesn't retry this
        extra request every single cycle.

        Args:
            merged: The already-merged (cached + freshly polled) data dict
                for this cycle, to be updated in place with any
                reconciled STATMAP values.

        Returns:
            merged, with any successfully reconciled STATMAP EPCs applied.
        """
        if not self._statmap_flag_batches:
            return merged

        now = time.monotonic()
        if now - self._last_statmap_reconcile < STATMAP_RECONCILE_INTERVAL:
            return merged

        _LOGGER.debug(
            "ECHONETLite %s-%s-%s at %s: running STATMAP reconciliation poll " "for %s",
            self._eojgc,
            self._eojcc,
            self._eojci,
            self._host,
            self._statmap_flag_batches,
        )
        try:
            recon_data = await self.poll_pychonet(
                no_request=False,
                best_effort=True,
                batches_override=self._statmap_flag_batches,
            )
            merged.update(recon_data)
        except Exception as err:
            # best_effort=True already absorbs genuine per-batch device
            # timeouts inside poll_pychonet — this catches anything else
            # unexpected so a reconciliation hiccup can never fail the
            # regular poll cycle it's piggybacking on.
            _LOGGER.debug(
                "ECHONETLite %s-%s-%s at %s: STATMAP reconciliation poll "
                "failed, will retry next interval: %s",
                self._eojgc,
                self._eojcc,
                self._eojci,
                self._host,
                err,
            )
        finally:
            # Advance the clock regardless of outcome, so a silent/offline
            # device doesn't turn this into an every-cycle retry.
            self._last_statmap_reconcile = now

        return merged

    async def async_update_callback(self, isPush: bool = False):
        """Handle push notifications from the device.

        When the device sends an unsolicited INF packet, pychonet fires this
        callback. Rather than reading the entire _state for this instance
        (which may contain None for EPCs not yet fetched in the current poll
        cycle), we restrict the read to EPCs listed in _ntfPropertyMap — the
        set of EPCs the device declared it will proactively notify about.
        This prevents mid-poll push notifications from overwriting good cached
        data with None for EPCs that haven't been batched yet.

        Args:
            isPush: Whether this update was triggered by a push notification.
        """
        if not self._ntfPropertyMap:
            # Device declared no notification EPCs — nothing useful to merge.
            return

        try:
            _LOGGER.debug(
                "Push notification for %s-%s-%s-%s, reading ntfmap EPCs: %s",
                self._host,
                self._eojgc,
                self._eojcc,
                self._eojci,
                self._ntfPropertyMap,
            )

            # Read only the EPCs the device declared it notifies about.
            # _instance.update() with no_request=True reads from the library's
            # internal _state cache — no network call is made.
            # Note: _state is written by echonetMessageReceived BEFORE the
            # callback is awaited (sequential within the same coroutine), so
            # there is no race condition here.
            raw = await self._instance.update(
                list(self._ntfPropertyMap), no_request=True
            )

            if not raw:
                return

            # raw may be a dict (multiple EPCs) or a scalar (single EPC).
            if isinstance(raw, dict):
                new_data = raw
            elif len(self._ntfPropertyMap) == 1:
                new_data = {self._ntfPropertyMap[0]: raw}
            else:
                return

            # Drop any None values — a device push should never produce None,
            # but guard against it so we never overwrite good cached data.
            new_data = {k: v for k, v in new_data.items() if v is not None}

            if not new_data:
                return

            _LOGGER.debug("Push notification data for %s: %s", self._host, new_data)

            # Merge into coordinator data and notify listeners.
            self.data = {**(self.data or {}), **new_data}
            self.async_update_listeners()

        except Exception as err:
            _LOGGER.error("Failed to process ECHONETLite push notification: %s", err)

    async def poll_pychonet(
        self,
        no_request: bool = False,
        best_effort: bool = False,
        include_ntf: bool = False,
        batches_override: list[list[int]] | None = None,
    ) -> dict[int, Any]:
        """Fetch data from pychonet instance.

        Args:
            no_request: If True, only return cached data without network request.
            best_effort: If True, skip genuine device timeouts rather than raising
                DeviceTimeoutError. Used during initial setup.
            include_ntf: If True, include STATMAP EPCs in the poll even when
                CONF_FORCE_POLLING is False. Used during setup to warm pychonet's
                _state cache so push notification reads via no_request=True
                return real values rather than None.
            batches_override: If given, poll exactly these batches instead of
                the instance's regular poll list. Used for the low-frequency
                STATMAP reconciliation poll (self._statmap_flag_batches),
                which must go through the same timeout/best-effort handling
                as a normal poll without being folded into the every-cycle
                _update_flag_batches list.

        Returns:
            A dictionary of EPC codes and their current values.

        Note on pychonet return values:
            False  — request was sent but device did not respond (genuine timeout)
            None   — pychonet _waiting queue was busy, request was not sent
            dict   — success with EPC data
            other  — success with single EPC value

        None (queue busy) is treated as a cache-serve rather than an error,
        matching the silent-skip behaviour of 3.9.0's @Throttle which also
        silently returned stale data when the device was busy.
        """
        update_data = {}
        timed_out_batches = []

        # Use full batch list for setup (include_ntf=True) so all EPCs including
        # STATMAP ones are fetched at least once. For regular polling use the
        # pruned list (STATMAP EPCs served via push). An explicit override
        # (e.g. the STATMAP reconciliation batches) takes priority over both.
        if batches_override is not None:
            batches = batches_override
        elif include_ntf:
            # Build full batch list bypassing STATMAP prune
            batch_size_max = self._user_options.get(
                CONF_BATCH_SIZE_MAX, MAX_UPDATE_BATCH_SIZE
            )
            full_list = [
                e
                for e in self._update_flags_full_list
                if e not in self._singleton_poll_epcs
            ]
            batches = self._chunk_batches(full_list, batch_size_max)
        else:
            batches = self._update_flag_batches

        for i, flags in enumerate(batches):
            if not flags:
                # Nothing to request in this batch (e.g. all EPCs pruned as
                # STATMAP/singleton). Requesting zero EPCs gets no response
                # from the device and would just time out every cycle, so
                # skip it outright rather than calling pychonet.
                continue

            if i > 0 and not no_request:
                # Back off longer after a timeout — device may need more time
                # to recover between requests than after a successful response.
                await asyncio.sleep(1.0 if timed_out_batches else 0.1)

            try:
                batch_data = await self._instance.update(flags, no_request)
            except TimeoutError:
                # pychonet raises TimeoutError("Pychonet UDP request timeout.")
                # when echonetMessage() returns False (genuine device non-response).
                # Treat the same as a False return — skip this batch and continue.
                if no_request:
                    continue
                _LOGGER.warning(
                    "Device at %s did not respond to EPCs %s — skipping batch",
                    self._host,
                    flags,
                )
                timed_out_batches.append(flags)
                continue

            if batch_data is None:
                # pychonet _waiting queue was busy — another request in flight.
                # Serve cached data silently, matching 3.9.0 @Throttle behaviour.
                _LOGGER.debug(
                    "Device at %s queue busy for EPCs %s — serving cached data",
                    self._host,
                    flags,
                )
                continue

            if batch_data is False:
                if no_request:
                    continue
                # Track timed out batches regardless of best_effort.
                # If we got some data from other batches we return what we
                # have rather than raising — partial data is better than
                # marking all entities unavailable. DeviceTimeoutError is
                # only raised if every batch failed (device genuinely offline).
                _LOGGER.warning(
                    "Device at %s did not respond to EPCs %s — skipping batch",
                    self._host,
                    flags,
                )
                timed_out_batches.append(flags)
                continue

            if isinstance(batch_data, dict):
                update_data.update(batch_data)
            elif len(flags) == 1:
                update_data[flags[0]] = batch_data

        if timed_out_batches:
            _LOGGER.warning(
                "Device at %s: %d batch(es) timed out and were skipped: %s.",
                self._host,
                len(timed_out_batches),
                timed_out_batches,
            )
            # Only raise DeviceTimeoutError if ALL batches failed — meaning
            # the device is genuinely offline. Partial failures serve cached
            # data for the missing EPCs rather than marking everything unavailable.
            # Compare against `batches` (what was actually polled this call),
            # not self._update_flag_batches — those differ when include_ntf
            # or batches_override (STATMAP reconciliation) is in use.
            if not update_data and len(timed_out_batches) == len(batches):
                raise DeviceTimeoutError(
                    f"Device at {self._host} failed to respond to any EPCs"
                )

        # Poll singleton EPCs individually after normal batches.
        # Singletons get one retry after a short pause — they carry high-value
        # data (e.g. 29-channel power lists) and a brief delay may allow the
        # device to recover from momentary load before the second attempt.
        for epc in self._singleton_poll_epcs:
            if epc not in self._update_flags_full_list:
                continue
            if not no_request:
                await asyncio.sleep(0.1)

            singleton_data = None
            for attempt in range(2):  # initial attempt + one retry
                try:
                    singleton_data = await self._instance.update([epc], no_request)
                    break  # success — exit retry loop
                except TimeoutError:
                    if attempt == 0:
                        _LOGGER.debug(
                            "Device at %s did not respond to singleton EPC %s "
                            "— retrying after pause",
                            self._host,
                            hex(epc),
                        )
                        await asyncio.sleep(0.2)
                    else:
                        _LOGGER.warning(
                            "Device at %s did not respond to singleton EPC %s "
                            "after retry — serving cached data",
                            self._host,
                            hex(epc),
                        )

            if singleton_data is None:
                _LOGGER.debug(
                    "Device at %s queue busy for singleton EPC %s — serving cached data",
                    self._host,
                    hex(epc),
                )
            elif singleton_data is False:
                _LOGGER.warning(
                    "Device at %s did not respond to singleton EPC %s",
                    self._host,
                    hex(epc),
                )
            else:
                # Always store singleton result under its EPC key.
                # update() returns the value directly (not wrapped in {epc: value})
                # when called with a single EPC, so we must key it explicitly.
                update_data[epc] = singleton_data

        return update_data

    async def poll_pychonet_specific(self, epcs: list[int]) -> dict[int, Any]:
        """Fetch specific EPCs from the pychonet instance.

        This bypasses the standard batching logic to allow for rapid
        verification of specific state changes.
        """
        _LOGGER.debug("Targeted poll for %s at %s", epcs, self._host)
        update_data = {}

        # We call the library update directly with the specific list
        # No 'no_request' logic here because the whole point is a fresh network hit
        batch_data = await self._instance.update(epcs)

        if batch_data is False:
            # We don't necessarily want to raise UpdateFailed here and mark
            # the whole device unavailable just because a targeted sniff failed.
            _LOGGER.warning("Targeted poll failed for EPCs %s", epcs)
            return {}

        if isinstance(batch_data, dict):
            update_data.update(batch_data)
        elif len(epcs) == 1:
            # Handle the case where pychonet returns a single value
            # instead of a dict for a single-EPC request
            update_data[epcs[0]] = batch_data

        return update_data

    async def async_set_and_verify(self, epcs: list[int], set_coro):
        """
        Executes the pychonet setter command, and schedules a targeted poll.
        """
        # 1. Execute the set command
        await set_coro

        # 2. Targeted Background Verification
        async def verify():
            await asyncio.sleep(0.8)
            confirmed = await self.poll_pychonet_specific(epcs)
            if confirmed:
                self.data.update(confirmed)
                self.async_update_listeners()

        self.hass.async_create_task(verify())

    def _make_update_flags_full_list(self) -> bool:
        """Build the complete list of EPC codes to poll.

        This method constructs the full list of property codes that should be updated
        during polling, including super energy codes and device-specific properties.

        Returns:
            True if the list has changed, False otherwise (for change detection).
        """
        _prev_update_flags_full_list = self._update_flags_full_list.copy()

        # Reset the update flags list
        self._update_flags_full_list = []

        # Include super energy codes if enabled
        _enabled_super_energy = self._user_options.get(
            CONF_ENABLE_SUPER_ENERGY,
            ENABLE_SUPER_ENERGY_DEFAULT.get(self._eojgc, {}).get(self._eojcc, True),
        )

        if _enabled_super_energy:
            _enl_super_codes = ENL_SUPER_CODES
        else:
            _enl_super_codes = {
                k: v for k, v in ENL_SUPER_CODES.items() if k not in ENL_SUPER_ENERGES
            }

        flags = list(_enl_super_codes)  # PR 246

        # Add supported EPC_FUNCTIONS from the pychonet object class.
        # _update_flags_full_list always includes ALL supported GETMAP EPCs
        # so the initial setup fetch populates self.data with real values for
        # every EPC including those in STATMAP. The push-prune only applies
        # to _make_batch_request_flags which drives ongoing polling.
        _epc_keys = set(self._instance.EPC_FUNCTIONS.keys()) - set(EPC_SUPER.keys())
        for item in self._getPropertyMap:
            if item in _epc_keys:
                flags.append(item)

        # Build final list with None initialization
        for value in flags:
            if value in self._getPropertyMap:
                self._update_flags_full_list.append(value)
                self.data[value] = (
                    None  # This should instantiate self.data with the correct keys for DataUpdateCoordinator
                )
        _LOGGER.debug(
            f"Echonet device {self._host}-{self._eojgc}-{self._eojcc}-{self._eojci} "
            f"update_flags_full_list: {self._update_flags_full_list}"
        )

        return _prev_update_flags_full_list != self._update_flags_full_list

    @staticmethod
    def _chunk_batches(flat_list: list[int], batch_size_max: int) -> list[list[int]]:
        """Split a flat EPC list into batches of at most batch_size_max.

        Never emits an empty trailing batch — if flat_list is empty, returns
        an empty list of batches rather than [[]] (a zero-EPC batch would
        cause poll_pychonet() to send a request the device can never answer,
        resulting in a permanent, pointless timeout loop).
        """
        batches: list[list[int]] = []
        start_index = 0
        length = len(flat_list)
        while start_index + batch_size_max < length:
            batches.append(flat_list[start_index : start_index + batch_size_max])
            start_index += batch_size_max
        remaining = flat_list[start_index:length]
        if remaining:
            batches.append(remaining)
        return batches

    def _make_batch_request_flags(self):
        """Split the update flags list into batched requests.

        The ECHONET protocol has limits on how many properties can be requested
        in a single message. This method splits the full list into manageable batches.
        EPCs marked as SINGLETON_POLL in quirks are excluded from batches and
        polled individually to avoid device firmware buffer overflow issues.

        If CONF_FORCE_POLLING is False (default), EPCs in STATMAP are also
        excluded from the regular poll batches (_update_flag_batches) — they
        are served via push notifications instead. Those same EPCs are also
        batched separately into _statmap_flag_batches, which is polled only
        occasionally (see STATMAP_RECONCILE_INTERVAL) as a fallback in case
        an INF notification is dropped or missed — UDP gives no delivery
        guarantee, so without this a single lost push could leave HA state
        stale indefinitely.
        The initial setup fetch still polls all EPCs to populate self.data.
        If CONF_FORCE_POLLING is True (fallback for unreliable multicast),
        all GETMAP EPCs are polled regardless of STATMAP, and there is
        nothing left over to reconcile.

        Args:
            CONF_BATCH_SIZE_MAX: User-configurable maximum batch size (default 10).
        """
        # Prune STATMAP EPCs from ongoing poll batches if force_polling is off.
        # These EPCs are covered by push notifications so polling them on
        # every cycle is redundant — they get their own low-frequency
        # reconciliation batch instead (see _statmap_flag_batches below).
        _force_polling = self._user_options.get(CONF_FORCE_POLLING, False)
        _ntf_set = set(self._ntfPropertyMap) if not _force_polling else set()
        if self.is_sharp_fps42y:
            # Physical mode/LED/lock changes must reconcile every normal poll,
            # even if multicast notifications cannot traverse the device VLAN.
            _ntf_set.discard(0xF3)

        if _ntf_set:
            _pruned = [
                e
                for e in self._ntfPropertyMap
                if e in self._update_flags_full_list
                and e not in self._singleton_poll_epcs
            ]
            if _pruned:
                _LOGGER.debug(
                    "ECHONETLite %s-%s-%s: pruning %d EPC(s) from poll batches "
                    "(served via push, reconciled every %ds): %s",
                    self._eojgc,
                    self._eojcc,
                    self._eojci,
                    len(_pruned),
                    STATMAP_RECONCILE_INTERVAL,
                    [hex(e) for e in _pruned],
                )

        batch_size_max = self._user_options.get(
            CONF_BATCH_SIZE_MAX, MAX_UPDATE_BATCH_SIZE
        )

        # Exclude singleton EPCs and (optionally) STATMAP EPCs from batch list
        batch_list = [
            epc
            for epc in self._update_flags_full_list
            if epc not in self._singleton_poll_epcs and epc not in _ntf_set
        ]
        self._update_flag_batches = self._chunk_batches(batch_list, batch_size_max)

        # Build the separate, rarely-polled STATMAP reconciliation batch list.
        # Excludes singleton EPCs (those already have their own dedicated
        # polling path) but keeps everything that was pruned above.
        statmap_list = [
            epc
            for epc in self._update_flags_full_list
            if epc not in self._singleton_poll_epcs and epc in _ntf_set
        ]
        self._statmap_flag_batches = self._chunk_batches(statmap_list, batch_size_max)

        _LOGGER.debug(
            f"Echonet device {self._host}-{self._eojgc}-{self._eojcc}-{self._eojci} "
            f"batch request flags list: {self._update_flag_batches}, "
            f"statmap reconciliation flags list: {self._statmap_flag_batches}"
        )

    def register_async_update_callbacks(self, update_func: callable):
        """Register a callback function to be called on data updates.

        This method allows entities and other components to receive notifications
        when device data changes via push notifications or polling.

        Args:
            update_func: Async callable that will be invoked with (isPush) parameter.
        """
        self._update_callbacks.append(update_func)

    def add_update_option_listener(self, update_func: callable):
        """Register a listener for option change notifications.

        This method allows components to react when user options are changed
        and require rebuilding of flag lists or batch configurations.

        Args:
            update_func: Callable that returns True if a reload is needed.
        """
        self._update_option_func.append(update_func)

    async def _load_quirk(self):
        """Load device-specific quirks for manufacturer-specific behavior.

        Quirks are used to handle devices with non-standard EPC implementations
        or proprietary extensions that require special handling.
        """

        def update(extention: Any):
            """Apply quirk definitions to the instance."""
            for epc in extention.QUIRKS:
                if func := extention.QUIRKS[epc].get("EPC_FUNCTION"):
                    op_code = extention.QUIRKS[epc].get("ENL_OP_CODE")
                    self._instance.register_epc_function(epc, func, op_code)
                    if op_code:
                        self._enl_op_codes.update({epc: op_code})
                if extention.QUIRKS[epc].get("SINGLETON_POLL"):
                    if epc not in self._singleton_poll_epcs:
                        self._singleton_poll_epcs.append(epc)
                        _LOGGER.debug(
                            "Echonet quirk: EPC %s will be polled individually "
                            "(SINGLETON_POLL) for %s-%s-%s at %s",
                            hex(epc),
                            self._eojgc,
                            self._eojcc,
                            self._eojci,
                            self._host,
                        )
            _LOGGER.debug(f"Echonet EPC_FUNCTIONS is: {self._instance.EPC_FUNCTIONS}")
            _LOGGER.debug(f"Echonet _enl_op_codes is: {self._enl_op_codes}")

        # Check for manufacturer-specific quirks
        if self._manufacturer:
            check = [
                "quirks",
                self._manufacturer,
                "all",
                "{:0>2X}".format(self._eojgc) + "{:0>2X}".format(self._eojcc),
            ]
            path = os.path.dirname(__file__) + "/" + "/".join(check) + ".py"
            _LOGGER.debug(f"Echonet _load_quirk check path is: {path}")

            if os.path.isfile(path):
                mod = "." + ".".join(check)
                _LOGGER.debug(f"Echonet import module is: {mod} of {__package__}")
                extention = await self.hass.async_add_executor_job(
                    partial(import_module, mod, package=__package__)
                )
                update(extention)

            # Check for product-code-specific quirks
            if self._quirk_product_code:
                check = [
                    "quirks",
                    self._manufacturer,
                    self._quirk_product_code,
                    "{:0>2X}".format(self._eojgc) + "{:0>2X}".format(self._eojcc),
                ]
                path = os.path.dirname(__file__) + "/" + "/".join(check) + ".py"
                _LOGGER.debug(f"Echonet _load_quirk check path is: {path}")

                if os.path.isfile(path):
                    mod = "." + ".".join(check)
                    _LOGGER.debug(f"Echonet import module is: {mod} of {__package__}")
                    extention = await self.hass.async_add_executor_job(
                        partial(import_module, mod, package=__package__)
                    )
                    update(extention)
