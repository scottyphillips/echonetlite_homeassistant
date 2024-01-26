import logging
from homeassistant.components.number import NumberEntity
from .const import (
    DOMAIN,
    CONF_FORCE_POLLING,
    ENL_OP_CODES,
    CONF_ICON,
    CONF_NAME,
    CONF_TYPE,
    CONF_MINIMUM,
    CONF_MAXIMUM,
    CONF_AS_ZERO,
    CONF_MAX_OPC,
    CONF_UNIT_OF_MEASUREMENT,
    TYPE_TIME,
    TYPE_NUMBER,
    NumberDeviceClass,
    UnitOfTemperature,
)
from pychonet.lib.epc import EPC_CODE
from pychonet.lib.eojx import EOJX_CLASS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        # configure select entities by looking up full ENL_OP_CODE dict
        for op_code in entity["instance"]["setmap"]:
            if eojgc in ENL_OP_CODES.keys():
                if eojcc in ENL_OP_CODES[eojgc].keys():
                    if op_code in ENL_OP_CODES[eojgc][eojcc].keys():
                        if TYPE_NUMBER in ENL_OP_CODES[eojgc][eojcc][op_code].keys():
                            entities.append(
                                EchonetNumber(
                                    hass,
                                    entity["echonetlite"],
                                    config,
                                    op_code,
                                    ENL_OP_CODES[eojgc][eojcc][op_code],
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
        self._attr_name = f"{config.title} {EPC_CODE[self._connector._eojgc][self._connector._eojcc][self._code]}"
        self._attr_unique_id = (
            f"{self._connector._uidi}-{self._code}"
            if self._connector._uidi
            else f"{self._connector._uid}-{self._code}"
        )

        self._options = options[TYPE_NUMBER]
        self._as_zero = int(options[TYPE_NUMBER].get(CONF_AS_ZERO, 0))
        self._conf_max = int(options[TYPE_NUMBER][CONF_MAXIMUM])

        self._device_name = name
        self._attr_device_class = self._options.get(CONF_TYPE, None)
        self._attr_should_poll = True
        self._attr_available = True
        self._attr_native_value = self.get_value()
        self._attr_native_max_value = self.get_max_value()
        self._attr_native_min_value = self._options.get(CONF_MINIMUM, 0) - self._as_zero
        self._attr_native_unit_of_measurement = options.get(
            CONF_UNIT_OF_MEASUREMENT, None
        )

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
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._instance._eojgc][
                self._connector._instance._eojcc
            ]
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
            self._code, int(value + self._as_zero)
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

    async def async_update_callback(self, isPush=False):
        new_val = self.get_value()
        changed = (
            self._attr_native_value != new_val
            or self._attr_available != self._server_state["available"]
            or self._attr_native_max_value != self.get_max_value()
        )
        if changed:
            self._attr_native_value = new_val
            self._attr_native_max_value = self.get_max_value()
            self._attr_available = self._server_state["available"]
            self.async_schedule_update_ha_state()

    def update_option_listener(self):
        self._attr_should_poll = (
            self._connector._user_options.get(CONF_FORCE_POLLING, False)
            or self._code not in self._connector._ntfPropertyMap
        )
        _LOGGER.info(
            f"{self._device_name}({self._code}): _should_poll is {self._attr_should_poll}"
        )
