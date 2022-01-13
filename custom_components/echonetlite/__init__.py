"""The echonetlite integration."""
from __future__ import annotations
import logging
import pychonet as echonet
from pychonet.lib.epc import EPC_SUPER, EPC_CODE
from pychonet.lib.const import VERSION
from datetime import timedelta
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle
from .const import DOMAIN
from aioudp import UDPServer
# from pychonet import Factory
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
    ENL_HVAC_ROOM_HUMIDITY,
    ENL_HVAC_ROOM_TEMP,
    ENL_HVAC_OUT_TEMP
)

from pychonet.GeneralLighting import (
    ENL_BRIGHTNESS,
    ENL_COLOR_TEMP
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", 'climate', 'select', 'light', 'fan']
PARALLEL_UPDATES = 0
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
MAX_UPDATE_BATCH_SIZE = 10

HVAC_API_CONNECTOR_DEFAULT_FLAGS = [
    ENL_STATUS, ENL_FANSPEED, ENL_AUTO_DIRECTION, ENL_SWING_MODE, ENL_AIR_VERT, ENL_AIR_HORZ, ENL_HVAC_MODE,
    ENL_HVAC_SET_TEMP, ENL_HVAC_ROOM_HUMIDITY, ENL_HVAC_ROOM_TEMP, ENL_HVAC_OUT_TEMP,
    ENL_INSTANTANEOUS_POWER, ENL_CUMULATIVE_POWER
]

LIGHT_API_CONNECTOR_DEFAULT_FLAGS = [
    ENL_STATUS, ENL_BRIGHTNESS, ENL_COLOR_TEMP
]

POWER_RELATE_FLAGS = [
    ENL_INSTANTANEOUS_POWER, ENL_CUMULATIVE_POWER
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.async_on_unload(entry.add_update_listener(update_listener))
    host = None
    udp = None
    loop = None
    server = None

    if DOMAIN in hass.data:  # maybe set up by config entry?
        _LOGGER.debug(f"{hass.data[DOMAIN]} has already been setup..")
        server = hass.data[DOMAIN]['api']
        hass.data[DOMAIN].update({entry.entry_id: []})
    else:  # setup API
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN].update({entry.entry_id: []})
        udp = UDPServer()
        loop = asyncio.get_event_loop()
        udp.run("0.0.0.0", 3610, loop=loop)
        server = ECHONETAPIClient(server=udp, loop=loop)
        server._message_timeout = 300
        hass.data[DOMAIN].update({"api": server})
    _LOGGER.debug(f"pychonet version in use is {VERSION}")

    for instance in entry.data["instances"]:
        echonetlite = None
        host = instance["host"]
        eojgc = instance["eojgc"]
        eojcc = instance["eojcc"]
        eojci = instance["eojci"]
        getmap = instance["getmap"]
        setmap = instance["setmap"]
        uid = instance["uid"]
        _LOGGER.debug(f'{instance["uid"]} is the UID..')

        # manually update API states using config entry data
        if host not in list(server._state):
            server._state[host] = {
                "instances": {
                    eojgc: {
                        eojcc: {
                            eojci: {
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
                        ENL_SETMAP: setmap,
                        ENL_GETMAP: getmap,
                        ENL_UID: uid
                    }
                }
            })
        if eojci not in list(server._state[host]["instances"][eojgc][eojcc]):
            server._state[host]["instances"][eojgc][eojcc].update({
                eojci: {
                    ENL_SETMAP: setmap,
                    ENL_GETMAP: getmap,
                    ENL_UID: uid
                }
            })

        echonetlite = ECHONETConnector(instance, hass.data[DOMAIN]['api'], entry)
        await echonetlite.async_update()
        hass.data[DOMAIN][entry.entry_id].append({"instance": instance, "echonetlite": echonetlite})

    _LOGGER.debug(f"Plaform entry data - {entry.data}")

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


# TODO FIX CODE REPETITION
async def update_listener(hass, entry):
    for instance in hass.data[DOMAIN][entry.entry_id]:
        if instance['instance']['eojgc'] == 1 and instance['instance']['eojcc'] == 48:
            if entry.options.get("fan_settings") is not None:  # check if options has been created
                if len(entry.options.get("fan_settings")) > 0:  # if it has been created then check list length.
                    instance["echonetlite"]._user_options.update({ENL_FANSPEED: entry.options.get("fan_settings")})
                else:
                    instance["echonetlite"]._user_options.update({ENL_FANSPEED: False})

            if entry.options.get("swing_horiz") is not None:
                if len(entry.options.get("swing_horiz")) > 0:
                    instance["echonetlite"]._user_options.update({ENL_AIR_HORZ: entry.options.get("swing_horiz")})
                else:
                    instance["echonetlite"]._user_options.update({ENL_AIR_HORZ: False})

            if entry.options.get("swing_vert") is not None:
                if len(entry.options.get("swing_vert")) > 0:
                    instance["echonetlite"]._user_options.update({ENL_AIR_VERT: entry.options.get("swing_vert")})
                else:
                    instance["echonetlite"]._user_options.update({ENL_AIR_VERT: False})

            if entry.options.get("auto_direction") is not None:
                if len(entry.options.get("auto_direction")) > 0:
                    instance["echonetlite"]._user_options.update({ENL_AUTO_DIRECTION: entry.options.get("auto_direction")})
                else:
                    instance["echonetlite"]._user_options.update({ENL_AUTO_DIRECTION: False})

            if entry.options.get("swing_mode") is not None:
                if len(entry.options.get("swing_mode")) > 0:
                    instance["echonetlite"]._user_options.update({ENL_SWING_MODE: entry.options.get("swing_mode")})
                else:
                    instance["echonetlite"]._user_options.update({ENL_SWING_MODE: False})


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
        self._getPropertyMap = self._api._state[self._host]["instances"][self._eojgc][self._eojcc][self._eojci][ENL_GETMAP]
        self._setPropertyMap = self._api._state[self._host]["instances"][self._eojgc][self._eojcc][self._eojci][ENL_SETMAP]
        self._manufacturer = None
        if "manufacturer" in instance:
            self._manufacturer = instance["manufacturer"]

        # Detect HVAC - eventually we will use factory here.
        self._update_flags_full_list = []
        if self._eojgc == 1 and self._eojcc == 48:
            _LOGGER.debug(f"Create new HomeAirConditioner instance for: {self._eojgc}-{self._eojcc}-{self._eojci}")
            for value in HVAC_API_CONNECTOR_DEFAULT_FLAGS:
                if value in self._getPropertyMap:
                    self._update_flags_full_list.append(value)
            self._instance = echonet.HomeAirConditioner(self._host, self._api)
        elif self._eojgc == 2 and self._eojcc == 144:
            _LOGGER.debug(f"Create new GeneralLighting instance for: {self._eojgc}-{self._eojcc}-{self._eojci}")
            for value in LIGHT_API_CONNECTOR_DEFAULT_FLAGS:
                if value in self._getPropertyMap:
                    self._update_flags_full_list.append(value)
            self._instance = echonet.GeneralLighting(self._host, self._api, self._eojci)
        else:
            _LOGGER.debug(f"Create new default instance for: {self._eojgc}-{self._eojcc}-{self._eojci}")
            self._update_flags_full_list = [ENL_STATUS]
            for item in self._getPropertyMap:
                if item not in list(EPC_SUPER.keys()):
                    if item in list(EPC_CODE[self._eojgc][self._eojcc].keys()):
                        self._update_flags_full_list.append(item)
                if item in POWER_RELATE_FLAGS:
                    self._update_flags_full_list.append(item)
            self._instance = echonet.Factory(self._host, self._api, self._eojgc, self._eojcc, self._eojci)

        # Split list of codes into batches of 10
        start_index = 0
        full_list_length = len(self._update_flags_full_list)

        while start_index + MAX_UPDATE_BATCH_SIZE < full_list_length:
            self._update_flag_batches.append(self._update_flags_full_list[start_index:start_index+MAX_UPDATE_BATCH_SIZE])
            start_index += MAX_UPDATE_BATCH_SIZE
        self._update_flag_batches.append(self._update_flags_full_list[start_index:full_list_length])

        self._user_options = {
            ENL_FANSPEED: False,
            ENL_AUTO_DIRECTION: False,
            ENL_SWING_MODE: False,
            ENL_AIR_VERT: False,
            ENL_AIR_HORZ: False
        }
        # Stitch together user selectable options for fan + swing modes for HVAC
        # TODO - fix code repetition
        if entry.options.get("fan_settings") is not None:  # check if options has been created
            if len(entry.options.get("fan_settings")) > 0:  # if it has been created then check list length.
                self._user_options[ENL_FANSPEED] = entry.options.get("fan_settings")
        if entry.options.get("swing_horiz") is not None:
            if len(entry.options.get("swing_horiz")) > 0:
                self._user_options[ENL_AIR_HORZ] = entry.options.get("swing_horiz")
        if entry.options.get("swing_vert") is not None:  # check if options has been created
            if len(entry.options.get("swing_vert")) > 0:
                self._user_options[ENL_AIR_VERT] = entry.options.get("swing_vert")
        if entry.options.get("auto_direction") is not None:  # check if options has been created
            if len(entry.options.get("auto_direction")) > 0:
                self._user_options[ENL_AUTO_DIRECTION] = entry.options.get("auto_direction")
        if entry.options.get("swing_mode") is not None:  # check if options has been created
            if len(entry.options.get("swing_mode")) > 0:
                self._user_options[ENL_SWING_MODE] = entry.options.get("swing_mode")

        self._uid = self._api._state[self._host]["instances"][self._eojgc][self._eojcc][self._eojci][ENL_UID]
        _LOGGER.debug(f'{self._uid} is the UID in ECHONET connector..')
        if self._uid is None:
            self._uid = f"{self._host}-{self._eojgc}-{self._eojcc}-{self._eojci}"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs):
        for retry in range(1, 4):
            update_data = {}
            for flags in self._update_flag_batches:
                batch_data = await self._instance.update(flags)
                if batch_data is not False:
                    if isinstance(batch_data, dict):
                        update_data.update(batch_data)
                    elif len(flags) == 1:
                        update_data[flags[0]] = batch_data
            _LOGGER.debug(f"{list(update_data.values())}")
            if len(update_data) > 0 and False not in list(update_data.values()):
                # polling succeded.
                if retry > 1:
                    _LOGGER.debug(f"polling ECHONET Instance host {self._host} succeeded - Retry {retry} of 3")
                self._update_data = update_data
                return self._update_data
            else:
                _LOGGER.debug(f"polling ECHONET Instance host {self._host} timed out - Retry {retry} of 3")
                _LOGGER.debug(f"Number of missed ECHONETLite msssages since reboot is - {len(self._api._message_list)}")
        return self._update_data
