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
    HVAC_SENSOR_OP_CODES
)

_LOGGER = logging.getLogger(__name__)
entities = []

# TODO
async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    for entity in hass.data[DOMAIN][config.entry_id]:
        if entity['eojgc'] == 1 and entity['eojcc'] == 48: #Home Air Conditioner
            if HVAC_SENSOR_OP_CODES["Measured value of room temperature"] in list(entity['API']._api.propertyMaps[159].values()): #room temperature
                entities.append(EchonetClimateSensor(entity['API'], ATTR_INSIDE_TEMPERATURE, hass.config.units, config.data["title"]))
            if HVAC_SENSOR_OP_CODES["Measured outdoor air temperature"] in list(entity['API']._api.propertyMaps[159].values()): #outside temperature
                entities.append(EchonetClimateSensor(entity['API'], ATTR_OUTSIDE_TEMPERATURE, hass.config.units, config.data["title"]))
    async_add_entities(entities)


class EchonetClimateSensor(Entity):
    """Representation of an ECHONETLite HVAC Sensor."""

    def __init__(self, instance, monitored_state, units: UnitSystem, name=None) -> None:
        """Initialize the sensor."""
        self._instance = instance
        _LOGGER.debug("sensor init %s",self._instance._update_data)
        self._sensor = SENSOR_TYPES.get(monitored_state)

        if name is None:
            self._name = f"{self._sensor[CONF_NAME]}"
        else:
            self._name = f"{name} {self._sensor[CONF_NAME]}"
        self._device_attribute = monitored_state
        try:
           self._uid = f'{self._instance._uid}-{self._device_attribute}'
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
            if self._instance._update_data["Measured value of room temperature"] == 126 or self._instance._update_data["Measured value of room temperature"] == None:
               return 'unavailable'
            else:
               return self._instance._update_data["Measured value of room temperature"]

        if self._device_attribute == ATTR_OUTSIDE_TEMPERATURE:
            if self._instance._update_data["Measured outdoor air temperature"] == 126 or self._instance._update_data["Measured outdoor air temperature"]  == None:
               return 'unavailable'
            else:
               return self._instance._update_data["Measured outdoor air temperature"]
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    async def async_update(self):
        """Retrieve latest state."""
        await self._instance.async_update()
