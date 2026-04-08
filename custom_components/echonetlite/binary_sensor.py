"""Support for ECHONETLite Binary Sensors."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from pychonet.lib.eojx import EOJX_CLASS
from . import get_device_name
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the ECHONETLite binary sensor platform."""
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]

        _enl_op_codes = entity["echonetlite"]._enl_op_codes
        
        # Check if this device has binary sensor capabilities (EPC 0x81 - ON/OFF)
        has_binary_sensor_support = any(
            code in entity["instance"]["setmap"] for code in [0x80, 0x81]
        )

        if has_binary_sensor_support:
            entities.append(
                EchonetBinarySensor(
                    entity["echonetlite"],
                    config,
                    _enl_op_codes,
                    hass,
                )
            )

    async_add_entities(entities, True)


class EchonetBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of an ECHONETLite Binary Sensor."""

    _attr_translation_key = DOMAIN
    coordinator: DataUpdateCoordinator | None

    def __init__(self, connector, config, enl_op_codes, hass=None) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(connector.coordinator) if connector.coordinator else None
        
        self._connector = connector
        self._config = config
        self._enl_op_codes = enl_op_codes
        self._device_name = get_device_name(connector, config)

        self._attr_unique_id = (
            f"{self._connector._uidi}" if self._connector._uidi else self._connector._uid
        )
        self._attr_name = self._device_name
        
        # Default device class - can be overridden by EPC mapping
        self._attr_device_class = BinarySensorDeviceClass.MOTION

        # Initialize state from connector data
        self._is_on = False
        
        update_data = getattr(self.coordinator, 'data', None) or getattr(connector, '_update_data', {})
        
        if 0x81 in update_data:
            self._is_on = (update_data[0x81] == 0x01)

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
        """Return if the binary sensor is on."""
        return self._is_on

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
            self._is_on = (update_data[0x81] == 0x01)

        self.async_write_ha_state()

    def update_option_listener(self):
        """Update listener for option changes."""
        pass