"""Support for ECHONETLite Select entities."""

import logging

from homeassistant.components.select import (
    SelectEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from pychonet.lib.eojx import EOJX_CLASS
from . import get_device_name
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the ECHONETLite select platform."""
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]

        _enl_op_codes = entity["echonetlite"]._enl_op_codes
        
        # Check if this device has select capabilities (enum-like settings)
        has_select_support = any(
            code in entity["instance"]["setmap"] for code in [0x82, 0x94, 0x95]
        )

        if has_select_support:
            entities.append(
                EchonetSelect(
                    entity["echonetlite"],
                    config,
                    _enl_op_codes,
                    hass,
                )
            )

    async_add_entities(entities, True)


class EchonetSelect(CoordinatorEntity, SelectEntity):
    """Representation of an ECHONETLite Select."""

    _attr_translation_key = DOMAIN
    coordinator: DataUpdateCoordinator | None

    def __init__(self, connector, config, enl_op_codes, hass=None) -> None:
        """Initialize the select entity."""
        super().__init__(connector.coordinator) if connector.coordinator else None
        
        self._connector = connector
        self._config = config
        self._enl_op_codes = enl_op_codes
        self._device_name = get_device_name(connector, config)

        # Determine the EPC code and options for this select entity
        self._epc_code = 0x82  # Default to operation status
        
        self._attr_unique_id = (
            f"{self._connector._uidi}-{self._epc_code}" if self._connector._uidi 
            else f"{self._connector._uid}-{self._eojgc}-{self._eojcc}-{self._eojci}-{self._epc_code}"
        )
        self._attr_name = f"{self._device_name} {get_select_description(self._epc_code)}"

        # Define available options based on EPC code
        if self._epc_code == 0x82:  # Operation status
            self._options = ["off", "idle", "heating", "cooling", "drying"]
        elif self._epc_code == 0x94:  # Horizontal swing
            self._options = ["stop", "swing", "position1", "position2"]
        elif self._epc_code == 0x95:  # Vertical swing
            self._options = ["stop", "swing", "position1", "position2"]
        else:
            self._options = []

        # Initialize state from connector data
        self._current_option = None
        
        update_data = getattr(self.coordinator, 'data', None) or getattr(connector, '_update_data', {})
        
        if self._epc_code in update_data and self._options:
            epc_value = int(update_data[self._epc_code])
            option_index = min(epc_value, len(self._options) - 1)
            self._current_option = self._options[option_index]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._connector._uid)},
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._eojgc][self._connector._eojcc],
        }

    @property
    def options(self):
        """Return the list of available options."""
        return self._options

    @property
    def current_option(self):
        """Return the currently selected option."""
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Select a new option."""
        try:
            epc_value = self._options.index(option)
            await self._connector._instance.setMessage(self._epc_code, epc_value)
            self._current_option = option
            self.async_write_ha_state()
        except ValueError:
            _LOGGER.error(f"Invalid option selected: {option}")

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush: bool = False):
        """Handle coordinator updates."""
        if self.coordinator and not self.coordinator.last_update_success:
            return
            
        update_data = self.coordinator.data
        
        if self._epc_code in update_data and self._options:
            epc_value = int(update_data[self._epc_code])
            option_index = min(epc_value, len(self._options) - 1)
            self._current_option = self._options[option_index]

        self.async_write_ha_state()

    def update_option_listener(self):
        """Update listener for option changes."""
        pass


def get_select_description(epc_code: int) -> str:
    """Get description for select EPC code."""
    descriptions = {
        0x82: "Operation Status",
        0x94: "Horizontal Swing",
        0x95: "Vertical Swing",
    }
    return descriptions.get(epc_code, f"Select {hex(epc_code)}")