"""Support for ECHONETLite sensors."""
import logging

from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE, CONF_IP_ADDRESS, CONF_SENSORS
from homeassistant.helpers.entity import Entity
from homeassistant.util.unit_system import UnitSystem

from .const import (
    DOMAIN,
    ATTR_INSIDE_TEMPERATURE,
    ATTR_OUTSIDE_TEMPERATURE,
    SENSOR_TYPE_TEMPERATURE,
    SENSOR_TYPES,
    HVAC_OP_CODES
)

_LOGGER = logging.getLogger(__name__)
sensors = [ATTR_INSIDE_TEMPERATURE]

async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    instance = hass.data[DOMAIN][config.entry_id]

    # query device to see if outside temp is supported and add the entity  
    if HVAC_OP_CODES["outdoor_temperature"] in instance._api.propertyMaps[159].values(): #outside temperature
        sensors.append(ATTR_OUTSIDE_TEMPERATURE)

    async_add_entities(
        [
            EchonetClimateSensor(instance, sensor, hass.config.units, config.data["title"])
            for sensor in sensors
        ]
    )


class EchonetClimateSensor(Entity):
    """Representation of an ECHONETLite HVAC Sensor."""

    def __init__(self, instance, monitored_state, units: UnitSystem, name=None) -> None:
        """Initialize the sensor."""
        self._instance = instance
        self._update_data = {}
        self._sensor = SENSOR_TYPES.get(monitored_state)
        
        if name is None:
            self._name = f"{self._sensor[CONF_NAME]}"
        else:
            self._name = f"{name} {self._sensor[CONF_NAME]}"
        self._device_attribute = monitored_state
        try:
           self._uid = f'{self._instance._uid}-{self._device_attribute}'
           self._update_data = self._instance._update_data
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
            if self._instance._update_data["room_temperature"] == 126 or self._instance._update_data["room_temperature"] == None:
               return 'unavailable'
            else:
               return self._update_data["room_temperature"]

        if self._device_attribute == ATTR_OUTSIDE_TEMPERATURE:
            if self._instance._update_data["outdoor_temperature"] == 126 or self._instance._update_data["outdoor_temperature"]  == None:
               return 'unavailable'
            else:
               return self._instance._update_data["outdoor_temperature"] 
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    async def async_update(self):
        """Retrieve latest state."""
        await self._instance.async_update()