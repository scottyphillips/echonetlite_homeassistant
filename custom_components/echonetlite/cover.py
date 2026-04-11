"""Support for ECHONETLite covers."""

import logging
import math

from typing import Any

from pychonet.lib.epc_functions import (
    DATA_STATE_CLOSE,
    DATA_STATE_OPEN,
    DATA_STATE_STOP,
    DATA_STATE_OPENING,
    DATA_STATE_CLOSING,
)
from . import get_device_name
from .const import DOMAIN

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from .base_entity import EchonetEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pychonet.lib.eojx import EOJX_CLASS
from pychonet.ElectricBlind import (
    ENL_BLIND_ANGLE,
    ENL_OPENCLOSE_STATUS,
    ENL_OPENING_LEVEL,
    ENL_OPENSTATE,
)

from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

TILT_RANGE = (1, 180)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        if entity["instance"]["eojgc"] == 0x02 and entity["instance"]["eojcc"] in (
            0x60,
            0x61,
            0x62,
            0x63,
            0x64,
            0x65,
            0x66,
        ):
            # 0x60: "Electrically operated blind/shade"
            # 0x61: "Electrically operated shutter"
            # 0x62: "Electrically operated curtain"
            # 0x63: "Electrically operated rain sliding door/shutter"
            # 0x64: "Electrically operated gate"
            # 0x65: "Electrically operated window"
            # 0x66: "Automatically operated entrance door/sliding door"
            entities.append(EchonetCover(entity["echonetlite"], config_entry))
    async_add_devices(entities, True)


class EchonetCover(EchonetEntity, CoverEntity):
    """Representation of an ECHONETLite cover device."""

    def __init__(self, coordinator, config):
        """Initialize the cover device.

        Args:
            coordinator: The ECHONETConnector instance which is also a DataUpdateCoordinator.
            config: The config entry for this integration.
        """
        super().__init__(coordinator, config)
        name = get_device_name(coordinator, config)
        self._attr_name = name
        self._device_name = name
        self._attr_unique_id = (
            self.coordinator._uidi if self.coordinator._uidi else self.coordinator._uid
        )

        self._support_flags = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        if ENL_OPENING_LEVEL in list(self.coordinator._setPropertyMap):
            self._support_flags |= CoverEntityFeature.SET_POSITION

        if ENL_BLIND_ANGLE in list(self.coordinator._setPropertyMap):
            self._support_flags |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                # not supported individually (just global STOP)
                # | CoverEntityFeature.STOP_TILT
                | CoverEntityFeature.SET_TILT_POSITION
            )

    @property
    def current_cover_position(self):
        """Return the current cover position."""
        if (
            ENL_OPENING_LEVEL in self.coordinator.data
            and self.coordinator.data[ENL_OPENING_LEVEL] is not None
        ):
            return int(self.coordinator.data[ENL_OPENING_LEVEL])
        return None

    @property
    def current_cover_tilt_position(self):
        """Return the current cover tilt position."""
        if (
            ENL_BLIND_ANGLE in self.coordinator.data
            and self.coordinator.data[ENL_BLIND_ANGLE] is not None
        ):
            return ranged_value_to_percentage(
                TILT_RANGE, int(self.coordinator.data[ENL_BLIND_ANGLE])
            )
        return None

    @property
    def is_closed(self):
        """Return true if the cover is closed."""
        position = self.current_cover_position
        if position is not None:
            return position == 0
        # Fallback to OPENSTATE if no position data available
        openstate = self.coordinator.data.get(ENL_OPENSTATE)
        return openstate == DATA_STATE_CLOSE

    @property
    def is_opening(self):
        """Return true if the cover is opening."""
        status = self.coordinator.data.get(ENL_OPENCLOSE_STATUS)
        return status == DATA_STATE_OPENING if status else False

    @property
    def is_closing(self):
        """Return true if the cover is closing."""
        status = self.coordinator.data.get(ENL_OPENCLOSE_STATUS)
        return status == DATA_STATE_CLOSING if status else False

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.coordinator._instance.setMessage(ENL_OPENSTATE, 0x42)
        self.coordinator.data[ENL_OPENSTATE] = DATA_STATE_CLOSE

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.coordinator._instance.setMessage(ENL_OPENSTATE, 0x41)
        self.coordinator.data[ENL_OPENSTATE] = DATA_STATE_OPEN

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover movement."""
        await self.coordinator._instance.setMessage(ENL_OPENSTATE, 0x43)
        self.coordinator.data[ENL_OPENSTATE] = DATA_STATE_STOP

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        desired_position = kwargs[ATTR_POSITION]
        current_position = self.current_cover_position or 0
        await self.coordinator._instance.setMessage(ENL_OPENING_LEVEL, desired_position)
        self.coordinator.data[ENL_OPENING_LEVEL] = int(desired_position)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        await self.coordinator._instance.setMessage(ENL_BLIND_ANGLE, 0)
        self.coordinator.data[ENL_BLIND_ANGLE] = 0

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self.coordinator._instance.setMessage(ENL_BLIND_ANGLE, 180)
        self.coordinator.data[ENL_BLIND_ANGLE] = 180

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the cover tilt position."""
        tilt = math.ceil(
            percentage_to_ranged_value(TILT_RANGE, kwargs[ATTR_TILT_POSITION])
        )
        await self.coordinator._instance.setMessage(ENL_BLIND_ANGLE, tilt)
        self.coordinator.data[ENL_BLIND_ANGLE] = int(tilt)
