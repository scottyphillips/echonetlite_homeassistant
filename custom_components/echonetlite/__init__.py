"""The echonetlite integration."""

from __future__ import annotations

import asyncio
import logging
import os
import time as pytime
from datetime import timedelta
from functools import partial
from importlib import import_module
from typing import Any

import pychonet as echonet
from homeassistant import config_entries
from homeassistant.components.number.const import NumberDeviceClass
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    PERCENTAGE,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

# Throttle removed - UpdateCoordinator handles update intervals
from pychonet import ECHONETAPIClient
from pychonet.echonetapiclient import EchonetMaxOpcError
from pychonet.EchonetInstance import (
    ENL_CUMULATIVE_POWER,
    ENL_GETMAP,
    ENL_INSTANTANEOUS_POWER,
    ENL_SETMAP,
    ENL_STATUS,
    ENL_UID,
)
from pychonet.HomeAirConditioner import (
    ENL_AIR_HORZ,
    ENL_AIR_VERT,
    ENL_AUTO_DIRECTION,
    ENL_FANSPEED,
    ENL_SWING_MODE,
)
from pychonet.lib.const import ENL_STATMAP, VERSION
from pychonet.lib.epc import EPC_CODE, EPC_SUPER
from pychonet.lib.epc_functions import (
    DICT_30_ON_OFF,
    DICT_30_OPEN_CLOSED,
    DICT_30_TRUE_FALSE,
    DICT_41_ON_OFF,
    _hh_mm,
)
from pychonet.lib.udpserver import UDPServer

from .config_flow import ErrorConnect, async_discover_newhost, enumerate_instances
from .const import (
    CONF_BATCH_SIZE_MAX,
    CONF_ENABLE_SUPER_ENERGY,
    DOMAIN,
    ENABLE_SUPER_ENERGY_DEFAULT,
    ENL_OP_CODES,
    ENL_SUPER_CODES,
    ENL_SUPER_ENERGES,
    ENL_TIMER_SETTING,
    MISC_OPTIONS,
    TEMP_OPTIONS,
    USER_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.LIGHT,
    Platform.FAN,
    Platform.SWITCH,
    Platform.TIME,
    Platform.NUMBER,
    Platform.COVER,
]
PARALLEL_UPDATES = 0
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)
MAX_UPDATE_BATCH_SIZE = 10
MIN_UPDATE_BATCH_SIZE = 3
SETUP_BUDGET = 45.0
DISCOVERY_MAX_BUDGET = 20.0
DISCOVERY_MIN_BUDGET = 8.0
INSTANCE_MAX_BUDGET = 8.0
INSTANCE_MIN_BUDGET = 4.0
INSTANCE_RETRY_DELAY = 0.3


def _remaining_setup_budget(started: float) -> float:
    """Return remaining setup budget in seconds."""
    return SETUP_BUDGET - (pytime.monotonic() - started)


async def _run_with_timeout(coro, timeout_s: float):
    """Run coroutine with timeout."""
    async with asyncio.timeout(timeout_s):
        return await coro


def get_device_name(connector, config) -> str:
    if connector._name:
        return connector._name
    if connector._instance._eojci > 1:
        return f"{config.title} {connector._instance._eojci}"
    return config.title


def get_name_by_epc_code(
    jgc: int,
    jcc: int,
    code: int,
    unknown: str | None = None,
    given_name: str | None = None,
) -> str:
    if given_name != None:
        return given_name
    if code in EPC_SUPER:
        return EPC_SUPER[code]
    else:
        if unknown == None:
            unknown = f"({code})"
        name = EPC_CODE.get(jgc, {}).get(jcc, {}).get(code, None)
        if name == None:
            _code = f"[{hex(jgc)}({jgc})-{hex(jcc)}({jcc})-{hex(code)}({code})]"
            _LOGGER.warning(
                f"{_code} - Unable to resolve the item name. "
                + f"Please report the unknown code {_code} at the issue tracker on GitHub!"
            )
            if unknown == None:
                name = f"({code})"
            else:
                name = unknown
        return name


def polling_update_debug_log(values: dict[int, Any], conn_instance: ECHONETConnector):
    eojgc = conn_instance._eojgc
    eojcc = conn_instance._eojcc
    debug_log = "\nECHONETlite polling update data:\n"
    for value in list(values.keys()):
        name = conn_instance._enl_op_codes.get(value, {}).get(CONF_NAME)
        debug_log = (
            debug_log
            + f" - {get_name_by_epc_code(eojgc, eojcc, value, None, name)} {value:#x}({value}): {values[value]}\n"
        )
    return debug_log


