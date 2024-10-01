import logging
from homeassistant.const import CONF_ICON
from homeassistant.components.select import SelectEntity
from pychonet.HomeAirConditioner import (
    ENL_AIR_HORZ,
    ENL_AIR_VERT,
    ENL_AUTO_DIRECTION,
    ENL_FANSPEED,
    ENL_HVAC_MODE,
    ENL_SWING_MODE,
)
from . import get_name_by_epc_code, get_device_name
from .const import (
    CONF_DISABLED_DEFAULT,
    DOMAIN,
    CONF_FORCE_POLLING,
    ENL_OP_CODES,
    CONF_ICONS,
    TYPE_SELECT,
    NON_SETUP_SINGLE_ENYITY,
)
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.epc_functions import _swap_dict

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        _enl_op_codes = ENL_OP_CODES.get(eojgc, {}).get(eojcc, {})
        _non_setup_single_entity = NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(
            eojcc, set()
        )
        # configure select entities by looking up full ENL_OP_CODE dict
        for op_code in list(
            set(entity["instance"]["setmap"])
            - NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(eojcc, set())
        ):
            epc_function_data = entity["echonetlite"]._instance.EPC_FUNCTIONS.get(
                op_code, None
            )
            if op_code in _non_setup_single_entity:
                continue
            _by_epc_func = (
                type(epc_function_data) == list
                and type(epc_function_data[1]) == dict
                and len(epc_function_data[1]) > 2
            )
            _enl_op_code_dict = _enl_op_codes.get(op_code, {})
            if _by_epc_func or TYPE_SELECT in _enl_op_code_dict.keys():
                entities.append(
                    EchonetSelect(
                        hass,
                        entity["echonetlite"],
                        config,
                        op_code,
                        _enl_op_code_dict,
                    )
                )

    async_add_entities(entities, True)


class EchonetSelect(SelectEntity):
    _attr_translation_key = DOMAIN

    SELECT_USING_USER_OPTIONS = {
        "0x1-0x30": {
            ENL_FANSPEED,
            ENL_SWING_MODE,
            ENL_AUTO_DIRECTION,
            ENL_AIR_HORZ,
            ENL_AIR_VERT,
            ENL_HVAC_MODE,
        },
        "0x1-0x35": {
            ENL_FANSPEED,
            ENL_SWING_MODE,
            ENL_AUTO_DIRECTION,
            ENL_AIR_HORZ,
            ENL_AIR_VERT,
        },
    }

    def __init__(self, hass, connector, config, code, options):
        """Initialize the select."""
        name = get_device_name(connector, config)
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

        self._user_option_epcs = self.SELECT_USING_USER_OPTIONS.get(
            hex(self._connector._instance._eojgc)
            + "-"
            + hex(self._connector._instance._eojcc),
            set(),
        ).intersection(set(self._connector._user_options.keys()))

        if self._code in self._user_option_epcs:
            if self._connector._user_options[code] is not False:
                self._attr_options = self._connector._user_options[code]
        self._attr_current_option = self._connector._update_data.get(self._code)
        self._attr_name = f"{config.title} {get_name_by_epc_code(self._connector._eojgc,self._connector._eojcc,self._code)}"
        self._attr_unique_id = (
            f"{self._connector._uidi}-{self._code}"
            if self._connector._uidi
            else f"{self._connector._uid}-{self._code}"
        )
        self._device_name = name
        self._attr_should_poll = True
        self._attr_available = True
        self._attr_force_update = False

        self._attr_entity_registry_enabled_default = not bool(
            options.get(CONF_DISABLED_DEFAULT)
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
        if self._code in self._user_option_epcs:
            if self._connector._user_options[self._code] is not False:
                self._attr_options = self._connector._user_options[self._code]

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush: bool = False):
        new_val = self._connector._update_data.get(self._code)
        changed = (
            new_val is not None and self._attr_current_option != new_val
        ) or self._attr_available != self._server_state["available"]
        if changed:
            _force = bool(not self._attr_available and self._server_state["available"])
            self._attr_current_option = new_val
            if self._attr_available != self._server_state["available"]:
                if self._server_state["available"]:
                    self.update_option_listener()
                else:
                    self._attr_should_poll = True
            self._attr_available = self._server_state["available"]
            self.update_attr()
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
