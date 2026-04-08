"""Support for ECHONETLite Time entities."""

import logging

from homeassistant.components.time import (
    TimeEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from pychonet.lib.eojx import EOJX_CLASS
from . import get_device_name
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the ECHONETLite time platform."""
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]

        _enl_op_codes = entity["echonetlite"]._enl_op_codes
        
        # Check if this device has time capabilities (timer settings)
        has_time_support = any(
            code in entity["instance"]["setmap"] for code in [0x91, 0x3E]
        )

        if has_time_support:
            entities.append(
                EchonetTime(
                    entity["echonetlite"],
                    config,
                    _enl_op_codes,
                    hass,
                )
            )

    async_add_entities(entities, True)


class EchonetTime(CoordinatorEntity, TimeEntity):
    """Representation of an ECHONETLite Time (e.g., timer settings)."""

    _attr_translation_key = DOMAIN
    coordinator: DataUpdateCoordinator | None

    def __init__(self, connector, config, enl_op_codes, hass=None) -> None:
        """Initialize the time entity."""
        super().__init__(connector.coordinator) if connector.coordinator else None
        
        self._connector = connector
        self._config = config
        self._enl_op_codes = enl_op_codes
        self._device_name = get_device_name(connector, config)

        # Determine the EPC code for this time entity (0x91=on timer, 0x3E=sleep timer, etc.)
        self._epc_code = 0x91  # Default to on timer
        
        self._attr_unique_id = (
            f"{self._connector._uidi}-{self._epc_code}" if self._connector._uidi 
            else f"{self._connector._uid}-{self._eojgc}-{self._eojcc}-{self._eojci}-{self._epc_code}"
        )
        self._attr_name = f"{self._device_name} {get_timer_description(self._epc_code)}"

        # Initialize state from connector data
        self._time_value = None
        
        update_data = getattr(self.coordinator, 'data', None) or getattr(connector, '_update_data', {})
        
        if self._epc_code in update_data:
            value = update_data[self._epc_code]
            # Convert from ECHONET format (HH*256 + MM) to time string "HH:MM"
            if isinstance(value, int):
                hours = value // 256
                minutes = value % 256
                self._time_value = f"{hours:02d}:{minutes:02d}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._connector._uid)},
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._eojgc][self._connector._eojcc],
        }

    @property
    def time(self):
        """Return the current time value."""
        return self._time_value

    async def async_set_time(self, value: str) -> None:
        """Set new time value."""
        # Parse "HH:MM" format to ECHONET format (HH*256 + MM)
        try:
            parts = value.split(":")
            hours = int(parts[0])
            minutes = int(parts[1])
            epc_value = hours * 256 + minutes
            
            await self._connector._instance.setMessage(self._epc_code, epc_value)
            self._time_value = value
            self.async_write_ha_state()
        except (ValueError, IndexError):
            _LOGGER.error(f"Invalid time format: {value}")

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush: bool = False):
        """Handle coordinator updates."""
        if self.coordinator and not self.coordinator.last_update_success:
            return
            
        update_data = self.coordinator.data
        
        if self._epc_code in update_data:
            value = update_data[self._epc_code]
            # Convert from ECHONET format (HH*256 + MM) to time string "HH:MM"
            if isinstance(value, int):
                hours = value // 256
                minutes = value % 256
                self._time_value = f"{hours:02d}:{minutes:02d}"

        self.async_write_ha_state()

    def update_option_listener(self):
        """Update listener for option changes."""
        pass


def get_timer_description(epc_code: int) -> str:
    """Get description for timer EPC code."""
    descriptions = {
        0x91: "On Timer",
        0x3E: "Sleep Timer",
        0x92: "Timer Setting Time",
    }
    return descriptions.get(epc_code, f"Timer {hex(epc_code)}")