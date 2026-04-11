import logging
import datetime
from datetime import time
from homeassistant.const import CONF_ICON, CONF_NAME
from homeassistant.components.time import TimeEntity
from homeassistant.exceptions import InvalidStateError
from .base_entity import EchonetEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import get_name_by_epc_code, get_device_name
from .const import (
    CONF_DISABLED_DEFAULT,
    DOMAIN,
    CONF_FORCE_POLLING,
    ENL_SUPER_CODES,
    NON_SETUP_SINGLE_ENYITY,
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
        _enl_op_codes = entity["echonetlite"]._enl_op_codes | ENL_SUPER_CODES
        # configure select entities by looking up full ENL_OP_CODE dict
        for op_code in list(
            set(entity["instance"]["setmap"])
            - NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(eojcc, set())
        ):
            epc_function_data = entity["echonetlite"]._instance.EPC_FUNCTIONS.get(
                op_code, None
            )
            _by_epc_func = (
                type(epc_function_data) == list and epc_function_data[0] == _hh_mm
            ) or (callable(epc_function_data) and epc_function_data == _hh_mm)
            if _by_epc_func or TYPE_TIME in _enl_op_codes.get(op_code, {}).keys():
                entities.append(
                    EchonetTime(
                        entity["echonetlite"],
                        config,
                        _enl_op_codes.get(op_code, {}),
                        op_code,  
                    )
                )

    async_add_entities(entities, True)


class EchonetTime(EchonetEntity, TimeEntity):
    """Representation of an ECHONET Lite Time entity."""

    def __init__(self, coordinator, config, options, epc_code ):
        """Initialize the time entity.

        Args:
            coordinator: The update coordinator for this device (extends CoordinatorEntity).
            config: Home Assistant configuration entry.
            code: EPC operation code for this time entity.
            options: Entity configuration options including icon and name.
        """
        super().__init__(coordinator, config)

        self._config = config
        self._code = epc_code

        self._attr_icon = options.get(CONF_ICON, None)
        self._attr_name = f"{config.title} {get_name_by_epc_code(self.coordinator._eojgc, self.coordinator._eojcc, self._code, None, self.coordinator._enl_op_codes.get(self._code, {}).get(CONF_NAME))}"
        self._attr_unique_id = (
            f"{self.coordinator._uidi}-{self._code}"
            if self.coordinator._uidi
            else f"{self.coordinator._uid}-{self._code}"
        )

        self._device_name = get_device_name(coordinator, config)
        self._attr_entity_registry_enabled_default = not bool(
            options.get(CONF_DISABLED_DEFAULT)
        )

    @property
    def native_value(self) -> time | None:
        """Return the current time value.

        Reads the time value from coordinator data and converts it to a datetime.time object.
        The coordinator handles all polling and update notifications automatically.
        """
        if self.coordinator and self.coordinator.data:
            hh_mm = self.coordinator.data.get(self._code)
            if hh_mm is not None:
                val = hh_mm.split(":")
                return datetime.time(int(val[0]), int(val[1]))

        return None

    @property
    def device_info(self):
        """Return device information for Home Assistant."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    self.coordinator._uid,
                    self.coordinator._instance._eojgc,
                    self.coordinator._instance._eojcc,
                    self.coordinator._instance._eojci,
                )
            },
            "name": self._device_name,
            "manufacturer": self.coordinator._manufacturer
            + (
                " " + self.coordinator._host_product_code
                if self.coordinator._host_product_code
                else ""
            ),
            "model": EOJX_CLASS[self.coordinator._instance._eojgc][
                self.coordinator._instance._eojcc
            ],
        }

    async def async_set_value(self, value: time) -> None:
        """Update the current time value on the device.

        Args:
            value: The new time value to set.

        Raises:
            InvalidStateError: If setting the value fails due to unsupported operation or invalid value.
        """
        h = int(value.hour)
        m = int(value.minute)
        mes = {"EPC": self._code, "PDC": 0x02, "EDT": h * 256 + m}

        if await self.coordinator._instance.setMessages([mes]):
            pass
        else:
            raise InvalidStateError(
                "The state setting is not supported or is an invalid value."
            )
