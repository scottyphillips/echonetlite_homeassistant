"""Support for ECHONETLite fans."""

import logging

from pychonet.HomeAirCleaner import FAN_SPEED
from pychonet.lib.const import ENL_STATUS

from pychonet.lib.eojx import EOJX_CLASS
from pychonet.CeilingFan import (
    ENL_FANSPEED_PERCENT,
    ENL_FAN_DIRECTION,
    ENL_FAN_OSCILLATION,
)
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import PRECISION_WHOLE
from .base_entity import EchonetEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_device_name
from .const import (
    DATA_STATE_ON,
    DOMAIN,
    ENL_FANSPEED,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_FAN_MODES = list(
    FAN_SPEED.keys()
)  # ["auto","minimum","low","medium-low","medium","medium-high","high","very-high","max"]


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        if entity["instance"]["eojgc"] == 0x01 and (
            entity["instance"]["eojcc"] == 0x35
            or entity["instance"]["eojcc"]
            == 0x30  # Temporary added back in for testing on my air conditioner which has 0x30 class code - remove when testing is done
            or entity["instance"]["eojcc"] == 0x3A
        ):  # Home Air Cleaner or Ceiling Fan
            _LOGGER.debug(f"Configuring ECHONETLite fan {entity}")
            entities.append(EchonetFan(entity["echonetlite"], config_entry))
    async_add_devices(entities, True)


class EchonetFan(EchonetEntity, FanEntity):
    """Representation of an ECHONETLite Fan device (eg Air purifier)."""

    def __init__(self, coordinator, config) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator, config)

        name = get_device_name(coordinator, config)
        self._attr_name = name
        self._device_name = name

        # Use uidi if available for unique_id, otherwise fall back to uid
        self._attr_unique_id = (
            coordinator._uidi if coordinator._uidi else coordinator._uid
        )

        # Set supported features based on device capabilities
        self._attr_supported_features = FanEntityFeature(0)
        if hasattr(FanEntityFeature, "TURN_ON"):  # v2024.8
            self._attr_supported_features |= FanEntityFeature.TURN_ON
        if hasattr(FanEntityFeature, "TURN_OFF"):
            self._attr_supported_features |= FanEntityFeature.TURN_OFF
        if ENL_FANSPEED in list(coordinator._setPropertyMap):
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE
        if ENL_FANSPEED_PERCENT in list(coordinator._setPropertyMap):
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
        if ENL_FAN_DIRECTION in list(coordinator._setPropertyMap):
            self._attr_supported_features |= FanEntityFeature.DIRECTION
        if ENL_FAN_OSCILLATION in list(coordinator._setPropertyMap):
            self._attr_supported_features |= FanEntityFeature.OSCILLATE

        # Set speed count for the fan
        self._attr_speed_count = getattr(coordinator._instance, "SPEED_COUNT", 100)

    @property
    def device_info(self):
        """Return device information for this entity."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    self.coordinator._uid,
                    self.coordinator._eojgc,
                    self.coordinator._eojcc,
                    self.coordinator._eojci,
                )
            },
            "name": self._device_name,
            "manufacturer": self.coordinator._manufacturer
            + (
                f" {self.coordinator._host_product_code}"
                if self.coordinator._host_product_code
                else ""
            ),
            "model": EOJX_CLASS[self.coordinator._eojgc][self.coordinator._eojcc],
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the device is on."""
        return True if self.coordinator.data.get(ENL_STATUS) == DATA_STATE_ON else False

    @property
    def preset_mode(self) -> str | None:
        """Return the fan setting."""
        return self.coordinator.data.get(ENL_FANSPEED)

    @property
    def percentage(self) -> int | None:
        """Return the fan speed percentage."""
        return self.coordinator.data.get(ENL_FANSPEED_PERCENT)

    @property
    def current_direction(self) -> str | None:
        """Return the fan direction."""
        return self.coordinator.data.get(ENL_FAN_DIRECTION)

    @property
    def oscillating(self) -> bool | None:
        """Return true if the fan is oscillating."""
        return self.coordinator.data.get(ENL_FAN_OSCILLATION)

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        if (
            ENL_FANSPEED in list(self.coordinator._user_options.keys())
            and self.coordinator._user_options[ENL_FANSPEED] is not False
        ):
            return self.coordinator._user_options[ENL_FANSPEED]
        return DEFAULT_FAN_MODES

    async def async_set_direction(self, direction: str) -> None:
        """Set the fan direction."""
        await self.coordinator._instance.setFanDirection(direction)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        await self.coordinator._instance.on()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        await self.coordinator._instance.off()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set the fan oscillation state."""
        await self.coordinator._instance.setFanOscillation(oscillating)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        await self.coordinator._instance.setFanSpeedPercent(percentage)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new fan mode."""
        await self.coordinator._instance.setFanSpeed(preset_mode)
