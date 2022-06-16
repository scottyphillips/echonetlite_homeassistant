"""Support for ECHONETLite sensors."""
import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_ICON, CONF_TYPE, CONF_UNIT_OF_MEASUREMENT, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_ENERGY, PERCENTAGE, POWER_WATT,
    TEMP_CELSIUS, ENERGY_WATT_HOUR, VOLUME_CUBIC_METERS,
    STATE_UNAVAILABLE, DEVICE_CLASS_GAS
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.typing import StateType

from pychonet.lib.epc import EPC_CODE, EPC_SUPER
from pychonet.lib.eojx import EOJX_CLASS
from .const import DOMAIN, ENL_OP_CODES, CONF_STATE_CLASS, TYPE_SWITCH

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
            for op_code in ENL_OP_CODES[eojgc][eojcc].keys():
                if op_code in entity['instance']['getmap']:
                    entities.append(
                        EchonetSensor(
                            entity['echonetlite'],
                            op_code,
                            ENL_OP_CODES[eojgc][eojcc][op_code],
                            config.title
                        )
                    )
        elif eojgc == 1 and eojcc == 53:
            _LOGGER.debug("This is an ECHONET fan device so not all sensors will be configured.")
            for op_code in ENL_OP_CODES[eojgc][eojcc].keys():
                if op_code in entity['instance']['getmap']:
                    entities.append(
                        EchonetSensor(
                            entity['echonetlite'],
                            op_code,
                            ENL_OP_CODES[eojgc][eojcc][op_code],
                            config.title
                        )
                    )
        else:  # For all other devices, sensors will be configured but customise if applicable.
            for op_code in list(entity['echonetlite']._update_flags_full_list):
                if eojgc in ENL_OP_CODES.keys():
                    if eojcc in ENL_OP_CODES[eojgc].keys():
                        if op_code in ENL_OP_CODES[eojgc][eojcc].keys():
                            if TYPE_SWITCH in ENL_OP_CODES[eojgc][eojcc][op_code].keys():
                                continue # dont configure as sensor, it will be configured as switch instead.

                            entities.append(
                                EchonetSensor(
                                    entity['echonetlite'],
                                    op_code,
                                    ENL_OP_CODES[eojgc][eojcc][op_code],
                                    config.title
                                )
                            )
                            continue
                entities.append(
                    EchonetSensor(entity['echonetlite'], op_code, ENL_OP_CODES['default'], config.title)
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

        _attr_keys = self._sensor_attributes.keys()
        if CONF_ICON not in _attr_keys:
            self._sensor_attributes[CONF_ICON] = None
        if CONF_TYPE not in _attr_keys:
            self._sensor_attributes[CONF_TYPE] = None
        if CONF_STATE_CLASS not in _attr_keys:
            self._sensor_attributes[CONF_STATE_CLASS] = None

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
        elif self._sensor_attributes[CONF_TYPE] == PERCENTAGE:
            self._unit_of_measurement = PERCENTAGE
        elif self._sensor_attributes[CONF_TYPE] == DEVICE_CLASS_GAS:
            self._unit_of_measurement = VOLUME_CUBIC_METERS
        elif self._sensor_attributes[CONF_TYPE] == VOLUME_CUBIC_METERS:
            self._unit_of_measurement = VOLUME_CUBIC_METERS
        else:
            if CONF_UNIT_OF_MEASUREMENT in _attr_keys:
                self._unit_of_measurement = self._sensor_attributes[CONF_UNIT_OF_MEASUREMENT]
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
            if self._op_code == 0xC0 or self._op_code == 0xC1: # kludge for distribution panel meter.
               if self._eojgc == 0x02 and self._eojcc == 0x87 and 0xC2 in self._instance._update_data:
                   if self._instance._update_data[0xC2] is not None and self._instance._update_data[self._op_code] is not None:
                        return self._instance._update_data[self._op_code] * self._instance._update_data[0xC2] * 1000 # value in Wh

            if self._op_code == 0xE0: # kludge for electric energy meter and water volume meters
               if self._eojgc == 0x02 and self._eojcc == 0x80 and 0xE2 in self._instance._update_data:
                   if self._instance._update_data[0xE2] is not None and self._instance._update_data[self._op_code] is not None: # electric energy
                       return self._instance._update_data[self._op_code] * self._instance._update_data[0xE2] * 1000 # value in Wh

               if self._eojgc == 0x02 and self._eojcc == 0x81 and 0xE1 in self._instance._update_data: # water flow
                   if self._instance._update_data[0xE1] is not None and self._instance._update_data[self._op_code] is not None:
                       return self._instance._update_data[self._op_code] * self._instance._update_data[0xE1]

               if self._eojgc == 0x02 and self._eojcc == 0x82:  # GAS
                   if self._instance._update_data[self._op_code] is not None:
                       return self._instance._update_data[self._op_code] * 0.001

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