def get_unit_by_devise_class(device_class: str) -> str | None:
    if (
        device_class == SensorDeviceClass.TEMPERATURE
        or device_class == NumberDeviceClass.TEMPERATURE
    ):
        unit = UnitOfTemperature.CELSIUS
    elif (
        device_class == SensorDeviceClass.ENERGY
        or device_class == NumberDeviceClass.ENERGY
    ):
        unit = UnitOfEnergy.WATT_HOUR
    elif (
        device_class == SensorDeviceClass.POWER
        or device_class == NumberDeviceClass.POWER
    ):
        unit = UnitOfPower.WATT
    elif (
        device_class == SensorDeviceClass.CURRENT
        or device_class == NumberDeviceClass.CURRENT
    ):
        unit = UnitOfElectricCurrent.AMPERE
    elif (
        device_class == SensorDeviceClass.VOLTAGE
        or device_class == NumberDeviceClass.VOLTAGE
    ):
        unit = UnitOfElectricPotential.VOLT
    elif (
        device_class == SensorDeviceClass.HUMIDITY
        or device_class == SensorDeviceClass.BATTERY
        or device_class == NumberDeviceClass.HUMIDITY
        or device_class == NumberDeviceClass.BATTERY
    ):
        unit = PERCENTAGE
    elif device_class == SensorDeviceClass.GAS or device_class == NumberDeviceClass.GAS:
        unit = UnitOfVolume.CUBIC_METERS
    elif (
        device_class == SensorDeviceClass.WATER
        or device_class == NumberDeviceClass.WATER
    ):
        unit = UnitOfVolume.CUBIC_METERS
    else:
        unit = None

    return unit


