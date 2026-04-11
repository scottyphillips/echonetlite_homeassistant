import logging
import math

import voluptuous as vol
from homeassistant.core import callback
from homeassistant.components.climate import (
    ClimateEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from pychonet.HomeAirConditioner import (
    AIRFLOW_VERT,
    ENL_AIR_VERT,
    ENL_AUTO_DIRECTION,
    ENL_FANSPEED,
    ENL_HVAC_MODE,
    ENL_HVAC_ROOM_TEMP,
    ENL_HVAC_SET_HUMIDITY,
    ENL_HVAC_SET_TEMP,
    ENL_HVAC_SILENT_MODE,
    ENL_STATUS,
    ENL_SWING_MODE,
    FAN_SPEED,
    SILENT_MODE,
)
from pychonet.lib.eojx import EOJX_CLASS

from . import get_device_name
from .const import DATA_STATE_ON, DOMAIN, OPTION_HA_UI_SWING
from .base_entity import EchonetEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_FAN_MODES = list(
    FAN_SPEED.keys()
)  # ["auto","minimum","low","medium-low","medium","medium-high","high","very-high","max"]
DEFAULT_HVAC_MODES = [
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
    HVACMode.HEAT_COOL,
    HVACMode.OFF,
]
DEFAULT_SWING_MODES = ["auto-vert"] + list(
    AIRFLOW_VERT.keys()
)  # ["auto-vert","upper","upper-central","central","lower-central","lower"]
DEFAULT_PRESET_MODES = list(SILENT_MODE.keys())  # ["normal", "high-speed", "silent"]

SERVICE_SET_HUMIDIFER_DURING_HEATER = "set_humidifier_during_heater"
ATTR_STATE = "state"
ATTR_HUMIDITY = "humidity"


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        if (
            entity["instance"]["eojgc"] == 0x01 and entity["instance"]["eojcc"] == 0x30
        ):  # Home Air Conditioner
            entities.append(EchonetClimate(entity["echonetlite"], config_entry))
    async_add_devices(entities, True)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_HUMIDIFER_DURING_HEATER,
        {
            vol.Required(ATTR_STATE): cv.boolean,
            vol.Required(ATTR_HUMIDITY): cv.byte,
        },
        "async_set_humidifier_during_heater",
    )


