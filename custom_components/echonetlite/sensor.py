import logging
import voluptuous as vol

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_SERVICE,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.update_coordinator import CoordinatorEntity
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
    entities = []
    platform = entity_platform.async_get_current_platform()

    for entity in hass.data[DOMAIN][config.entry_id]:
        coordinator = entity["coordinator"]
        connector = entity["echonetlite"]
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]

        # Super Energy Logic
        use_super_energy = connector._user_options.get(
            CONF_ENABLE_SUPER_ENERGY,
            ENABLE_SUPER_ENERGY_DEFAULT.get(eojgc, {}).get(eojcc, True),
        )

        _enl_super_codes = (
            ENL_SUPER_CODES
            if use_super_energy
            else {
                k: v for k, v in ENL_SUPER_CODES.items() if k not in ENL_SUPER_ENERGES
            }
        )

        _enl_op_codes = connector._enl_op_codes | _enl_super_codes
        _epc_functions = connector._instance.EPC_FUNCTIONS | EPC_SUPER_FUNCTIONS

        for op_code in list(
            set(connector._update_flags_full_list)
            - NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(eojcc, set())
        ):
            # Filtering logic to ensure we don't create sensors for things handled by switches/selects
            if isinstance(
                _enl_op_codes.get(op_code, {}).get(CONF_TYPE), BinarySensorDeviceClass
            ) or regist_as_binary_sensor(_epc_functions.get(op_code)):
                continue

            _is_settable = op_code in entity["instance"]["setmap"]
            _keys = _enl_op_codes.get(op_code, {}).keys()
            _has_conf_service = CONF_SERVICE in _keys

            if (
                _is_settable
                and not _has_conf_service
                and regist_as_inputs(_epc_functions.get(op_code))
            ):
                continue

            # Handle advanced service registrations
            if _is_settable and _has_conf_service:
                for service_name in _enl_op_codes.get(op_code, {}).get(
                    CONF_SERVICE, []
                ):
                    if service_name == SERVICE_SET_ON_TIMER_TIME:
                        platform.async_register_entity_service(
                            service_name,
                            {vol.Required("timer_time"): cv.time_period},
                            f"async_{service_name}",
                        )
                    elif service_name == SERVICE_SET_INT_1B:
                        platform.async_register_entity_service(
                            service_name,
                            {
                                vol.Required("value"): cv.positive_int,
                                vol.Optional("epc", default=op_code): cv.positive_int,
                            },
                            f"async_{service_name}",
                        )

            # Array and Dictionary data handling
            if TYPE_DATA_DICT in _keys:
                for attr_key in _enl_op_codes[op_code][TYPE_DATA_DICT]:
                    entities.append(
                        EchonetSensor(
                            coordinator,
                            config,
                            op_code,
                            _enl_op_codes[op_code] | {"dict_key": attr_key},
                        )
                    )
                continue

            if TYPE_DATA_ARRAY_WITH_SIZE_OPCODE in _keys:
                array_size_op = _enl_op_codes[op_code][TYPE_DATA_ARRAY_WITH_SIZE_OPCODE]
                array_max_size = await connector._instance.update(array_size_op)
                for x in range(array_max_size):
                    attr = _enl_op_codes[op_code].copy()
                    attr.update(
                        {
                            "accessor_index": x,
                            "accessor_lambda": lambda v, i: (
                                v["values"][i] if i < v["range"] else None
                            ),
                        }
                    )
                    entities.append(EchonetSensor(coordinator, config, op_code, attr))
                continue

            entities.append(
                EchonetSensor(
                    coordinator,
                    config,
                    op_code,
                    _enl_op_codes.get(
                        op_code, ENL_OP_CODES["default"] | {CONF_DISABLED_DEFAULT: True}
                    ),
                )
            )

    async_add_entities(entities, False)


