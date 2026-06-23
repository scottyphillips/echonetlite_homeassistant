"""ECHONET device connector and coordinator."""

import asyncio
import logging
import os
from functools import partial
from importlib import import_module
from typing import Any
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pychonet import ECHONETAPIClient
from pychonet.echonetapiclient import EchonetMaxOpcError
from pychonet.lib.epc import EPC_SUPER
from pychonet.lib.epc_functions import _hh_mm

from .const import (
    CONF_BATCH_SIZE_MAX,
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

_LOGGER = logging.getLogger(__name__)

# Batch size constants for ECHONET protocol
MAX_UPDATE_BATCH_SIZE = 10
MIN_UPDATE_BATCH_SIZE = 3
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


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

        # ECHONET property maps from configuration
        self._ntfPropertyMap = instance["ntfmap"]
        self._getPropertyMap = instance["getmap"]
        self._setPropertyMap = instance["setmap"]

        # Operation codes mapping for this device type
        self._enl_op_codes = ENL_OP_CODES.get(self._eojgc, {}).get(self._eojcc, {})

        # Update management - batch requests and flags
        self._update_flag_batches: list[list[int]] = []
        self._update_flags_full_list: list[int] = []

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
        return await self.poll_pychonet(no_request=False, best_effort=True)

    async def _async_update_data(self) -> dict[int, Any]:
        """Fetch the latest data from the ECHONET device.

        Returns:
            A dictionary of EPC codes and their current values.

        Raises:
            UpdateFailed: If device is offline or update fails.
        """
        try:
            # Standard poll
            _LOGGER.debug(f"Polling ECHONETLite Host {self._host}: %s")
            return await self.poll_pychonet(no_request=False)

        except EchonetMaxOpcError as ex:
            # Memory Pressure Control (MPC): Device rejected batch size, adjust and retry
            # 1. Adjust batch size
            batch_size_max = self._user_options.get(
                CONF_BATCH_SIZE_MAX, MAX_UPDATE_BATCH_SIZE
            )
            batch_data_len = max(ex.args[0], MIN_UPDATE_BATCH_SIZE, batch_size_max - 1)

            if batch_data_len >= batch_size_max:
                raise UpdateFailed(
                    f"MPC Error: Device at {self._host} rejected batch even at minimum size."
                )

            # 2. Persist new batch size
            self._user_options[CONF_BATCH_SIZE_MAX] = batch_data_len
            self.hass.config_entries.async_update_entry(
                self._entry,
                options={**self._entry.options, CONF_BATCH_SIZE_MAX: batch_data_len},
            )

            # 3. Rebuild and Retry
            self._make_batch_request_flags()
            try:
                return await self.poll_pychonet(no_request=False)
            except Exception as err:
                _LOGGER.error(
                    "Failed to process ECHONETLite polling notification: %s", err
                )
                raise UpdateFailed(f"Retry failed after MPC adjustment: {err}")

        except DeviceTimeoutError as err:
            # This is the "Magic Clause": Raising UpdateFailed marks entities as Unavailable
            _LOGGER.debug("Device Timeout for {self._host}: %s", err)
            raise UpdateFailed(f"Offline: {err}")

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
        self, no_request: bool = False, best_effort: bool = False
    ) -> dict[int, Any]:
        """Fetch data from pychonet instance.

        Args:
            no_request: If True, only return cached data without network request.
            best_effort: If True, skip batches that time out rather than raising
                DeviceTimeoutError. Used during initial setup so that slow or
                partially-unresponsive devices (e.g. devices that silently drop
                requests for certain EPCs) can still complete setup with whatever
                data they return. Regular polling uses best_effort=False so that
                a completely unresponsive device correctly marks entities unavailable.

        Returns:
            A dictionary of EPC codes and their current values.
        """
        update_data = {}
        timed_out_batches = []

        for i, flags in enumerate(self._update_flag_batches):
            if i > 0 and not no_request:
                await asyncio.sleep(0.1)

            # Hit the library. Returns False if a network request fails.
            batch_data = await self._instance.update(flags, no_request)

            if batch_data is False:
                if no_request:  # Should not happen with local cache access
                    continue
                if best_effort:
                    # Skip this batch and continue — device may be slow or
                    # silently dropping requests for certain EPCs.
                    _LOGGER.warning(
                        "Device at %s did not respond to EPCs %s — skipping batch "
                        "(best_effort mode)",
                        self._host,
                        flags,
                    )
                    timed_out_batches.append(flags)
                    continue
                # Raise custom error so _async_update_data can catch it
                raise DeviceTimeoutError(
                    f"Device at {self._host} failed to respond to EPCs {flags}"
                )

            if isinstance(batch_data, dict):
                update_data.update(batch_data)
            elif len(flags) == 1:
                update_data[flags[0]] = batch_data

        if best_effort and timed_out_batches:
            _LOGGER.warning(
                "Device at %s: %d batch(es) timed out during setup and were skipped: %s. "
                "Affected EPCs will be retried on the next scheduled poll.",
                self._host,
                len(timed_out_batches),
                timed_out_batches,
            )

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

        # Add supported EPC_FUNCTIONS from the pychonet object class
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

    def _make_batch_request_flags(self):
        """Split the update flags list into batched requests.

        The ECHONET protocol has limits on how many properties can be requested
        in a single message. This method splits the full list into manageable batches.

        Args:
            CONF_BATCH_SIZE_MAX: User-configurable maximum batch size (default 10).
        """
        self._update_flag_batches = []
        start_index = 0
        full_list_length = len(self._update_flags_full_list)

        batch_size_max = self._user_options.get(
            CONF_BATCH_SIZE_MAX, MAX_UPDATE_BATCH_SIZE
        )

        while start_index + batch_size_max < full_list_length:
            self._update_flag_batches.append(
                self._update_flags_full_list[start_index : start_index + batch_size_max]
            )
            start_index += batch_size_max

        # Add remaining flags as final batch
        self._update_flag_batches.append(
            self._update_flags_full_list[start_index:full_list_length]
        )

        _LOGGER.debug(
            f"Echonet device {self._host}-{self._eojgc}-{self._eojcc}-{self._eojci} "
            f"batch request flags list: {self._update_flag_batches}"
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
                    self._instance.EPC_FUNCTIONS.update({epc: func})
                    if op_code := extention.QUIRKS[epc].get("ENL_OP_CODE"):
                        self._enl_op_codes.update({epc: op_code})
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
            if self._host_product_code:
                check = [
                    "quirks",
                    self._manufacturer,
                    self._host_product_code,
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
