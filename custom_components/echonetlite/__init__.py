"""The echonetlite integration."""
from __future__ import annotations
import logging
import pychonet as echonet
from pychonet.lib.epc import EPC_SUPER, EPC_CODE
from pychonet.lib.const import VERSION, ENL_STATMAP
from datetime import timedelta
import asyncio
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle
from homeassistant.const import Platform
from .const import DOMAIN, USER_OPTIONS, TEMP_OPTIONS, CONF_FORCE_POLLING, MISC_OPTIONS
from pychonet.lib.udpserver import UDPServer

from pychonet import ECHONETAPIClient
from pychonet.EchonetInstance import (
    ENL_GETMAP,
    ENL_SETMAP,
    ENL_UID,
    ENL_STATUS,
    ENL_INSTANTANEOUS_POWER,
    ENL_CUMULATIVE_POWER
)
from pychonet.HomeAirConditioner import (
    ENL_FANSPEED,
    ENL_AUTO_DIRECTION,
    ENL_SWING_MODE,
    ENL_AIR_VERT,
    ENL_AIR_HORZ,
    ENL_HVAC_MODE,
    ENL_HVAC_SET_TEMP,
    ENL_HVAC_SET_HUMIDITY,
    ENL_HVAC_ROOM_HUMIDITY,
    ENL_HVAC_ROOM_TEMP,
    ENL_HVAC_SILENT_MODE,
    ENL_HVAC_OUT_TEMP
)

from pychonet.DistributionPanelMeter import (
    ENL_DPM_ENG_NOR,
    ENL_DPM_ENG_REV,
    ENL_DPM_ENG_UNIT,
    ENL_DPM_DAY_GET_HISTORY,
    ENL_DPM_INSTANT_ENG,
    ENL_DPM_INSTANT_CUR,
    ENL_DPM_INSTANT_VOL
)

from pychonet.GeneralLighting import (
    ENL_BRIGHTNESS,
    ENL_COLOR_TEMP
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.CLIMATE, Platform.SELECT, Platform.LIGHT, Platform.FAN, Platform.SWITCH]
PARALLEL_UPDATES = 0
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
MAX_UPDATE_BATCH_SIZE = 10

HVAC_API_CONNECTOR_DEFAULT_FLAGS = [
    ENL_STATUS, ENL_FANSPEED, ENL_AUTO_DIRECTION, ENL_SWING_MODE, ENL_AIR_VERT, ENL_AIR_HORZ, ENL_HVAC_MODE,
    ENL_HVAC_SET_TEMP, ENL_HVAC_SET_HUMIDITY, ENL_HVAC_ROOM_HUMIDITY, ENL_HVAC_ROOM_TEMP, ENL_HVAC_OUT_TEMP, ENL_HVAC_SILENT_MODE,
    ENL_INSTANTANEOUS_POWER, ENL_CUMULATIVE_POWER
]

LIGHT_API_CONNECTOR_DEFAULT_FLAGS = [
    ENL_STATUS, ENL_BRIGHTNESS, ENL_COLOR_TEMP
]

_0287_API_CONNECTOR_DEFAULT_FLAGS = [ENL_STATUS, ENL_DPM_ENG_NOR, ENL_DPM_ENG_REV, ENL_DPM_ENG_UNIT, ENL_DPM_DAY_GET_HISTORY, ENL_DPM_INSTANT_ENG, ENL_DPM_INSTANT_CUR, ENL_DPM_INSTANT_VOL]