class EchonetSensor(CoordinatorEntity, SensorEntity):
    _attr_translation_key = DOMAIN

    def __init__(self, coordinator, config, op_code, attributes) -> None:
        super().__init__(coordinator)
        self._connector = coordinator.connector
        self._op_code = op_code
        self._sensor_attributes = attributes
        self._device_name = get_device_name(self._connector, config)

        # Identity
        self._attr_unique_id = (
            f"{self._connector._uidi or self._connector._uid}-{self._op_code}"
        )
        if "dict_key" in attributes:
            self._attr_unique_id += f"-{attributes['dict_key']}"
        if "accessor_index" in attributes:
            self._attr_unique_id += f"-{attributes['accessor_index']}"

        # Metadata
        self._attr_device_class = attributes.get(CONF_TYPE)
        self._attr_state_class = attributes.get(CONF_STATE_CLASS)
        self._attr_native_unit_of_measurement = attributes.get(
            CONF_UNIT_OF_MEASUREMENT
        ) or get_unit_by_devise_class(self._attr_device_class)
        self._attr_entity_registry_enabled_default = not bool(
            attributes.get(CONF_DISABLED_DEFAULT)
        )

        # Name construction
        base_name = get_name_by_epc_code(
            self._connector._eojgc,
            self._connector._eojcc,
            self._op_code,
            self._attr_device_class,
            self._connector._enl_op_codes.get(self._op_code, {}).get(CONF_NAME),
        )
        self._attr_name = f"{self._device_name} {base_name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        raw_data = self._connector._update_data.get(self._op_code)
        if raw_data is None:
            return None

        # Value Extraction
        if "dict_key" in self._sensor_attributes:
            val = (
                raw_data.get(self._sensor_attributes["dict_key"])
                if hasattr(raw_data, "get")
                else None
            )
        elif "accessor_lambda" in self._sensor_attributes:
            val = self._sensor_attributes["accessor_lambda"](
                raw_data, self._sensor_attributes.get("accessor_index")
            )
        else:
            val = raw_data

        if val is None:
            return None

        # Multipliers
        calc_val = val
        if CONF_MULTIPLIER in self._sensor_attributes:
            calc_val *= self._sensor_attributes[CONF_MULTIPLIER]

        for m_key in [CONF_MULTIPLIER_OPCODE, CONF_MULTIPLIER_OPTIONAL_OPCODE]:
            if m_key in self._sensor_attributes:
                m_val = self._connector._update_data.get(self._sensor_attributes[m_key])
                if m_val is not None:
                    calc_val *= m_val
                elif m_key == CONF_MULTIPLIER_OPCODE:
                    return None  # Primary multiplier missing

        # Special Device Class Handling
        if self._attr_device_class in [
            SensorDeviceClass.TEMPERATURE,
            SensorDeviceClass.HUMIDITY,
        ] and val in [126, 253]:
            return None
        if self._attr_device_class == SensorDeviceClass.POWER and val == 65534:
            return 1

        # Final string length check for HA safety
        if isinstance(calc_val, str) and len(calc_val) > 255:
            return None

        return calc_val

    @property
    def icon(self):
        """Handle dynamic icons based on value."""
        val = self.native_value
        if CONF_ICON_POSITIVE in self._sensor_attributes and isinstance(
            val, (int, float)
        ):
            if val > 0:
                return self._sensor_attributes[CONF_ICON_POSITIVE]
            if val < 0:
                return self._sensor_attributes[CONF_ICON_NEGATIVE]
            return self._sensor_attributes[CONF_ICON_ZERO]
        return self._sensor_attributes.get(CONF_ICON)

    @property
    def available(self) -> bool:
        return self._connector._api._state[self._connector._instance._host].get(
            "available", True
        )

    @property
    def extra_state_attributes(self):
        should_poll = self._op_code not in self._connector._ntfPropertyMap
        return {"notify": "No" if should_poll else "Yes"}

    @property
    def should_poll(self):
        return self._connector._user_options.get(CONF_FORCE_POLLING, False) or (
            self._op_code not in self._connector._ntfPropertyMap
        )

    async def async_set_on_timer_time(self, timer_time):
        val = str(timer_time).split(":")
        mes = {"EPC": 0x91, "PDC": 0x02, "EDT": int(val[0]) * 256 + int(val[1])}
        if not await self._connector._instance.setMessages([mes]):
            raise InvalidStateError("Timer setting failed.")

    async def async_set_value_int_1b(self, value, epc=None):
        target_epc = epc or self._op_code
        if not await self._connector._instance.setMessage(target_epc, int(value)):
            raise InvalidStateError(f"Setting EPC {target_epc} failed.")

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
            "manufacturer": f"{self._connector._manufacturer} {self._connector._host_product_code or ''}".strip(),
            "model": EOJX_CLASS[self._connector._eojgc][self._connector._eojcc],
        }
