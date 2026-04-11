"""Support for ECHONETLite sensors."""

import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_SERVICE,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers import config_validation as cv, entity_platform
from .base_entity import EchonetEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.exceptions import InvalidStateError, NoEntitySpecifiedError

from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.epc_functions import (
    DATA_STATE_OFF,
    DATA_STATE_ON,
    DATA_STATE_CLOSE,
    DATA_STATE_OPEN,
    EPC_SUPER_FUNCTIONS,
)

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

MAP_BINARY_STATE = {
    True: True,
    "1": True,
    DATA_STATE_ON: True,
    DATA_STATE_OPEN: True,
    "yes": True,
    False: False,
    "0": False,
    DATA_STATE_OFF: False,
    DATA_STATE_CLOSE: False,
    "no": False,
}


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    platform = entity_platform.async_get_current_platform()
    for entity in hass.data[DOMAIN][config.entry_id]:
        _LOGGER.debug(f"Configuring ECHONETLite binary sensor {entity}")
        _LOGGER.debug(
            f"Update flags for this binary sensor are {entity['echonetlite']._update_flags_full_list}"
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
            # Check DeviceClass and regist_as_binary_sensor()
            if not isinstance(
                _enl_op_codes.get(op_code, {}).get(CONF_TYPE), BinarySensorDeviceClass
            ) and not regist_as_binary_sensor(_epc_functions.get(op_code, None)):
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
                                EchonetBinarySensor(
                                    entity["echonetlite"],
                                    config,
                                    op_code,
                                    _enl_op_codes.get(op_code) | {"dict_key": attr_key},
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
                            EchonetBinarySensor(
                                entity["echonetlite"],
                                config,
                                op_code,
                                attr,
                            )
                        )
                    continue
                else:
                    entities.append(
                        EchonetBinarySensor(
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
                EchonetBinarySensor(
                    entity["echonetlite"],
                    config,
                    op_code,
                    ENL_OP_CODES["default"],
                )
            )
    async_add_entities(entities, True)


class EchonetBinarySensor(EchonetEntity, BinarySensorEntity):
    """Representation of an ECHONETLite binary sensor."""

    def __init__(self, coordinator, config, epc_code, attributes) -> None:
        """Initialize the sensor."""
        # Initialize coordinator first - must call parent before setting other properties
        super().__init__(coordinator, config)

        name = get_device_name(coordinator, config)
        self._op_code = epc_code
        self._sensor_attributes = attributes
        self._attr_unique_id = (
            f"{self.coordinator._uidi}-{self._op_code}"
            if self.coordinator._uidi
            else f"{self.coordinator._uid}-{self.coordinator._eojgc}-{self.coordinator._eojcc}-{self.coordinator._eojci}-{self._op_code}"
        )
        self._device_name = name
        self._state_value = None

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

        self._attr_entity_registry_enabled_default = not bool(
            self._sensor_attributes.get(CONF_DISABLED_DEFAULT)
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        raw_val = self.coordinator.data.get(self._op_code)

        # Handle dictionary or array accessors
        if "dict_key" in self._sensor_attributes:
            raw_val = (
                raw_val.get(self._sensor_attributes["dict_key"])
                if hasattr(raw_val, "get")
                else None
            )
        elif "accessor_lambda" in self._sensor_attributes:
            raw_val = self._sensor_attributes["accessor_lambda"](
                raw_val, self._sensor_attributes["accessor_index"]
            )

        return MAP_BINARY_STATE.get(raw_val)

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return device-specific state attributes."""
        # Indicate that updates come from coordinator (both polling and push notifications)
        return {"notify": "Yes"}