def regist_as_inputs(epc_function_data):
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.async_on_unload(entry.add_update_listener(update_listener))
    started = pytime.monotonic()
    host = None
    udp = None
    server = None

    async def discover_callback(host):
        await async_discover_newhost(hass, host)

    def unload_config_entry():
        if server != None:
            _LOGGER.debug(
                f"Called unload_config_entry() try to remove {host} from server._state."
            )
            if server._state.get(host):
                server._state.pop(host)
            # Remove update callback function
            for _key in list(server._update_callbacks.keys()):
                if _key.startswith(host):
                    del server._update_callbacks[_key]

    entry.async_on_unload(unload_config_entry)

    if DOMAIN in hass.data:  # maybe set up by config entry?
        _LOGGER.debug("ECHONETlite platform is already started.")
        server = hass.data[DOMAIN]["api"]
        hass.data[DOMAIN].update({entry.entry_id: []})
    else:  # setup API
        _LOGGER.debug("Starting up ECHONETlite platform..")
        _LOGGER.debug(f"pychonet version is {VERSION}")
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN].update({entry.entry_id: []})
        udp = UDPServer()
        udp.run("0.0.0.0", 3610, loop=hass.loop)
        server = ECHONETAPIClient(udp)
        server._debug_flag = True
        server._logger = _LOGGER.debug
        server._message_timeout = 300
        server._discover_callback = discover_callback
        hass.data[DOMAIN].update({"api": server})

    if not entry.pref_disable_new_entities:
        host = (
            entry.data["host"]
            if "host" in entry.data
            else entry.data["instances"][0]["host"]
        )

        # make sure multicast is registered with the local IP used to reach this host
        server._server.register_multicast_from_host(host)

        try:
            remaining = _remaining_setup_budget(started)
            if remaining < DISCOVERY_MIN_BUDGET:
                raise ConfigEntryNotReady(
                    f"Not enough setup time left for ECHONET Lite discovery on {host}"
                )

            discovery_budget = min(remaining, DISCOVERY_MAX_BUDGET)

            instances = await _run_with_timeout(
                enumerate_instances(hass, host),
                discovery_budget,
            )

        except ErrorConnect as ex:
            raise ConfigEntryNotReady(
                f"Connection error while connecting to {host}: {ex}"
            ) from ex
        except (TimeoutError, asyncio.TimeoutError) as ex:
            raise ConfigEntryNotReady(
                f"ECHONET Lite discovery timed out for {host}"
            ) from ex
        except asyncio.CancelledError:
            raise

        # Maintain old entity configuration types to avoid duplicate creation of new entities
        _registed_instances = {}
        for _instance in entry.data["instances"]:
            _uidi = f"{_instance['uid']}-{_instance['eojgc']}-{_instance['eojcc']}-{_instance['eojci']}"
            _registed_instances[_uidi] = _instance
        for _instance in instances:
            _uidi = _instance["uidi"]
            _registed = _registed_instances.get(_uidi)
            if _registed and _registed.get("uidi") == None:
                # keep old type config (echonetlite < 3.6.0)
                del _instance["uidi"]

        hass.config_entries.async_update_entry(
            entry, title=entry.title, data={"host": host, "instances": instances}
        )

    for instance in entry.data["instances"]:
        # auto update to new style
        if "ntfmap" not in instance:
            instance["ntfmap"] = []
        echonetlite = None
        host = instance["host"]
        eojgc = instance["eojgc"]
        eojcc = instance["eojcc"]
        eojci = instance["eojci"]
        ntfmap = instance["ntfmap"]
        getmap = instance["getmap"]
        setmap = instance["setmap"]
        uid = instance["uid"]

        # manually update API states using config entry data
        if host not in list(server._state):
            server._state[host] = {
                "instances": {
                    eojgc: {
                        eojcc: {
                            eojci: {
                                ENL_STATMAP: ntfmap,
                                ENL_SETMAP: setmap,
                                ENL_GETMAP: getmap,
                                ENL_UID: uid,
                            }
                        }
                    }
                }
            }
        if eojgc not in list(server._state[host]["instances"]):
            server._state[host]["instances"].update(
                {
                    eojgc: {
                        eojcc: {
                            eojci: {
                                ENL_STATMAP: ntfmap,
                                ENL_SETMAP: setmap,
                                ENL_GETMAP: getmap,
                                ENL_UID: uid,
                            }
                        }
                    }
                }
            )
        if eojcc not in list(server._state[host]["instances"][eojgc]):
            server._state[host]["instances"][eojgc].update(
                {
                    eojcc: {
                        eojci: {
                            ENL_STATMAP: ntfmap,
                            ENL_SETMAP: setmap,
                            ENL_GETMAP: getmap,
                            ENL_UID: uid,
                        }
                    }
                }
            )
        if eojci not in list(server._state[host]["instances"][eojgc][eojcc]):
            server._state[host]["instances"][eojgc][eojcc].update(
                {
                    eojci: {
                        ENL_STATMAP: ntfmap,
                        ENL_SETMAP: setmap,
                        ENL_GETMAP: getmap,
                        ENL_UID: uid,
                    }
                }
            )

        echonetlite = ECHONETConnector(instance, hass, entry)
        await echonetlite.startup()
        try:
            # Since there is a small chance of failure, perform a few retries for each instance.
            for retry in range(1, 4):
                remaining = _remaining_setup_budget(started)
                if remaining < INSTANCE_MIN_BUDGET:
                    raise ConfigEntryNotReady(
                        f"Not enough setup time left to initialize ECHONET Lite instances for {host}"
                    )

                per_try_budget = min(remaining, INSTANCE_MAX_BUDGET)

                try:
                    await _run_with_timeout(
                        echonetlite.async_update(),
                        per_try_budget,
                    )
                    hass.data[DOMAIN][entry.entry_id].append(
                        {"instance": instance, "echonetlite": echonetlite}
                    )
                    break

                except (TimeoutError, asyncio.TimeoutError) as ex:
                    _LOGGER.debug(
                        "Setting up ECHONET instance %s-%s-%s on %s timed out "
                        "(retry %s/3, remaining %.1fs)",
                        eojgc,
                        eojcc,
                        eojci,
                        host,
                        retry,
                        _remaining_setup_budget(started),
                    )
                    if retry == 3:
                        raise ConfigEntryNotReady(
                            f"Initial update timed out for {host}"
                        ) from ex

                    await asyncio.sleep(INSTANCE_RETRY_DELAY)

        except asyncio.CancelledError:
            raise
        except KeyError as ex:
            raise ConfigEntryNotReady(
                f"IP address change was detected during setup of {host}"
            ) from ex

    _LOGGER.debug(f"Plaform entry data - {entry.data}")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


