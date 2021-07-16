"""The echonetlite integration."""
from __future__ import annotations
import logging
import pychonet as echonet
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
    for instance in entry.data["instances"]:
        # if ECHONETLite instance is HomeAirConditioner enable climate platform
        echonetlite = None
        if instance['eojgc'] == 1 and instance['eojcc'] == 48:
            echonetlite = EchonetHVACAPIConnector(entry.data["host"])
        hass.data[DOMAIN][entry.entry_id].append({"instance_data": instance, "API":echonetlite})
    # _LOGGER.debug(hass.data[DOMAIN])
    # _LOGGER.debug("does config data get smushed? %s", entry.data["instances"])
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

"""EchonetAPIConnector is used to centralise API calls per platform
   At some stage this will need to be refactored or extended to use the generic EchonetInstance class"""
class EchonetHVACAPIConnector():
    def __init__(self, host):
       self._update_flags = [0x80, 0xB3, 0xA0, 0xA1, 0xA3, 0xA4, 0xA5, 0xB0, 0xBB, 0xBE] # outdoor temperature
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
        _LOGGER.debug("Commence polling ECHONET Instance")
        self._update_data = self._api.update(self._update_flags)
        _LOGGER.debug(f"polling ECHONET Instance complete - {self._update_data}")
        return self._update_data
