import logging
import math
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from pychonet.lib.epc_functions import (
    DATA_STATE_CLOSE,
    DATA_STATE_OPEN,
    DATA_STATE_STOP,
    DATA_STATE_OPENING,
    DATA_STATE_CLOSING,
)
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.ElectricBlind import (
    ENL_BLIND_ANGLE,
    ENL_OPENCLOSE_STATUS,
    ENL_OPENING_LEVEL,
    ENL_OPENSTATE,
)

from . import get_device_name
from .const import DOMAIN

TILT_RANGE = (1, 180)
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_devices):
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        # Filter for cover-class devices (0x02, 0x60-0x66)
        if entity["instance"]["eojgc"] == 0x02 and 0x60 <= entity["instance"]["eojcc"] <= 0x66:
            entities.append(EchonetCover(entity["echonetlite"], config_entry))
    async_add_devices(entities, True)

class EchonetCover(CoordinatorEntity, CoverEntity):
    """Representation of an ECHONETLite cover device."""

    def __init__(self, connector, config):
        """Initialize the cover device."""
        super().__init__(connector)
        name = get_device_name(connector, config)
        self._attr_name = name
        self._device_name = name
        self._connector = connector
        self._attr_unique_id = self._connector._uidi if self._connector._uidi else self._connector._uid
        
        # Supported Features
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        if ENL_OPENING_LEVEL in self._connector._setPropertyMap:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION
        if ENL_BLIND_ANGLE in self._connector._setPropertyMap:
            self._attr_supported_features |= (
                CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT | CoverEntityFeature.SET_TILT_POSITION
            )

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if ENL_OPENING_LEVEL in self._connector._update_data:
            pos = self._connector._update_data.get(ENL_OPENING_LEVEL)
            return pos == 0 if pos is not None else None
        return self._connector._update_data.get(ENL_OPENSTATE) == DATA_STATE_CLOSE

    @property
    def current_cover_position(self):
        """Return current position of cover. 0 is closed, 100 is open."""
        return self._connector._update_data.get(ENL_OPENING_LEVEL)

    @property
    def is_opening(self):
        return self._connector._update_data.get(ENL_OPENCLOSE_STATUS) == DATA_STATE_OPENING

    @property
    def is_closing(self):
        return self._connector._update_data.get(ENL_OPENCLOSE_STATUS) == DATA_STATE_CLOSING

    @property
    def current_cover_tilt_position(self):
        """Return current tilt position of cover."""
        raw_tilt = self._connector._update_data.get(ENL_BLIND_ANGLE)
        if raw_tilt is not None:
            return ranged_value_to_percentage(TILT_RANGE, int(raw_tilt))
        return None

    async def async_close_cover(self, **kwargs: Any) -> None:
        if await self._connector._instance.setMessage(ENL_OPENSTATE, 0x42):
            self._connector._update_data[ENL_OPENSTATE] = DATA_STATE_CLOSE
            self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        if await self._connector._instance.setMessage(ENL_OPENSTATE, 0x41):
            self._connector._update_data[ENL_OPENSTATE] = DATA_STATE_OPEN
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        if await self._connector._instance.setMessage(ENL_OPENSTATE, 0x43):
            self._connector._update_data[ENL_OPENSTATE] = DATA_STATE_STOP
            self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        pos = kwargs[ATTR_POSITION]
        if await self._connector._instance.setMessage(ENL_OPENING_LEVEL, pos):
            self._connector._update_data[ENL_OPENING_LEVEL] = pos
            self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        tilt = math.ceil(percentage_to_ranged_value(TILT_RANGE, kwargs[ATTR_TILT_POSITION]))
        if await self._connector._instance.setMessage(ENL_BLIND_ANGLE, tilt):
            self._connector._update_data[ENL_BLIND_ANGLE] = tilt
            self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._connector._uid, self._connector._instance._eojgc, 
                             self._connector._instance._eojcc, self._connector._instance._eojci)},
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._instance._eojgc][self._connector._instance._eojcc],
        }