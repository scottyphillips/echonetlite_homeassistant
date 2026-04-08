"""Support for ECHONETLite Fan."""

import logging

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from pychonet.lib.eojx import EOJX_CLASS
from . import get_device_name
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the ECHONETLite fan platform."""
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]

        # Check if this device is a fan (EPC 0x81 - ON/OFF, 0x83 - Speed)
        _enl_op_codes = entity["echonetlite"]._enl_op_codes
        
        has_fan_support = any(
            code in entity["instance"]["setmap"] for code in [0x80, 0x81, 0x83]
        )

        if has_fan_support:
            entities.append(
                EchonetFan(
                    entity["echonetlite"],
                    config,
                    _enl_op_codes,
                    hass,
                )
            )

    async_add_entities(entities, True)


class EchonetFan(CoordinatorEntity, FanEntity):
    """Representation of an ECHONETLite Fan."""

    _attr_translation_key = DOMAIN
    coordinator: DataUpdateCoordinator | None

    def __init__(self, connector, config, enl_op_codes, hass=None) -> None:
        """Initialize the fan entity."""
        super().__init__(connector.coordinator) if connector.coordinator else None
        
        self._connector = connector
        self._config = config
        self._enl_op_codes = enl_op_codes
        self._device_name = get_device_name(connector, config)

        self._attr_unique_id = (
            f"{self._connector._uidi}" if self._connector._uidi else self._connector._uid
        )
        self._attr_name = self._device_name
        
        # Fan supports speed control via EPC 0x83
        self._attr_supported_features = (
            FanEntity.SET_SPEED | FanEntity.OMNI_DIRECTIONAL
        )
        
        # Fan speeds - typically 1-5 or 1-6 in ECHONET
        _fan_speeds = ["low", "medium_low", "medium", "medium_high", "high"]
        self._attr_percentage_steps = len(_fan_speeds) + 1
        self._attr_speed_count = 3
        
        # Initialize state from connector data
        self._is_on = False
        self._percentage = None
        
        update_data = getattr(self.coordinator, 'data', None) or getattr(connector, '_update_data', {})
        
        if 0x81 in update_data:
            self._is_on = (update_data[0x81] != 0x02)  # Not OFF
        if 0x83 in update_data:
            # EPC 0x83: Fan speed - typically 1-5 or similar scale
            speed_value = int(update_data[0x83])
            self._percentage = min(max(speed_value * 20, 20), 100)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._connector._uid)},
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._eojgc][self._connector._eojcc],
        }

    @property
    def is_on(self):
        """Return if the fan is on."""
        return self._is_on

    @property
    def percentage(self):
        """Return the current speed percentage."""
        return self._percentage

    @property
    def oscillating(self):
        """Return if the fan is oscillating."""
        # Check EPC 0x94 (oscillation) if available
        update_data = getattr(self.coordinator, 'data', None) or getattr(self._connector, '_update_data', {})
        return bool(update_data.get(0x94)) if update_data else False

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        # Check for turbo/sleep modes (EPC 0x3A or similar)
        update_data = getattr(self.coordinator, 'data', None) or getattr(self._connector, '_update_data', {})
        if self.coordinator and 0x3A in self.coordinator.data:
            epc_3a = self.coordinator.data[0x3A]
            if epc_3a == 0xC1:
                return "sleep"
            elif epc_3a == 0xD1:
                return "turbo"
        return None

    async def async_turn_on(self, percentage: int = None, **kwargs) -> None:
        """Turn the fan on."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
        
        # Turn on (EPC 0x81 = 0x01 for operation start)
        await self._connector._instance.setMessage(0x81, 0x01)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        # Turn off (EPC 0x81 = 0x02 for stop)
        await self._connector._instance.setMessage(0x81, 0x02)
        self._is_on = False
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs) -> None:
        """Toggle the fan."""
        if self.is_on:
            await self.async_turn_off(**kwargs)
        else:
            await self.async_turn_on(**kwargs)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        # Convert HA percentage (0-100) to ECHONET scale
        epc_value = max(1, round(percentage / 20))
        await self._connector._instance.setMessage(0x83, epc_value)
        self._percentage = percentage
        self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation of the fan."""
        # EPC 0x94 controls horizontal swing/oscillation
        await self._connector._instance.setMessage(0x94, 0x01 if oscillating else 0x02)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        # EPC 0x3A for special modes
        mode_map = {
            "turbo": 0xD1,
            "sleep": 0xC1,
        }
        
        if preset_mode in mode_map:
            await self._connector._instance.setMessage(0x3A, mode_map[preset_mode])

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush: bool = False):
        """Handle coordinator updates."""
        if self.coordinator and not self.coordinator.last_update_success:
            return
            
        update_data = self.coordinator.data
        
        if 0x81 in update_data:
            # EPC 0x81: Operation status - 0x01=ON, 0x02=OFF
            self._is_on = (update_data[0x81] != 0x02)
        
        if 0x83 in update_data:
            # EPC 0x83: Fan speed
            speed_value = int(update_data[0x83])
            self._percentage = min(max(speed_value * 20, 20), 100)

        self.async_write_ha_state()

    def update_option_listener(self):
        """Update listener for option changes."""
        pass