def polling_update_debug_log(values, eojgc, eojcc):
    debug_log = f"\nECHONETlite polling update data:\n"
    for value in list(values.keys()):
        if value in EPC_CODE[eojgc][eojcc]:
             debug_log = debug_log + f' - {EPC_CODE[eojgc][eojcc][value]} ({value:#x}): {values[value]}\n'
        if value in EPC_SUPER:
             debug_log = debug_log + f' - {EPC_SUPER[value]} ({value:#x}): {values[value]}\n'
    return debug_log

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.async_on_unload(entry.add_update_listener(update_listener))
    host = None
    udp = None
    loop = None
    server = None

    async def discover_callback(host):
        await config_entries.HANDLERS[DOMAIN].async_discover_newhost(hass, host)

    def unload_config_entry():
        _LOGGER.debug(f"Called unload_config_entry() try to remove {host} from server._state.")
        server._state.pop(host)

    entry.async_on_unload(unload_config_entry)

    if DOMAIN in hass.data:  # maybe set up by config entry?
        _LOGGER.debug(f"ECHONETlite platform is already started.")
        server = hass.data[DOMAIN]['api']
        hass.data[DOMAIN].update({entry.entry_id: []})
    else:  # setup API
        _LOGGER.debug(f"Starting up ECHONETlite platform..")
        _LOGGER.debug(f"pychonet version is {VERSION}")
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN].update({entry.entry_id: []})
        udp = UDPServer()
        loop = asyncio.get_event_loop()
        udp.run("0.0.0.0", 3610, loop=loop)
        server = ECHONETAPIClient(udp)
        server._debug_flag = True
        server._logger = _LOGGER.debug
        server._message_timeout = 300
        server._discover_callback = discover_callback
        hass.data[DOMAIN].update({"api": server})


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
                                ENL_UID: uid
                            }
                        }
                    }
                }
            }
        if eojgc not in list(server._state[host]["instances"]):
            server._state[host]["instances"].update({
                eojgc: {
                    eojcc: {
                        eojci: {
                            ENL_STATMAP: ntfmap,
                            ENL_SETMAP: setmap,
                            ENL_GETMAP: getmap,
                            ENL_UID: uid
                        }
                    }
                }
            })
        if eojcc not in list(server._state[host]["instances"][eojgc]):
            server._state[host]["instances"][eojgc].update({
                eojcc: {
                    eojci: {
                        ENL_STATMAP: ntfmap,
                        ENL_SETMAP: setmap,
                        ENL_GETMAP: getmap,
                        ENL_UID: uid
                    }
                }
            })
        if eojci not in list(server._state[host]["instances"][eojgc][eojcc]):
            server._state[host]["instances"][eojgc][eojcc].update({
                eojci: {
                    ENL_STATMAP: ntfmap,
                    ENL_SETMAP: setmap,
                    ENL_GETMAP: getmap,
                    ENL_UID: uid
                }
            })

        echonetlite = ECHONETConnector(instance, hass.data[DOMAIN]['api'], entry)
        await echonetlite.async_update()
        hass.data[DOMAIN][entry.entry_id].append({"instance": instance, "echonetlite": echonetlite})

    _LOGGER.debug(f"Plaform entry data - {entry.data}")

    # this api is too recent (around April 2021): hass.config_entries.async_setup_platforms(entry, PLATFORMS)
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
        if instance['instance']['eojgc'] == 1 and instance['instance']['eojcc'] == 48:
            for option in USER_OPTIONS.keys():
                if entry.options.get(USER_OPTIONS[option]["option"]) is not None:  # check if options has been created
                    if isinstance(entry.options.get(USER_OPTIONS[option]["option"]), list):
                        if len(entry.options.get(USER_OPTIONS[option]["option"])) > 0:  # if it has been created then check list length.
                            instance["echonetlite"]._user_options.update({option: entry.options.get(USER_OPTIONS[option]["option"])})
                        else:
                            instance["echonetlite"]._user_options.update({option: False})
                    else:
                        instance["echonetlite"]._user_options.update({option: entry.options.get(USER_OPTIONS[option]["option"])})
            for option in TEMP_OPTIONS.keys():
                if entry.options.get(option) is not None:
                    instance["echonetlite"]._user_options.update({option: entry.options.get(option)})

        for key, option in MISC_OPTIONS.items():
            if entry.options.get(key) is not None or option.get('default'):
                instance["echonetlite"]._user_options.update({key: entry.options.get(key, option.get('default'))})

        for func in instance["echonetlite"]._update_option_func:
            func()

