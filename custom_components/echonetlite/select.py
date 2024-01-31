import logging
from homeassistant.components.select import SelectEntity
from .const import (
    DOMAIN,
    CONF_FORCE_POLLING,
    ENL_OP_CODES,
    CONF_ICON,
    CONF_ICONS,
    TYPE_SELECT,
)
from pychonet.lib.epc import EPC_CODE
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.epc_functions import _swap_dict

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
                        epc_function_data = entity[
                            "echonetlite"
                        ]._instance.EPC_FUNCTIONS.get(op_code, None)
                        if TYPE_SELECT in ENL_OP_CODES[eojgc][eojcc][
                            op_code
                        ].keys() or (
                            type(epc_function_data) == list
                            and type(epc_function_data[1]) == dict
                            and len(epc_function_data[1]) > 2
                        ):
                            entities.append(
                                EchonetSelect(
                                    hass,
                                    entity["echonetlite"],
                                    config,
                                    op_code,
                                    ENL_OP_CODES[eojgc][eojcc][op_code],
                                    entity["echonetlite"]._name or config.title,
                                )
                            )

    async_add_entities(entities, True)


class EchonetSelect(SelectEntity):
    _attr_translation_key = DOMAIN

    def __init__(self, hass, connector, config, code, options, name=None):
        """Initialize the select."""
        self._connector = connector
        self._config = config
        self._code = code
        self._optimistic = False
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]
        self._sub_state = None
        if type(options.get(TYPE_SELECT)) == dict:
            self._options = options[TYPE_SELECT]
        else:
            # Read from _instance.EPC FUNCTIONS definition
            # Swap key, value of _instance.EPC_FUNCTIONS[opc][1]
            self._options = _swap_dict(connector._instance.EPC_FUNCTIONS[code][1])
        self._icons = options.get(CONF_ICONS, {})
        self._attr_icon = options.get(CONF_ICON, None)
        self._icon_default = self._attr_icon
        self._attr_options = list(self._options.keys())
        if self._code in list(self._connector._user_options.keys()):
            if self._connector._user_options[code] is not False:
                self._attr_options = self._connector._user_options[code]
        self._attr_current_option = self._connector._update_data.get(self._code)
        self._attr_name = f"{config.title} {EPC_CODE[self._connector._eojgc][self._connector._eojcc][self._code]}"
        self._uid = (
            f"{self._connector._uidi}-{self._code}"
            if self._connector._uidi
            else f"{self._connector._uid}-{self._code}"
        )
        self._device_name = name
        self._should_poll = True
        self._available = True
        self._attr_force_update = False
        self.update_option_listener()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._uid

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

    @property
    def available(self) -> bool:
        """Return true if the device is available."""
        self._available = (
            self._server_state["available"]
            if "available" in self._server_state
            else True
        )
        return self._available

    async def async_select_option(self, option: str):
        self._attr_current_option = option
        self.async_schedule_update_ha_state()
        if not await self._connector._instance.setMessage(
            self._code, self._options[option]
        ):
            # Restore previous state
            self._attr_current_option = self._connector._update_data.get(self._code)
            self.async_schedule_update_ha_state()

    async def async_update(self):
        """Retrieve latest state."""
        try:
            await self._connector.async_update()
        except TimeoutError:
            pass

    def update_attr(self):
        self._attr_options = list(self._options.keys())
        if self._attr_current_option not in self._attr_options:
            # maybe data value is raw(int)
            keys = [
                k for k, v in self._options.items() if v == self._attr_current_option
            ]
            if keys:
                self._attr_current_option = keys[0]
        self._attr_icon = self._icons.get(self._attr_current_option, self._icon_default)
        if self._code in list(self._connector._user_options.keys()):
            if self._connector._user_options[self._code] is not False:
                self._attr_options = self._connector._user_options[self._code]

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush=False):
        new_val = self._connector._update_data.get(self._code)
        changed = (
            new_val is not None and self._attr_current_option != new_val
        ) or self._available != self._server_state["available"]
        if changed:
            self._attr_current_option = new_val
            self.update_attr()
            self.async_schedule_update_ha_state()

    def update_option_listener(self):
        self._should_poll = (
            self._connector._user_options.get(CONF_FORCE_POLLING, False)
            or self._code not in self._connector._ntfPropertyMap
        )
        _LOGGER.info(
            f"{self._device_name}({self._code}): _should_poll is {self._should_poll}"
        )
