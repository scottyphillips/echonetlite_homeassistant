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

# TODO
async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        if entity['instance_data']['eojgc'] == 1 and entity['instance_data']['eojcc'] == 48: #Home Air Conditioner
            for op_code in HVAC_SENSOR_OP_CODES.keys():
                if op_code in list(entity['API']._api.propertyMaps[159].values()):
                    entities.append(EchonetClimateSensor(entity['API'], op_code, HVAC_SENSOR_OP_CODES[op_code], hass.config.units, config.data["title"]))
    async_add_entities(entities)


class EchonetClimateSensor(Entity):
    """Representation of an ECHONETLite HVAC Sensor."""

    def __init__(self, instance, op_code, attributes, units: UnitSystem, name=None) -> None:
        """Initialize the sensor."""
        self._instance = instance
        self._op_code = op_code
        self._sensor_attributes = attributes

        if name is None:
            self._name = f"{self._sensor_attributes[CONF_NAME]}"
        else:
            self._name = f"{name} {self._sensor_attributes[CONF_NAME]}"
        self._uid = f'{self._instance._uid}-{op_code}'
        if self._sensor_attributes[CONF_TYPE] == SENSOR_TYPE_TEMPERATURE:
            self._unit_of_measurement = units.temperature_unit

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._sensor_attributes[CONF_ICON]

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
        if self._instance._update_data[HVAC_SENSOR_OP_CODES[self._op_code][CONF_NAME]] == 126 or self._instance._update_data[HVAC_SENSOR_OP_CODES[self._op_code][CONF_NAME]]  == None:
            return 'unavailable'
        else:
            return self._instance._update_data[HVAC_SENSOR_OP_CODES[self._op_code][CONF_NAME]]
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    async def async_update(self):
        """Retrieve latest state."""
        await self._instance.async_update()
