"""Support for ECHONETLite sensors."""

import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_ICON,
    CONF_SERVICE,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.exceptions import InvalidStateError, NoEntitySpecifiedError

from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.epc_functions import EPC_SUPER_FUNCTIONS, _hh_mm

from . import get_name_by_epc_code, get_unit_by_devise_class, get_device_name
from .const import (
    DOMAIN,
    ENABLE_SUPER_ENERGY_DEFAULT,
    ENL_OP_CODES,
    CONF_STATE_CLASS,
    ENL_SUPER_CODES,
    ENL_SUPER_ENERGES,
    NON_SETUP_SINGLE_ENYITY,
    TYPE_SWITCH,
    TYPE_SELECT,
    TYPE_TIME,
    TYPE_NUMBER,
    SERVICE_SET_ON_TIMER_TIME,
    SERVICE_SET_INT_1B,
    CONF_FORCE_POLLING,
    CONF_ENABLE_SUPER_ENERGY,
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


#
def regist_as_inputs(epc_function_data):
    if epc_function_data:
        if type(epc_function_data) == list:
            if type(epc_function_data[1]) == dict and len(epc_function_data[1]) > 1:
                return True  # Switch or Select
            if callable(epc_function_data[0]) and epc_function_data[0] == _hh_mm:
                return True  # Time
        elif callable(epc_function_data) and epc_function_data == _hh_mm:
            return True  # Time
    return False


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

        if entity["echonetlite"]._user_options.get(
            CONF_ENABLE_SUPER_ENERGY,
            ENABLE_SUPER_ENERGY_DEFAULT.get(eojgc, {}).get(eojcc, False),
        ):
            _enl_super_codes = ENL_SUPER_CODES
        else:
            _enl_super_codes = {
                k: v for k, v in ENL_SUPER_CODES.items() if not k in ENL_SUPER_ENERGES
            }
        _enl_op_codes = ENL_OP_CODES.get(eojgc, {}).get(eojcc, {}) | _enl_super_codes
        _epc_functions = (
            entity["echonetlite"]._instance.EPC_FUNCTIONS | EPC_SUPER_FUNCTIONS
        )
        # For all other devices, sensors will be configured but customise if applicable.
        for op_code in list(
            set(entity["echonetlite"]._update_flags_full_list)
            - NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(eojcc, set())
        ):
            # Is settable
            _is_settable = op_code in entity["instance"]["setmap"]
            # Conf Keys list
            _keys = _enl_op_codes.get(op_code, {}).keys()
            # For backward compatibility (Deprecated)
            _has_conf_service = CONF_SERVICE in _keys
            # Check this op_code will be configured as input(switch, select ot time) entity
            if (
                _is_settable
                and not _has_conf_service
                and regist_as_inputs(_epc_functions.get(op_code, None))
            ):
                continue
            # Configuration check with ENL_OP_CODE definition
            if len(_keys):
                if (
                    _is_settable
                    and not _has_conf_service
                    and (
                        TYPE_SWITCH in _keys
                        or TYPE_SELECT in _keys
                        or TYPE_TIME in _keys
                        or TYPE_NUMBER in _keys
                    )
                ):
                    continue  # dont configure as sensor, it will be configured as switch, select or time instead.

                # For backward compatibility (Deprecated)
                if (
                    _is_settable and _has_conf_service
                ):  # Some devices support advanced service calls.
                    _enl_op_codes[op_code][CONF_DISABLED_DEFAULT] = True
                    for service_name in _enl_op_codes.get(op_code, {}).get(
                        CONF_SERVICE
                    ):
                        if service_name == SERVICE_SET_ON_TIMER_TIME:
                            platform.async_register_entity_service(
                                service_name,
                                {vol.Required("timer_time"): cv.time_period},
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
                    type_data = _enl_op_codes.get(op_code, {}).get(TYPE_DATA_DICT)
                    if isinstance(type_data, list):
                        for attr_key in type_data:
                            entities.append(
                                EchonetSensor(
                                    entity["echonetlite"],
                                    config,
                                    op_code,
                                    _enl_op_codes.get(op_code) | {"dict_key": attr_key},
                                    hass,
                                )
                            )
                        continue
                    else:
                        continue
                if TYPE_DATA_ARRAY_WITH_SIZE_OPCODE in _keys:
                    array_size_op_code = _enl_op_codes[op_code][
                        TYPE_DATA_ARRAY_WITH_SIZE_OPCODE
                    ]
                    array_max_size = await entity["echonetlite"]._instance.update(
                        array_size_op_code
                    )
                    for x in range(0, array_max_size):
                        attr = _enl_op_codes[op_code].copy()
                        attr["accessor_index"] = x
                        attr["accessor_lambda"] = lambda value, index: (
                            value["values"][index] if index < value["range"] else None
                        )
                        entities.append(
                            EchonetSensor(
                                entity["echonetlite"],
                                config,
                                op_code,
                                attr,
                            )
                        )
                    continue
                else:
                    entities.append(
                        EchonetSensor(
                            entity["echonetlite"],
                            config,
                            op_code,
                            _enl_op_codes[op_code],
                            hass,
                        )
                    )
                continue
            entities.append(
                EchonetSensor(
                    entity["echonetlite"],
                    config,
                    op_code,
                    ENL_OP_CODES["default"],
                )
            )
    async_add_entities(entities, True)


class EchonetSensor(SensorEntity):
    """Representation of an ECHONETLite Temperature Sensor."""

    _attr_translation_key = DOMAIN

    def __init__(self, connector, config, op_code, attributes, hass=None) -> None:
        """Initialize the sensor."""
        name = get_device_name(connector, config)
        self._connector = connector
        self._op_code = op_code
        self._sensor_attributes = attributes
        self._eojgc = self._connector._eojgc
        self._eojcc = self._connector._eojcc
        self._eojci = self._connector._eojci
        self._attr_unique_id = (
            f"{self._connector._uidi}-{self._op_code}"
            if self._connector._uidi
            else f"{self._connector._uid}-{self._eojgc}-{self._eojcc}-{self._eojci}-{self._op_code}"
        )
        self._device_name = name
        self._state_value = None
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]
        self._hass = hass

        _attr_keys = self._sensor_attributes.keys()

        self._attr_icon = self._sensor_attributes.get(CONF_ICON)
        self._attr_device_class = self._sensor_attributes.get(CONF_TYPE)
        self._attr_state_class = self._sensor_attributes.get(CONF_STATE_CLASS)

        # Create name based on sensor description from EPC codes, super class codes or fallback to using the sensor type
        self._attr_name = f"{name} {get_name_by_epc_code(self._eojgc, self._eojcc, self._op_code, self._attr_device_class)}"

        if "dict_key" in _attr_keys:
            self._attr_unique_id += f'-{self._sensor_attributes["dict_key"]}'
            if type(self._sensor_attributes[TYPE_DATA_DICT]) == int:
                # As of Version 3.8.0, no configuration is defined that uses this definition.
                self._attr_name += f' {str(self._sensor_attributes["accessor_index"] + 1).zfill(len(str(self._sensor_attributes[TYPE_DATA_DICT])))}'
            else:
                self._attr_name += f' {self._sensor_attributes["dict_key"]}'

        if "accessor_index" in _attr_keys:
            self._attr_unique_id += f'-{self._sensor_attributes["accessor_index"]}'
            self._attr_name += f' {str(self._sensor_attributes["accessor_index"] + 1).zfill(len(str(self._sensor_attributes[TYPE_DATA_ARRAY_WITH_SIZE_OPCODE])))}'

        self._attr_native_unit_of_measurement = self._sensor_attributes.get(
            CONF_UNIT_OF_MEASUREMENT
        )
        if not self._attr_native_unit_of_measurement:
            self._attr_native_unit_of_measurement = get_unit_by_devise_class(
                self._attr_device_class
            )
        self._attr_entity_registry_enabled_default = not bool(
            self._sensor_attributes.get(CONF_DISABLED_DEFAULT)
        )

        self._attr_should_poll = True
        self._attr_available = True

        self.update_option_listener()

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
            "manufacturer": self._connector._manufacturer
            + (
                " " + self._connector._host_product_code
                if self._connector._host_product_code
                else ""
            ),
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
                        return None
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
            elif self._attr_device_class in [
                SensorDeviceClass.TEMPERATURE,
                SensorDeviceClass.HUMIDITY,
            ]:
                if self._state_value in [126, 253]:
                    return None
                else:
                    return self._state_value
            elif self._attr_device_class == SensorDeviceClass.POWER:
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

    async def async_update(self):
        """Retrieve latest state."""
        try:
            await self._connector.async_update()
            self._attr_native_value = self.get_attr_native_value()
        except TimeoutError:
            pass

    async def async_set_on_timer_time(self, timer_time):
        val = str(timer_time).split(":")
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

    async def async_update_callback(self, isPush: bool = False):
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
        ) or self._attr_available != self._server_state["available"]
        if changed:
            _force = bool(not self._attr_available and self._server_state["available"])
            self._state_value = new_val
            self._attr_native_value = self.get_attr_native_value()
            if self._attr_available != self._server_state["available"]:
                if self._server_state["available"]:
                    self.update_option_listener()
                else:
                    self._attr_should_poll = True
            self._attr_available = self._server_state["available"]
            self.async_schedule_update_ha_state(_force)

    def update_option_listener(self):
        _should_poll = self._op_code not in self._connector._ntfPropertyMap
        self._attr_should_poll = (
            self._connector._user_options.get(CONF_FORCE_POLLING, False) or _should_poll
        )
        self._attr_extra_state_attributes = {"notify": "No" if _should_poll else "Yes"}
        _LOGGER.debug(
            f"{self._attr_name}({self._op_code}): _should_poll is {_should_poll}"
        )
