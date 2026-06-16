import logging
from homeassistant.const import CONF_ICON, CONF_NAME
from homeassistant.components.select import SelectEntity
from .base_entity import EchonetEntity
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
    CONF_ICONS,
    TYPE_SELECT,
    NON_SETUP_SINGLE_ENTITY,
)
from pychonet.lib.epc_functions import _swap_dict

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        _enl_op_codes = entity["echonetlite"]._enl_op_codes
        _non_setup_single_entity = NON_SETUP_SINGLE_ENTITY.get(eojgc, {}).get(
            eojcc, set()
        )
        # configure select entities by looking up full ENL_OP_CODE dict
        for op_code in list(
            set(entity["instance"]["setmap"])
            - NON_SETUP_SINGLE_ENTITY.get(eojgc, {}).get(eojcc, set())
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
                        entity["echonetlite"],
                        config,
                        _enl_op_code_dict,
                        op_code,
                    )
                )

    async_add_entities(entities, True)


class EchonetSelect(EchonetEntity, SelectEntity):

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

    def __init__(self, coordinator, config, options, epc_code):
        """Initialize the select."""
        super().__init__(coordinator, config)
        self._config = config
        self._code = epc_code
        self._optimistic = False
        self._server_state = self.coordinator._api._state[
            self.coordinator._instance._host
        ]
        self._sub_state = None
        if type(options.get(TYPE_SELECT)) == dict:
            self._options = options[TYPE_SELECT]
        else:
            # Read from _instance.EPC FUNCTIONS definition
            # Swap key, value of _instance.EPC_FUNCTIONS[opc][1]
            self._options = _swap_dict(
                self.coordinator._instance.EPC_FUNCTIONS[epc_code][1]
            )
        self._icons = options.get(CONF_ICONS, {})
        self._attr_icon = options.get(CONF_ICON, None)
        self._icon_default = self._attr_icon
        self._attr_options = list(self._options.keys())

        self._user_option_epcs = self.SELECT_USING_USER_OPTIONS.get(
            hex(self.coordinator._instance._eojgc)
            + "-"
            + hex(self.coordinator._instance._eojcc),
            set(),
        ).intersection(set(self.coordinator._user_options.keys()))

        if self._code in self._user_option_epcs:
            if self.coordinator._user_options[epc_code] is not False:
                self._attr_options = self.coordinator._user_options[epc_code]
        self._attr_current_option = self.coordinator.data.get(self._code)
        self._attr_name = f"{config.title} {get_name_by_epc_code(self.coordinator._eojgc, self.coordinator._eojcc, self._code, None, self.coordinator._enl_op_codes.get(self._code, {}).get(CONF_NAME))}"
        self._attr_unique_id = self._build_unique_id(self._code)
        self._attr_available = True
        self._attr_force_update = False

        self._attr_entity_registry_enabled_default = not bool(
            options.get(CONF_DISABLED_DEFAULT)
        )

        # self.update_option_listener()

    @property
    def options(self) -> list:
        """Return available select options, with user override support."""
        if self._code in self._user_option_epcs:
            if self.coordinator._user_options[self._code] is not False:
                return self.coordinator._user_options[self._code]
        return list(self._options.keys())

    @property
    def current_option(self) -> str | None:
        """Return current option with fallback for raw int values, reading fresh from coordinator."""
        val = self.coordinator.data.get(self._code)
        if val is not None and val not in self.options:
            # Handle raw int case - reverse lookup in _options dict
            keys = [k for k, v in self._options.items() if v == val]
            if keys:
                return keys[0]
        return val

    @property
    def icon(self) -> str | None:
        """Return icon for current option with default fallback."""
        return self._icons.get(self.current_option, self._icon_default)

    async def async_select_option(self, option: str):
        self._attr_current_option = option
        # self.async_schedule_update_ha_state()
        if not await self.coordinator._instance.setMessage(
            self._code, self._options[option]
        ):
            # Restore previous state
            self._attr_current_option = self.coordinator.data.get(self._code)
        #    self.async_schedule_update_ha_state()

    # @callback
    # def _handle_coordinator_update(self) -> None:
    #     """Handle updated data from the coordinator."""
    #     _LOGGER.debug(
    #         f"Coordinator update callback for Select triggered for {self._device_name} with data: {self.coordinator.data}"
    #     )

    #     # We use the Coordinator's availability status.
    #     self._attr_available = self.coordinator.last_update_success

    #     # Inform HA that the state needs writing to the UI.
    #     self.async_write_ha_state()
