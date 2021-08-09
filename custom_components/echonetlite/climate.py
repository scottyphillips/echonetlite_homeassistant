import logging

_LOGGER = logging.getLogger(__name__)

from pychonet.HomeAirConditioner import (
    ENL_STATUS,
    ENL_FANSPEED,
    ENL_AUTO_DIRECTION,
    ENL_SWING_MODE,
    ENL_AIR_VERT,
    ENL_AIR_HORZ,
    ENL_HVAC_MODE,
    ENL_HVAC_SET_TEMP,
    ENL_HVAC_ROOM_TEMP,
    ENL_HVAC_OUT_TEMP
)

from pychonet.EchonetInstance import ENL_SETMAP, ENL_GETMAP
from pychonet.lib.eojx import EOJX_CLASS

from homeassistant.components.climate import ClimateEntity
from homeassistant.util.unit_system import UnitSystem
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    ATTR_FAN_MODES,
    ATTR_SWING_MODES,
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
from .const import DOMAIN
SUPPORT_FLAGS = 0

DEFAULT_FAN_MODES = ['auto', 'minimum', 'low', 'medium-low', 'medium', 'medium-high', 'high', 'very-high', 'max']
DEFAULT_HVAC_MODES = ["heat", "cool", "dry", "fan_only", "heat_cool", "off"]
DEFAULT_SWING_MODES = ['upper', 'upper-central','central', 'lower-central', 'lower']

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        if entity['instance']['eojgc'] == 0x01 and  entity['instance']['eojcc'] == 0x30 : #Home Air Conditioner
             entities.append(EchonetClimate(config_entry.title, entity['echonetlite'], hass.config.units))
    async_add_devices(entities, True)

"""Representation of an ECHONETLite climate device."""
class EchonetClimate(ClimateEntity):
    def __init__(self, name, connector, units: UnitSystem, fan_modes=None, swing_vert=None):
        """Initialize the climate device."""
        self._name = name
        self._connector = connector  # new line
        self._uid = self._connector._uid
        self._unit_of_measurement = units.temperature_unit
        self._precision = 1.0
        self._target_temperature_step = 1
        self._support_flags = SUPPORT_FLAGS
        self._support_flags = self._support_flags | SUPPORT_TARGET_TEMPERATURE
        if ENL_FANSPEED in list(self._connector._setPropertyMap):
            self._support_flags = self._support_flags | SUPPORT_FAN_MODE
        if ENL_AIR_VERT in list(self._connector._setPropertyMap):
            self._support_flags = self._support_flags | SUPPORT_SWING_MODE
        self._hvac_modes =  DEFAULT_HVAC_MODES

    async def async_update(self):
        """Get the latest state from the HVAC."""
        await self._connector.async_update()

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
    def device_info(self):
        return {
            "identifiers": {
                  (DOMAIN, self._connector._uid, self._connector._instance._eojgc, self._connector._instance._eojcc, self._connector._instance._eojci)
            },
            "name": EOJX_CLASS[self._connector._instance._eojgc][self._connector._instance._eojcc]
            #"manufacturer": "Mitsubishi",
            #"model": "",
            #"sw_version": "",
        }

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
        if ENL_HVAC_ROOM_TEMP in self._connector._api._state[self._connector._instance._host]['instances'][1][48][1][ENL_GETMAP]:
            return self._connector._update_data[ENL_HVAC_ROOM_TEMP] if ENL_HVAC_ROOM_TEMP in self._connector._update_data else 'unavailable'
        else:
            return self._connector._update_data[ENL_HVAC_SET_TEMP]

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._connector._update_data[ENL_HVAC_SET_TEMP] if ENL_HVAC_SET_TEMP in self._connector._update_data else 'unavailable'

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._target_temperature_step

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self._connector._update_data[ENL_HVAC_MODE] if self._connector._update_data[ENL_STATUS] == "On" else "off"

    @property
    def hvac_action(self):
        """Return current operation ie. heat, cool, idle."""
        if self._connector._update_data[ENL_STATUS] == "On":
            if self._connector._update_data[ENL_HVAC_MODE] == HVAC_MODE_HEAT:
                return CURRENT_HVAC_HEAT
            elif self._connector._update_data[ENL_HVAC_MODE] == HVAC_MODE_COOL:
                return CURRENT_HVAC_COOL
            elif self._connector._update_data[ENL_HVAC_MODE]== HVAC_MODE_DRY:
                return CURRENT_HVAC_DRY
            elif self._connector._update_data[ENL_HVAC_MODE] == HVAC_MODE_FAN_ONLY:
                return CURRENT_HVAC_FAN
            elif self._connector._update_data[ENL_HVAC_MODE] == HVAC_MODE_HEAT_COOL:
                if ENL_HVAC_ROOM_TEMP in self._connector._update_data:
                    if self._connector._update_data[ENL_HVAC_SET_TEMP]  < self._connector._update_data[ENL_HVAC_ROOM_TEMP]:
                        return CURRENT_HVAC_COOL
                    elif self._connector._update_data[ENL_HVAC_SET_TEMP]  > self._connector._update_data[ENL_HVAC_ROOM_TEMP]:
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
        return True if self._connector._update_data[ENL_STATUS] == "On" else False

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._connector._update_data[ENL_FANSPEED] if ENL_FANSPEED in self._connector._update_data else "unavailable"

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        if ENL_FANSPEED in list(self._connector._user_options.keys()):
           if self._connector._user_options[ENL_FANSPEED ] is not False:
                return self._connector._user_options[ENL_FANSPEED]
        return DEFAULT_FAN_MODES

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        await self.hass.async_add_executor_job(self._connector._instance.setFanSpeed, fan_mode)
        self._connector._update_data[ENL_FANSPEED] = fan_mode

    @property
    def swing_modes(self):
        """Return the list of available swing modes."""
        if ENL_AIR_VERT in list(self._connector._user_options.keys()):
           if self._connector._user_options[ENL_AIR_VERT ] is not False:
                return self._connector._user_options[ENL_AIR_VERT]
        return DEFAULT_SWING_MODES

    @property
    def swing_mode(self):
        """Return the swing mode setting."""
        return self._connector._update_data[ENL_AIR_VERT] if ENL_AIR_VERT in self._connector._update_data else "unavailable"

    async def async_set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        await self._connector._instance.setAirflowVert(swing_mode)
        self._connector._update_data[ENL_AIR_VERT] = swing_mode

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            await self._connector._instance.setOperationalTemperature(kwargs.get(ATTR_TEMPERATURE))
            self._connector._update_data[ENL_HVAC_SET_TEMP] =  kwargs.get(ATTR_TEMPERATURE)


    async def async_set_hvac_mode(self, hvac_mode):
        # _LOGGER.warning(self._connector._update_data)
        """Set new operation mode (including off)"""
        if hvac_mode == "heat_cool":
            await self._connector._instance.setMode("auto")
        else:
            await self._connector._instance.setMode(hvac_mode)
        self._connector._update_data[ENL_HVAC_MODE]  = hvac_mode
        if hvac_mode == "off":
            self._connector._update_data[ENL_STATUS] = "Off"
        else:
            self._connector._update_data[ENL_STATUS] = "On"

    async def async_turn_on(self):
        """Turn on."""
        await self._connector._instance.on()

    async def async_turn_off(self):
        """Turn off."""
        await self._connector._instance.off()
