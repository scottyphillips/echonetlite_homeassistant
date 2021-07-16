import logging

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE,
    ATTR_FAN_MODES,
    CURRENT_HVAC_OFF,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_DRY,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_FAN,
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_AUTO,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
)
from homeassistant.const import (
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    PRECISION_WHOLE,
)
from .const import DOMAIN, HVAC_OP_CODES
SUPPORT_FLAGS = 0

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    entities.append(
           EchonetClimate(config_entry.data["title"],
           hass.data[DOMAIN][config_entry.entry_id],
           TEMP_CELSIUS)
           )
    async_add_devices(entities)

"""Representation of an ECHONETLite climate device."""
class EchonetClimate(ClimateEntity):
    def __init__(self, name, instance, unit_of_measurement, fan_modes=None):
        """Initialize the climate device."""
        self._name = name
        self._instance = instance  # new line
        self._uid = self._instance._uid
        self._unit_of_measurement = unit_of_measurement
        self._precision = 1.0
        self._target_temperature_step = 1
        self._support_flags = SUPPORT_FLAGS
        self._support_flags = self._support_flags | SUPPORT_TARGET_TEMPERATURE
        if HVAC_OP_CODES["fan_speed"] in list(instance._api.propertyMaps[158].values()):
            self._support_flags = self._support_flags | SUPPORT_FAN_MODE

        if fan_modes is not None:
            self._fan_modes = fan_modes
        else:
            self._fan_modes = ['auto', 'minimum', 'low', 'medium-low', 'medium', 'medium-high', 'high', 'very-high', 'max']
        self._hvac_modes = ["heat", "cool", "dry", "fan_only", "heat_cool", "off"]

    async def async_update(self):
        """Get the latest state from the HVAC."""
        await self._instance.async_update()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def precision(self) -> float:
        return PRECISION_WHOLE

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._uid

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._instance._update_data["room_temperature"] if "room_temperature" in self._instance._update_data else self._instance._update_data["set_temperature"]

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._instance._update_data["set_temperature"] if "set_temperature" in self._instance._update_data else 'unavailable'

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._target_temperature_step

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self._instance._update_data["mode"] if self._instance._update_data["status"] == "On" else "off"

    @property
    def hvac_action(self):
        """Return current operation ie. heat, cool, idle."""
        if self._instance._update_data["status"] == "On":
            if self._instance._update_data["mode"] == HVAC_MODE_HEAT:
                return CURRENT_HVAC_HEAT
            elif self._instance._update_data["mode"] == HVAC_MODE_COOL:
                return CURRENT_HVAC_COOL
            elif self._instance._update_data["mode"]== HVAC_MODE_DRY:
                return CURRENT_HVAC_DRY
            elif self._instance._update_data["mode"] == HVAC_MODE_FAN_ONLY:
                return CURRENT_HVAC_FAN
            elif self._instance._update_data["mode"] == HVAC_MODE_HEAT_COOL:
                if "room_temperature" in self._instance._update_data:
                    if self._instance._update_data["set_temperature"]  < self._instance._update_data["room_temperature"]:
                        return CURRENT_HVAC_COOL
                    elif self._instance._update_data["set_temperature"]  > self._instance._update_data["room_temperature"]:
                        return CURRENT_HVAC_HEAT
                return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_OFF

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._hvac_modes

    @property
    def is_on(self):
        """Return true if the device is on."""
        return True if self._instance._update_data["status"] == "On" else False

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._instance._update_data["fan_speed"] if "fan_speed" in self._instance._update_data else "medium-high"

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_modes

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            await self.hass.async_add_executor_job(self._instance._api.setOperationalTemperature, kwargs.get(ATTR_TEMPERATURE))
            self._instance._update_data["set_temperature"] =  kwargs.get(ATTR_TEMPERATURE)

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        await self.hass.async_add_executor_job(self._instance._api.setFanSpeed, fan_mode)
        self._instance._update_data["fan_speed"] = fan_mode

    async def async_set_hvac_mode(self, hvac_mode):
        _LOGGER.warning(self._instance._update_data)
        """Set new operation mode (including off)"""
        if hvac_mode == "heat_cool":
            await self.hass.async_add_executor_job(self._instance._api.setMode, "auto")
        else:
            await self.hass.async_add_executor_job(self._instance._api.setMode, hvac_mode)
        self._instance._update_data["mode"]  = hvac_mode
        if hvac_mode == "off":
            self._instance._update_data["status"] = "Off"
        else:
            self._instance._update_data["status"] = "On"

    async def async_turn_on(self):
        """Turn on."""
        self.hass.async_add_executor_job(self._instance._api.on())

    async def async_turn_off(self):
        """Turn off."""
        self.hass.async_add_executor_job(self._instance._api.off())
