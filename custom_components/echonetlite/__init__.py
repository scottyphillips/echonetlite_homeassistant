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

PLATFORMS = ["sensor",'climate', 'select']
PARALLEL_UPDATES = 0
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # TODO - fix this up to seletive configure API depending on entities. 
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].update({entry.entry_id: []})
    _LOGGER.debug("platform entry data - %s", entry.data)
    for instance in entry.data["instances"]:
        # if ECHONETLite instance is HomeAirConditioner enable climate platform
        echonetlite = None
        if instance['eojgc'] == 1 and instance['eojcc'] == 48:
            echonetlite = HVACConnector(entry.data["host"])
        else:
            echonetlite = ECHONETConnector(instance['eojgc'],instance['eojcc'], instance['eojci'], entry.data["host"] )
        hass.data[DOMAIN][entry.entry_id].append({"instance_data": instance, "API":echonetlite})
        
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

"""EchonetHVACAPIConnector is used to centralise API calls for climate entities"""
class HVACConnector():
    def __init__(self, host):
       self._update_flags = [0x80, 0xB3, 0xA0, 0xA1, 0xA3, 0xA4, 0xA5, 0xB0, 0xBB, 0xBE]
       self._update_data = {'status': 'Off'}
       self._api = echonet.HomeAirConditioner(host)
       self._update_data = self._api.update(self._update_flags)

       # TODO - occasional bug here if ECHONETLite node doesnt return ID. 
       try:
          self._uid = self._api.getIdentificationNumber()
       except IndexError:
          self._uid = f"{host}-{self._api.eojgc}-{self._api.eojcc}-{self._api.instance}"
          
    @Throttle(MIN_TIME_BETWEEN_UPDATES)   
    async def async_update(self, **kwargs):
        _LOGGER.debug("Commence polling ECHONET HVAC Instance")
        self._update_data = self._api.update(self._update_flags)
        _LOGGER.debug(f"polling ECHONET HVAC Instance complete - {self._update_data}")
        return self._update_data

"""EchonetAPIConnector is used to centralise API calls for generic Echonet devicess"""
class ECHONETConnector():
    def __init__(self, eojgc, eojcc, eojci, host):
       _LOGGER.debug("initialisating generic ECHONET connector %s %s %s %s", eojgc, eojcc, eojci, host)    
       self._update_data = {'status': 'Off'}
       self._api = echonet.EchonetInstance(eojgc, eojcc, eojci, host)
       _LOGGER.debug(f"what is this list giving me? {self._api.propertyMaps[0x9f].values()}")
       self._useful_attributes = list(self._api.propertyMaps[0x9f].values())
       for item in list(EPC_SUPER.keys()):
            if item in self._useful_attributes:
                self._useful_attributes.remove(item)
       self._useful_attributes.append(0x80)
       self._useful_attributes.append(0x84)
       self._useful_attributes.append(0x85)
       self._update_data = self._api.update(self._useful_attributes)

       # TODO - occasional bug here if ECHONETLite node doesnt return ID. 
       try:
          self._uid = self._api.getIdentificationNumber()
       except IndexError:
          self._uid = f"{host}-{self._api.eojgc}-{self._api.eojcc}-{self._api.instance}"
          
    @Throttle(MIN_TIME_BETWEEN_UPDATES)   
    async def async_update(self, **kwargs):
        _LOGGER.debug("Commence polling ECHONET Instance")
        self._update_data = self._api.update(self._useful_attributes)
        _LOGGER.debug(f"polling ECHONET Instance complete - {self._update_data}")
        return self._update_data
    