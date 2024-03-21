import logging

from pychonet.HomeAirConditioner import (
    AIRFLOW_VERT,
    ENL_STATUS,
    ENL_FANSPEED,
    ENL_AIR_VERT,
    ENL_AUTO_DIRECTION,
    ENL_SWING_MODE,
    ENL_HVAC_MODE,
    ENL_HVAC_SET_TEMP,
    ENL_HVAC_SET_HUMIDITY,
    ENL_HVAC_ROOM_TEMP,
    ENL_HVAC_SILENT_MODE,
    FAN_SPEED,
    SILENT_MODE,
)

from pychonet.lib.eojx import EOJX_CLASS

import voluptuous as vol

from homeassistant.components.climate import (
    ClimateEntity,
)
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    ATTR_HVAC_MODE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from . import get_device_name
from .const import DATA_STATE_ON, DOMAIN, OPTION_HA_UI_SWING

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


class EchonetClimate(ClimateEntity):
    """Representation of an ECHONETLite climate device."""

    _attr_translation_key = DOMAIN

    def __init__(self, connector, config):
        """Initialize the climate device."""
        name = get_device_name(connector, config)
        self._attr_name = name
        self._device_name = name
        self._connector = connector  # new line
        self._attr_unique_id = (
            self._connector._uidi if self._connector._uidi else self._connector._uid
        )
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
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]
        self._opc_data = {
            ENL_AUTO_DIRECTION: list(
                self._connector._instance.EPC_FUNCTIONS[ENL_AUTO_DIRECTION][1].values()
            ),
            ENL_SWING_MODE: list(
                self._connector._instance.EPC_FUNCTIONS[ENL_SWING_MODE][1].values()
            ),
        }
        if ENL_FANSPEED in list(self._connector._setPropertyMap):
            self._attr_supported_features = (
                self._attr_supported_features | ClimateEntityFeature.FAN_MODE
            )
        if ENL_AIR_VERT in list(self._connector._setPropertyMap):
            self._attr_supported_features = (
                self._attr_supported_features | ClimateEntityFeature.SWING_MODE
            )
        if ENL_HVAC_SILENT_MODE in list(self._connector._setPropertyMap):
            self._attr_supported_features = (
                self._attr_supported_features | ClimateEntityFeature.PRESET_MODE
            )
        self._attr_hvac_modes = DEFAULT_HVAC_MODES
        self._attr_preset_modes = DEFAULT_PRESET_MODES
        self._olddata = {}
        # self._should_poll = True
        self._last_mode = HVACMode.OFF
        # self._available = True
        self._attr_should_poll = True
        self._attr_available = True

        self.update_option_listener()
        self._set_attrs()

        # see, https://developers.home-assistant.io/blog/2024/01/24/climate-climateentityfeatures-expanded
        self._enable_turn_on_off_backwards_compatibility = False

    async def async_update(self):
        """Get the latest state from the HVAC."""
        try:
            await self._connector.async_update()
        except TimeoutError:
            pass

    @property
    def device_info(self):
        return {
            "identifiers": {
                (
                    DOMAIN,
                    self._connector._uid,
                    self._connector._instance._eojgc,
                    self._connector._instance._eojcc,
                    self._connector._instance._eojci,
                )
            },
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer
            + (
                " " + self._connector._host_product_code
                if self._connector._host_product_code
                else ""
            ),
            "model": EOJX_CLASS[self._connector._instance._eojgc][
                self._connector._instance._eojcc
            ],
            # "sw_version": "",
        }

    def _set_min_max_temp(self):
        self._attr_min_temp = self._connector._user_options["min_temp_auto"]
        self._attr_max_temp = self._connector._user_options["max_temp_auto"]

        if hasattr(self, "_attr_hvac_mode"):
            """minimum/maximum temperature supported by the HVAC."""
            if self._attr_hvac_mode == HVACMode.HEAT:
                self._attr_min_temp = self._connector._user_options["min_temp_heat"]
                self._attr_max_temp = self._connector._user_options["max_temp_heat"]
            elif self._attr_hvac_mode == HVACMode.COOL:
                self._attr_min_temp = self._connector._user_options["min_temp_cool"]
                self._attr_max_temp = self._connector._user_options["max_temp_cool"]

    def _set_attrs(self):
        """current temperature."""
        _val = self._connector._update_data.get(ENL_HVAC_ROOM_TEMP)
        # 0x7F: Overflow, 0x80: Underflow, 0x7E:Value cannot be returned
        if _val in {0x7F, 0x80, 0x7E}:
            _val = None
        self._attr_current_temperature = _val

        """temperature we try to reach."""
        _val = self._connector._update_data.get(ENL_HVAC_SET_TEMP)
        # -3: Rule of thumb, 0xFD: Temperature indeterminable
        if _val in {-3, 0xFD}:
            _val = None
        self._attr_target_temperature = _val

        """temperature we try to reach."""
        self._attr_target_humidity = self._connector._update_data.get(
            ENL_HVAC_SET_HUMIDITY
        )

        """current operation ie. heat, cool, idle."""
        _val = self._connector._update_data.get(ENL_HVAC_MODE)
        self._attr_hvac_mode = HVACMode.OFF
        if self._connector._update_data[ENL_STATUS] == DATA_STATE_ON:
            if _val == "auto":
                self._attr_hvac_mode = HVACMode.HEAT_COOL
            elif _val == "other":
                if self._connector._user_options.get(ENL_HVAC_MODE) == "as_idle":
                    self._attr_hvac_mode = self._last_mode
                else:
                    self._attr_hvac_mode = HVACMode.OFF
            else:
                self._attr_hvac_mode = _val
            if self._attr_hvac_mode != HVACMode.OFF:
                self._last_mode = self._attr_hvac_mode

        """current operation ie. heat, cool, idle."""
        self._attr_hvac_action = HVACAction.OFF
        if self._connector._update_data[ENL_STATUS] == DATA_STATE_ON:
            if self._connector._update_data[ENL_HVAC_MODE] == HVACMode.HEAT:
                self._attr_hvac_action = HVACAction.HEATING
            elif self._connector._update_data[ENL_HVAC_MODE] == HVACMode.COOL:
                self._attr_hvac_action = HVACAction.COOLING
            elif self._connector._update_data[ENL_HVAC_MODE] == HVACMode.DRY:
                self._attr_hvac_action = HVACAction.DRYING
            elif self._connector._update_data[ENL_HVAC_MODE] == HVACMode.FAN_ONLY:
                self._attr_hvac_action = HVACAction.FAN
            elif (
                self._connector._update_data[ENL_HVAC_MODE] == HVACMode.HEAT_COOL
                or self._connector._update_data[ENL_HVAC_MODE] == "auto"
            ):
                _room_temp = self._connector._update_data.get(ENL_HVAC_ROOM_TEMP)
                if _room_temp := self._connector._update_data.get(ENL_HVAC_ROOM_TEMP):
                    if self._connector._update_data[ENL_HVAC_SET_TEMP] < _room_temp:
                        self._attr_hvac_action = HVACAction.COOLING
                    elif self._connector._update_data[ENL_HVAC_SET_TEMP] > _room_temp:
                        self._attr_hvac_action = HVACAction.HEATING
                else:
                    self._attr_hvac_action = HVACAction.IDLE
            elif self._connector._update_data[ENL_HVAC_MODE] == "other":
                if self._connector._user_options.get(ENL_HVAC_MODE) == "as_idle":
                    self._attr_hvac_action = HVACAction.IDLE
                else:
                    self._attr_hvac_action = HVACAction.OFF
            else:
                _LOGGER.warning(
                    f"Unknown HVAC mode {self._connector._update_data.get(ENL_HVAC_MODE)}"
                )
                self._attr_hvac_action = HVACAction.IDLE

        """true if the device is on."""
        self._attr_is_on = (
            True if self._connector._update_data[ENL_STATUS] == DATA_STATE_ON else False
        )

        """fan setting."""
        self._attr_fan_mode = (
            self._connector._update_data[ENL_FANSPEED]
            if ENL_FANSPEED in self._connector._update_data
            else None
        )

        """preset setting."""
        self._attr_preset_mode = (
            self._connector._update_data[ENL_HVAC_SILENT_MODE]
            if ENL_HVAC_SILENT_MODE in self._connector._update_data
            else None
        )

        """swing mode setting."""
        if (
            self._connector._update_data.get(ENL_AUTO_DIRECTION)
            in self._attr_swing_modes
        ):
            self._attr_swing_mode = self._connector._update_data.get(ENL_AUTO_DIRECTION)
        elif self._connector._update_data.get(ENL_SWING_MODE) in self._attr_swing_modes:
            self._attr_swing_mode = self._connector._update_data.get(ENL_SWING_MODE)
        else:
            self._attr_swing_mode = (
                self._connector._update_data[ENL_AIR_VERT]
                if ENL_AIR_VERT in self._connector._update_data
                else None
            )

        self._set_min_max_temp()

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug(f"Updated fan mode is: {fan_mode}")
        await self._connector._instance.setFanSpeed(fan_mode)

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode - This is normal/high-speed/silent"""
        await self._connector._instance.setSilentMode(preset_mode)

    async def async_set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        if swing_mode in self._opc_data[ENL_AUTO_DIRECTION]:
            await self._connector._instance.setAutoDirection(swing_mode)
        elif swing_mode in self._opc_data[ENL_SWING_MODE]:
            await self._connector._instance.setSwingMode(swing_mode)
        else:
            await self._connector._instance.setAirflowVert(swing_mode)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        # Check has HVAC Mode
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)

        if kwargs.get(ATTR_TEMPERATURE) is not None:
            await self._connector._instance.setOperationalTemperature(
                kwargs.get(ATTR_TEMPERATURE)
            )

    async def async_set_humidity(self, humidity: int) -> None:
        await self._connector._instance.setOperationalTemperature(humidity)

    async def async_set_hvac_mode(self, hvac_mode):
        # _LOGGER.warning(self._connector._update_data)
        """Set new operation mode (including off)"""
        if hvac_mode == "heat_cool":
            await self._connector._instance.setMode("auto")
        else:
            await self._connector._instance.setMode(hvac_mode)

    async def async_turn_on(self):
        """Turn on."""
        await self._connector._instance.on()

    async def async_turn_off(self):
        """Turn off."""
        await self._connector._instance.off()

    async def async_set_humidifier_during_heater(self, state, humidity):
        """Handle boost heating service call."""
        await self._connector._instance.setHeaterHumidifier(state, humidity)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush: bool = False):
        changed = (
            self._olddata != self._connector._update_data
            or self._attr_available != self._server_state["available"]
        )
        _LOGGER.debug(
            f"Called async_update_callback on {self._device_name}.\nChanged: {changed}\nUpdate data: {self._connector._update_data}\nOld data: {self._olddata}"
        )
        if changed:
            _force = bool(not self._attr_available and self._server_state["available"])
            self._olddata = self._connector._update_data.copy()
            self._attr_available = self._server_state["available"]
            self._set_attrs()
            self.async_schedule_update_ha_state(_force | isPush)

    def update_option_listener(self):
        """list of available fan modes."""
        _modes = self._connector._user_options.get(ENL_FANSPEED)
        if _modes:
            self._attr_fan_modes = _modes
        else:
            self._attr_fan_modes = DEFAULT_FAN_MODES

        """list of available swing modes."""
        _modes = self._connector._user_options.get(OPTION_HA_UI_SWING)
        if _modes and len(_modes):
            self._attr_swing_modes = _modes
        elif _modes := self._connector._user_options.get(ENL_AIR_VERT):
            self._attr_swing_modes = _modes
        else:
            self._attr_swing_modes = DEFAULT_SWING_MODES

        self._set_min_max_temp()
        if self.hass:
            self.async_schedule_update_ha_state()
