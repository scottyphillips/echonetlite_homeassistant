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


class EchonetCover(CoverEntity):
    """Representation of an ECHONETLite climate device."""

    def __init__(self, connector, config):
        """Initialize the cover device."""
        name = get_device_name(connector, config)
        self._attr_name = name
        self._device_name = name
        self._connector = connector  # new line
        self._attr_unique_id = (
            self._connector._uidi if self._connector._uidi else self._connector._uid
        )
        self._attr_is_closed = False
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]
        self._olddata = {}
        self._attr_should_poll = True
        self._support_flags = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        if ENL_OPENING_LEVEL in list(self._connector._setPropertyMap):
            self._support_flags |= CoverEntityFeature.SET_POSITION

        if ENL_BLIND_ANGLE in list(self._connector._setPropertyMap):
            self._support_flags |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                # not supported individually (just global STOP)
                # | CoverEntityFeature.STOP_TILT
                | CoverEntityFeature.SET_TILT_POSITION
            )

        self._attr_current_cover_position = None
        self._attr_current_cover_tilt_position = None
        self._attr_is_opening = False
        self._attr_is_closing = False
        self.update_attr()
        self.update_option_listener()

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._connector._instance.setMessage(ENL_OPENSTATE, 0x42)
        self._connector._update_data[ENL_OPENSTATE] = DATA_STATE_CLOSE
        if ENL_OPENCLOSE_STATUS in self._connector._update_data:
            self._attr_is_opening = False
            self._attr_is_closing = True

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._connector._instance.setMessage(ENL_OPENSTATE, 0x41)
        self._connector._update_data[ENL_OPENSTATE] = DATA_STATE_OPEN
        if ENL_OPENCLOSE_STATUS in self._connector._update_data:
            self._attr_is_opening = True
            self._attr_is_closing = False

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._connector._instance.setMessage(ENL_OPENSTATE, 0x43)
        self._connector._update_data[ENL_OPENSTATE] = DATA_STATE_STOP
        self._attr_is_opening = False
        self._attr_is_closing = False
        await self._connector.async_update()
        self.update_attr()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        desired_position = kwargs[ATTR_POSITION]
        current_position = self._attr_current_cover_position
        await self._connector._instance.setMessage(ENL_OPENING_LEVEL, desired_position)
        self._connector._update_data[ENL_OPENING_LEVEL] = int(desired_position)
        self._attr_is_opening = desired_position > current_position
        self._attr_is_closing = desired_position < current_position

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        await self._connector._instance.setMessage(ENL_BLIND_ANGLE, 0)
        self._connector._update_data[ENL_BLIND_ANGLE] = 0

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        await self._connector._instance.setMessage(ENL_BLIND_ANGLE, 180)
        self._connector._update_data[ENL_BLIND_ANGLE] = 180

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        tilt = math.ceil(
            percentage_to_ranged_value(TILT_RANGE, kwargs[ATTR_TILT_POSITION])
        )
        await self._connector._instance.setMessage(ENL_BLIND_ANGLE, tilt)
        self._connector._update_data[ENL_BLIND_ANGLE] = int(tilt)

    async def async_update(self):
        await self._connector.async_update()

    def update_attr(self):
        if (
            ENL_OPENING_LEVEL in self._connector._update_data
            and self._connector._update_data[ENL_OPENING_LEVEL] != None
        ):
            self._attr_current_cover_position = int(
                self._connector._update_data[ENL_OPENING_LEVEL]
            )
            self._attr_is_closed = self._attr_current_cover_position == 0
        else:
            self._attr_is_closed = (
                self._connector._update_data[ENL_OPENSTATE] == DATA_STATE_CLOSE
            )
        if ENL_OPENCLOSE_STATUS in self._connector._update_data:
            self._attr_is_opening = (
                self._connector._update_data[ENL_OPENCLOSE_STATUS] == DATA_STATE_OPENING
            )
            self._attr_is_closing = (
                self._connector._update_data[ENL_OPENCLOSE_STATUS] == DATA_STATE_CLOSING
            )
        if (
            ENL_BLIND_ANGLE in self._connector._update_data
            and self._connector._update_data[ENL_BLIND_ANGLE] != None
        ):
            self._attr_current_cover_tilt_position = ranged_value_to_percentage(
                TILT_RANGE, int(self._connector._update_data[ENL_BLIND_ANGLE])
            )

    @property
    def device_info(self):
        return {
            "identifiers": {
                (
                    DOMAIN,
                    self._connector._uid,
                    self._connector._instance._eojgc,
                    self._connector._instance._eojcc,
                    self._connector._instance._eojci,
                )
            },
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer
            + (
                " " + self._connector._host_product_code
                if self._connector._host_product_code
                else ""
            ),
            "model": EOJX_CLASS[self._connector._instance._eojgc][
                self._connector._instance._eojcc
            ],
            # "sw_version": "",
        }

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush=False):
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
        _LOGGER.info(f"{self._device_name}: _should_poll is {self._attr_should_poll}")
