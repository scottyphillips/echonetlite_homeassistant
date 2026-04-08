import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import CONF_ICON, CONF_NAME

from pychonet.HomeAirConditioner import (
    ENL_AIR_HORZ,
    ENL_AIR_VERT,
    ENL_AUTO_DIRECTION,
    ENL_FANSPEED,
    ENL_HVAC_MODE,
    ENL_SWING_MODE,
)
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.epc_functions import _swap_dict

from . import get_name_by_epc_code, get_device_name
from .const import (
    CONF_DISABLED_DEFAULT,
    DOMAIN,
    CONF_FORCE_POLLING,
    CONF_ICONS,
    TYPE_SELECT,
    NON_SETUP_SINGLE_ENYITY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        connector = entity["echonetlite"]
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        _enl_op_codes = connector._enl_op_codes
        _non_setup_entities = NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(eojcc, set())

        for op_code in list(set(entity["instance"]["setmap"]) - _non_setup_entities):
            epc_func = connector._instance.EPC_FUNCTIONS.get(op_code)
            _by_epc_func = (
                isinstance(epc_func, list)
                and len(epc_func) > 1
                and isinstance(epc_func[1], dict)
                and len(epc_func[1]) > 2
            )

            op_code_dict = _enl_op_codes.get(op_code, {})
            if _by_epc_func or TYPE_SELECT in op_code_dict:
                entities.append(EchonetSelect(connector, config, op_code, op_code_dict))

    async_add_entities(entities, True)


class EchonetSelect(CoordinatorEntity, SelectEntity):
    """Representation of an ECHONETLite select entity."""

    _attr_translation_key = DOMAIN

    # Mapping for EPCs that support user-defined option filtering
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

    def __init__(self, connector, config, code, options):
        super().__init__(connector)
        self._connector = connector
        self._code = code
        self._device_name = get_device_name(connector, config)

        # Resolve Option Mapping
        if isinstance(options.get(TYPE_SELECT), dict):
            self._options_map = options[TYPE_SELECT]
        else:
            # Fallback to internal library EPC_FUNCTIONS
            self._options_map = _swap_dict(connector._instance.EPC_FUNCTIONS[code][1])

        self._icons = options.get(CONF_ICONS, {})
        self._default_icon = options.get(CONF_ICON)

        # Entity Identification
        self._attr_name = f"{config.title} {get_name_by_epc_code(connector._eojgc, connector._eojcc, code, None, options.get(CONF_NAME))}"
        self._attr_unique_id = f"{connector._uidi or connector._uid}-{code}"
        self._attr_entity_registry_enabled_default = not bool(
            options.get(CONF_DISABLED_DEFAULT)
        )

        # Check for user-overridden option lists
        key = f"{hex(connector._instance._eojgc)}-{hex(connector._instance._eojcc)}"
        self._user_option_epcs = self.SELECT_USING_USER_OPTIONS.get(
            key, set()
        ).intersection(set(connector._user_options.keys()))

    @property
    def options(self) -> list[str]:
        """Return a list of available options."""
        if self._code in self._user_option_epcs:
            user_opts = self._connector._user_options.get(self._code)
            if user_opts is not False:
                return user_opts
        return list(self._options_map.keys())

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        raw_value = self._connector._update_data.get(self._code)
        if raw_value is None:
            return None

        # If the raw value is a string (already mapped), return it
        if isinstance(raw_value, str) and raw_value in self._options_map:
            return raw_value

        # Otherwise, lookup the string key by the integer value
        for k, v in self._options_map.items():
            if v == raw_value:
                return k
        return None

    @property
    def icon(self):
        """Return the icon based on the current selection."""
        return self._icons.get(self.current_option, self._default_icon)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if await self._connector._instance.setMessage(
            self._code, self._options_map[option]
        ):
            # Optimistically update the coordinator's data
            self._connector._update_data[self._code] = self._options_map[option]
            self.async_write_ha_state()
        else:
            _LOGGER.error(f"Failed to set {self.name} to {option}")

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
            "manufacturer": f"{self._connector._manufacturer} {self._connector._host_product_code or ''}".strip(),
            "model": EOJX_CLASS[self._connector._instance._eojgc][
                self._connector._instance._eojcc
            ],
        }

    @property
    def extra_state_attributes(self):
        should_poll = self._code not in self._connector._ntfPropertyMap
        return {"notify": "No" if should_poll else "Yes"}
