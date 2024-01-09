"""Support for ECHONETLite sensors."""
import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_ICON,
    CONF_SERVICE,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfEnergy,
    UnitOfVolume,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.typing import StateType
from homeassistant.exceptions import InvalidStateError, NoEntitySpecifiedError

from pychonet.lib.epc import EPC_CODE, EPC_SUPER
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.ElectricBlind import ENL_OPENSTATE
from .const import (
    DOMAIN,
    ENL_OP_CODES,
    CONF_STATE_CLASS,
    TYPE_SWITCH,
    SERVICE_SET_ON_TIMER_TIME,
    SERVICE_SET_INT_1B,
    ENL_STATUS,
    CONF_FORCE_POLLING,
    TYPE_DATA_DICT,
    CONF_DISABLED_DEFAULT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    platform = entity_platform.async_get_current_platform()
    for entity in hass.data[DOMAIN][config.entry_id]:
        _LOGGER.debug(f"Configuring ECHONETLite sensor {entity}")
        _LOGGER.debug(
            f"Update flags for this sensor are {entity['echonetlite']._update_flags_full_list}"
        )
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        power_switch = ENL_STATUS in entity["instance"]["setmap"]
        mode_select = ENL_OPENSTATE in entity["instance"]["setmap"]

        # Home Air Conditioner we dont bother exposing all sensors
        if eojgc == 1 and eojcc == 48:
            _LOGGER.debug(
                "This is an ECHONET climate device so not all sensors will be configured."
            )
            for op_code in ENL_OP_CODES[eojgc][eojcc].keys():
                if op_code in entity["instance"]["getmap"]:
                    entities.append(
                        EchonetSensor(
                            entity["echonetlite"],
                            op_code,
                            ENL_OP_CODES[eojgc][eojcc][op_code],
                            config.title,
                            hass,
                        )
                    )
        elif eojgc == 1 and eojcc == 53:
            _LOGGER.debug(
                "This is an ECHONET fan device so not all sensors will be configured."
            )
            for op_code in ENL_OP_CODES[eojgc][eojcc].keys():
                if op_code in entity["instance"]["getmap"]:
                    entities.append(
                        EchonetSensor(
                            entity["echonetlite"],
                            op_code,
                            ENL_OP_CODES[eojgc][eojcc][op_code],
                            config.title,
                            hass,
                        )
                    )
        else:  # For all other devices, sensors will be configured but customise if applicable.
            for op_code in list(entity["echonetlite"]._update_flags_full_list):
                if (power_switch and ENL_STATUS == op_code) or (
                    mode_select and ENL_OPENSTATE == op_code
                ):
                    continue
                if eojgc in ENL_OP_CODES.keys():
                    if eojcc in ENL_OP_CODES[eojgc].keys():
                        if op_code in ENL_OP_CODES[eojgc][eojcc].keys():
                            _keys = ENL_OP_CODES[eojgc][eojcc][op_code].keys()
                            if (
                                CONF_SERVICE in _keys
                                and op_code in entity["instance"]["setmap"]
                            ):  # Some devices support advanced service calls.
                                for service_name in ENL_OP_CODES[eojgc][eojcc][op_code][
                                    CONF_SERVICE
                                ]:
                                    if service_name == SERVICE_SET_ON_TIMER_TIME:
                                        platform.async_register_entity_service(
                                            service_name,
                                            {
                                                vol.Required(
                                                    "timer_time"
                                                ): cv.time_period
                                            },
                                            "async_" + service_name,
                                        )
                                    elif service_name == SERVICE_SET_INT_1B:
                                        platform.async_register_entity_service(
                                            service_name,
                                            {
                                                vol.Required("value"): cv.positive_int,
                                                vol.Optional(
                                                    "epc", default=op_code
                                                ): cv.positive_int,
                                            },
                                            "async_" + service_name,
                                        )

                            if TYPE_SWITCH in _keys:
                                continue  # dont configure as sensor, it will be configured as switch instead.

                            if TYPE_DATA_DICT in _keys:
                                type_data = ENL_OP_CODES[eojgc][eojcc][op_code][
                                    TYPE_DATA_DICT
                                ]
                                if isinstance(type_data, list):
                                    for attr_key in type_data:
                                        attr = ENL_OP_CODES[eojgc][eojcc][
                                            op_code
                                        ].copy()
                                        attr["dict_key"] = attr_key
                                        entities.append(
                                            EchonetSensor(
                                                entity["echonetlite"],
                                                op_code,
                                                attr,
                                                config.title,
                                                hass,
                                            )
                                        )
                                else:
                                    continue
                            else:
                                entities.append(
                                    EchonetSensor(
                                        entity["echonetlite"],
                                        op_code,
                                        ENL_OP_CODES[eojgc][eojcc][op_code],
                                        config.title,
                                        hass,
                                    )
                                )
                            continue
                entities.append(
                    EchonetSensor(
                        entity["echonetlite"],
                        op_code,
                        ENL_OP_CODES["default"],
                        config.title,
                    )
                )
    async_add_entities(entities, True)


class EchonetSensor(SensorEntity):
    """Representation of an ECHONETLite Temperature Sensor."""

    _attr_translation_key = DOMAIN

    def __init__(self, connector, op_code, attributes, name=None, hass=None) -> None:
        """Initialize the sensor."""
        self._connector = connector
        self._op_code = op_code
        self._sensor_attributes = attributes
        self._eojgc = self._connector._eojgc
        self._eojcc = self._connector._eojcc
        self._eojci = self._connector._eojci
        self._uid = (
            f"{self._connector._uidi}-{self._op_code}"
            if self._connector._uidi
            else f"{self._connector._uid}-{self._eojgc}-{self._eojcc}-{self._eojci}-{self._op_code}"
        )
        self._device_name = name
        self._should_poll = True
        self._state_value = None
        self._hass = hass

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

        if "dict_key" in _attr_keys:
            self._uid += f'-{self._sensor_attributes["dict_key"]}'
            if isinstance(self._sensor_attributes[TYPE_DATA_DICT], int):
                self._name += f' {str(self._sensor_attributes["accessor_index"] + 1).zfill(len(str(self._sensor_attributes[TYPE_DATA_DICT])))}'
            else:
                self._name += f' {self._sensor_attributes["dict_key"]}'

        if CONF_UNIT_OF_MEASUREMENT in _attr_keys:
            self._unit_of_measurement = self._sensor_attributes[
                CONF_UNIT_OF_MEASUREMENT
            ]
        elif self._sensor_attributes[CONF_TYPE] == SensorDeviceClass.TEMPERATURE:
            self._unit_of_measurement = UnitOfTemperature.CELSIUS
        elif self._sensor_attributes[CONF_TYPE] == SensorDeviceClass.ENERGY:
            self._unit_of_measurement = UnitOfEnergy.WATT_HOUR
        elif self._sensor_attributes[CONF_TYPE] == SensorDeviceClass.POWER:
            self._unit_of_measurement = UnitOfPower.WATT
        elif self._sensor_attributes[CONF_TYPE] == SensorDeviceClass.CURRENT:
            self._unit_of_measurement = UnitOfElectricCurrent.AMPERE
        elif self._sensor_attributes[CONF_TYPE] == SensorDeviceClass.VOLTAGE:
            self._unit_of_measurement = UnitOfElectricPotential.VOLT
        elif self._sensor_attributes[CONF_TYPE] == SensorDeviceClass.HUMIDITY:
            self._unit_of_measurement = PERCENTAGE
        elif self._sensor_attributes[CONF_TYPE] == PERCENTAGE:
            self._unit_of_measurement = PERCENTAGE
        elif self._sensor_attributes[CONF_TYPE] == SensorDeviceClass.GAS:
            self._unit_of_measurement = UnitOfVolume.CUBIC_METERS
        elif self._sensor_attributes[CONF_TYPE] == UnitOfVolume.CUBIC_METERS:
            self._unit_of_measurement = UnitOfVolume.CUBIC_METERS
        else:
            self._unit_of_measurement = None

        self.update_option_listener()

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._sensor_attributes[CONF_ICON]

    @property
    def should_poll(self):
        return self._should_poll

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
                (
                    DOMAIN,
                    self._connector._uid,
                    self._connector._eojgc,
                    self._connector._eojcc,
                    self._connector._eojci,
                )
            },
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._eojgc][self._eojcc]
            # "sw_version": "",
        }

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self._op_code in self._connector._update_data:
            new_val = self._connector._update_data[self._op_code]
            if "dict_key" in self._sensor_attributes:
                if hasattr(new_val, "get"):
                    self._state_value = new_val.get(self._sensor_attributes["dict_key"])
                else:
                    self._state_value = None
            else:
                self._state_value = new_val

            if (
                self._op_code == 0xC0 or self._op_code == 0xC1
            ):  # kludge for distribution panel meter.
                if (
                    self._eojgc == 0x02
                    and self._eojcc == 0x87
                    and 0xC2 in self._connector._update_data
                ):
                    if (
                        self._connector._update_data[0xC2] is not None
                        and self._state_value is not None
                    ):
                        return (
                            self._state_value
                            * self._connector._update_data[0xC2]
                            * 1000
                        )  # value in Wh
            if (
                self._op_code == 0xD3
            ):  # for Measured instantaneous charging/discharging electric energy
                if (
                    self._eojgc == 0x02 and self._eojcc == 0x7D
                ):  # for home battery storage
                    if self._state_value is not None:  # electric energy
                        # Change icon
                        if self._state_value > 0:
                            self._sensor_attributes[CONF_ICON] = "mdi:battery-arrow-up"
                        elif self._state_value < 0:
                            self._sensor_attributes[
                                CONF_ICON
                            ] = "mdi:battery-arrow-down"
                        else:
                            self._sensor_attributes[CONF_ICON] = "mdi:battery"
                        self._push_icon_to_frontent()

                        return self._state_value

            if (
                self._op_code == 0xE0
            ):  # kludge for electric energy meter and water volume meters
                if self._eojgc == 0x02 and self._eojcc == 0x79:  # for solar power
                    if self._state_value is not None:  # electric energy
                        # Change icon
                        if self._state_value > 0:
                            self._sensor_attributes[
                                CONF_ICON
                            ] = "mdi:solar-power-variant"
                        else:
                            self._sensor_attributes[
                                CONF_ICON
                            ] = "mdi:solar-power-variant-outline"
                        self._push_icon_to_frontent()

                        return self._state_value
                if (
                    self._eojgc == 0x02
                    and self._eojcc == 0x80
                    and 0xE2 in self._connector._update_data
                ):
                    if (
                        self._connector._update_data[0xE2] is not None
                        and self._state_value is not None
                    ):  # electric energy
                        return (
                            self._state_value
                            * self._connector._update_data[0xE2]
                            * 1000
                        )  # value in Wh

                if (
                    self._eojgc == 0x02
                    and self._eojcc == 0x81
                    and 0xE1 in self._connector._update_data
                ):  # water flow
                    if (
                        self._connector._update_data[0xE1] is not None
                        and self._state_value is not None
                    ):
                        return self._state_value * self._connector._update_data[0xE1]

                if self._eojgc == 0x02 and self._eojcc == 0x82:  # GAS
                    if self._state_value is not None:
                        return self._state_value * 0.001

            if self._op_code in [
                0xE0,
                0xE3,
            ]:  # Measured cumulative amounts normal or revers
                if self._eojgc == 0x02 and self._eojcc == 0x88:
                    if self._connector._update_data.get(0xE1):
                        coef = self._connector._update_data.get(0xD3) or 1
                        return (
                            self._state_value
                            * coef
                            * self._connector._update_data[0xE1]
                        )  # value in kWh
                    else:
                        return None

            if self._state_value is None:
                return None
            elif self._sensor_attributes[CONF_TYPE] in [
                SensorDeviceClass.TEMPERATURE,
                SensorDeviceClass.HUMIDITY,
            ]:
                if self._state_value in [126, 253]:
                    return None
                else:
                    return self._state_value
            elif self._sensor_attributes[CONF_TYPE] == SensorDeviceClass.POWER:
                # Underflow (less than 1 W)
                if self._state_value == 65534:
                    return 1
                else:
                    return self._state_value
            elif self._op_code in self._connector._update_data:
                if isinstance(self._state_value, (int, float)):
                    return self._state_value
                if len(self._state_value) < 255:
                    return self._state_value
                else:
                    return None
        return None

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

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return not bool(self._sensor_attributes.get(CONF_DISABLED_DEFAULT))

    async def async_update(self):
        """Retrieve latest state."""
        try:
            await self._connector.async_update()
        except TimeoutError:
            pass

    def _push_icon_to_frontent(self):
        self._hass.services.async_call(
            "homeassistant",
            "set_entity_icon",
            {
                "entity_id": self.entity_id,
                "icon_path": self._sensor_attributes[CONF_ICON],
            },
            blocking=True,
        )

    async def async_set_on_timer_time(self, timer_time):
        val = str(timer_time).split(":")
        hh_mm = ":".join([val[0], val[1]])
        mes = {"EPC": 0x91, "PDC": 0x02, "EDT": int(val[0]) * 256 + int(val[1])}
        if await self._connector._instance.setMessages([mes]):
            self._connector._update_data[0x91] = hh_mm
            self.async_write_ha_state()
        else:
            raise InvalidStateError(
                "The state setting is not supported or is an invalid value."
            )

    async def async_set_value_int_1b(self, value, epc=None):
        if epc:
            value = int(value)
            if await self._connector._instance.setMessage(epc, value):
                self._connector._update_data[epc] = value
                self.async_write_ha_state()
            else:
                raise InvalidStateError(
                    "The state setting is not supported or is an invalid value."
                )
        else:
            raise NoEntitySpecifiedError(
                "The required parameter EPC has not been specified."
            )

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush=False):
        new_val = self._connector._update_data.get(self._op_code)
        if "dict_key" in self._sensor_attributes:
            if hasattr(new_val, "get"):
                new_val = new_val.get(self._sensor_attributes["dict_key"])
            else:
                new_val = None
        changed = new_val is not None and self._state_value != new_val
        if changed:
            self._state_value = new_val
            self.async_schedule_update_ha_state()

    def update_option_listener(self):
        self._should_poll = (
            self._connector._user_options.get(CONF_FORCE_POLLING, False)
            or self._op_code not in self._connector._ntfPropertyMap
        )
        _LOGGER.info(
            f"{self._name}({self._op_code}): _should_poll is {self._should_poll}"
        )
