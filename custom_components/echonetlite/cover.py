import logging
import math
import asyncio

from typing import Any
from .const import DOMAIN, CONF_FORCE_POLLING

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntity,
    CoverEntityFeature,
)

from pychonet.lib.eojx import EOJX_CLASS
from pychonet.ElectricBlind import ENL_OPENSTATE

from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

ENL_OPENCLOSE_STATUS = 0xEA
ENL_OPENING_LEVEL = 0xE1
ENL_BLIND_ANGLE = 0xE2
TILT_RANGE = (1, 180)
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        if entity['instance']['eojgc'] == 0x02 and entity['instance']['eojcc'] in (0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66):
            # 0x60: "Electrically operated blind/shade"
            # 0x61: "Electrically operated shutter"
            # 0x62: "Electrically operated curtain"
            # 0x63: "Electrically operated rain sliding door/shutter"
            # 0x64: "Electrically operated gate"
            # 0x65: "Electrically operated window"
            # 0x66: "Automatically operated entrance door/sliding door"
            name = f"{config_entry.title} {entity['instance']['eojci']}"
            entities.append(EchonetCover(name, entity['echonetlite']))
    async_add_devices(entities, True)


class EchonetCover(CoverEntity):
    """Representation of an ECHONETLite climate device."""

    def __init__(self, name, connector):
        """Initialize the cover device."""
        self._name = name
        self._device_name = name
        self._connector = connector  # new line
        self._uid = self._connector._uidi if self._connector._uidi else self._connector._uid
        self._attr_is_closed = False
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]
        self._olddata = {}
        self._should_poll = True
        self._support_flags = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.STOP
        )

        if ENL_BLIND_ANGLE in self._connector._update_data:
            self._support_flags |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                # not supported individually (just global STOP)
                #| CoverEntityFeature.STOP_TILT
                | CoverEntityFeature.SET_TILT_POSITION
            )

        self.update_attr()
        self.update_option_listener()

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._connector._instance.setMessage(ENL_OPENSTATE, 0x42)
        self._connector._update_data[ENL_OPENSTATE] = "close"
        self._attr_is_opening = False
        self._attr_is_closing = True

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._connector._instance.setMessage(ENL_OPENSTATE, 0x41)
        self._connector._update_data[ENL_OPENSTATE] = "open"
        self._attr_is_closing = False
        self._attr_is_opening = True

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._connector._instance.setMessage(ENL_OPENSTATE, 0x43)
        self._connector._update_data[ENL_OPENSTATE] = "stop"
        self._attr_is_opening = False
        self._attr_is_closing = False
        await self._connector.async_update()
        self.update_attr()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        desired_position = kwargs[ATTR_POSITION]
        current_position = self._attr_current_cover_position
        await self._connector._instance.setMessage(ENL_OPENING_LEVEL, desired_position)
        self._connector._update_data[ENL_OPENING_LEVEL] = hex(desired_position)
        self._attr_is_opening = desired_position > current_position
        self._attr_is_closing = desired_position < current_position

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        await self._connector._instance.setMessage(ENL_BLIND_ANGLE, 0)
        self._connector._update_data[ENL_BLIND_ANGLE] = hex(0)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        await self._connector._instance.setMessage(ENL_BLIND_ANGLE, 180)
        self._connector._update_data[ENL_BLIND_ANGLE] = hex(180)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        tilt = math.ceil(percentage_to_ranged_value(TILT_RANGE, kwargs[ATTR_TILT_POSITION]))
        await self._connector._instance.setMessage(ENL_BLIND_ANGLE, tilt)
        self._connector._update_data[ENL_BLIND_ANGLE] = hex(tilt)

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the roller blind.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return int(self._connector._update_data[ENL_OPENING_LEVEL], 16)

    async def async_update(self):
        await self._connector.async_update()

    def update_attr(self):
        self._attr_current_cover_position = int(self._connector._update_data[ENL_OPENING_LEVEL], 16)
        self._attr_is_closed = self._attr_current_cover_position == 0
        if ENL_OPENCLOSE_STATUS in self._connector._update_data:
            self._attr_is_opening = int(self._connector._update_data[ENL_OPENCLOSE_STATUS], 16) == 0x43
            self._attr_is_closing = int(self._connector._update_data[ENL_OPENCLOSE_STATUS], 16) == 0x44
        else:
            self._attr_is_opening = self._connector._update_data[ENL_OPENSTATE] == "open"
            self._attr_is_closing = self._connector._update_data[ENL_OPENSTATE] == "close"
        if ENL_BLIND_ANGLE in self._connector._update_data:
            self._attr_current_cover_tilt_position = ranged_value_to_percentage(TILT_RANGE, int(self._connector._update_data[ENL_BLIND_ANGLE], 16))

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._uid

    @property
    def device_info(self):
        return {
            "identifiers": {(
                DOMAIN, self._connector._uid,
                self._connector._instance._eojgc,
                self._connector._instance._eojcc,
                self._connector._instance._eojci
            )},
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._instance._eojgc][self._connector._instance._eojcc]
            # "sw_version": "",
        }

    @property
    def should_poll(self):
        """Return the polling state."""
        return self._should_poll

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush = False):
        changed = (
            self._olddata != self._connector._update_data
        ) or self._attr_available != self._server_state["available"]
        if changed:
            self._olddata = self._connector._update_data.copy()
            self.update_attr()
            if self._attr_available != self._server_state["available"]:
                if self._server_state["available"]:
                    self.update_option_listener()
                else:
                    self._attr_should_poll = True
            self._attr_available = self._server_state["available"]
            self.async_schedule_update_ha_state()

    def update_option_listener(self):
        self._should_poll = True
        _LOGGER.info(f"{self._device_name}: _should_poll is {self._should_poll}")