class ECHONETConnector():
    """EchonetAPIConnector is used to centralise API calls for  Echonet devices.
    API calls are aggregated per instance (not per node!)"""
    def __init__(self, instance, api, entry):
        self._host = instance['host']
        self._instance = None
        self._eojgc = instance['eojgc']
        self._eojcc = instance['eojcc']
        self._eojci = instance['eojci']
        self._update_flag_batches = []
        self._update_data = {}
        self._api = api
        self._update_callbacks = []
        self._update_option_func = []
        self._ntfPropertyMap = instance["ntfmap"]
        self._getPropertyMap = instance["getmap"]
        self._setPropertyMap = instance["setmap"]
        self._manufacturer = None
        if "manufacturer" in instance:
            self._manufacturer = instance["manufacturer"]
        self._uid = instance.get('uid')
        self._uidi = instance.get('uidi')
        self._api.register_async_update_callbacks(self._host, self._eojgc, self._eojcc, self._eojci, self.async_update_callback)

        # Detect HVAC - eventually we will use factory here.
        self._update_flags_full_list = []
        flags = []
        if self._eojgc == 0x01 and self._eojcc == 0x30:
            _LOGGER.debug(f"Starting ECHONETLite HomeAirConditioner instance at {self._host}")
            flags = HVAC_API_CONNECTOR_DEFAULT_FLAGS
        elif self._eojgc == 0x02 and self._eojcc == 0x90:
            _LOGGER.debug(f"Starting ECHONETLite GeneralLighting instance at {self._host}")
            flags = LIGHT_API_CONNECTOR_DEFAULT_FLAGS
        elif self._eojgc == 0x02 and self._eojcc == 0x87:
            _LOGGER.debug(f"Starting ECHONETLite DistributionPanelMeter instance at {self._host}")
            flags = _0287_API_CONNECTOR_DEFAULT_FLAGS
        else:
            _LOGGER.debug(f"Starting ECHONETLite Generic instance for {self._eojgc}-{self._eojcc}-{self._eojci} at {self._host}")
            flags = [ENL_STATUS]
            for item in self._getPropertyMap:
                if item not in list(EPC_SUPER.keys()):
                    if item in list(EPC_CODE[self._eojgc][self._eojcc].keys()):
                        flags.append(item)

        for value in flags:
            if value in self._getPropertyMap:
                self._update_flags_full_list.append(value)
                self._update_data[value] = None
        self._instance = echonet.Factory(self._host, self._api, self._eojgc, self._eojcc, self._eojci)

        # Split list of codes into batches of 10
        start_index = 0
        full_list_length = len(self._update_flags_full_list)

        while start_index + MAX_UPDATE_BATCH_SIZE < full_list_length:
            self._update_flag_batches.append(self._update_flags_full_list[start_index:start_index+MAX_UPDATE_BATCH_SIZE])
            start_index += MAX_UPDATE_BATCH_SIZE
        self._update_flag_batches.append(self._update_flags_full_list[start_index:full_list_length])

        # TODO this looks messy.
        self._user_options = {
            ENL_FANSPEED: False,
            ENL_AUTO_DIRECTION: False,
            ENL_SWING_MODE: False,
            ENL_AIR_VERT: False,
            ENL_AIR_HORZ: False,
            'min_temp_heat': 15,
            'max_temp_heat': 35,
            'min_temp_cool': 15,
            'max_temp_cool': 35,
            'min_temp_auto': 15,
            'max_temp_auto': 35,
        }
        # User selectable options for fan + swing modes for HVAC
        for option in USER_OPTIONS.keys():
            if entry.options.get(USER_OPTIONS[option]['option']) is not None:  # check if options has been created
                if len(entry.options.get(USER_OPTIONS[option]['option'])) > 0:  # if it has been created then check list length.
                    self._user_options[option] = entry.options.get(USER_OPTIONS[option]['option'])

        # Temperature range options for heat, cool and auto modes
        for option in TEMP_OPTIONS.keys():
            if entry.options.get(option) is not None:
                self._user_options[option] = entry.options.get(option)

        _LOGGER.debug(f'UID for ECHONETLite instance at {self._host}  is {self._uid}.')
        if self._uid is None:
            self._uid = f"{self._host}-{self._eojgc}-{self._eojcc}-{self._eojci}"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs):
        return await self.async_update_data(kwargs = kwargs)

    async def async_update_data(self, kwargs):
        for retry in range(1, 4):
            update_data = {}
            no_request = 'no_request' in kwargs and kwargs['no_request']
            for flags in self._update_flag_batches:
                batch_data = await self._instance.update(flags, no_request)
                if batch_data is not False:
                    if isinstance(batch_data, dict):
                        update_data.update(batch_data)
                    elif len(flags) == 1:
                        update_data[flags[0]] = batch_data
            _LOGGER.debug(polling_update_debug_log(update_data, self._eojgc, self._eojcc))
            # check if polling succeeded
            polling_succeeded = False
            for value in list(update_data.values()):
                if value is not None:
                    polling_succeeded = True
            if len(update_data) > 0 and polling_succeeded == True:
                # polling succeded.
                if retry > 1:
                    _LOGGER.debug(f"Polling ECHONET Instance host at {self._host} succeeded. Retry {retry} of 3")
                self._update_data.update(update_data)
                return self._update_data
            else:
                _LOGGER.debug(f"Polling ECHONET Instance host {self._host} timed out. Retry {retry} of 3")
                _LOGGER.debug(f"Number of missed ECHONETLite msssages since reboot is {len(self._api._message_list)}")
        self._update_data.update(update_data)
        return self._update_data

    async def async_update_callback(self, isPush = False):
        await self.async_update_data(kwargs = {"no_request": True})
        for update_func in self._update_callbacks:
            await update_func(isPush)

    def register_async_update_callbacks(self, update_func):
        self._update_callbacks.append(update_func)

    def add_update_option_listener(self, update_func):
        self._update_option_func.append(update_func)
