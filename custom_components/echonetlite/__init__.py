"""The echonetlite integration."""
from __future__ import annotations
import logging
import pychonet as echonet
from pychonet.lib.epc import EPC_SUPER
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle

from .const import DOMAIN


from pychonet.EchonetInstance import ENL_STATUS, ENL_SETMAP, ENL_GETMAP
from pychonet.HomeAirConditioner import (
    ENL_FANSPEED,
    ENL_AUTO_DIRECTION,
    ENL_SWING_MODE,
    ENL_AIR_VERT,
    ENL_AIR_HORZ,
    ENL_HVAC_MODE,
    ENL_HVAC_SET_TEMP,
    ENL_HVAC_ROOM_TEMP,
    ENL_HVAC_OUT_TEMP
)

PLATFORMS = ["sensor",'climate', 'select']
PARALLEL_UPDATES = 0
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

HVAC_API_CONNECTOR_DEFAULT_FLAGS = [ENL_STATUS, 
        ENL_FANSPEED, ENL_AUTO_DIRECTION, ENL_SWING_MODE, 
        ENL_AIR_VERT, ENL_AIR_HORZ, ENL_HVAC_MODE, ENL_HVAC_SET_TEMP, ENL_HVAC_ROOM_TEMP, ENL_HVAC_OUT_TEMP]



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.async_on_unload(entry.add_update_listener(update_listener))
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].update({entry.entry_id: []})
    _LOGGER.debug("platform entry data - %s", entry.data)
    for instance in entry.data["instances"]:
        # if ECHONETLite instance is HomeAirConditioner enable climate platform
        echonetlite = None
        if instance['eojgc'] == 1 and instance['eojcc'] == 48:
            echonetlite = HVACConnector(entry, instance['UID'], instance['getPropertyMap'], instance['setPropertyMap'])
        else:
            echonetlite = ECHONETConnector(instance['eojgc'],instance['eojcc'], instance['eojci'], entry.data["host"], instance['UID'], instance['getPropertyMap'], instance['setPropertyMap'])
        hass.data[DOMAIN][entry.entry_id].append({"instance_data": instance, "API":echonetlite})
        
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def update_listener(hass, entry):
    for instance in hass.data[DOMAIN][entry.entry_id]:
       if instance['instance_data']['eojgc'] == 1 and instance['instance_data']['eojcc'] == 48:
            if entry.options.get("fan_settings") is not None: # check if options has been created
                if len(entry.options.get("fan_settings")) > 0: # if it has been created then check list length. 
                     instance["API"]._user_options.update({ENL_FANSPEED : entry.options.get("fan_settings")})
                else:
                     instance["API"]._user_options.update({ENL_FANSPEED : False})


"""EchonetHVACAPIConnector is used to centralise API calls for climate entities"""
class HVACConnector():
    def __init__(self, entry, uid, getmap, setmap):
        self._update_data = {}
        self._getPropertyMap = getmap
        self._setPropertyMap = setmap
        self._update_flags = []
        for value in HVAC_API_CONNECTOR_DEFAULT_FLAGS:
            if value in self._getPropertyMap:
                self._update_flags.append(value)
        self._user_options = {ENL_FANSPEED: False, ENL_AUTO_DIRECTION: False, ENL_SWING_MODE: False, ENL_AIR_VERT: False, ENL_AIR_HORZ: False }
        
        
        # Stich together user selectable options for fan + swing modes for HVAC #TODO - fix code repetition
        if entry.options.get("fan_settings") is not None: # check if options has been created
            if len(entry.options.get("fan_settings")) > 0: # if it has been created then check list length. 
                self._user_options[ENL_FANSPEED] = entry.options.get("fan_settings")
        if entry.options.get("swing_horiz") is not None: 
            if len(entry.options.get("swing_horiz")) > 0: 
                self._user_options[ENL_AIR_HORZ] = entry.options.get("swing_horiz")
        if entry.options.get("swing_vert") is not None: # check if options has been created
            if len(entry.options.get("swing_vert")) > 0: 
                self._user_options[ENL_AIR_VERT] = entry.options.get("swing_vert")
        
        for value in self._update_flags:
            self._update_data[value] = False
        self._update_data = {ENL_STATUS: 'Off'}
        self._api = echonet.HomeAirConditioner(entry.data["host"])
        # self._update_data = self._api.update(self._update_flags)
        self._uid = uid
       

    @Throttle(MIN_TIME_BETWEEN_UPDATES)   
    async def async_update(self, **kwargs):
        _LOGGER.debug(f"commence polling ECHONET HVAC Instance")
        self._update_data = self._api.update(self._update_flags)
        _LOGGER.debug(f"polling ECHONET HVAC Instance complete - {self._update_data}")
        return self._update_data

"""EchonetAPIConnector is used to centralise API calls for generic Echonet devices"""
class ECHONETConnector():
    def __init__(self, eojgc, eojcc, eojci, host, uid, getmap, setmap):
       _LOGGER.debug("initialisating generic ECHONET connector %s %s %s %s", eojgc, eojcc, eojci, host)    
       self._update_data = {}
       self._getPropertyMap = getmap
       self._setPropertyMap = setmap
       self._api = echonet.EchonetInstance(eojgc, eojcc, eojci, host)
       self._update_flags = [ENL_STATUS]
       for item in self._getPropertyMap:
            if item not in list(EPC_SUPER.keys()):
                self._update_flags.append(item)
                self._update_data[item] = False
       self._uid = uid
          
    @Throttle(MIN_TIME_BETWEEN_UPDATES)   
    async def async_update(self, **kwargs):
        self._update_data = self._api.update(self._update_flags)
        _LOGGER.debug(f"polling ECHONET Instance complete - {self._update_data}")
        return self._update_data
    