import logging

from pychonet.EchonetInstance import ENL_GETMAP
from pychonet.lib.eojx import EOJX_CLASS
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import (
    PRECISION_WHOLE,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ENL_FANSPEED = 0xA0
ENL_FANSPEED_PERCENT = 0xF0
ENL_FAN_DIRECTION = 0xF1
ENL_FAN_OSCILLATION = 0xF2

SUPPORT_FLAGS = 0

DEFAULT_FAN_MODES = [
    "auto",
    "minimum",
    "low",
    "medium-low",
    "medium",
    "medium-high",
    "high",
    "very-high",
    "max",
]


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
        self._name = name
        self._device_name = name
        self._connector = connector  # new line
        self._uid = (
            self._connector._uidi if self._connector._uidi else self._connector._uid
        )
        self._precision = 1.0
        self._target_temperature_step = 1
        self._support_flags = SUPPORT_FLAGS
        if ENL_FANSPEED in list(self._connector._setPropertyMap):
            self._support_flags = self._support_flags | FanEntityFeature.PRESET_MODE
        if ENL_FANSPEED_PERCENT in list(self._connector._setPropertyMap):
            self._support_flags = self._support_flags | FanEntityFeature.SET_SPEED
        if ENL_FAN_DIRECTION in list(self._connector._setPropertyMap):
            self._support_flags = self._support_flags | FanEntityFeature.DIRECTION
        if ENL_FAN_OSCILLATION in list(self._connector._setPropertyMap):
            self._support_flags = self._support_flags | FanEntityFeature.OSCILLATE
        self._olddata = {}
        self._should_poll = True

    async def async_update(self):
        try:
            await self._connector.async_update()
        except TimeoutError:
            pass

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def precision(self) -> float:
        return PRECISION_WHOLE

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._uid

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
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._instance._eojgc][
                self._connector._instance._eojcc
            ]
            # "sw_version": "",
        }

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def is_on(self):
        """Return true if the device is on."""
        return True if self._connector._update_data[0x80] == "On" else False

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ):
        """Turn on."""
        await self._connector._instance.on()

    async def async_turn_off(self):
        """Turn off."""
        await self._connector._instance.off()

    @property
    def preset_mode(self):
        """Return the fan setting."""
        return (
            self._connector._update_data[ENL_FANSPEED]
            if ENL_FANSPEED in self._connector._update_data
            else "unavailable"
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        await self._connector._instance.setFanSpeedPercent(percentage)
        self._connector._update_data[ENL_FANSPEED_PERCENT] = percentage

    @property
    def percentage(self):
        """Return the fan setting."""
        return (
            self._connector._update_data[ENL_FANSPEED_PERCENT]
            if ENL_FANSPEED_PERCENT in self._connector._update_data
            else "unavailable"
        )

    @property
    def direction(self):
        """Return the fan direction."""
        return (
            self._connector._update_data[ENL_FAN_DIRECTION]
            if ENL_FAN_DIRECTION in self._connector._update_data
            else "unavailable"
        )

    async def async_set_direction(self, direction: str) -> None:
        await self._connector._instance.setFanDirection(direction)
        self._connector._update_data[ENL_FAN_DIRECTION] = direction

    @property
    def oscillating(self):
        """Return the fan oscillating."""
        return (
            self._connector._update_data[ENL_FAN_OSCILLATION]
            if ENL_FAN_OSCILLATION in self._connector._update_data
            else "unavailable"
        )

    async def async_oscillate(self, oscillating: bool) -> None:
        await self._connector._instance.setFanOscillation(oscillating)

    @property
    def preset_modes(self):
        """Return the list of available fan modes."""
        if ENL_FANSPEED in list(self._connector._user_options.keys()):
            if self._connector._user_options[ENL_FANSPEED] is not False:
                return self._connector._user_options[ENL_FANSPEED]
        return DEFAULT_FAN_MODES

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new fan mode."""
        await self._connector._instance.setFanSpeed(preset_mode)
        self._connector._update_data[ENL_FANSPEED] = preset_mode

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush=False):
        changed = self._olddata != self._connector._update_data
        if changed:
            self._olddata = self._connector._update_data.copy()
            self.async_schedule_update_ha_state()
            if isPush:
                try:
                    await self._connector.async_update()
                except TimeoutError:
                    pass
