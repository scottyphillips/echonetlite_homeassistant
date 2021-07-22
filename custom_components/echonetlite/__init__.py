"""The echonetlite integration."""
from __future__ import annotations
import logging
import pychonet as echonet
from pychonet.lib.epc import EPC_SUPER
from datetime import timedelta
import asyncio

_LOGGER = logging.getLogger(__name__)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle

from .const import DOMAIN

from aioudp import UDPServer
from pychonet import Factory
from pychonet import ECHONETAPIClient
from pychonet import HomeAirConditioner
from pychonet import EchonetInstance
from pychonet.EchonetInstance import ENL_STATUS, ENL_SETMAP, ENL_GETMAP, ENL_UID
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
    host = None
    udp = None
    loop = None
    server = None
    
    if DOMAIN in hass.data: # maybe set up by config entry?
        _LOGGER.debug(f"{hass.data[DOMAIN]} has already been setup..")
        server = hass.data[DOMAIN]['api']
        hass.data[DOMAIN].update({entry.entry_id: []})
    else: #setup API
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN].update({entry.entry_id: []})
        udp = UDPServer()
        loop = asyncio.get_event_loop()
        udp.run("0.0.0.0",3610, loop=loop)
        server = ECHONETAPIClient(server=udp,loop=loop)
        hass.data[DOMAIN].update({"api":server})
        
    for instance in entry.data["instances"]:
        echonetlite = None
        host =   instance["host"]
        eojgc =  instance["eojgc"]
        eojcc =  instance["eojcc"]
        eojci =  instance["eojci"]
        getmap = instance["getmap"]
        setmap = instance["setmap"]
        uid =    instance["uid"]
        
        # manually update API states using config entry data
        if host not in list(server._state):
            server._state[host] = {"instances": {eojgc: {eojcc: {eojci: {ENL_SETMAP:setmap, ENL_GETMAP:getmap, ENL_UID:uid}}}}}
        if eojgc not in list(server._state[host]["instances"]):
            server._state[host]["instances"].update({eojgc:{eojcc:{eojci:{ENL_SETMAP:setmap, ENL_GETMAP:getmap, ENL_UID:uid}}}})
        if eojcc not in list(server._state[host]["instances"][eojgc]):
            server._state[host]["instances"][eojgc].update({eojcc:{eojci:{ENL_SETMAP:setmap, ENL_GETMAP:getmap, ENL_UID:uid}}})
        if eojci not in list(server._state[host]["instances"][eojgc][eojcc]):
            server._state[host]["instances"][eojgc][eojcc].update({eojci:{ENL_SETMAP:setmap, ENL_GETMAP:getmap, ENL_UID:uid}})
        
        # detect HVAC
        if eojgc == 1 and eojcc == 48:
            _LOGGER.debug("HVAC being set up..")
            echonetlite = HVACConnector(instance, hass.data[DOMAIN]['api'], entry)
        else: 
            echonetlite = ECHONETConnector(instance, hass.data[DOMAIN]['api'])
        await echonetlite.async_update()
        _LOGGER.debug(f"Why is this failing???? {hass.data[DOMAIN]}")
        hass.data[DOMAIN][entry.entry_id].append({"instance": instance, "echonetlite":echonetlite})
                 
    _LOGGER.debug(f"platform entry data - {entry.data}")
    _LOGGER.debug(f"HASS Domain Data - {hass.data[DOMAIN]['api']._state}")
    _LOGGER.debug(f"HASS Domain Entry ID- {hass.data[DOMAIN][entry.entry_id]}")
    
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
       if instance['instance']['eojgc'] == 1 and instance['instance']['eojcc'] == 48:
            if entry.options.get("fan_settings") is not None: # check if options has been created
                if len(entry.options.get("fan_settings")) > 0: # if it has been created then check list length. 
                     instance["echonetlite"]._user_options.update({ENL_FANSPEED : entry.options.get("fan_settings")})
                else:
                     instance["echonetlite"]._user_options.update({ENL_FANSPEED : False})


"""EchonetHVACAPIConnector is used to centralise API calls for climate entities per node"""
class HVACConnector():
    def __init__(self, instance, api, entry):
        self._host = instance['host']
        self._eojgc = instance['eojgc']
        self._eojcc = instance['eojcc']
        self._eojci = instance['eojci']        
        self._update_data = {}
        self._api = api
        self._getPropertyMap = api._state[self._host]["instances"][self._eojgc][self._eojcc][self._eojci][ENL_GETMAP]
        self._setPropertyMap = api._state[self._host]["instances"][self._eojgc][self._eojcc][self._eojci][ENL_SETMAP]
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
        self._instance = echonet.HomeAirConditioner(self._host, self._api)
        self._uid = self._api._state[self._host]["instances"][self._eojgc][self._eojcc][self._eojci][ENL_UID]
        if self._uid == None:
            self._uid = f"{self._host}-{self._eojgc}-{self._eojcc}-{self._eojci}"
       
    @Throttle(MIN_TIME_BETWEEN_UPDATES)   
    async def async_update(self, **kwargs):
        #_LOGGER.debug(f"commence polling ECHONET HVAC Instance")
        update_data = await self._instance.update(self._update_flags)
        if False not in list(update_data.values()):
           # polling succeded. 
           self._update_data = update_data
        else:
           _LOGGER.debug(f"polling ECHONET Generic Instance host {self._host} failed - data not updated {self._update_data}")
           _LOGGER.debug(f"message list length is - {len(self._api._message_list)}")
        return self._update_data

"""EchonetAPIConnector is used to centralise API calls for generic Echonet devices. API calls are aggregated per instance (not per node!)"""
class ECHONETConnector():
    def __init__(self, instance, api):
       self._host = instance['host']
       self._eojgc = instance['eojgc']
       self._eojcc = instance['eojcc']
       self._eojci = instance['eojci'] 
       self._api = api
       _LOGGER.debug(f"initialisating generic ECHONET connector for host {self._host} - instanace {self._eojgc}-{self._eojcc}-{self._eojci}")    
       self._update_data = {}
       self._getPropertyMap = self._api._state[self._host]["instances"][self._eojgc][self._eojcc][self._eojci][ENL_GETMAP]
       self._setPropertyMap = self._api._state[self._host]["instances"][self._eojgc][self._eojcc][self._eojci][ENL_SETMAP]
       self._instance = echonet.EchonetInstance(self._host, self._eojgc, self._eojcc, self._eojci, self._api)
       self._update_flags = [ENL_STATUS]
       for item in self._getPropertyMap:
            if item not in list(EPC_SUPER.keys()):
                self._update_flags.append(item)
                self._update_data[item] = False
       self._uid = self._api._state[self._host]["instances"][self._eojgc][self._eojcc][self._eojci][ENL_UID]
       if self._uid == None:
            self._uid = f"{self._host}-{self._eojgc}-{self._eojcc}-{self._eojci}"
          
    @Throttle(MIN_TIME_BETWEEN_UPDATES)   
    async def async_update(self, **kwargs):
        update_data = await self._instance.update(self._update_flags)
        if False not in list(update_data.values()):
           # polling succeded. 
           self._update_data = update_data
        else:
           _LOGGER.debug(f"polling ECHONET Generic Instance host {self._host} failed - data not updated {self._update_data}")
           _LOGGER.debug(f"message list - {len(self._api._message_list)}")
        return self._update_data
    