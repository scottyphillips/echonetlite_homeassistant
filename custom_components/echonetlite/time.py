import logging
import datetime
from datetime import time
from homeassistant.components.time import TimeEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import CONF_ICON, CONF_NAME
from homeassistant.exceptions import InvalidStateError

from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.epc_functions import _hh_mm
from . import get_name_by_epc_code, get_device_name
from .const import (
    CONF_DISABLED_DEFAULT,
    DOMAIN,
    CONF_FORCE_POLLING,
    ENL_SUPER_CODES,
    NON_SETUP_SINGLE_ENYITY,
    TYPE_TIME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        connector = entity["echonetlite"]
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        _enl_op_codes = connector._enl_op_codes | ENL_SUPER_CODES

        # Filter and create Time entities
        for op_code in list(
            set(entity["instance"]["setmap"])
            - NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(eojcc, set())
        ):
            epc_func = connector._instance.EPC_FUNCTIONS.get(op_code)
            _by_epc_func = (isinstance(epc_func, list) and epc_func[0] == _hh_mm) or (
                callable(epc_func) and epc_func == _hh_mm
            )

            if _by_epc_func or TYPE_TIME in _enl_op_codes.get(op_code, {}):
                entities.append(
                    EchonetTime(
                        connector,
                        config,
                        op_code,
                        _enl_op_codes.get(op_code, {}),
                    )
                )

    async_add_entities(entities, True)


class EchonetTime(CoordinatorEntity, TimeEntity):
    """Representation of an ECHONETLite time entity."""

    _attr_translation_key = DOMAIN

    def __init__(self, connector, config, code, options):
        super().__init__(connector)
        self._connector = connector
        self._code = code
        self._device_name = get_device_name(connector, config)

        # Entity Metadata
        self._attr_icon = options.get(CONF_ICON)
        self._attr_name = f"{config.title} {get_name_by_epc_code(connector._eojgc, connector._eojcc, code, None, options.get(CONF_NAME))}"
        self._attr_unique_id = f"{connector._uidi or connector._uid}-{code}"
        self._attr_entity_registry_enabled_default = not bool(
            options.get(CONF_DISABLED_DEFAULT)
        )

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time entity."""
        hh_mm = self._connector._update_data.get(self._code)
        if hh_mm is not None and ":" in hh_mm:
            try:
                h, m = map(int, hh_mm.split(":"))
                return datetime.time(h, m)
            except (ValueError, IndexError):
                _LOGGER.warning(
                    f"Invalid time format received for {self.name}: {hh_mm}"
                )
        return None

    async def async_set_value(self, value: time) -> None:
        """Update the current value."""
        # Convert time object to ECHONETLite EDT format (H*256 + M)
        edt = (value.hour << 8) + value.minute
        mes = {"EPC": self._code, "PDC": 0x02, "EDT": edt}

        if await self._connector._instance.setMessages([mes]):
            # Optimistically update the local state
            self._connector._update_data[self._code] = (
                f"{value.hour:02d}:{value.minute:02d}"
            )
            self.async_write_ha_state()
        else:
            raise InvalidStateError(
                f"Failed to set time for {self.name}. The device rejected the value."
            )

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
