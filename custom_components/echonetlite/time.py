import logging
import datetime
from datetime import time
from homeassistant.const import CONF_ICON
from homeassistant.components.time import TimeEntity
from homeassistant.exceptions import InvalidStateError
from . import get_name_by_epc_code
from .const import (
    DOMAIN,
    CONF_FORCE_POLLING,
    ENL_OP_CODES,
    TYPE_TIME,
)
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.epc_functions import _hh_mm

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        _enl_op_codes = ENL_OP_CODES.get(eojgc, {}).get(eojcc, {})
        # configure select entities by looking up full ENL_OP_CODE dict
        for op_code in entity["instance"]["setmap"]:
            epc_function_data = entity["echonetlite"]._instance.EPC_FUNCTIONS.get(
                op_code, None
            )
            _by_epc_func = (
                type(epc_function_data) == list and epc_function_data[0] == _hh_mm
            ) or (callable(epc_function_data) and epc_function_data == _hh_mm)
            if _by_epc_func or TYPE_TIME in _enl_op_codes.get(op_code, {}).keys():
                entities.append(
                    EchonetTime(
                        hass,
                        entity["echonetlite"],
                        config,
                        op_code,
                        _enl_op_codes.get(op_code, {}),
                        entity["echonetlite"]._name or config.title,
                    )
                )

    async_add_entities(entities, True)


class EchonetTime(TimeEntity):
    _attr_translation_key = DOMAIN

    def __init__(self, hass, connector, config, code, options, device_name=None):
        """Initialize the time."""
        self._connector = connector
        self._config = config
        self._code = code
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]
        self._attr_icon = options.get(CONF_ICON, None)
        self._attr_name = f"{config.title} {get_name_by_epc_code(self._connector._eojgc,self._connector._eojcc,self._code)}"
        self._attr_unique_id = (
            f"{self._connector._uidi}-{self._code}"
            if self._connector._uidi
            else f"{self._connector._uid}-{self._code}"
        )

        self._device_name = device_name
        self._attr_native_value = self.get_time()
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
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._instance._eojgc][
                self._connector._instance._eojcc
            ],
            # "sw_version": "",
        }

    def get_time(self):
        hh_mm = self._connector._update_data.get(self._code)
        if hh_mm != None:
            val = hh_mm.split(":")
            time_obj = datetime.time(int(val[0]), int(val[1]))
        else:
            time_obj = None
        return time_obj

    async def async_set_value(self, value: time) -> None:
        """Update the current value."""
        h = int(value.hour)
        m = int(value.minute)
        mes = {"EPC": self._code, "PDC": 0x02, "EDT": h * 256 + m}
        if await self._connector._instance.setMessages([mes]):
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
        new_val = self.get_time()
        changed = (
            self._attr_native_value != new_val
            or self._attr_available != self._server_state["available"]
        )
        if changed:
            _force = bool(not self._attr_available and self._server_state["available"])
            self._attr_native_value = new_val
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