class EchonetClimate(EchonetEntity, ClimateEntity):
    """Representation of an ECHONETLite climate device."""

    def __init__(self, coordinator, config):
        """Initialize the climate device.

        Args:
            connector: The ECHONETConnector instance which is also a DataUpdateCoordinator.
            config: The config entry for this integration.
        """
        super().__init__(coordinator, config)
        self._attr_unique_id = self._build_unique_id()
        # The temperature unit of echonet lite is defined as Celsius.
        # Set temperature_unit setting to Celsius,
        # HA's automatic temperature unit conversion function works correctly.
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = PRECISION_WHOLE
        self._attr_target_temperature_step = 1
        if hasattr(ClimateEntityFeature, "TURN_ON"):
            self._attr_supported_features = ClimateEntityFeature(
                ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
            )
        else:
            self._attr_supported_features = ClimateEntityFeature(0)
        self._attr_supported_features = (
            self._attr_supported_features | ClimateEntityFeature.TARGET_TEMPERATURE
        )
        self._server_state = self.coordinator._api._state[
            self.coordinator._instance._host
        ]
        self._opc_data = {
            ENL_AUTO_DIRECTION: list(
                self.coordinator._instance.EPC_FUNCTIONS[ENL_AUTO_DIRECTION][1].values()
            ),
            ENL_SWING_MODE: list(
                self.coordinator._instance.EPC_FUNCTIONS[ENL_SWING_MODE][1].values()
            ),
        }
        if ENL_FANSPEED in list(self.coordinator._setPropertyMap):
            self._attr_supported_features = (
                self._attr_supported_features | ClimateEntityFeature.FAN_MODE
            )
        if ENL_AIR_VERT in list(
            self.coordinator._setPropertyMap
        ) or ENL_SWING_MODE in list(self.coordinator._setPropertyMap):
            self._attr_supported_features = (
                self._attr_supported_features | ClimateEntityFeature.SWING_MODE
            )
        if ENL_HVAC_SILENT_MODE in list(self.coordinator._setPropertyMap):
            self._attr_supported_features = (
                self._attr_supported_features | ClimateEntityFeature.PRESET_MODE
            )
        self._attr_hvac_modes = DEFAULT_HVAC_MODES
        self._attr_preset_modes = DEFAULT_PRESET_MODES
        self._olddata = {}

        self._last_mode = HVACMode.OFF

        self._attr_available = True

        self.update_option_listener()
        self._set_attrs()

        # see, https://developers.home-assistant.io/blog/2024/01/24/climate-climateentityfeatures-expanded
        self._enable_turn_on_off_backwards_compatibility = False

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature."""
        _val = self.coordinator.data.get(ENL_HVAC_ROOM_TEMP)
        # 0x7F: Overflow, 0x80: Underflow, 0x7E: Value cannot be returned
        if _val in {0x7F, 0x80, 0x7E}:
            return None
        return _val

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        _val = self.coordinator.data.get(ENL_HVAC_SET_TEMP)
        # -3: Rule of thumb, 0xFD: Temperature indeterminable
        if _val in {-3, 0xFD}:
            return None
        return _val

    @property
    def target_humidity(self) -> int | None:
        """Return the target humidity."""
        return self.coordinator.data.get(ENL_HVAC_SET_HUMIDITY)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current operation mode."""
        _val = self.coordinator.data.get(ENL_HVAC_MODE)

        if self.coordinator.data[ENL_STATUS] != DATA_STATE_ON:
            return HVACMode.OFF

        if _val == "auto":
            return HVACMode.HEAT_COOL
        elif _val == "other":
            if self.coordinator._user_options.get(ENL_HVAC_MODE) == "as_idle":
                # Return last known mode when in 'other' state with as_idle option
                return getattr(self, "_last_mode", HVACMode.OFF)
            else:
                return HVACMode.OFF
        else:
            # Store the mode for later reference
            # if hasattr(self, '_last_mode'):
            #     self._last_mode = _val
            return _val

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current HVAC action."""
        if self.coordinator.data[ENL_STATUS] != DATA_STATE_ON:
            return HVACAction.OFF

        mode = self.coordinator.data.get(ENL_HVAC_MODE)

        if mode == HVACMode.HEAT:
            return HVACAction.HEATING
        elif mode == HVACMode.COOL:
            return HVACAction.COOLING
        elif mode == HVACMode.DRY:
            return HVACAction.DRYING
        elif mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        elif mode in (HVACMode.HEAT_COOL, "auto"):
            _room_temp = self.coordinator.data.get(ENL_HVAC_ROOM_TEMP)
            set_temp = self.coordinator.data.get(ENL_HVAC_SET_TEMP)
            if _room_temp is not None and set_temp is not None:
                if set_temp < _room_temp:
                    return HVACAction.COOLING
                elif set_temp > _room_temp:
                    return HVACAction.HEATING
            return HVACAction.IDLE
        elif mode == "other":
            if self.coordinator._user_options.get(ENL_HVAC_MODE) == "as_idle":
                return HVACAction.IDLE
            else:
                return HVACAction.OFF
        else:
            _LOGGER.warning(f"Unknown HVAC mode {mode}")
            return HVACAction.IDLE

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        return self.coordinator.data[ENL_STATUS] == DATA_STATE_ON

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        if ENL_FANSPEED in self.coordinator.data:
            return self.coordinator.data[ENL_FANSPEED]
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode (normal/high-speed/silent)."""
        if ENL_HVAC_SILENT_MODE in self.coordinator.data:
            return self.coordinator.data[ENL_HVAC_SILENT_MODE]
        return None

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        if self.coordinator.data.get(ENL_AUTO_DIRECTION) in getattr(
            self, "_attr_swing_modes", DEFAULT_SWING_MODES
        ):
            return self.coordinator.data.get(ENL_AUTO_DIRECTION)
        elif self.coordinator.data.get(ENL_SWING_MODE) in getattr(
            self, "_attr_swing_modes", DEFAULT_SWING_MODES
        ):
            return self.coordinator.data.get(ENL_SWING_MODE)
        else:
            if ENL_AIR_VERT in self.coordinator.data:
                return self.coordinator.data[ENL_AIR_VERT]
            return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature based on current operation mode."""
        mode = self.hvac_mode

        if mode == HVACMode.HEAT:
            return self.coordinator._user_options.get("min_temp_heat", 16)
        if mode == HVACMode.COOL:
            return self.coordinator._user_options.get("min_temp_cool", 18)

        # Default/Auto (HEAT_COOL), DRY, FAN_ONLY, OFF ranges
        return self.coordinator._user_options.get("min_temp_auto", 16)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature based on current operation mode."""
        mode = self.hvac_mode

        if mode == HVACMode.HEAT:
            return self.coordinator._user_options.get("max_temp_heat", 30)
        if mode == HVACMode.COOL:
            return self.coordinator._user_options.get("max_temp_cool", 27)

        # Default/Auto (HEAT_COOL), DRY, FAN_ONLY, OFF ranges
        return self.coordinator._user_options.get("max_temp_auto", 30)

    def _set_attrs(self):
        """Update internal state.

        Note: All climate attributes including min/max temperature are now @property
        getters that compute values on demand based on current hvac_mode.
        This method is kept for backward compatibility and to handle side effects like
        updating _last_mode.
        """
        # Update _last_mode based on current hvac mode
        if self.coordinator.data[ENL_STATUS] == DATA_STATE_ON:
            mode = self.coordinator.data.get(ENL_HVAC_MODE)
            if mode and mode not in ("auto", "other"):
                self._last_mode = mode

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug(f"Updated fan mode is: {fan_mode}")
        await self.coordinator._instance.setFanSpeed(fan_mode)

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode - This is normal/high-speed/silent"""
        await self.coordinator._instance.setSilentMode(preset_mode)

    async def async_set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        if swing_mode in self._opc_data[ENL_AUTO_DIRECTION]:
            await self.coordinator._instance.setAutoDirection(swing_mode)
        elif swing_mode in self._opc_data[ENL_SWING_MODE]:
            await self.coordinator._instance.setSwingMode(swing_mode)
        else:
            await self.coordinator._instance.setAirflowVert(swing_mode)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        # Check has HVAC Mode
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)

        settemp = self._normalize_settemp(kwargs.get(ATTR_TEMPERATURE))
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            await self.coordinator._instance.setOperationalTemperature(settemp)

    async def async_set_humidity(self, humidity: int) -> None:
        await self.coordinator._instance.setOperationalTemperature(humidity)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new operation mode (including off)"""
        if hvac_mode == "heat_cool":
            await self.coordinator._instance.setMode("auto")
        else:
            await self.coordinator._instance.setMode(hvac_mode)

    async def async_turn_on(self):
        """Turn on."""
        await self.coordinator._instance.on()

    async def async_turn_off(self):
        """Turn off."""
        await self.coordinator._instance.off()

    async def async_set_humidifier_during_heater(self, state, humidity):
        """Handle boost heating service call."""
        await self.coordinator._instance.setHeaterHumidifier(state, humidity)

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()
        self.coordinator.add_update_option_listener(self.update_option_listener)
        # self.coordinator.register_async_update_callbacks(self.async_update_callback)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            f"Coordinator update callback triggered for {self._device_name} with data: {self.coordinator.data}"
        )
        # We update the local attributes from the central data.
        self._set_attrs()

        # We use the Coordinator's availability status.
        self._attr_available = self.coordinator.last_update_success

        # Inform HA that the state needs writing to the UI.
        self.async_write_ha_state()

    def update_option_listener(self):
        """Update list of available fan and swing modes from options."""
        _modes = self.coordinator._user_options.get(ENL_FANSPEED)
        if _modes:
            self._attr_fan_modes = _modes
        else:
            self._attr_fan_modes = DEFAULT_FAN_MODES

        """list of available swing modes."""
        _modes = self.coordinator._user_options.get(OPTION_HA_UI_SWING)
        if _modes and len(_modes):
            self._attr_swing_modes = _modes
        elif _modes := self.coordinator._user_options.get(ENL_AIR_VERT):
            self._attr_swing_modes = _modes
        else:
            self._attr_swing_modes = DEFAULT_SWING_MODES

        if self.hass:
            self.async_schedule_update_ha_state()

    def _normalize_settemp(self, req: float | int | None) -> int | None:
        """
        Normalize a requested temperature to the 1°C resolution supported by
        ECHONET Lite HVAC devices.

        Matter controllers may send fractional values (e.g., 22.5°C). Since most
        ECHONET air conditioners accept only integer setpoints, this function
        converts the request to a valid value while preserving user intent:
        - Integer values are used as-is.
        - `.5` values are rounded directionally based on the previous target
          temperature (up when increasing, down when decreasing).
        - Other fractions are rounded to the nearest integer.
        """
        if req is None:
            return None

        res = None
        if abs(req - round(req)) < 1e-9:
            res = int(round(req))
        else:
            prev = self._attr_target_temperature
            frac = req - math.floor(req)

            if abs(frac - 0.5) < 1e-9 and prev is not None:
                if req >= prev:
                    res = math.ceil(req)
                if req < prev:
                    res = math.floor(req)
            else:
                res = int(math.floor(req + 0.5))

        return res
