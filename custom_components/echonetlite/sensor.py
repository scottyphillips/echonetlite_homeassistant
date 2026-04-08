"""Support for ECHONETLite sensors."""

import logging
from logging import config
import voluptuous as vol

from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_SERVICE,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.exceptions import InvalidStateError, NoEntitySpecifiedError

from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.epc_functions import EPC_SUPER_FUNCTIONS

from . import (
    get_name_by_epc_code,
    get_unit_by_devise_class,
    get_device_name,
    regist_as_inputs,
    regist_as_binary_sensor,
)
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


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up entry."""
    entities = []
    platform = entity_platform.async_get_current_platform()
    for entity in hass.data[DOMAIN][config.entry_id]:
        # Reference the wrapper objects
        coordinator = entity["coordinator"]
        connector = entity["echonetlite"]
        _LOGGER.debug(f"Configuring ECHONETLite sensor {entity}")
        _LOGGER.debug(
            f"Update flags for this sensor are {entity['echonetlite']._update_flags_full_list}"
        )
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]

        if entity["echonetlite"]._user_options.get(
            CONF_ENABLE_SUPER_ENERGY,
            ENABLE_SUPER_ENERGY_DEFAULT.get(eojgc, {}).get(eojcc, True),
        ):
            _enl_super_codes = ENL_SUPER_CODES
        else:
            _enl_super_codes = {
                k: v for k, v in ENL_SUPER_CODES.items() if not k in ENL_SUPER_ENERGES
            }
        _enl_op_codes = entity["echonetlite"]._enl_op_codes | _enl_super_codes
        _epc_functions = (
            entity["echonetlite"]._instance.EPC_FUNCTIONS | EPC_SUPER_FUNCTIONS
        )
        # For all other devices, sensors will be configured but customise if applicable.
        for op_code in list(
            set(entity["echonetlite"]._update_flags_full_list)
            - NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(eojcc, set())
        ):
            # Check DeviceClass or regist_as_binary_sensor()
            if isinstance(
                _enl_op_codes.get(op_code, {}).get(CONF_TYPE), BinarySensorDeviceClass
            ) or regist_as_binary_sensor(_epc_functions.get(op_code, None)):
                continue
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
                                    coordinator,
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
                                coordinator,
                                config,
                                op_code,
                                attr,
                            )
                        )
                    continue
                else:
                    entities.append(
                        EchonetSensor(
                            coordinator,
                            config,
                            op_code,
                            _enl_op_codes.get(
                                op_code,
                                ENL_OP_CODES["default"] | {CONF_DISABLED_DEFAULT: True},
                            ),
                            hass,
                        )
                    )
                continue
            entities.append(
                EchonetSensor(
                    coordinator,
                    config,
                    op_code,
                    ENL_OP_CODES["default"],
                    hass,
                )
            )
    async_add_entities(entities, False)


from homeassistant.helpers.update_coordinator import CoordinatorEntity

class EchonetSensor(CoordinatorEntity, SensorEntity):
    """Representation of an ECHONETLite Temperature Sensor."""
    _attr_translation_key = DOMAIN

    def __init__(self, coordinator, config, op_code, attributes, hass=None) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator) # Link to coordinator
        
        connector = coordinator.connector
        self._connector = connector
        self._op_code = op_code
        self._sensor_attributes = attributes

        name = get_device_name(connector, config)
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
        self._attr_name = f"{name} {get_name_by_epc_code(self._eojgc, self._eojcc, self._op_code, self._attr_device_class, self._connector._enl_op_codes.get(self._op_code, {}).get(CONF_NAME))}"

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
    @property
    def native_value(self):
        """Return the state of the sensor using the standard HA property name."""
        # 1. Access the data from the connector/coordinator
        if self._op_code not in self._connector._update_data:
            return None
            
        new_val = self._connector._update_data[self._op_code]
        
        # 2. Extract specific value (Dict or Lambda)
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

        # 3. FIXED: Interactive icon logic
        # Changed 'is None' to 'is not None' so the comparison actually works
        if CONF_ICON_POSITIVE in self._sensor_attributes:
            if self._state_value is not None and self._state_value > 0:
                self._attr_icon = self._sensor_attributes[CONF_ICON_POSITIVE]
            elif self._state_value is not None and self._state_value < 0:
                self._attr_icon = self._sensor_attributes[CONF_ICON_NEGATIVE]
            else:
                self._attr_icon = self._sensor_attributes[CONF_ICON_ZERO]

        # 4. Apply coefficients / Multipliers
        if (
            CONF_MULTIPLIER in self._sensor_attributes
            or CONF_MULTIPLIER_OPCODE in self._sensor_attributes
            or CONF_MULTIPLIER_OPTIONAL_OPCODE in self._sensor_attributes
        ):
            calc_val = self._state_value
            if CONF_MULTIPLIER in self._sensor_attributes:
                calc_val = calc_val * self._sensor_attributes[CONF_MULTIPLIER]
            
            # Opcode Multiplier
            if CONF_MULTIPLIER_OPCODE in self._sensor_attributes:
                m_op = self._sensor_attributes[CONF_MULTIPLIER_OPCODE]
                m_data = self._connector._update_data.get(m_op)
                if m_data is not None:
                    calc_val = calc_val * m_data
                else:
                    return None # Still 'unknown' until multiplier arrives
            
            # Optional Opcode Multiplier
            if CONF_MULTIPLIER_OPTIONAL_OPCODE in self._sensor_attributes:
                m_opt = self._sensor_attributes[CONF_MULTIPLIER_OPTIONAL_OPCODE]
                m_data = self._connector._update_data.get(m_opt)
                if m_data is not None:
                    calc_val = calc_val * m_data
            return calc_val

        # 5. Device Class Overrides
        if self._attr_device_class in [SensorDeviceClass.TEMPERATURE, SensorDeviceClass.HUMIDITY]:
            if self._state_value in [126, 253]:
                return None
            return self._state_value

        if self._attr_device_class == SensorDeviceClass.POWER:
            return 1 if self._state_value == 65534 else self._state_value

        # 6. Final Type Check (FIXED: added check for non-iterable types)
        if isinstance(self._state_value, (int, float)):
            return self._state_value
        
        # Only call len() if it's a string/bytes/list
        if hasattr(self._state_value, "__len__"):
            return self._state_value if len(self._state_value) < 255 else None
            
        return self._state_value

    # async def async_update(self):
    #     """Retrieve latest state."""
    #     try:
    #         await self._connector.async_update()
    #         self._attr_native_value = self.get_attr_native_value()
    #     except TimeoutError:
    #         pass

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

    # async def async_added_to_hass(self):
    #     """Register callbacks."""
    #     self._connector.add_update_option_listener(self.update_option_listener)
    #     self._connector.register_async_update_callbacks(self.async_update_callback)

    # async def async_update_callback(self, isPush: bool = False):
    #     new_val = self._connector._update_data.get(self._op_code)
    #     if "dict_key" in self._sensor_attributes:
    #         if hasattr(new_val, "get"):
    #             new_val = new_val.get(self._sensor_attributes["dict_key"])
    #         else:
    #             new_val = None
    #     if "accessor_lambda" in self._sensor_attributes:
    #         new_val = self._sensor_attributes["accessor_lambda"](
    #             new_val, self._sensor_attributes["accessor_index"]
    #         )
    #     changed = (
    #         new_val is not None and self._state_value != new_val
    #     ) or self._attr_available != self._server_state["available"]
    #     if changed:
    #         _force = bool(not self._attr_available and self._server_state["available"])
    #         self._state_value = new_val
    #         self._attr_native_value = self.get_attr_native_value()
    #         if self._attr_available != self._server_state["available"]:
    #             if self._server_state["available"]:
    #                 self.update_option_listener()
    #             else:
    #                 self._attr_should_poll = True
    #         self._attr_available = self._server_state["available"]
    #         self.async_schedule_update_ha_state(_force)

    def update_option_listener(self):
        _should_poll = self._op_code not in self._connector._ntfPropertyMap
        self._attr_should_poll = (
            self._connector._user_options.get(CONF_FORCE_POLLING, False) or _should_poll
        )
        self._attr_extra_state_attributes = {"notify": "No" if _should_poll else "Yes"}
        _LOGGER.debug(
            f"{self._attr_name}({self._op_code}): _should_poll is {_should_poll}"
        )
