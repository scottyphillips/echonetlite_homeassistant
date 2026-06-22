"""The echonetlite integration."""

from __future__ import annotations

import asyncio
import logging
import time as pytime
from datetime import timedelta
from typing import Any

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

# Throttle removed - UpdateCoordinator handles update intervals
from pychonet import ECHONETAPIClient
from pychonet.EchonetInstance import (
    ENL_GETMAP,
    ENL_SETMAP,
    ENL_UID,
)
from pychonet.lib.const import ENL_STATMAP, VERSION
from pychonet.lib.epc import EPC_CODE, EPC_SUPER
from pychonet.lib.udpserver import UDPServer

from .config_flow import ErrorConnect, async_discover_newhost, enumerate_instances
from .const import (
    DOMAIN,
    MISC_OPTIONS,
    TEMP_OPTIONS,
    USER_OPTIONS,
)
from .connectors import (
    ECHONETConnector,
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
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)
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


def get_unit_by_device_class(device_class: str) -> str | None:
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the ECHONET Lite integration."""

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
                f"Called unload_config_entry() to try to remove {host} from server._state."
            )
            if server._state.get(host):
                server._state.pop(host)
            # Remove update callback function
            for _key in list(server._update_callbacks.keys()):
                if _key.startswith(host):
                    del server._update_callbacks[_key]

    entry.async_on_unload(unload_config_entry)

    if DOMAIN in hass.data:  # maybe set up by config entry?
        _LOGGER.debug("Adding additional instance to existing ECHONETlite platform.")
        server = hass.data[DOMAIN]["api"]
        hass.data[DOMAIN].update({entry.entry_id: []})
    else:  # setup API
        _LOGGER.debug("Starting up ECHONETlite platform.")
        _LOGGER.debug(f"pychonet version is {VERSION}")
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN].update({entry.entry_id: []})

        # instantiate pychonet API client and UDP server for receiving push notifications
        udp = UDPServer()
        udp.run("0.0.0.0", 3610, loop=hass.loop)
        server = ECHONETAPIClient(udp)
        server._debug_flag = True  # Set pychonet debug flag to True to enable debug logging from the library
        server._logger = _LOGGER.warning
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
            # Echonet can be slow to respond, so we need to manage our setup budget carefully to avoid timeouts in Home Assistant.
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
                # keep old type config (echonetlite < 3.6.0) # legacy uses _instance['uid']. Shoould be removed in the future
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
        _LOGGER.debug("Instantiating ECHONETConnector.")
        echonetlite = ECHONETConnector(instance, hass, entry)
        await echonetlite.startup()
        # first refresh of data required by DataUpdateCoordinator to populate initial data and start polling.
        await echonetlite.async_config_entry_first_refresh()
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
                        # echonetlite.async_config_entry_first_refresh(),
                        echonetlite._async_update_data(),
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

    _LOGGER.debug(f"ECHONETLite Platform entry data - {entry.data}")

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
