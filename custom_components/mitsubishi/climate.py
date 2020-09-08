"""
Mitsubishi platform to control HVAC using MAC-568IF-E Interface over ECHONET-lite
Protocol.

EXPERIMENTAL ASYNC UPDATE

Use this custom component for HA 0.96 and above
There are probably a lot of methods in here now that are obsolete with the
revised Climate class in HA 0.96

See https://github.com/home-assistant/home-assistant/pull/23899 for more details

Uses mitsubishi_echonet python Library for API calls.
The library should download automatically and it should download to config/deps

As a last resort if the automatic pip install doesnt work:
1. Download the GIT repo
2. Copy the 'misubishi-echonet' subfolder out of the repo and into 'custom_components
3. Flip the comments on the following lines under setup_platform:
import mitsubishi_echonet as mit
# import custom_components.mitsubishi_echonet as mit
"""


import logging
_LOGGER = logging.getLogger(__name__)

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE, ATTR_FAN_MODES,
    CURRENT_HVAC_OFF, CURRENT_HVAC_HEAT, CURRENT_HVAC_COOL,
    CURRENT_HVAC_DRY, CURRENT_HVAC_IDLE, CURRENT_HVAC_FAN,
    HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_COOL,
    HVAC_MODE_HEAT_COOL, HVAC_MODE_AUTO, HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY)
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE, CONF_HOST, CONF_IP_ADDRESS, CONF_NAME

DOMAIN = "mitsubishi"
REQUIREMENTS = ['mitsubishi_echonet==0.4.1']
SUPPORT_FLAGS = 0

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    import mitsubishi_echonet as mit
    """Set up the Mitsubishi ECHONET climate devices."""
    entities = []
    if config.get(CONF_IP_ADDRESS) is None:
        hvac_list = mit.discover("Home air conditioner")
        if len(hvac_list) > 0:
            for idx, hvac in enumerate(hvac_list):
                entities.append(MitsubishiClimate("hvac_{}".format(idx),
                   hvac, TEMP_CELSIUS))
        else:
            _LOGGER.warning("No ECHONET lite HVAC found")
    else:
        entities.append(MitsubishiClimate(config.get(CONF_NAME),
           mit.HomeAirConditioner(config.get(CONF_IP_ADDRESS)),
           TEMP_CELSIUS, config.get(ATTR_FAN_MODES)))
    async_add_entities(entities)


