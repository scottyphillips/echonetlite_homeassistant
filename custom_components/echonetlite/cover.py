"""Support for ECHONETLite Cover."""

import logging

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from pychonet.lib.eojx import EOJX_CLASS
from . import get_device_name
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the ECHONETLite cover platform."""
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]

        # Check if this device is a cover (EPC 0x81 - ON/OFF, 0xB5 - Position)
        _enl_op_codes = entity["echonetlite"]._enl_op_codes
        
        has_cover_support = any(
            code in entity["instance"]["setmap"] for code in [0x80, 0x81, 0xB5]
        )

        if has_cover_support:
            entities.append(
                EchonetCover(
                    entity["echonetlite"],
                    config,
                    _enl_op_codes,
                    hass,
                )
            )

    async_add_entities(entities, True)


class EchonetCover(CoordinatorEntity, CoverEntity):
    """Representation of an ECHONETLite Cover (e.g., window blinds)."""

    _attr_translation_key = DOMAIN
    coordinator: DataUpdateCoordinator | None

    def __init__(self, connector, config, enl_op_codes, hass=None) -> None:
        """Initialize the cover entity."""
        super().__init__(connector.coordinator) if connector.coordinator else None
        
        self._connector = connector
        self._config = config
        self._enl_op_codes = enl_op_codes
        self._device_name = get_device_name(connector, config)

        self._attr_unique_id = (
            f"{self._connector._uidi}" if self._connector._uidi else self._connector._uid
        )
        self._attr_name = self._device_name
        self._attr_device_class = CoverDeviceClass.BLIND
        
        # Supported features: open, close, stop, and position
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | 
            CoverEntityFeature.CLOSE | 
            CoverEntityFeature.STOP |
            CoverEntityFeature.SET_POSITION
        )
        
        # Initialize state from connector data
        self._is_opening = False
        self._is_closing = False
        self._position = None
        
        update_data = getattr(self.coordinator, 'data', None) or getattr(connector, '_update_data', {})
        
        if 0x81 in update_data:
            # EPC 0x81: Operation status - 0x01=ON (open), 0x02=OFF (close), 0x03=STOP
            operation = update_data[0x81]
            self._is_opening = (operation == 0x01)
            self._is_closing = (operation == 0x02)
        if 0xB5 in update_data:
            # EPC 0xB5: Position - typically 0-100 or 0-255 scale
            pos_value = int(update_data[0xB5])
            self._position = min(max(pos_value, 0), 100)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._connector._uid)},
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._eojgc][self._connector._eojcc],
        }

    @property
    def device_class(self):
        """Return the class of this cover."""
        return CoverDeviceClass.BLIND

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        return self._is_opening

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        return self._is_closing

    @property
    def position(self):
        """Return the current position of the cover (0-100)."""
        return self._position

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover."""
        # EPC 0x81 = 0x01 to open/start operation
        await self._connector._instance.setMessage(0x81, 0x01)
        self._is_opening = True
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs) -> None:
        """Close the cover."""
        # EPC 0x81 = 0x02 to close/stop operation
        await self._connector._instance.setMessage(0x81, 0x02)
        self._is_closing = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop the cover."""
        # EPC 0x81 = 0x03 to stop operation
        await self._connector._instance.setMessage(0x81, 0x03)
        self._is_opening = False
        self._is_closing = False
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs) -> None:
        """Set the position of the cover."""
        if ATTR_POSITION in kwargs:
            # EPC 0xB5 - Position (convert to appropriate scale)
            position = int(kwargs[ATTR_POSITION])
            await self._connector._instance.setMessage(0xB5, position)
            self._position = position
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
            # EPC 0x81: Operation status - 0x01=OPEN, 0x02=CLOSE, 0x03=STOP
            operation = update_data[0x81]
            self._is_opening = (operation == 0x01)
            self._is_closing = (operation == 0x02)
        
        if 0xB5 in update_data:
            # EPC 0xB5: Position
            pos_value = int(update_data[0xB5])
            self._position = min(max(pos_value, 0), 100)

        self.async_write_ha_state()

    def update_option_listener(self):
        """Update listener for option changes."""
        pass