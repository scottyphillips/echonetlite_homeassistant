"""Support for ECHONETLite sensors."""
import logging

from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE, CONF_IP_ADDRESS, CONF_SENSORS
from homeassistant.helpers.entity import Entity
from homeassistant.util.unit_system import UnitSystem
from pychonet.lib.epc import EPC_CODE 
from pychonet.lib.eojx import EOJX_CLASS

from .const import (
    DOMAIN,
    SENSOR_TYPE_TEMPERATURE,
    HVAC_SENSOR_OP_CODES
)

_LOGGER = logging.getLogger(__name__)

# TODO
async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        _LOGGER.debug("processing entity %s: %s", config.entry_id, config.data["title"])
        if entity['instance_data']['eojgc'] == 1 and entity['instance_data']['eojcc'] == 48: #Home Air Conditioner
            for op_code in HVAC_SENSOR_OP_CODES.keys():
                if op_code in list(entity['API']._api.propertyMaps[159].values()):
                    entities.append(EchonetClimateSensor(entity['API'], op_code, HVAC_SENSOR_OP_CODES[op_code], hass.config.units, config.data["title"]))
        else: #Generic Echonet
            for op_code in EPC_CODE[entity['instance_data']['eojgc']][entity['instance_data']['eojcc']]:
                if op_code in list(entity['API']._api.propertyMaps[159].values()):
                    entities.append(EchonetSensor(entity['API'], op_code, hass.config.units, config.data["title"]))
    async_add_entities(entities, True)


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
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._instance._uid)
            },
            #"name": "",
            #"manufacturer": "Mitsubishi",
            #"model": "",
            #"sw_version": "",
        }

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


class EchonetSensor(Entity):
    def __init__(self, instance, op_code, units: UnitSystem, name=None) -> None:
        """Initialize the sensor."""
        self._instance = instance
        self._eojgc = self._instance._api.eojgc
        self._eojcc = self._instance._api.eojcc
        self._eojci = self._instance._api.instance
        self._op_code = op_code

        if name is None:
            self._name = f"{EOJX_CLASS[self._eojgc][self._eojcc]}-{self._op_code}"
        else:
            self._name = f"{name} {EOJX_CLASS[self._eojgc][self._eojcc]}-{self._op_code}"
        self._uid = f'{self._instance._uid}-{op_code}'
        self._unit_of_measurement = None

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:thermometer"

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
        if EPC_CODE[self._eojgc ][self._eojcc][self._op_code] in self._instance._update_data:
            if len(self._instance._update_data[EPC_CODE[self._eojgc ][self._eojcc][self._op_code]]) < 255:
                return self._instance._update_data[EPC_CODE[self._eojgc ][self._eojcc][self._op_code]] 
            else:
                return 'unavailable'
        return 'unavailable'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    async def async_update(self):
        """Retrieve latest state."""
        await self._instance.async_update()
