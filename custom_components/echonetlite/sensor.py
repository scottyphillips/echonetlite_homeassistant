"""Support for ECHONETLite sensors."""

import logging
import voluptuous as vol
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional

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
from .base_entity import EchonetEntity
from homeassistant.exceptions import InvalidStateError, NoEntitySpecifiedError

from pychonet.lib.epc_functions import EPC_SUPER_FUNCTIONS

from . import (
    get_name_by_epc_code,
    get_unit_by_device_class,
    get_device_name,
)
from .connectors import (
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
    NON_SETUP_SINGLE_ENTITY,
    TYPE_SWITCH,
    TYPE_SELECT,
    TYPE_TIME,
    TYPE_NUMBER,
    SERVICE_SET_ON_TIMER_TIME,
    SERVICE_SET_INT_1B,
    CONF_ENABLE_SUPER_ENERGY,
    TYPE_DATA_DICT,
    TYPE_DATA_DICT_OVERRIDES,
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


@dataclass
class ProcessingContext:
    """Carries state through the value processing pipeline."""

    raw_value: Any  # The original value from the coordinator
    current_value: Any  # The value as it evolves through the pipeline
    attributes: dict  # Sensor configuration attributes
    coordinator: Any  # DataUpdateCoordinator
    op_code: int


class ValueProcessor(ABC):
    """Base class for all pipeline stages."""

    @abstractmethod
    def process(self, context: ProcessingContext) -> ProcessingContext:
        pass


class ExtractionProcessor(ValueProcessor):
    """Handles extracting the value from dicts or arrays."""

    def process(self, context: ProcessingContext) -> ProcessingContext:
        val = context.raw_value
        attrs = context.attributes

        if "dict_key" in attrs:
            if hasattr(val, "get"):
                context.current_value = val.get(attrs["dict_key"])
            else:
                context.current_value = None
        elif "accessor_lambda" in attrs:
            context.current_value = attrs["accessor_lambda"](
                val, attrs["accessor_index"]
            )
        return context


class MultiplierProcessor(ValueProcessor):
    """Handles coefficient and multiplier logic."""

    def process(self, context: ProcessingContext) -> ProcessingContext:
        val = context.current_value
        if not isinstance(val, (int, float)):
            return context

        attrs = context.attributes
        res = val

        # Direct Multiplier
        if CONF_MULTIPLIER in attrs:
            res *= attrs[CONF_MULTIPLIER]

        # Opcode-based Multipliers
        for key in [CONF_MULTIPLIER_OPCODE, CONF_MULTIPLIER_OPTIONAL_OPCODE]:
            if key in attrs:
                multiplier_opcode = attrs[key]
                m_val = context.coordinator.data.get(multiplier_opcode)
                if m_val is not None:
                    res *= m_val
                else:
                    # If a required multiplier is missing, we invalidate the value
                    context.current_value = None
                    return context

        context.current_value = res
        return context


class NormalizationProcessor(ValueProcessor):
    """Handles device-specific edge cases and sensor class overrides."""

    def process(self, context: ProcessingContext) -> ProcessingContext:
        val = context.current_value
        if val is None:
            return context

        attrs = context.attributes
        device_class = attrs.get(CONF_TYPE)

        # Temperature/Humidity edge cases (126/253)
        if device_class in [SensorDeviceClass.TEMPERATURE, SensorDeviceClass.HUMIDITY]:
            if val in [126, 253]:
                context.current_value = None
                return context

        # Power underflow (65534 -> 1)
        elif device_class == SensorDeviceClass.POWER:
            if val == 65534:
                context.current_value = 1
                return context

        # Generic safety check for other types
        elif isinstance(val, (int, float)):
            pass
        elif len(str(val)) < 255:
            pass
        else:
            context.current_value = None

        return context


class IconProcessor(ValueProcessor):
    """Handles dynamic icon changes based on value."""

    def process(self, context: ProcessingContext) -> ProcessingContext:
        val = context.current_value
        attrs = context.attributes

        if (
            val is not None
            and isinstance(val, (int, float))
            and CONF_ICON_POSITIVE in attrs
        ):
            if val > 0:
                attrs[CONF_ICON] = attrs[CONF_ICON_POSITIVE]
            elif val < 0:
                attrs[CONF_ICON] = attrs[CONF_ICON_NEGATIVE]
            else:
                attrs[CONF_ICON] = attrs[CONF_ICON_ZERO]

        return context


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
            - NON_SETUP_SINGLE_ENTITY.get(eojgc, {}).get(eojcc, set())
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
                    dict_overrides = _enl_op_codes.get(op_code, {}).get(
                        TYPE_DATA_DICT_OVERRIDES, {}
                    )
                    if isinstance(type_data, list):
                        for attr_key in type_data:
                            base_attrs = _enl_op_codes.get(op_code)
                            # Apply override if defined for this specific dict key
                            if attr_key in dict_overrides:
                                entity_attrs = (
                                    base_attrs | {"dict_key": attr_key} | dict_overrides[attr_key]
                                )
                            else:
                                entity_attrs = base_attrs | {"dict_key": attr_key}
                            entities.append(
                                EchonetSensor(
                                    entity["echonetlite"],
                                    config,
                                    op_code,
                                    entity_attrs,
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
                            _enl_op_codes.get(
                                op_code,
                                ENL_OP_CODES["default"] | {CONF_DISABLED_DEFAULT: True},
                            ),
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


class EchonetSensor(EchonetEntity, SensorEntity):
    """Representation of an ECHONETLite Temperature Sensor."""

    def __init__(self, coordinator, config, epc_code, attributes) -> None:
        """Initialize the sensor.

        Args:
            connector: The ECHONETConnector instance which is also a DataUpdateCoordinator.
            config: The config entry for this integration.
            op_code: The EPC code for this sensor.
            attributes: Sensor configuration attributes.
            hass: Home Assistant instance (optional).
        """
        super().__init__(coordinator, config)

        name = get_device_name(coordinator, config)
        self._op_code = epc_code
        self._sensor_attributes = attributes
        self._attr_unique_id = self._build_unique_id(self._op_code)
        self._device_name = name
        self._server_state = self.coordinator._api._state[
            self.coordinator._instance._host
        ]

        _attr_keys = self._sensor_attributes.keys()

        self._attr_icon = self._sensor_attributes.get(CONF_ICON)
        self._attr_device_class = self._sensor_attributes.get(CONF_TYPE)
        self._attr_state_class = self._sensor_attributes.get(CONF_STATE_CLASS)

        # Create name based on sensor description from EPC codes, super class codes or fallback to using the sensor type
        self._attr_name = f"{name} {get_name_by_epc_code(self.coordinator._eojgc, self.coordinator._eojcc, self._op_code, self._attr_device_class, self.coordinator._enl_op_codes.get(self._op_code, {}).get(CONF_NAME))}"

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
            self._attr_native_unit_of_measurement = get_unit_by_device_class(
                self._attr_device_class
            )
        self._attr_entity_registry_enabled_default = not bool(
            self._sensor_attributes.get(CONF_DISABLED_DEFAULT)
        )

        self._attr_available = True

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.get_attr_native_value()

    def get_attr_native_value(self):
        """Return the state of the sensor using a processing pipeline.

        This method orchestrates several processors to transform raw data into
        the final sensor value.
        """
        if self._op_code not in self.coordinator.data:
            return None

        # 1. Initialize context
        context = ProcessingContext(
            raw_value=self.coordinator.data[self._op_code],
            current_value=self.coordinator.data[self._op_code],
            attributes=self._sensor_attributes,
            coordinator=self.coordinator,
            op_code=self._op_code,
        )

        # 2. Define the pipeline (could be moved to __init__ for performance)
        pipeline: List[ValueProcessor] = [
            ExtractionProcessor(),
            MultiplierProcessor(),
            NormalizationProcessor(),
            IconProcessor(),
        ]

        # 3. Execute the pipeline
        for processor in pipeline:
            context = processor.process(context)

        return context.current_value

    async def async_set_on_timer_time(self, timer_time):
        val = str(timer_time).split(":")
        mes = {"EPC": 0x91, "PDC": 0x02, "EDT": int(val[0]) * 256 + int(val[1])}
        if await self.coordinator._instance.setMessages([mes]):
            pass
        else:
            raise InvalidStateError(
                "The state setting is not supported or is an invalid value."
            )

    async def async_set_value_int_1b(self, value, epc=None):
        if epc:
            value = int(value)
            if await self.coordinator._instance.setMessage(epc, value):
                pass
            else:
                raise InvalidStateError(
                    "The state setting is not supported or is an invalid value."
                )
        else:
            raise NoEntitySpecifiedError(
                "The required parameter EPC has not been specified."
            )
