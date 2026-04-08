import logging
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.exceptions import InvalidStateError
from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_TYPE,
    CONF_MINIMUM,
    CONF_MAXIMUM,
    CONF_UNIT_OF_MEASUREMENT,
)
from pychonet.lib.eojx import EOJX_CLASS
from . import get_name_by_epc_code, get_unit_by_devise_class, get_device_name
from .const import (
    CONF_DISABLED_DEFAULT,
    DOMAIN,
    CONF_FORCE_POLLING,
    CONF_AS_ZERO,
    CONF_MAX_OPC,
    CONF_BYTE_LENGTH,
    NON_SETUP_SINGLE_ENYITY,
    TYPE_NUMBER,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        _enl_op_codes = entity["echonetlite"]._enl_op_codes
        
        # Filter and create Number entities
        for op_code in list(
            set(entity["instance"]["setmap"])
            - NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(eojcc, set())
        ):
            if TYPE_NUMBER in _enl_op_codes.get(op_code, {}).keys():
                entities.append(
                    EchonetNumber(
                        entity["echonetlite"],
                        config,
                        op_code,
                        _enl_op_codes[op_code],
                    )
                )

    async_add_entities(entities, True)

class EchonetNumber(CoordinatorEntity, NumberEntity):
    """Representation of an ECHONETLite number entity."""
    _attr_translation_key = DOMAIN

    def __init__(self, connector, config, code, options):
        super().__init__(connector)
        self._connector = connector
        self._code = code
        self._options = options[TYPE_NUMBER]
        
        # Configuration settings
        self._as_zero = int(self._options.get(CONF_AS_ZERO, 0))
        self._conf_max = int(self._options[CONF_MAXIMUM])
        self._byte_length = int(self._options.get(CONF_BYTE_LENGTH, 1))
        
        # Entity Metadata
        self._device_name = get_device_name(connector, config)
        self._attr_name = f"{config.title} {get_name_by_epc_code(connector._eojgc, connector._eojcc, code, None, options.get(CONF_NAME))}"
        self._attr_unique_id = f"{connector._uidi if connector._uidi else connector._uid}-{code}"
        self._attr_icon = options.get(CONF_ICON)
        self._attr_device_class = self._options.get(CONF_TYPE, options.get(CONF_TYPE))
        self._attr_native_min_value = self._options.get(CONF_MINIMUM, 0) - self._as_zero
        self._attr_entity_registry_enabled_default = not bool(options.get(CONF_DISABLED_DEFAULT))
        
        # Unit of Measurement
        self._attr_native_unit_of_measurement = self._options.get(
            CONF_UNIT_OF_MEASUREMENT, options.get(CONF_UNIT_OF_MEASUREMENT)
        )
        if not self._attr_native_unit_of_measurement:
            self._attr_native_unit_of_measurement = get_unit_by_devise_class(self._attr_device_class)

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        value = self._connector._update_data.get(self._code)
        if value is not None:
            return float(int(value) - self._as_zero)
        return None

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        max_opc = self._options.get(CONF_MAX_OPC)
        max_value = self._conf_max
        
        if max_opc:
            if isinstance(max_opc, list):
                # Handle nested dictionary lookup if applicable
                data = self._connector._update_data.get(max_opc[0])
                if isinstance(data, dict):
                    max_value = data.get(max_opc[1], self._conf_max)
            else:
                max_value = self._connector._update_data.get(max_opc, self._conf_max)
                
        return float(int(max_value) - self._as_zero)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value on the device."""
        if await self._connector._instance.setMessage(
            self._code, int(value + self._as_zero), self._byte_length
        ):
            # Optimistically update the local cache and the UI
            self._connector._update_data[self._code] = int(value + self._as_zero)
            self.async_write_ha_state()
        else:
            raise InvalidStateError("The value setting is not supported by the device.")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._connector._uid, self._connector._instance._eojgc, 
                             self._connector._instance._eojcc, self._connector._instance._eojci)},
            "name": self._device_name,
            "manufacturer": f"{self._connector._manufacturer} {self._connector._host_product_code or ''}".strip(),
            "model": EOJX_CLASS[self._connector._instance._eojgc][self._connector._instance._eojcc],
        }

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        should_poll = self._code not in self._connector._ntfPropertyMap
        return {"notify": "No" if should_poll else "Yes"}