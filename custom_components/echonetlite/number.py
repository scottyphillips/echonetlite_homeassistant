import logging
from homeassistant.const import (
    CONF_ICON,
    CONF_TYPE,
    CONF_MINIMUM,
    CONF_MAXIMUM,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.exceptions import InvalidStateError
from homeassistant.components.number import NumberEntity
from pychonet.lib.eojx import EOJX_CLASS
from . import get_name_by_epc_code, get_unit_by_devise_class
from .const import (
    DOMAIN,
    CONF_FORCE_POLLING,
    ENL_OP_CODES,
    CONF_AS_ZERO,
    CONF_MAX_OPC,
    CONF_BYTE_LENGTH,
    TYPE_NUMBER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        _enl_op_codes = ENL_OP_CODES.get(eojgc, {}).get(eojcc, {})
        # configure select entities by looking up full ENL_OP_CODE dict
        for op_code in entity["instance"]["setmap"]:
            if TYPE_NUMBER in _enl_op_codes.get(op_code, {}).keys():
                entities.append(
                    EchonetNumber(
                        hass,
                        entity["echonetlite"],
                        config,
                        op_code,
                        _enl_op_codes[op_code],
                        entity["echonetlite"]._name or config.title,
                    )
                )

    async_add_entities(entities, True)


class EchonetNumber(NumberEntity):
    _attr_translation_key = DOMAIN

    def __init__(self, hass, connector, config, code, options, name=None):
        """Initialize the number."""
        self._connector = connector
        self._config = config
        self._code = code
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]
        self._attr_icon = options.get(CONF_ICON, None)
        self._attr_name = f"{config.title} {get_name_by_epc_code(self._connector._eojgc, self._connector._eojcc,self._code)}"
        self._attr_unique_id = (
            f"{self._connector._uidi}-{self._code}"
            if self._connector._uidi
            else f"{self._connector._uid}-{self._code}"
        )

        self._options = options[TYPE_NUMBER]
        self._as_zero = int(options[TYPE_NUMBER].get(CONF_AS_ZERO, 0))
        self._conf_max = int(options[TYPE_NUMBER][CONF_MAXIMUM])
        self._byte_length = int(options[TYPE_NUMBER].get(CONF_BYTE_LENGTH, 1))

        self._device_name = name
        self._attr_device_class = self._options.get(
            CONF_TYPE, options.get(CONF_TYPE, None)
        )
        self._attr_native_value = self.get_value()
        self._attr_native_max_value = self.get_max_value()
        self._attr_native_min_value = self._options.get(CONF_MINIMUM, 0) - self._as_zero
        self._attr_native_unit_of_measurement = self._options.get(
            CONF_UNIT_OF_MEASUREMENT, options.get(CONF_UNIT_OF_MEASUREMENT, None)
        )
        if not self._attr_native_unit_of_measurement:
            self._attr_native_unit_of_measurement = get_unit_by_devise_class(
                self._attr_device_class
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
            # "sw_version": "",
        }

    def get_value(self):
        value = self._connector._update_data.get(self._code)
        if value != None:
            return int(self._connector._update_data.get(self._code)) - self._as_zero
        else:
            return None

    def get_max_value(self):
        max_value = self.get_max_opc_value()
        if max_value == None:
            max_value = self._conf_max
        return max_value - self._as_zero

    def get_max_opc_value(self):
        max_opc_value = None
        if self._options.get(CONF_MAX_OPC):
            max_opc_value = self._connector._update_data.get(CONF_MAX_OPC)
            if max_opc_value != None:
                max_opc_value = int(max_opc_value)
        return max_opc_value

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if await self._connector._instance.setMessage(
            self._code, int(value + self._as_zero), self._byte_length
        ):
            # self._connector._update_data[epc] = value
            # self.async_write_ha_state()
            pass
        else:
            raise InvalidStateError(
                "The state setting is not supported or is an invalid value."
            )

    async def async_update(self):
        """Retrieve latest state."""
        try:
            await self._connector.async_update()
        except TimeoutError:
            pass

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush: bool = False):
        new_val = self.get_value()
        changed = (
            self._attr_native_value != new_val
            or self._attr_available != self._server_state["available"]
            or self._attr_native_max_value != self.get_max_value()
        )
        if changed:
            _force = bool(not self._attr_available and self._server_state["available"])
            self._attr_native_value = new_val
            self._attr_native_max_value = self.get_max_value()
            if self._attr_available != self._server_state["available"]:
                if self._server_state["available"]:
                    self.update_option_listener()
                else:
                    self._attr_should_poll = True
            self._attr_available = self._server_state["available"]
            self.async_schedule_update_ha_state(_force)

    def update_option_listener(self):
        _should_poll = self._code not in self._connector._ntfPropertyMap
        self._attr_should_poll = (
            self._connector._user_options.get(CONF_FORCE_POLLING, False) or _should_poll
        )
        self._attr_extra_state_attributes = {"notify": "No" if _should_poll else "Yes"}
        _LOGGER.debug(
            f"{self._device_name}({self._code}): _should_poll is {_should_poll}"
        )
