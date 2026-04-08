"""Support for ECHONETLite Climate."""

import logging

from homeassistant.components.climate import (
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRESET_NONE, UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from pychonet.lib.eojx import EOJX_CLASS
from . import get_device_name, get_name_by_epc_code
from .const import (
    CONF_FORCE_POLLING,
    DOMAIN,
    ENL_OP_CODES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the ECHONETLite climate platform."""
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        _enl_op_codes = entity["echonetlite"]._enl_op_codes
        
        if (
            eojgc == 0x30 and eojcc in [0x00, 0x81, 0x82, 0x84]
        ):  # Air conditioner
            entities.append(
                EchonetClimate(
                    entity["echonetlite"],
                    config,
                    _enl_op_codes,
                    hass,
                )
            )

    async_add_entities(entities, True)


class EchonetClimate(CoordinatorEntity, ClimateEntity):
    """Representation of an ECHONETLite Air Conditioner."""

    _attr_translation_key = DOMAIN
    coordinator: DataUpdateCoordinator | None

    def __init__(self, connector, config, enl_op_codes, hass=None) -> None:
        """Initialize the climate entity."""
        super().__init__(connector.coordinator) if connector.coordinator else None
        
        self._connector = connector
        self._config = config
        self._enl_op_codes = enl_op_codes
        self._device_name = get_device_name(connector, config)

        self._attr_unique_id = (
            f"{self._connector._uidi}" if self._connector._uidi else self._connector._uid
        )
        self._attr_name = self._device_name

        # HVAC Operation Modes - EPC 0x80
        _operation_modes = {
            0x01: "heat_cool",  # Automatic
            0x02: "cool",       # Cooling
            0x03: "dry",        # Dehumidifying
            0x04: "fan_only",   # Fan
            0x05: "heat",       # Heating
            0x81: "off",        # Off (set operation mode)
            0x82: None,         # Off (stop operation)
            0xB0: None,         # Forced heating
            0xB1: None,         # Forced cooling
            0xB2: None,         # Forced dehumidifying
        }

        self._attr_hvac_modes = list(
            set([m for m in _operation_modes.values() if m is not None])
        )

        # Fan Speeds - EPC 0x83
        _fan_speeds = [None, "low", "medium_low", "medium", "medium_high", "high"]
        self._attr_fan_modes = _fan_speeds[1:]

        # Swing Modes - EPC 0x94, 0x95
        self._swing_modes = [SWING_BOTH, SWING_HORIZONTAL, SWING_VERTICAL]
        self._attr_swing_modes = self._swing_modes.copy()

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.PRESET_MODE
        )

        # Initialize state values from connector data
        self._hvac_mode = _operation_modes.get(
            connector._update_data.get(0x80, 0x81), "off"
        )
        self._fan_speed = _fan_speeds[
            min(connector._update_data.get(0x83, 1), len(_fan_speeds) - 1)
        ]

        # Temperature ranges (default values for Japanese market)
        self._min_temp = connector._user_options["min_temp_heat"]
        self._max_temp = connector._user_options["max_temp_heat"]
        
        if "min_temp_cool" in connector._user_options:
            self._min_temp = min(
                self._min_temp, connector._user_options.get("min_temp_cool", 15)
            )
            self._max_temp = max(
                self._max_temp, connector._user_options.get("max_temp_cool", 30)
            )

        # Current temperature from EPC 0xD0 (room temp) or 0x92 (outdoor temp)
        self._current_temperature = None
        if 0xD0 in connector._update_data:
            self._current_temperature = round(connector._update_data[0xD0], 1)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._connector._uid)},
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._eojgc][self._connector._eojcc],
        }

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return self._hvac_mode

    @property
    def target_temperature(self):
        """Return the temperature we're trying to achieve."""
        if 0x91 in self.coordinator.data:
            temp = self.coordinator.data[0x91]
            # Convert from ECHONET scale (0.5°C steps)
            return round(temp * 0.5, 1) if temp else None
        elif 0x91 in getattr(self._connector, '_update_data', {}):
            temp = self._connector._update_data[0x91]
            return round(temp * 0.5, 1) if temp else None
        return None

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def hvac_action(self):
        """Return the current HVAC action."""
        if self.hvac_mode == "off":
            return "off"
        
        # Check EPC 0x82 (operation status) for active state
        operation_status = None
        if self.coordinator:
            operation_status = self.coordinator.data.get(0x82)
        else:
            operation_status = getattr(self._connector, '_update_data', {}).get(0x82)
        
        action_map = {
            0x01: "heating",
            0x02: "cooling",
            0x03: "drying",
            0x04: None,  # Fan only - no specific action
            0x80: "idle",
        }
        
        return action_map.get(operation_status)

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        return self._fan_speed

    @property
    def swing_mode(self):
        """Return the current swing mode."""
        # Combine horizontal (0x94) and vertical (0x95) settings
        h_swing = getattr(
            self.coordinator.data if self.coordinator else None, 0x94, None
        )
        v_swing = getattr(
            self.coordinator.data if self.coordinator else None, 0x95, None
        )
        
        if not h_swing and not v_swing:
            # Try connector fallback
            h_swing = getattr(self._connector._update_data, get(0x94), None)
            v_swing = getattr(self._connector._update_data, get(0x95), None)
        
        if h_swing and v_swing:
            return SWING_BOTH
        elif h_swing:
            return SWING_HORIZONTAL
        elif v_swing:
            return SWING_VERTICAL
        else:
            return None

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        # Check for power saving / eco modes (EPC 0x3A)
        if self.coordinator and 0x3A in self.coordinator.data:
            epc_3a = self.coordinator.data[0x3A]
            if epc_3a == 0x81:
                return "eco"
            elif epc_3a in [0xC1, 0xC2]:
                return "power_saving"
        return PRESET_NONE

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target HVAC mode."""
        operation_map = {
            "heat_cool": 0x01,
            "cool": 0x02,
            "dry": 0x03,
            "fan_only": 0x04,
            "heat": 0x05,
            "off": 0x81,
        }

        if hvac_mode in operation_map:
            await self._connector._instance.setMessage(0x80, operation_map[hvac_mode])
            self._hvac_mode = hvac_mode
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            temp = int(kwargs[ATTR_TEMPERATURE] / 0.5)
            await self._connector._instance.setMessage(0x91, temp)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        _fan_speeds = [None, "low", "medium_low", "medium", "medium_high", "high"]
        if fan_mode in _fan_speeds:
            await self._connector._instance.setMessage(0x83, _fan_speeds.index(fan_mode))

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode."""
        # For simplicity, set both horizontal and vertical when BOTH is selected
        if swing_mode == SWING_BOTH:
            await self._connector._instance.setMessage(0x94, 0x01)  # Swing on
            await self._connector._instance.setMessage(0x95, 0x01)
        elif swing_mode == SWING_HORIZONTAL:
            await self._connector._instance.setMessage(0x94, 0x01)
        elif swing_mode == SWING_VERTICAL:
            await self._connector._instance.setMessage(0x95, 0x01)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if preset_mode == "eco":
            await self._connector._instance.setMessage(0x3A, 0x81)
        elif preset_mode == "power_saving":
            await self._connector._instance.setMessage(0x3A, 0xC1)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush: bool = False):
        """Handle coordinator updates."""
        if self.coordinator and not self.coordinator.last_update_success:
            return
            
        # Update state from coordinator data
        update_data = self.coordinator.data
        
        if 0x80 in update_data:
            _operation_modes = {1: "heat_cool", 2: "cool", 3: "dry", 4: "fan_only", 5: "heat"}
            self._hvac_mode = _operation_modes.get(update_data[0x80], "off")
        
        if 0x83 in update_data:
            _fan_speeds = [None, "low", "medium_low", "medium", "medium_high", "high"]
            self._fan_speed = _fan_speeds[min(update_data[0x83], len(_fan_speeds) - 1)]

        if 0xD0 in update_data:
            self._current_temperature = round(update_data[0xD0], 1)

        self.async_write_ha_state()

    def update_option_listener(self):
        """Update listener for option changes."""
        _should_poll = True  # Climate typically uses polling
        self._attr_should_poll = (
            self._connector._user_options.get(CONF_FORCE_POLLING, False) or _should_poll
        )