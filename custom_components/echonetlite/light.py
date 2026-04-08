"""Support for ECHONETLite Light."""

import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from pychonet.lib.eojx import EOJX_CLASS
from . import get_device_name
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the ECHONETLite light platform."""
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]

        # Check if this device is a light (EPC 0x81 - ON/OFF, 0x90 - BRIGHTNESS)
        _enl_op_codes = entity["echonetlite"]._enl_op_codes
        
        # Common light EPC codes: 0x80 (operation status), 0x81 (on/off), 0x90 (brightness)
        has_light_support = any(
            code in entity["instance"]["setmap"] for code in [0x80, 0x81, 0x90]
        )

        if has_light_support:
            entities.append(
                EchonetLight(
                    entity["echonetlite"],
                    config,
                    _enl_op_codes,
                    hass,
                )
            )

    async_add_entities(entities, True)


class EchonetLight(CoordinatorEntity, LightEntity):
    """Representation of an ECHONETLite Light."""

    _attr_translation_key = DOMAIN
    coordinator: DataUpdateCoordinator | None

    def __init__(self, connector, config, enl_op_codes, hass=None) -> None:
        """Initialize the light entity."""
        super().__init__(connector.coordinator) if connector.coordinator else None
        
        self._connector = connector
        self._config = config
        self._enl_op_codes = enl_op_codes
        self._device_name = get_device_name(connector, config)

        self._attr_unique_id = (
            f"{self._connector._uidi}" if self._connector._uidi else self._connector._uid
        )
        self._attr_name = self._device_name
        
        # Light supports brightness if EPC 0x90 is available
        has_brightness = (
            0x90 in getattr(self.coordinator.data, 'keys', lambda: [])() 
            if self.coordinator 
            else 0x90 in getattr(connector, '_update_data', {})
        )
        
        self._attr_color_mode = ColorMode.BRIGHTNESS if has_brightness else ColorMode.ONOFF
        self._attr_supported_features = 0
        
        # Initialize state from connector data
        self._is_on = False
        self._brightness = None
        
        update_data = getattr(self.coordinator, 'data', None) or getattr(connector, '_update_data', {})
        
        if 0x81 in update_data:
            self._is_on = bool(update_data[0x81])
        if 0x90 in update_data:
            # ECHONET brightness is typically 0-255, convert to Home Assistant scale (0-255)
            self._brightness = int(update_data[0x90])

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
        """Return if the light is on."""
        return self._is_on

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        # Set operation mode to ON (EPC 0x80 = 0x03 or EPC 0x81 = 0x01)
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            await self._connector._instance.setMessage(0x90, brightness)
        
        # Turn on the light (EPC 0x81 = 0x01 for ON operation)
        await self._connector._instance.setMessage(0x81, 0x01)
        self._is_on = True
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = int(kwargs[ATTR_BRIGHTNESS])
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        # Turn off (EPC 0x81 = 0x02 for OFF operation)
        await self._connector._instance.setMessage(0x81, 0x02)
        self._is_on = False
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
        
        if 0x81 in update_data:
            # EPC 0x81: Operation status - 0x01=ON, 0x02=OFF
            self._is_on = (update_data[0x81] == 0x01)
        
        if 0x90 in update_data:
            # EPC 0x90: Brightness - 0-255
            self._brightness = int(update_data[0x90])

        self.async_write_ha_state()

    def update_option_listener(self):
        """Update listener for option changes."""
        pass