"""Support for ECHONETLite sensors."""
import logging

from homeassistant.const import (
    CONF_ICON, CONF_TYPE, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_ENERGY, PERCENTAGE, POWER_WATT,
    TEMP_CELSIUS, ENERGY_WATT_HOUR,
    STATE_UNAVAILABLE
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.typing import StateType

from pychonet.lib.epc import EPC_CODE, EPC_SUPER
from pychonet.lib.eojx import EOJX_CLASS
from .const import (
    DOMAIN,
    ENL_SENSOR_OP_CODES,
    CONF_STATE_CLASS
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        _LOGGER.debug(f"Configuring ECHONETLite sensor {entity}")
        _LOGGER.debug(f"Update flags for this sensor are {entity['echonetlite']._update_flags_full_list}")
        eojgc = entity['instance']['eojgc']
        eojcc = entity['instance']['eojcc']

        # Home Air Conditioner we dont bother exposing all sensors
        if eojgc == 1 and eojcc == 48:
            _LOGGER.debug("This is an ECHONET climate device so not all sensors will be configured.")
            for op_code in ENL_SENSOR_OP_CODES[eojgc][eojcc].keys():
                if op_code in entity['instance']['getmap']:
                    entities.append(
                        EchonetSensor(
                            entity['echonetlite'],
                            op_code,
                            ENL_SENSOR_OP_CODES[eojgc][eojcc][op_code],
                            config.title
                        )
                    )
        elif eojgc == 1 and eojcc == 53:
            _LOGGER.debug("This is an ECHONET fan device so not all sensors will be configured.")
            for op_code in ENL_SENSOR_OP_CODES[eojgc][eojcc].keys():
                if op_code in entity['instance']['getmap']:
                    entities.append(
                        EchonetSensor(
                            entity['echonetlite'],
                            op_code,
                            ENL_SENSOR_OP_CODES[eojgc][eojcc][op_code],
                            config.title
                        )
                    )
        else:  # handle other ECHONET instances
            for op_code in EPC_CODE[eojgc][eojcc]:
                if eojgc in ENL_SENSOR_OP_CODES.keys():
                    if eojcc in ENL_SENSOR_OP_CODES[eojgc].keys():
                        if op_code in ENL_SENSOR_OP_CODES[eojgc][eojcc].keys():
                            entities.append(
                                EchonetSensor(
                                    entity['echonetlite'],
                                    op_code,
                                    ENL_SENSOR_OP_CODES[eojgc][eojcc][op_code],
                                    config.title
                                )
                            )
                        else:
                            entities.append(
                                EchonetSensor(entity['echonetlite'], op_code, ENL_SENSOR_OP_CODES['default'], config.title)
                            )
                elif op_code in list(entity['echonetlite']._update_flags_full_list):
                    entities.append(
                        EchonetSensor(entity['echonetlite'], op_code, ENL_SENSOR_OP_CODES['default'], config.title)
                    )
    async_add_entities(entities, True)


class EchonetSensor(SensorEntity):
    """Representation of an ECHONETLite Temperature Sensor."""

    def __init__(self, instance, op_code, attributes, name=None) -> None:
        """Initialize the sensor."""
        self._instance = instance
        self._op_code = op_code
        self._sensor_attributes = attributes
        self._eojgc = self._instance._eojgc
        self._eojcc = self._instance._eojcc
        self._eojci = self._instance._eojci
        self._uid = f'{self._instance._host}-{self._eojgc}-{self._eojcc}-{self._eojci}-{self._op_code}'
        self._device_name = name

        # Create name based on sensor description from EPC codes, super class codes or fallback to using the sensor type
        if self._op_code in EPC_CODE[self._eojgc][self._eojcc].keys():
            self._name = f"{name} {EPC_CODE[self._eojgc][self._eojcc][self._op_code]}"
        elif self._op_code in EPC_SUPER.keys():
            self._name = f"{name} {EPC_SUPER[self._op_code]}"
        else:
            self._name = f"{name} self._sensor_attributes[CONF_TYPE]"

        if self._sensor_attributes[CONF_TYPE] == DEVICE_CLASS_TEMPERATURE:
            self._unit_of_measurement = TEMP_CELSIUS
        elif self._sensor_attributes[CONF_TYPE] == DEVICE_CLASS_ENERGY:
            self._unit_of_measurement = ENERGY_WATT_HOUR
        elif self._sensor_attributes[CONF_TYPE] == DEVICE_CLASS_POWER:
            self._unit_of_measurement = POWER_WATT
        elif self._sensor_attributes[CONF_TYPE] == DEVICE_CLASS_HUMIDITY:
            self._unit_of_measurement = PERCENTAGE
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
                (DOMAIN, self._instance._uid, self._instance._eojgc, self._instance._eojcc, self._instance._eojci)
            },
            "name": self._device_name,
            "manufacturer": self._instance._manufacturer,
            "model": EOJX_CLASS[self._eojgc][self._eojcc]
            # "sw_version": "",
        }

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self._op_code in self._instance._update_data:
            if self._instance._update_data[self._op_code] is None:
                return STATE_UNAVAILABLE
            elif self._sensor_attributes[CONF_TYPE] in [
                    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_HUMIDITY
            ]:
                if self._op_code in self._instance._update_data:
                    if self._instance._update_data[self._op_code] in [126, 253]:
                        return STATE_UNAVAILABLE
                    else:
                        return self._instance._update_data[self._op_code]
                else:
                    return STATE_UNAVAILABLE
            elif self._sensor_attributes[CONF_TYPE] == DEVICE_CLASS_POWER:
                if self._op_code in self._instance._update_data:
                    # Underflow (less than 1 W)
                    if self._instance._update_data[self._op_code] == 65534:
                        return 1
                    else:
                        return self._instance._update_data[self._op_code]
                else:
                    return STATE_UNAVAILABLE
            elif self._op_code in self._instance._update_data:
                if isinstance(self._instance._update_data[self._op_code], (int, float)):
                    return self._instance._update_data[self._op_code]
                if len(self._instance._update_data[self._op_code]) < 255:
                    return self._instance._update_data[self._op_code]
                else:
                    return STATE_UNAVAILABLE
        return STATE_UNAVAILABLE

    @property
    def native_unit_of_measurement(self):
        """Return the native unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class."""
        return self._sensor_attributes[CONF_TYPE]

    @property
    def state_class(self):
        """Return the state class type."""
        return self._sensor_attributes[CONF_STATE_CLASS]

    async def async_update(self):
        """Retrieve latest state."""
        await self._instance.async_update()
