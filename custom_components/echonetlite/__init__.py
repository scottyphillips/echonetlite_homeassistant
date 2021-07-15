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

PLATFORMS = ["sensor"]
PARALLEL_UPDATES = 0
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    echonetlite = EchonetAPIConnector(entry.data["host"])
    for instance in entry.data["instances"]:
        if instance['eojgc'] == 1 and instance['eojcc'] == 48:
            PLATFORMS.append("climate")
            PLATFORMS.append("select")
    hass.data.setdefault(DOMAIN, {}).update({entry.entry_id: echonetlite})
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

class EchonetAPIConnector():
    def __init__(self, host):
       self._update_data = {'status': 'Off'}
       self._api = echonet.HomeAirConditioner(host)
       self._update_data = self._api.update()
       self._uid = self._api.getIdentificationNumber()["identification_number"]
       
    @Throttle(MIN_TIME_BETWEEN_UPDATES)   
    async def async_update(self, **kwargs):
        _LOGGER.warning("Commence polling ECHONET Instance")
        self._update_data = self._api.update()
        _LOGGER.warning("polling ECHONET Instance complete")
        return self._update_data
    