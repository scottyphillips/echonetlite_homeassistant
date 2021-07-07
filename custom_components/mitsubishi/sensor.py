"""Support for Mitsubishi HVAC sensors."""
import logging

from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE, CONF_IP_ADDRESS, CONF_SENSORS
from homeassistant.helpers.entity import Entity
from homeassistant.util.unit_system import UnitSystem

from .const import (
    ATTR_INSIDE_TEMPERATURE,
    ATTR_OUTSIDE_TEMPERATURE,
    SENSOR_TYPE_TEMPERATURE,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    import mitsubishi_echonet as mit
    """Set up the Mitsubishi ECHONET climate devices."""
    mitsubishi_api = mit.HomeAirConditioner(config.get(CONF_IP_ADDRESS))

    # let users (optionally) configure sensors to monitor
    sensors = config.get(CONF_SENSORS)

    # no sensors in configuration, add default sensors
    if sensors is None:
        sensors = [ATTR_INSIDE_TEMPERATURE]

        # query device to see if outside temp is supported and add if so
        hvac_properties = mitsubishi_api.fetchGetProperties()
        if 190 in hvac_properties.values():
            sensors.append(ATTR_OUTSIDE_TEMPERATURE)

    async_add_entities(
        [
            MitsubishiClimateSensor(mitsubishi_api, sensor, hass.config.units, config.get(CONF_NAME))
            for sensor in sensors
        ]
    )


class MitsubishiClimateSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, api, monitored_state, units: UnitSystem, name=None) -> None:
        """Initialize the sensor."""
        self._api = api
        self._update_data = {}
        self._sensor = SENSOR_TYPES.get(monitored_state)

        if name is None:
            name = f"{self._sensor[CONF_NAME]}"
        else:
            self._name = f"{name} {self._sensor[CONF_NAME]}"
        self._device_attribute = monitored_state
        try:
           self._uid = f'{api.getIdentificationNumber()["identification_number"]}-{self._device_attribute}'
           _LOGGER.debug("Sensor has UID of %s",self._uid)
           self._update_data = self._api.update()
        except KeyError:
           self._uid = None
        if self._sensor[CONF_TYPE] == SENSOR_TYPE_TEMPERATURE:
            self._unit_of_measurement = units.temperature_unit


    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._sensor[CONF_ICON]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
         """Return a unique ID."""
         return self._uid

    @property
    def state(self):
        """Return the state of the sensor."""

        if self._device_attribute == ATTR_INSIDE_TEMPERATURE:
            if self._update_data["room_temperature"] == 126 or self._update_data["room_temperature"] == None:
               return 'unavailable'
            else:
               return self._update_data["room_temperature"]

        if self._device_attribute == ATTR_OUTSIDE_TEMPERATURE:
            if self._update_data["outdoor_temperature"] == 126 or self._update_data["outdoor_temperature"]  == None:
               return 'unavailable'
            else:
               return self._update_data["outdoor_temperature"]
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    async def async_update(self):
        """Retrieve latest state."""
        try:
            _LOGGER.debug("Requesting update from HVAC %s (%s)", self._name, self._api.netif)
            self._update_data = await self.hass.async_add_executor_job(self._api.update)
            _LOGGER.debug("Received response from HVAC %s (%s)", self._name, self._api.netif)
        except KeyError:
           _LOGGER.warning("HA requested an update from HVAC %s (%s) but no data was received", self._name, self._api.netif)
