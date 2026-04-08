"""Support for ECHONETLite Number entities."""

import logging

from homeassistant.components.number import (
    NumberEntity,
    NumberDeviceClass,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from pychonet.lib.eojx import EOJX_CLASS
from . import get_device_name
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the ECHONETLite number platform."""
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]

        _enl_op_codes = entity["echonetlite"]._enl_op_codes
        
        # Check if this device has number capabilities (settable numeric values)
        has_number_support = any(
            code in entity["instance"]["setmap"] for code in [0x91, 0x92, 0x93]
        )

        if has_number_support:
            entities.append(
                EchonetNumber(
                    entity["echonetlite"],
                    config,
                    _enl_op_codes,
                    hass,
                )
            )

    async_add_entities(entities, True)


class EchonetNumber(CoordinatorEntity, NumberEntity):
    """Representation of an ECHONETLite Number."""

    _attr_translation_key = DOMAIN
    coordinator: DataUpdateCoordinator | None

    def __init__(self, connector, config, enl_op_codes, hass=None) -> None:
        """Initialize the number entity."""
        super().__init__(connector.coordinator) if connector.coordinator else None
        
        self._connector = connector
        self._config = config
        self._enl_op_codes = enl_op_codes
        self._device_name = get_device_name(connector, config)

        # Determine the EPC code for this number entity (0x91=temperature, etc.)
        self._epc_code = 0x91  # Default to temperature
        
        self._attr_unique_id = (
            f"{self._connector._uidi}-{self._epc_code}" if self._connector._uidi 
            else f"{self._connector._uid}-{self._eojgc}-{self._eojcc}-{self._eojci}-{self._epc_code}"
        )
        self._attr_name = f"{self._device_name} {get_epc_description(self._epc_code)}"
        
        # Temperature range (default for Japanese market)
        self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self._attr_mode = NumberMode.SLIDER
        
        if self._epc_code == 0x91:  # Temperature setpoint
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_native_min_value = 15.0
            self._attr_native_max_value = 30.0
            self._attr_step = 0.5
        
        # Initialize state from connector data
        self._native_value = None
        
        update_data = getattr(self.coordinator, 'data', None) or getattr(connector, '_update_data', {})
        
        if self._epc_code in update_data:
            value = update_data[self._epc_code]
            # Convert from ECHONET scale (0.5°C steps for temperature)
            if self._attr_device_class == NumberDeviceClass.TEMPERATURE:
                self._native_value = round(value * 0.5, 1) if value else None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._connector._uid)},
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._eojgc][self._connector._eojcc],
        }

    @property
    def native_value(self):
        """Return the current value."""
        return self._native_value

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        # Convert HA value to ECHONET scale
        if self._attr_device_class == NumberDeviceClass.TEMPERATURE:
            epc_value = int(value / 0.5)
        else:
            epc_value = int(value)
        
        await self._connector._instance.setMessage(self._epc_code, epc_value)
        self._native_value = value
        self.async_write_ha_state()

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
            if self._attr_device_class == NumberDeviceClass.TEMPERATURE:
                self._native_value = round(value * 0.5, 1) if value else None

        self.async_write_ha_state()

    def update_option_listener(self):
        """Update listener for option changes."""
        pass


def get_epc_description(epc_code: int) -> str:
    """Get description for EPC code."""
    descriptions = {
        0x91: "Temperature Setpoint",
        0x92: "Outdoor Temperature",
        0x93: "Indoor Target Temperature",
    }
    return descriptions.get(epc_code, f"EPC {hex(epc_code)}")