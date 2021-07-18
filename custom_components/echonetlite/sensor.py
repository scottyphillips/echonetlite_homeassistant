"""Support for ECHONETLite sensors."""
import logging

from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE, CONF_IP_ADDRESS, CONF_SENSORS
from homeassistant.helpers.entity import Entity
from homeassistant.util.unit_system import UnitSystem
from pychonet.lib.epc import EPC_CODE 
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.EchonetInstance import ENL_GETMAP
from .const import (
    DOMAIN,
    SENSOR_TYPE_TEMPERATURE,
    ENL_SENSOR_OP_CODES
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity['instance_data']['eojgc']
        eojcc = entity['instance_data']['eojcc']
        
        #Home Air Conditioner we dont bother exposing all sensors
        if eojgc == 1 and eojcc == 48: 
            for op_code in ENL_SENSOR_OP_CODES[eojgc][eojcc].keys():
                if op_code in list(entity['API']._api.propertyMaps[ENL_GETMAP].values()):
                    entities.append(EchonetSensor(entity['API'], op_code, ENL_SENSOR_OP_CODES[eojgc][eojcc][op_code], hass.config.units, config.data["title"]))
        else: #handle other ECHONET instances
            for op_code in EPC_CODE[eojgc][eojcc]:
                if eojgc in ENL_SENSOR_OP_CODES.keys():
                    if eojcc in ENL_SENSOR_OP_CODES[eojgc].keys():
                        if op_code in ENL_SENSOR_OP_CODES[eojgc][eojcc].keys():
                            entities.append(EchonetSensor(entity['API'], op_code, ENL_SENSOR_OP_CODES[eojgc][eojcc][op_code], hass.config.units, config.data["title"]))
                        else:
                            entities.append(EchonetSensor(entity['API'], op_code, ENL_SENSOR_OP_CODES['default'], hass.config.units, config.data["title"]))
                elif op_code in list(entity['API']._api.propertyMaps[ENL_GETMAP].values()):
                    entities.append(EchonetSensor(entity['API'], op_code, ENL_SENSOR_OP_CODES['default'], hass.config.units, config.data["title"]))
    async_add_entities(entities, True)


class EchonetSensor(Entity):
    """Representation of an ECHONETLite Temperature Sensor."""

    def __init__(self, instance, op_code, attributes, units: UnitSystem, name=None) -> None:
        """Initialize the sensor."""
        self._instance = instance
        self._op_code = op_code
        self._sensor_attributes = attributes
        self._eojgc = self._instance._api.eojgc
        self._eojcc = self._instance._api.eojcc
        self._eojci = self._instance._api.instance
        self._name = f"{EPC_CODE[self._eojgc][self._eojcc][self._op_code]}"
        self._uid = f'{self._instance._api.netif}-{self._eojgc}-{self._eojcc}-{self._eojci}-{self._op_code}'
        if self._sensor_attributes[CONF_TYPE] == SENSOR_TYPE_TEMPERATURE:
            self._unit_of_measurement = units.temperature_unit
        else:
            self._unit_of_measurement = None

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
                (DOMAIN, self._instance._uid, self._instance._api.eojgc, self._instance._api.eojcc, self._instance._api.instance)
            },
            "name": EOJX_CLASS[self._eojgc][self._eojcc]
            #"manufacturer": "Mitsubishi",
            #"model": "",
            #"sw_version": "",
        }

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensor_attributes[CONF_TYPE] == SENSOR_TYPE_TEMPERATURE:
            if self._instance._update_data[self._op_code] == 126 or self._instance._update_data[self._op_code]  == None:
                return 'unavailable'
            else:
                return self._instance._update_data[self._op_code]
        elif self._op_code in self._instance._update_data:
            if isinstance(self._instance._update_data[self._op_code], (int,float)):
                return self._instance._update_data[self._op_code] 
            if len(self._instance._update_data[self._op_code]) < 255:
                return self._instance._update_data[self._op_code] 
            else:
                return 'unavailable'
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    async def async_update(self):
        """Retrieve latest state."""
        await self._instance.async_update()
