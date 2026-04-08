"""Support for ECHONETLite Switch."""

import logging

from homeassistant.components.switch import (
    SwitchEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from pychonet.lib.eojx import EOJX_CLASS
from . import get_device_name
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the ECHONETLite switch platform."""
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]

        # Check if this device is a switch (EPC 0x81 - ON/OFF)
        _enl_op_codes = entity["echonetlite"]._enl_op_codes
        
        has_switch_support = any(
            code in entity["instance"]["setmap"] for code in [0x80, 0x81]
        )

        if has_switch_support:
            entities.append(
                EchonetSwitch(
                    entity["echonetlite"],
                    config,
                    _enl_op_codes,
                    hass,
                )
            )

    async_add_entities(entities, True)


class EchonetSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an ECHONETLite Switch."""

    _attr_translation_key = DOMAIN
    coordinator: DataUpdateCoordinator | None

    def __init__(self, connector, config, enl_op_codes, hass=None) -> None:
        """Initialize the switch entity."""
        super().__init__(connector.coordinator) if connector.coordinator else None
        
        self._connector = connector
        self._config = config
        self._enl_op_codes = enl_op_codes
        self._device_name = get_device_name(connector, config)

        self._attr_unique_id = (
            f"{self._connector._uidi}" if self._connector._uidi else self._connector._uid
        )
        self._attr_name = self._device_name
        
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
        """Return if the switch is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        # Turn on (EPC 0x81 = 0x01 for ON operation)
        await self._connector._instance.setMessage(0x81, 0x01)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        # Turn off (EPC 0x81 = 0x02 for OFF operation)
        await self._connector._instance.setMessage(0x81, 0x02)
        self._is_on = False
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs) -> None:
        """Toggle the switch."""
        if self.is_on:
            await self.async_turn_off(**kwargs)
        else:
            await self.async_turn_on(**kwargs)

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