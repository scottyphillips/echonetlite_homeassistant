import logging
from pychonet.HomeAirCleaner import FAN_SPEED
from pychonet.lib.const import ENL_STATUS

from pychonet.lib.eojx import EOJX_CLASS
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import (
    PRECISION_WHOLE,
)
from .const import CONF_FORCE_POLLING, DATA_STATE_ON, DOMAIN

_LOGGER = logging.getLogger(__name__)

ENL_FANSPEED = 0xA0
ENL_FANSPEED_PERCENT = 0xF0
ENL_FAN_DIRECTION = 0xF1
ENL_FAN_OSCILLATION = 0xF2

DEFAULT_FAN_MODES = list(
    FAN_SPEED.keys()
)  # ["auto","minimum","low","medium-low","medium","medium-high","high","very-high","max"]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        if entity["instance"]["eojgc"] == 0x01 and (
            entity["instance"]["eojcc"] == 0x35 or entity["instance"]["eojcc"] == 0x3A
        ):  # Home Air Cleaner or Celing Fan
            entities.append(EchonetFan(config_entry.title, entity["echonetlite"]))
    async_add_devices(entities, True)


class EchonetFan(FanEntity):
    """Representation of an ECHONETLite Fan device (eg Air purifier)."""

    def __init__(self, name, connector):
        """Initialize the climate device."""
        self._attr_name = name
        self._device_name = name
        self._connector = connector  # new line
        self._attr_unique_id = (
            self._connector._uidi if self._connector._uidi else self._connector._uid
        )
        self._precision = 1.0
        self._target_temperature_step = 1
        self._attr_support_flags = FanEntityFeature(0)
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]
        if ENL_FANSPEED in list(self._connector._setPropertyMap):
            self._attr_support_flags = (
                self._attr_support_flags | FanEntityFeature.PRESET_MODE
            )
        if ENL_FANSPEED_PERCENT in list(self._connector._setPropertyMap):
            self._attr_support_flags = (
                self._attr_support_flags | FanEntityFeature.SET_SPEED
            )
        if ENL_FAN_DIRECTION in list(self._connector._setPropertyMap):
            self._attr_support_flags = (
                self._attr_support_flags | FanEntityFeature.DIRECTION
            )
        if ENL_FAN_OSCILLATION in list(self._connector._setPropertyMap):
            self._attr_support_flags = (
                self._attr_support_flags | FanEntityFeature.OSCILLATE
            )
        self._olddata = {}

        self._attr_should_poll = True
        self._attr_available = True

        self._set_attrs()
        self.update_option_listener()

    async def async_update(self):
        try:
            await self._connector.async_update()
        except TimeoutError:
            pass

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

    @property
    def precision(self) -> float:
        return PRECISION_WHOLE

    @property
    def is_on(self):
        """Return true if the device is on."""
        return True if self._connector._update_data[0x80] == DATA_STATE_ON else False

    def _set_attrs(self):
        # @property
        # def preset_mode(self):
        """Return the fan setting."""
        self._attr_preset_mode = (
            self._connector._update_data[ENL_FANSPEED]
            if ENL_FANSPEED in self._connector._update_data
            else None
        )

        # @property
        # def percentage(self):
        """Return the fan setting."""
        self._attr_percentage = (
            self._connector._update_data[ENL_FANSPEED_PERCENT]
            if ENL_FANSPEED_PERCENT in self._connector._update_data
            else None
        )

        # @property
        # def current_direction(self):
        """Return the fan direction."""
        self._attr_current_direction = (
            self._connector._update_data[ENL_FAN_DIRECTION]
            if ENL_FAN_DIRECTION in self._connector._update_data
            else None
        )

        # @property
        # def oscillating(self):
        """Return the fan oscillating."""
        self._attr_oscillating = (
            self._connector._update_data[ENL_FAN_OSCILLATION]
            if ENL_FAN_OSCILLATION in self._connector._update_data
            else None
        )

        # @property
        # def preset_modes(self):
        """Return the list of available fan modes."""
        if (
            ENL_FANSPEED in list(self._connector._user_options.keys())
            and self._connector._user_options[ENL_FANSPEED] is not False
        ):
            self._attr_preset_modes = self._connector._user_options[ENL_FANSPEED]
        else:
            self._attr_preset_modes = DEFAULT_FAN_MODES

    async def async_set_direction(self, direction: str) -> None:
        await self._connector._instance.setFanDirection(direction)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn on."""
        await self._connector._instance.on()

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        await self._connector._instance.off()

    async def async_oscillate(self, oscillating: bool) -> None:
        await self._connector._instance.setFanOscillation(oscillating)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        await self._connector._instance.setFanSpeedPercent(percentage)

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new fan mode."""
        await self._connector._instance.setFanSpeed(preset_mode)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.register_async_update_callbacks(self.async_update_callback)
        self._connector.add_update_option_listener(self.update_option_listener)

    async def async_update_callback(self, isPush: bool = False):
        changed = (
            self._olddata != self._connector._update_data
            or self._attr_available != self._server_state["available"]
        )
        if changed:
            _force = bool(not self._attr_available and self._server_state["available"])
            self._olddata = self._connector._update_data.copy()
            self._attr_available = self._server_state["available"]
            self._set_attrs()
            self.async_schedule_update_ha_state(_force | isPush)

    def update_option_listener(self):
        _should_poll = (
            ENL_STATUS not in self._connector._ntfPropertyMap
            or (
                FanEntityFeature.PRESET_MODE in self._attr_support_flags
                and ENL_FANSPEED not in self._connector._ntfPropertyMap
            )
            or (
                FanEntityFeature.SET_SPEED in self._attr_support_flags
                and ENL_FANSPEED_PERCENT not in self._connector._ntfPropertyMap
            )
            or (
                FanEntityFeature.DIRECTION in self._attr_support_flags
                and ENL_FAN_DIRECTION not in self._connector._ntfPropertyMap
            )
            or (
                FanEntityFeature.OSCILLATE in self._attr_support_flags
                and ENL_FAN_OSCILLATION not in self._connector._ntfPropertyMap
            )
        )
        self._attr_should_poll = (
            self._connector._user_options.get(CONF_FORCE_POLLING, False) or _should_poll
        )
        self._attr_extra_state_attributes = {"notify": "No" if _should_poll else "Yes"}
        _LOGGER.debug(f"{self._attr_name}: _should_poll is {_should_poll}")