class MitsubishiClimate(ClimateEntity):

    """Representation of a Mitsubishi ECHONET climate device."""
    def __init__(self, name, echonet_hvac, unit_of_measurement, fan_modes=None):

        """Initialize the climate device."""
        self._name = name
        self._api = echonet_hvac #new line
        _LOGGER.debug("ECHONET lite HVAC %s component added to HA", self._api.netif)

        self._unit_of_measurement = unit_of_measurement
        self._precision = 1.0
        self._support_flags = SUPPORT_FLAGS
        self._support_flags = self._support_flags | SUPPORT_TARGET_TEMPERATURE
        self._support_flags = self._support_flags | SUPPORT_FAN_MODE

        try:
            data = self._api.update()

            # Current and Target temperature
            self._target_temperature = data['set_temperature'] if 'set_temperature' in data else 20
            self._current_temperature = data['room_temperature'] if 'room_temperature' in data else 20

            # Current power setting
            self._on = True if data['status'] == 'On' else False

            # Mode and fan speed
            self._fan_mode= data['fan_speed'] if 'fan_speed' in data else 'medium-high'
            if data['status'] == 'On':
                self._hvac_mode = data['mode'] if 'mode' in data else 'heat_cool'
                if self._hvac_mode == 'auto':
                    self._hvac_mode = 'heat_cool'
            else:
                self._hvac_mode = 'off'

            # self._current_humidity = data['current_humidity'] if 'current_humidity' in data else None
            # self._target_humidity = data['target_humidity'] if 'target_humidity' in data else None
            # self._current_swing_mode = current_swing_mode if 'current_swing_mode' in data else None

        except KeyError:
            _LOGGER.warning("HA requested an update from HVAC %s but no data was received. Using Defaults", self._api.netif)

            self._target_temperature = 20
            self._current_temperature = 20

            # Mode and fan speed
            self._fan_mode= 'medium-high'
            self._hvac_mode = 'off'

            self._current_humidity = None
            self._target_humidity = None

        #self._fan_modes = ['On Low', 'On High', 'Auto Low', 'Auto High', 'Off']
        if fan_modes is not None:
            self._fan_modes = fan_modes
        else:
            self._fan_modes = ['low', 'medium-high']
        self._hvac_modes = ['heat', 'cool', 'dry','fan_only', 'heat_cool', 'off']
        # self._swing_list = ['auto', '1', '2', '3', 'off']

    async def async_update(self):
        """Get the latest state from the HVAC."""
        try:
           await self.hass.async_add_executor_job(self._api.update)
           self._target_temperature = self._api.setTemperature
           self._current_temperature = self._api.roomTemperature
           self._fan_mode = self._api.fan_speed
           self._hvac_mode = self._api.mode if self._api.status == 'On' else 'off'

           # Shim for Home assistants 'auto' vs 'heat_cool' stupidity
           if self._hvac_mode == 'auto':
              self._hvac_mode = 'heat_cool'

           self._on = True if self._api.status == 'On' else False
        except KeyError:
           _LOGGER.warning("HA requested an update from HVAC %s but no data was received", self._api.netif)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

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
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self._hvac_mode

    @property
    def hvac_action(self):
        """Return current operation ie. heat, cool, idle."""
        if self._hvac_mode == HVAC_MODE_HEAT:
           return CURRENT_HVAC_HEAT
        if self._hvac_mode == HVAC_MODE_COOL:
           return CURRENT_HVAC_COOL
        if self._hvac_mode == HVAC_MODE_DRY:
           return CURRENT_HVAC_DRY
        if self._hvac_mode == HVAC_MODE_FAN_ONLY:
           return CURRENT_HVAC_FAN
        if self._hvac_mode == HVAC_MODE_HEAT_COOL:
           if self._target_temperature < self._current_temperature:
               return CURRENT_HVAC_COOL
           if self._target_temperature > self._current_temperature:
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
        return self._on

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_modes

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            await self.hass.async_add_executor_job(self._api.setOperationalTemperature, kwargs.get(ATTR_TEMPERATURE))
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if kwargs.get(ATTR_TARGET_TEMP_HIGH) is not None and \
           kwargs.get(ATTR_TARGET_TEMP_LOW) is not None:
            self._target_temperature_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            self._target_temperature_low = kwargs.get(ATTR_TARGET_TEMP_LOW)

    async def async_set_fan_mode(self, fan_mode):
        """Set new target temperature."""
        await self.hass.async_add_executor_job(self._api.setFanSpeed, fan_mode)
        self._fan_mode = self._api.fan_speed

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new operation mode."""
        if hvac_mode == 'off':
           await self.async_turn_off()
        else:
           if self._on == False:
              await self.async_turn_on()

           # Shim for Home Assistants 'heat_cool' vs 'auto' stupidity
           if hvac_mode ==  'heat_cool':
              await self.hass.async_add_executor_job(self._api.setMode, 'auto')
           else:
              await self.hass.async_add_executor_job(self._api.setMode, hvac_mode)
        self._hvac_mode = hvac_mode

    async def async_turn_on(self):
        """Turn on."""
        self._api.on()
        self._on = True

    async def async_turn_off(self):
        """Turn off."""
        self._api.off()
        self._on = False

#    @property
#    def target_temperature_high(self):
#        """Return the highbound target temperature we try to reach."""
#        return self._target_temperature_high

#    @property
#    def target_temperature_low(self):
#        """Return the lowbound target temperature we try to reach."""
#        return self._target_temperature_low

#    @property
#    def current_swing_mode(self):
#        """Return the swing setting."""
#        return self._current_swing_mode

#    @property
#    def swing_list(self):
#        """List of available swing modes."""
#        return self._swing_list

#    def turn_away_mode_on(self):
#        """Turn away mode on."""
#        self._away = True
#        self.schedule_update_ha_state()

#    def turn_away_mode_off(self):
#        """Turn away mode off."""
#        self._away = False
#        self.schedule_update_ha_state()

#    def set_hold_mode(self, hold_mode):
#        """Update hold_mode on."""
#        self._hold = hold_mode
#        self.schedule_update_ha_state()

#    def turn_aux_heat_on(self):
#        """Turn auxiliary heater on."""
#        self._aux = True
#        self.schedule_update_ha_state()

#    def turn_aux_heat_off(self):
#        """Turn auxiliary heater off."""
#        self._aux = False
#        self.schedule_update_ha_state()

#    def set_humidity(self, humidity):
#        """Set new target temperature."""
#        self._target_humidity = humidity
#        # self.schedule_update_ha_state()

#    def set_swing_mode(self, swing_mode):
#        """Set new target temperature."""
#        self._current_swing_mode = swing_mode
#        # self.schedule_update_ha_state()

#    @property
#    def is_aux_heat_on(self):
#        """Return true if aux heat is on."""
#        return self._aux

#    @property
#    def is_away_mode_on(self):
#        """Return if away mode is on."""
#        return self._away

#    @property
#    def current_hold_mode(self):
#        """Return hold mode setting."""
#        return self._hold

#    @property
#    def current_humidity(self):
#       """Return the current humidity."""
#       return self._current_humidity

#    @property
#    def target_humidity(self):
#        """Return the humidity we try to reach."""
#        return self._target_humidity