# TODO update for Air Cleaner
async def update_listener(hass, entry):
    for instance in hass.data[DOMAIN][entry.entry_id]:
        if instance["instance"]["eojgc"] == 1 and instance["instance"]["eojcc"] == 48:
            for option in USER_OPTIONS.keys():
                if (
                    entry.options.get(USER_OPTIONS[option]["option"]) is not None
                ):  # check if options has been created
                    if isinstance(
                        entry.options.get(USER_OPTIONS[option]["option"]), list
                    ):
                        if (
                            len(entry.options.get(USER_OPTIONS[option]["option"])) > 0
                        ):  # if it has been created then check list length.
                            instance["echonetlite"]._user_options.update(
                                {
                                    option: entry.options.get(
                                        USER_OPTIONS[option]["option"]
                                    )
                                }
                            )
                        else:
                            instance["echonetlite"]._user_options.update(
                                {option: False}
                            )
                    else:
                        instance["echonetlite"]._user_options.update(
                            {option: entry.options.get(USER_OPTIONS[option]["option"])}
                        )
            for option in TEMP_OPTIONS.keys():
                if entry.options.get(option) is not None:
                    instance["echonetlite"]._user_options.update(
                        {option: entry.options.get(option)}
                    )

        for key, option in MISC_OPTIONS.items():
            if entry.options.get(key) is not None or option.get("default"):
                instance["echonetlite"]._user_options.update(
                    {key: entry.options.get(key, option.get("default"))}
                )

        _need_reload = False
        for func in instance["echonetlite"]._update_option_func:
            _need_reload |= bool(func())

        if _need_reload:
            return await hass.config_entries.async_reload(entry.entry_id)
        else:
            return None


async def get_echonet_connector():
    return


