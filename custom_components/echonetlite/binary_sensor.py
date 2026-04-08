import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE

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
    get_device_name,
    regist_as_binary_sensor,
)
from .const import (
    DOMAIN,
    CONF_FORCE_POLLING,
    TYPE_DATA_DICT,
    TYPE_DATA_ARRAY_WITH_SIZE_OPCODE,
    CONF_DISABLED_DEFAULT,
    NON_SETUP_SINGLE_ENYITY,
    ENL_SUPER_CODES,
    ENL_SUPER_ENERGES,
    CONF_ENABLE_SUPER_ENERGY,
    ENABLE_SUPER_ENERGY_DEFAULT,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up ECHONETLite binary sensors."""
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        coordinator = entity["coordinator"]
        connector = entity["echonetlite"]
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]

        # Handle Super Energy codes based on user options
        enable_super = connector._user_options.get(
            CONF_ENABLE_SUPER_ENERGY,
            ENABLE_SUPER_ENERGY_DEFAULT.get(eojgc, {}).get(eojcc, True),
        )
        
        _enl_super_codes = ENL_SUPER_CODES if enable_super else {
            k: v for k, v in ENL_SUPER_CODES.items() if k not in ENL_SUPER_ENERGES
        }
        
        _enl_op_codes = connector._enl_op_codes | _enl_super_codes
        _epc_functions = connector._instance.EPC_FUNCTIONS | EPC_SUPER_FUNCTIONS

        # Filter properties that should be binary sensors
        for op_code in list(set(connector._update_flags_full_list) - NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(eojcc, set())):
            
            op_config = _enl_op_codes.get(op_code, {})
            # Determine if this is a binary sensor (via DeviceClass or the helper function)
            is_binary = isinstance(op_config.get(CONF_TYPE), BinarySensorDeviceClass) or \
                        regist_as_binary_sensor(_epc_functions.get(op_code))
            
            if not is_binary:
                continue

            # Handle Dictionary types (e.g. status flags grouped in one EPC)
            if TYPE_DATA_DICT in op_config:
                for attr_key in op_config[TYPE_DATA_DICT]:
                    entities.append(EchonetBinarySensor(coordinator, config, op_code, op_config | {"dict_key": attr_key}))
                continue

            # Handle Array types (e.g. multiple circuit breakers or zones)
            if TYPE_DATA_ARRAY_WITH_SIZE_OPCODE in op_config:
                array_size_op = op_config[TYPE_DATA_ARRAY_WITH_SIZE_OPCODE]
                array_max_size = await connector._instance.update(array_size_op)
                for x in range(array_max_size):
                    attr = op_config.copy()
                    attr.update({
                        "accessor_index": x, 
                        "accessor_lambda": lambda v, i: v["values"][i] if i < v["range"] else None
                    })
                    entities.append(EchonetBinarySensor(coordinator, config, op_code, attr))
                continue

            entities.append(EchonetBinarySensor(coordinator, config, op_code, op_config))

    async_add_entities(entities, True)

class EchonetBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of an ECHONETLite Binary Sensor."""
    _attr_translation_key = DOMAIN

    def __init__(self, coordinator, config, op_code, attributes) -> None:
        super().__init__(coordinator)
        self._connector = coordinator.connector
        self._op_code = op_code
        self._sensor_attributes = attributes
        self._device_name = get_device_name(self._connector, config)

        # Unique ID Construction
        uid_base = self._connector._uidi or self._connector._uid
        self._attr_unique_id = f"{uid_base}-{self._connector._eojgc}-{self._connector._eojcc}-{self._op_code}"
        
        if "dict_key" in attributes:
            self._attr_unique_id += f"-{attributes['dict_key']}"
        if "accessor_index" in attributes:
            self._attr_unique_id += f"-{attributes['accessor_index']}"

        self._attr_device_class = attributes.get(CONF_TYPE)
        self._attr_icon = attributes.get(CONF_ICON)
        self._attr_entity_registry_enabled_default = not bool(attributes.get(CONF_DISABLED_DEFAULT))

        # Naming Logic
        base_name = get_name_by_epc_code(
            self._connector._eojgc, 
            self._connector._eojcc, 
            self._op_code, 
            self._attr_device_class, 
            attributes.get(CONF_NAME)
        )
        self._attr_name = f"{self._device_name} {base_name}"
        
        if "dict_key" in attributes:
            self._attr_name += f" {attributes['dict_key']}"
        if "accessor_index" in attributes:
            self._attr_name += f" {attributes['accessor_index'] + 1}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor by parsing raw ECHONET data."""
        raw_val = self._connector._update_data.get(self._op_code)
        if raw_val is None:
            return None

        # Extract value based on type (Dict, Array, or Scalar)
        if "dict_key" in self._sensor_attributes:
            val = raw_val.get(self._sensor_attributes["dict_key"]) if hasattr(raw_val, "get") else None
        elif "accessor_lambda" in self._sensor_attributes:
            val = self._sensor_attributes["accessor_lambda"](raw_val, self._sensor_attributes.get("accessor_index"))
        else:
            val = raw_val

        if val is None:
            return None

        # Mapping truthy ECHONET values
        return val in [True, "1", 1, 0x30, DATA_STATE_ON, DATA_STATE_OPEN, "yes"]

    @property
    def available(self) -> bool:
        """Check availability via the coordinator's API state."""
        return self._connector._api._state[self._connector._instance._host].get("available", True)

    @property
    def extra_state_attributes(self):
        """Standard extra attributes for debugging notification status."""
        should_poll = self._op_code not in self._connector._ntfPropertyMap
        return {"notify": "No" if should_poll else "Yes"}

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._connector._uid, self._connector._eojgc, self._connector._eojcc, self._connector._eojci)},
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._eojgc][self._connector._eojcc],
        }