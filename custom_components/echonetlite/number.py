import logging
from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_TYPE,
    CONF_MINIMUM,
    CONF_MAXIMUM,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.exceptions import InvalidStateError
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pychonet.lib.eojx import EOJX_CLASS
from . import get_name_by_epc_code, get_unit_by_devise_class, get_device_name
from .const import (
    CONF_DISABLED_DEFAULT,
    DOMAIN,
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
        # configure select entities by looking up full ENL_OP_CODE dict
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
    _attr_translation_key = DOMAIN

    def __init__(self, connector, config, code, options):
        """Initialize the number."""
        super().__init__(connector)

        self._connector = connector
        self._config = config
        self._code = code

        self._attr_icon = options.get(CONF_ICON, None)
        self._attr_name = f"{config.title} {get_name_by_epc_code(self._connector._eojgc, self._connector._eojcc, self._code, None, self._connector._enl_op_codes.get(self._code, {}).get(CONF_NAME))}"
        self._attr_unique_id = (
            f"{self._connector._uidi}-{self._code}"
            if self._connector._uidi
            else f"{self._connector._uid}-{self._code}"
        )

        self._options = options[TYPE_NUMBER]
        self._as_zero = int(options[TYPE_NUMBER].get(CONF_AS_ZERO, 0))
        self._conf_max = int(options[TYPE_NUMBER][CONF_MAXIMUM])
        self._byte_length = int(options[TYPE_NUMBER].get(CONF_BYTE_LENGTH, 1))

        self._device_name = get_device_name(connector, config)
        self._attr_device_class = self._options.get(
            CONF_TYPE, options.get(CONF_TYPE, None)
        )

        # Initialize values via properties - coordinator handles updates automatically
        self._attr_entity_registry_enabled_default = not bool(
            options.get(CONF_DISABLED_DEFAULT)
        )

    @property
    def native_value(self):
        """Return the current value."""
        if self.coordinator and self.coordinator.data:
            value = self.coordinator.data.get(self._code)
            if value is not None:
                return int(value) - self._as_zero
        # Fallback to connector data if coordinator data not available yet
        value = self._connector._update_data.get(self._code)
        if value is not None:
            return int(value) - self._as_zero
        return None

    @property
    def native_min_value(self):
        """Return the minimum value."""
        return self._options.get(CONF_MINIMUM, 0) - self._as_zero

    @property
    def native_max_value(self):
        """Return the maximum value."""
        # Calculate max OPC value inline from coordinator data
        max_opc = self._options.get(CONF_MAX_OPC)
        if max_opc:
            if isinstance(max_opc, list):
                # Handle nested dictionary access
                master_data = self.coordinator.data if self.coordinator else {}
                outer_value = master_data.get(max_opc[0])
                if outer_value and isinstance(outer_value, dict):
                    max_opc_value = outer_value.get(max_opc[1])
                else:
                    # Fallback to connector data
                    outer_value = self._connector._update_data.get(max_opc[0])
                    if outer_value and isinstance(outer_value, dict):
                        max_opc_value = outer_value.get(max_opc[1])
                    else:
                        return None
            else:
                master_data = self.coordinator.data if self.coordinator else {}
                max_opc_value = master_data.get(max_opc)
                if max_opc_value is None:
                    # Fallback to connector data
                    max_opc_value = self._connector._update_data.get(max_opc)

            if max_opc_value is not None:
                return int(max_opc_value) - self._as_zero
        return self._conf_max - self._as_zero

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    self._connector._uid,
                    self._connector._instance._eojgc,
                    self._connector._instance._eojcc,
                    self._connector._instance._eojci,
                )
            },
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer
            + (
                " " + self._connector._host_product_code
                if self._connector._host_product_code
                else ""
            ),
            "model": EOJX_CLASS[self._connector._instance._eojgc][
                self._connector._instance._eojcc
            ],
        }

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if await self._connector._instance.setMessage(
            self._code, int(value + self._as_zero), self._byte_length
        ):
            pass
        else:
            raise InvalidStateError(
                "The state setting is not supported or is an invalid value."
            )

    async def async_added_to_hass(self):
        """Register callbacks (handled automatically by CoordinatorEntity)."""
        await super().async_added_to_hass()