class ECHONETConnector(DataUpdateCoordinator[dict]):
    """EchonetAPIConnector is used to centralise API calls for Echonet devices.
    API calls are aggregated per instance (not per node!)

    This class extends DataUpdateCoordinator to manage ECHONET device data updates,
    providing built-in polling and caching capabilities while maintaining all
    existing bespoke logic for batch requests, quirks, and callbacks."""

    def __init__(self, instance: dict, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the ECHONETConnector coordinator.

        Args:
            instance: The ECHONET device instance configuration dictionary.
            hass: The Home Assistant instance.
            entry: The config entry for this integration.
        """
        # Calculate a unique name for this coordinator using string formatting
        # to avoid nested quote issues in f-strings
        display_name = self._get_display_name(instance)

        # Initialize as an DataUpdateCoordinator - the base class handles polling and caching
        super().__init__(
            hass,
            _LOGGER,
            name=display_name,
            update_method=self._async_update_data,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )

        # Store original instance config for reference
        self._instance_data = instance

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
        self._update_data: dict[int, Any] = {}

        # Callbacks for push notifications and option updates
        self._update_callbacks: list[callable] = []
        self._update_option_func: list[callable] = []

        # User configurable options (fan modes, swing modes, temperature ranges, etc.)
        self._user_options: dict[str, Any] = {}

        # Get API instance from Home Assistant data store
        self._api = hass.data[DOMAIN]["api"]

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
        """Generate a display name for the coordinator."""
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
        entry = self._entry

        _LOGGER.debug(
            f"Starting ECHONETLite {self._instance.__class__.__name__} instance for "
            f"{self._eojgc}-{self._eojcc}-{self._eojci}, manufacturer: {self._manufacturer}, "
            f"host_product_code: {self._host_product_code} at {self._host}"
        )

        # Load device-specific quirks
        await self._load_quirk()

        # Initialize default user options for fan, swing modes and temperature ranges
        self._user_options = {
            ENL_FANSPEED: False,
            ENL_AUTO_DIRECTION: False,
            ENL_SWING_MODE: False,
            ENL_AIR_VERT: False,
            ENL_AIR_HORZ: False,
            "min_temp_heat": 15,
            "max_temp_heat": 35,
            "min_temp_cool": 15,
            "max_temp_cool": 35,
            "min_temp_auto": 15,
            "max_temp_auto": 35,
        }

        # Apply user-configurable options from config entry
        for option in USER_OPTIONS.keys():
            if entry.options.get(USER_OPTIONS[option]["option"]) is not None:
                option_value = entry.options.get(USER_OPTIONS[option]["option"])
                if isinstance(option_value, list) and len(option_value) > 0:
                    self._user_options[option] = option_value
                else:
                    self._user_options[option] = False

        # Apply temperature range options
        for option in TEMP_OPTIONS.keys():
            if entry.options.get(option) is not None:
                self._user_options[option] = entry.options.get(option)

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

    async def _async_update_data(self) -> dict[int, Any]:
        """Fetch the latest data from the ECHONET device.

        This method is called periodically by UpdateCoordinator for polling updates.
        It handles batch requests and manages the maximum property code (MPC) error.

        Returns:
            Dictionary containing the latest device data keyed by EPC codes.

        Raises:
            ConfigEntryNotReady: If the device fails to respond within timeout.
        """
        try:
            update_data = await self.async_update_data({})
            return update_data
        except EchonetMaxOpcError as ex:
            # Adjust the maximum number of properties for batch requests when MPC error occurs
            batch_size_max = self._user_options.get(
                CONF_BATCH_SIZE_MAX, MAX_UPDATE_BATCH_SIZE
            )
            batch_data_len = max(
                ex.args[0],
                MIN_UPDATE_BATCH_SIZE,
                batch_size_max - 1,
            )
            if batch_data_len >= batch_size_max:
                _LOGGER.error(
                    f"The integration has adjusted the number of batch requests to "
                    f"{self._host} to {batch_size_max}, but no response is received. "
                    f"Please check and try restarting the device etc."
                )
                return self._update_data.copy()

            # Update user option for batch size and persist to config entry
            self._user_options[CONF_BATCH_SIZE_MAX] = batch_data_len
            entry_options = dict(self._entry.options)
            entry_options.update({CONF_BATCH_SIZE_MAX: batch_data_len})
            self.hass.config_entries.async_update_entry(
                self._entry, options=entry_options
            )

            # Rebuild batch flags with new size and retry update
            self._make_batch_request_flags()
            return await self._async_update_data()

    async def async_update(self, **kwargs):
        """Perform an immediate data update (bypassing coordinator polling).

        This method is maintained for backward compatibility with existing entities.
        It triggers a manual update of the device data.

        Args:
            **kwargs: Additional keyword arguments including 'no_request' to skip polling.
        """
        try:
            await self.async_update_data(kwargs)
        except EchonetMaxOpcError as ex:
            batch_size_max = self._user_options.get(
                CONF_BATCH_SIZE_MAX, MAX_UPDATE_BATCH_SIZE
            )
            batch_data_len = max(
                ex.args[0],
                MIN_UPDATE_BATCH_SIZE,
                batch_size_max - 1,
            )
            if batch_data_len >= batch_size_max:
                _LOGGER.error(
                    f"The integration has adjusted the number of batch requests to "
                    f"{self._host} to {batch_size_max}, but no response is received. "
                    f"Please check and try restarting the device etc."
                )
                return None

            self._user_options[CONF_BATCH_SIZE_MAX] = batch_data_len
            entry_options = dict(self._entry.options)
            entry_options.update({CONF_BATCH_SIZE_MAX: batch_data_len})
            self.hass.config_entries.async_update_entry(
                self._entry, options=entry_options
            )
            self._make_batch_request_flags()

            await self.async_update(**kwargs)

    async def async_update_data(self, kwargs: dict) -> dict[int, Any]:
        """Execute the data fetch from device properties.

        This method performs batched property requests to minimize network traffic.
        It handles the MPC (Maximum Property Code) error by adjusting batch sizes.

        Args:
            kwargs: Dictionary containing optional 'no_request' flag for push-only updates.

        Returns:
            Dictionary containing fetched data keyed by EPC codes.
        """
        update_data = {}
        no_request = "no_request" in kwargs and kwargs["no_request"]

        for i, flags in enumerate(self._update_flag_batches):
            if i > 0:
                # Add 100ms interval between batch requests to avoid overwhelming the device
                await asyncio.sleep(0.1)
            batch_data = await self._instance.update(flags, no_request)
            if batch_data is not False:
                if len(flags) == 1:
                    update_data[flags[0]] = batch_data
                elif isinstance(batch_data, dict):
                    update_data.update(batch_data)

        _LOGGER.debug(polling_update_debug_log(update_data, self))
        if len(update_data) > 0:
            self._update_data.update(update_data)

        return update_data.copy()

    async def async_update_callback(self, isPush: bool = False):
        """Handle push notification updates from the ECHONET API.

        This method is called when the device sends unsolicited updates via push notifications.
        It triggers a no-request update to refresh local state without additional network traffic.

        Args:
            isPush: Flag indicating this was triggered by a push notification.
        """
        await self.async_update_data(kwargs={"no_request": True})
        for update_func in self._update_callbacks:
            await update_func(isPush)

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
                self._update_data[value] = None

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
