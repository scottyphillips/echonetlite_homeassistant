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

from pychonet.GeneralLighting import ENL_BRIGHTNESS, ENL_COLOR_TEMP

from pychonet.lib.epc import EPC_CODE, EPC_SUPER
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.ElectricBlind import ENL_OPENSTATE
from .const import (
    DOMAIN,
    ENL_OP_CODES,
    CONF_STATE_CLASS,
    TYPE_SWITCH,
    TYPE_SELECT,
    TYPE_TIME,
    TYPE_NUMBER,
    SERVICE_SET_ON_TIMER_TIME,
    SERVICE_SET_INT_1B,
    ENL_STATUS,
    CONF_FORCE_POLLING,
    TYPE_DATA_DICT,
    TYPE_DATA_ARRAY_WITH_SIZE_OPCODE,
    CONF_DISABLED_DEFAULT,
    CONF_MULTIPLIER,
    CONF_MULTIPLIER_OPCODE,
    CONF_MULTIPLIER_OPTIONAL_OPCODE,
    CONF_ICON_POSITIVE,
    CONF_ICON_NEGATIVE,
    CONF_ICON_ZERO,
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
                    _keys = ENL_OP_CODES[eojgc][eojcc][op_code].keys()
                    if (
                        TYPE_SWITCH in _keys
                        or TYPE_SELECT in _keys
                        or TYPE_TIME in _keys
                        or TYPE_NUMBER in _keys
                    ):
                        if op_code in entity["instance"]["setmap"]:
                            continue
                    entities.append(
                        EchonetSensor(
                            entity["echonetlite"],
                            op_code,
                            ENL_OP_CODES[eojgc][eojcc][op_code],
                            entity["echonetlite"]._name or config.title,
                            hass,
                        )
                    )
        elif eojgc == 1 and eojcc == 53:
            _LOGGER.debug(
                "This is an ECHONET fan device so not all sensors will be configured."
            )
            for op_code in ENL_OP_CODES[eojgc][eojcc].keys():
                if op_code in entity["instance"]["getmap"]:
                    _keys = ENL_OP_CODES[eojgc][eojcc][op_code].keys()
                    if (
                        TYPE_SWITCH in _keys
                        or TYPE_SELECT in _keys
                        or TYPE_TIME in _keys
                        or TYPE_NUMBER in _keys
                    ):
                        if op_code in entity["instance"]["setmap"]:
                            continue
                    entities.append(
                        EchonetSensor(
                            entity["echonetlite"],
                            op_code,
                            ENL_OP_CODES[eojgc][eojcc][op_code],
                            entity["echonetlite"]._name or config.title,
                            hass,
                        )
                    )
        else:  # For all other devices, sensors will be configured but customise if applicable.
            for op_code in list(entity["echonetlite"]._update_flags_full_list):
                if (power_switch and ENL_STATUS == op_code) or (
                    mode_select and ENL_OPENSTATE == op_code
                ):
                    continue
                if eojgc == 0x02 and (eojcc == 0x90 or eojcc == 0x91):
                    # General Lighting, Single Function Lighting: skip already handled values
                    if op_code == ENL_BRIGHTNESS or op_code == ENL_COLOR_TEMP:
                        continue
                if eojgc in ENL_OP_CODES.keys():
                    if eojcc in ENL_OP_CODES[eojgc].keys():
                        if op_code in ENL_OP_CODES[eojgc][eojcc].keys():
                            _keys = ENL_OP_CODES[eojgc][eojcc][op_code].keys()
                            if (
                                TYPE_SWITCH in _keys
                                or TYPE_SELECT in _keys
                                or TYPE_TIME in _keys
                                or TYPE_NUMBER in _keys
                            ):
                                if op_code in entity["instance"]["setmap"]:
                                    continue  # dont configure as sensor, it will be configured as switch instead.

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
                                                entity["echonetlite"]._name
                                                or config.title,
                                                hass,
                                            )
                                        )
                                    continue
                                else:
                                    continue
                            if TYPE_DATA_ARRAY_WITH_SIZE_OPCODE in _keys:
                                array_size_op_code = ENL_OP_CODES[eojgc][eojcc][
                                    op_code
                                ][TYPE_DATA_ARRAY_WITH_SIZE_OPCODE]
                                array_max_size = await entity[
                                    "echonetlite"
                                ]._instance.update(array_size_op_code)
                                for x in range(0, array_max_size):
                                    attr = ENL_OP_CODES[eojgc][eojcc][op_code].copy()
                                    attr["accessor_index"] = x
                                    attr["accessor_lambda"] = lambda value, index: (
                                        value["values"][index]
                                        if index < value["range"]
                                        else None
                                    )
                                    entities.append(
                                        EchonetSensor(
                                            entity["echonetlite"],
                                            op_code,
                                            attr,
                                            config.title,
                                        )
                                    )
                                continue
                            else:
                                entities.append(
                                    EchonetSensor(
                                        entity["echonetlite"],
                                        op_code,
                                        ENL_OP_CODES[eojgc][eojcc][op_code],
                                        entity["echonetlite"]._name or config.title,
                                        hass,
                                    )
                                )
                            continue
                entities.append(
                    EchonetSensor(
                        entity["echonetlite"],
                        op_code,
                        ENL_OP_CODES["default"],
                        entity["echonetlite"]._name or config.title,
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
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]
        self._hass = hass
        self._available = True

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

        if "accessor_index" in _attr_keys:
            self._uid += f'-{self._sensor_attributes["accessor_index"]}'
            self._name += f' {str(self._sensor_attributes["accessor_index"] + 1).zfill(len(str(self._sensor_attributes[TYPE_DATA_ARRAY_WITH_SIZE_OPCODE])))}'

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
            "model": EOJX_CLASS[self._eojgc][self._eojcc],
            # "sw_version": "",
        }

    def get_attr_native_value(self):
        """Return the state of the sensor."""
        if self._op_code in self._connector._update_data:
            new_val = self._connector._update_data[self._op_code]
            if "dict_key" in self._sensor_attributes:
                if hasattr(new_val, "get"):
                    self._state_value = new_val.get(self._sensor_attributes["dict_key"])
                else:
                    self._state_value = None
            elif "accessor_lambda" in self._sensor_attributes:
                self._state_value = self._sensor_attributes["accessor_lambda"](
                    new_val, self._sensor_attributes["accessor_index"]
                )
            else:
                self._state_value = new_val

            if self._state_value is None:
                return None

            # interactive icon
            if CONF_ICON_POSITIVE in self._sensor_attributes:
                if self._state_value is None and self._state_value > 0:
                    self._sensor_attributes[CONF_ICON] = self._sensor_attributes[
                        CONF_ICON_POSITIVE
                    ]
                elif self._state_value is None and self._state_value < 0:
                    self._sensor_attributes[CONF_ICON] = self._sensor_attributes[
                        CONF_ICON_NEGATIVE
                    ]
                else:
                    self._sensor_attributes[CONF_ICON] = self._sensor_attributes[
                        CONF_ICON_ZERO
                    ]

            # apply coefficients
            if (
                CONF_MULTIPLIER in self._sensor_attributes
                or CONF_MULTIPLIER_OPCODE in self._sensor_attributes
                or CONF_MULTIPLIER_OPTIONAL_OPCODE in self._sensor_attributes
            ):
                new_val = self._state_value
                if CONF_MULTIPLIER in self._sensor_attributes:
                    new_val = new_val * self._sensor_attributes[CONF_MULTIPLIER]
                if CONF_MULTIPLIER_OPCODE in self._sensor_attributes:
                    multiplier_opcode = self._sensor_attributes[CONF_MULTIPLIER_OPCODE]
                    if (
                        multiplier_opcode in self._connector._update_data
                        and self._connector._update_data[multiplier_opcode] is not None
                    ):
                        new_val = (
                            new_val * self._connector._update_data[multiplier_opcode]
                        )
                    else:
                        return STATE_UNAVAILABLE
                if CONF_MULTIPLIER_OPTIONAL_OPCODE in self._sensor_attributes:
                    multiplier_opcode = self._sensor_attributes[
                        CONF_MULTIPLIER_OPTIONAL_OPCODE
                    ]
                    if (
                        multiplier_opcode in self._connector._update_data
                        and self._connector._update_data[multiplier_opcode] is not None
                    ):
                        new_val = (
                            new_val * self._connector._update_data[multiplier_opcode]
                        )
                return new_val
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

    @property
    def available(self) -> bool:
        """Return true if the device is available."""
        self._available = (
            self._server_state["available"]
            if "available" in self._server_state
            else True
        )
        return self._available

    async def async_update(self):
        """Retrieve latest state."""
        try:
            await self._connector.async_update()
            self._attr_native_value = self.get_attr_native_value()
        except TimeoutError:
            pass

    async def async_set_on_timer_time(self, timer_time):
        val = str(timer_time).split(":")
        hh_mm = ":".join([val[0], val[1]])
        mes = {"EPC": 0x91, "PDC": 0x02, "EDT": int(val[0]) * 256 + int(val[1])}
        if await self._connector._instance.setMessages([mes]):
            pass
        else:
            raise InvalidStateError(
                "The state setting is not supported or is an invalid value."
            )

    async def async_set_value_int_1b(self, value, epc=None):
        if epc:
            value = int(value)
            if await self._connector._instance.setMessage(epc, value):
                pass
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
        if "accessor_lambda" in self._sensor_attributes:
            new_val = self._sensor_attributes["accessor_lambda"](
                new_val, self._sensor_attributes["accessor_index"]
            )
        changed = (
            new_val is not None and self._state_value != new_val
        ) or self._available != self._server_state["available"]
        if changed:
            self._state_value = new_val
            self._attr_native_value = self.get_attr_native_value()
            self.async_schedule_update_ha_state()

    def update_option_listener(self):
        self._should_poll = (
            self._connector._user_options.get(CONF_FORCE_POLLING, False)
            or self._op_code not in self._connector._ntfPropertyMap
        )
        _LOGGER.info(
            f"{self._name}({self._op_code}): _should_poll is {self._should_poll}"
        )
