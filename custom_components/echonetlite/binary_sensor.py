"""Support for ECHONETLite binary sensors."""

import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_TYPE,
)
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
)
from .const import (
    DOMAIN,
    ENL_OP_CODES,
    CONF_STATE_CLASS,
    CONF_FORCE_POLLING,
    TYPE_DATA_DICT,
    TYPE_DATA_ARRAY_WITH_SIZE_OPCODE,
    CONF_DISABLED_DEFAULT,
)

_LOGGER = logging.getLogger(__name__)

# ... (async_setup_entry remains largely the same, just ensure it passes the coordinator) ...


class EchonetBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of an ECHONETLite Binary Sensor."""

    _attr_translation_key = DOMAIN

    def __init__(self, connector, config, op_code, attributes, hass=None) -> None:
        """Initialize the sensor."""
        # Note: connector here should be your DataUpdateCoordinator instance
        super().__init__(connector)

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

        # Use the coordinator's built-in state references
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]

        self._attr_icon = self._sensor_attributes.get(CONF_ICON)
        self._attr_device_class = self._sensor_attributes.get(CONF_TYPE)

        self._attr_name = f"{name} {get_name_by_epc_code(self._eojgc, self._eojcc, self._op_code, self._attr_device_class, self._connector._enl_op_codes.get(self._op_code, {}).get(CONF_NAME))}"

        if "dict_key" in self._sensor_attributes:
            self._attr_unique_id += f'-{self._sensor_attributes["dict_key"]}'
            self._attr_name += f' {self._sensor_attributes["dict_key"]}'

        if "accessor_index" in self._sensor_attributes:
            self._attr_unique_id += f'-{self._sensor_attributes["accessor_index"]}'
            self._attr_name += f' {str(self._sensor_attributes["accessor_index"] + 1)}'

        self._attr_entity_registry_enabled_default = not bool(
            self._sensor_attributes.get(CONF_DISABLED_DEFAULT)
        )

        # Initialize polling/attribute state
        self.update_option_listener()

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        if self._op_code not in self._connector._update_data:
            return None

        new_val = self._connector._update_data[self._op_code]

        # Data extraction logic
        if "dict_key" in self._sensor_attributes:
            if hasattr(new_val, "get"):
                val = new_val.get(self._sensor_attributes["dict_key"])
            else:
                val = None
        elif "accessor_lambda" in self._sensor_attributes:
            val = self._sensor_attributes["accessor_lambda"](
                new_val, self._sensor_attributes["accessor_index"]
            )
        else:
            val = new_val

        if val is None:
            return None

        # Mapping ECHONET values to Boolean
        _results = {
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

        return _results.get(val)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._server_state.get("available", True)

    def update_option_listener(self):
        """Update polling and extra attributes."""
        _should_poll = self._op_code not in self._connector._ntfPropertyMap
        self._attr_should_poll = (
            self._connector._user_options.get(CONF_FORCE_POLLING, False) or _should_poll
        )
        self._attr_extra_state_attributes = {"notify": "No" if _should_poll else "Yes"}

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._connector._uid, self._eojgc, self._eojcc, self._eojci)
            },
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._eojgc][self._eojcc],
        }
