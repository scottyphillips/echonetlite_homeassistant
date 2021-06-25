"""
Mitsubishi platform to control HVAC using MAC-568IF-E Interface over ECHONET-lite
Protocol.

Available on the Home Assistant Community Store

See https://github.com/home-assistant/home-assistant/pull/23899 for more details

Uses mitsubishi_echonet python Library for API calls.
The library should download automatically and it should download to config/deps
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
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE, CONF_HOST, CONF_IP_ADDRESS, CONF_NAME, PRECISION_WHOLE

DOMAIN = "mitsubishi"
REQUIREMENTS = ['mitsubishi_echonet==0.5.1']
SUPPORT_FLAGS = 0
CONF_TARGET_TEMP_STEP = 'target_temp_step'
PARALLEL_UPDATES = 1

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
        _LOGGER.debug("HVAC has the following get properties:")
        _LOGGER.debug(self._api.fetchGetProperties())
        _LOGGER.debug("HVAC has the following set properties:")
        _LOGGER.debug(self._api.fetchSetProperties())
        try:
            self._uid = echonet_hvac.getIdentificationNumber()["identification_number"]
            _LOGGER.debug("HVAC has UID of %s",self._uid)
        except KeyError:
            self._uid = None
        self._unit_of_measurement = unit_of_measurement
        self._precision = 1.0
        self._target_temperature_step = 1
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
            _LOGGER.warning("HA tried to query HVAC at %s but no data was received, so default values are being used. Please check IP connectivity and enable ECHONET", self._api.netif)

            self._target_temperature = 20
            self._current_temperature = 20
            self._on = False
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
        self._extra_attributes = {}

    async def async_update(self):
        """Get the latest state from the HVAC."""
        try:
           _LOGGER.debug("Requesting update from HVAC %s (%s)", self._name, self._api.netif)
           await self.hass.async_add_executor_job(self._api.update)
           _LOGGER.debug("Received response from HVAC %s (%s)", self._name, self._api.netif)
           self._target_temperature = self._api.setTemperature
           self._current_temperature = self._api.roomTemperature
           self._fan_mode = self._api.fan_speed
           self._hvac_mode = self._api.mode if self._api.status == 'On' else 'off'

           # Shim for Home assistants 'auto' vs 'heat_cool' stupidity
           if self._hvac_mode == 'auto':
              self._hvac_mode = 'heat_cool'

           self._on = True if self._api.status == 'On' else False

           if self._api.outdoorTemperature is not None:
              self._extra_attributes['outdoor_temperature'] = self._api.outdoorTemperature

        except KeyError as problem:
           _LOGGER.warning("HA requested an update from HVAC %s (%s) but no data was received", self._name, self._api.netif)
           _LOGGER.debug("The actual python error is: ", problem)

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
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._target_temperature_step

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

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return self._extra_attributes

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
        self.hass.async_add_executor_job(self._api.on())
        self._on = True

    async def async_turn_off(self):
        """Turn off."""
        self.hass.async_add_executor_job(self._api.off())
        self._on = False
