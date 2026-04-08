import asyncio
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import CONF_ICON, CONF_SERVICE_DATA, CONF_NAME

from pychonet.lib.eojx import EOJX_CLASS
from . import get_name_by_epc_code, get_device_name
from .const import (
    CONF_DISABLED_DEFAULT,
    DOMAIN,
    CONF_ON_VALUE,
    CONF_OFF_VALUE,
    DATA_STATE_ON,
    DATA_STATE_OFF,
    NON_SETUP_SINGLE_ENYITY,
    SWITCH_POWER,
    CONF_ENSURE_ON,
    TYPE_SWITCH,
    TYPE_NUMBER,
    ENL_STATUS,
    CONF_FORCE_POLLING,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        connector = entity["echonetlite"]
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        _enl_op_codes = connector._enl_op_codes
        _non_setup = NON_SETUP_SINGLE_ENYITY.get(eojgc, {}).get(eojcc, set())

        set_enl_status = False

        # configure switch entities by looking up full ENL_OP_CODE dict
        for op_code in list(set(entity["instance"]["setmap"]) - _non_setup):
            epc_function_data = connector._instance.EPC_FUNCTIONS.get(op_code)
            _by_epc_func = (
                isinstance(epc_function_data, list)
                and isinstance(epc_function_data[1], dict)
                and len(epc_function_data[1]) == 2
            )

            op_code_dict = _enl_op_codes.get(op_code, {})
            if _by_epc_func or TYPE_SWITCH in op_code_dict:
                entities.append(EchonetSwitch(connector, config, op_code, op_code_dict))
                if op_code == ENL_STATUS:
                    set_enl_status = True

            # Check for number-based switches (switches nested inside number configs)
            if switch_conf := op_code_dict.get(TYPE_NUMBER, {}).get(TYPE_SWITCH):
                combined_conf = op_code_dict.copy()
                combined_conf.update(switch_conf)
                entities.append(
                    EchonetSwitch(connector, config, op_code, combined_conf)
                )

        # Auto-configure power switch for non-AC/Lighting devices if not already added
        is_hvac_or_light = (eojgc == 0x01 and eojcc in (0x30, 0x35)) or (
            eojgc == 0x02 and eojcc in (0x90, 0x91)
        )

        if (
            not is_hvac_or_light
            and not set_enl_status
            and ENL_STATUS in entity["instance"]["setmap"]
        ):
            entities.append(
                EchonetSwitch(
                    connector,
                    config,
                    ENL_STATUS,
                    {CONF_ICON: "mdi:power-settings", CONF_SERVICE_DATA: SWITCH_POWER},
                )
            )

    async_add_entities(entities, True)


class EchonetSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an ECHONETLite switch entity."""

    def __init__(self, connector, config, code, options):
        super().__init__(connector)
        self._connector = connector
        self._code = code
        self._options = options.copy()
        self._device_name = get_device_name(connector, config)

        # Resolve EPC function data for ON/OFF values
        epc_function_data = connector._instance.EPC_FUNCTIONS.get(code)
        if isinstance(epc_function_data, list):
            data_keys = list(epc_function_data[1].keys())
            data_items = list(epc_function_data[1].values())
            self._options.update(
                {
                    CONF_SERVICE_DATA: {
                        DATA_STATE_ON: data_keys[0],
                        DATA_STATE_OFF: data_keys[1],
                    },
                    CONF_ON_VALUE: data_items[0],
                    CONF_OFF_VALUE: data_items[1],
                }
            )

        # Pre-calculate valid ON values for the is_on property
        on_val_raw = self._options.get(CONF_ON_VALUE, DATA_STATE_ON)
        on_service_val = self._options[CONF_SERVICE_DATA][DATA_STATE_ON]
        self._on_vals = {on_val_raw, on_service_val, hex(on_service_val)[2:]}

        # Metadata
        self._attr_icon = self._options.get(CONF_ICON)
        self._attr_name = f"{config.title} {get_name_by_epc_code(connector._eojgc, connector._eojcc, code, None, options.get(CONF_NAME))}"

        base_id = (
            connector._uidi
            or f"{connector._uid}-{connector._eojgc}-{connector._eojcc}-{connector._eojci}"
        )
        self._attr_unique_id = f"{base_id}-{code}"

        if options.get(TYPE_NUMBER):
            self._attr_unique_id += "-switch"
            self._attr_name += f" {options.get(CONF_NAME, 'Switch')}"

        self._attr_entity_registry_enabled_default = not bool(
            options.get(CONF_DISABLED_DEFAULT)
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._connector._update_data.get(self._code) in self._on_vals

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        # Handle dependencies (ensure main power is on)
        if main_sw_code := self._options.get(CONF_ENSURE_ON):
            if self._connector._update_data.get(main_sw_code) != DATA_STATE_ON:
                if await self._connector._instance.setMessage(
                    main_sw_code, SWITCH_POWER[DATA_STATE_ON]
                ):
                    self._connector._update_data[main_sw_code] = DATA_STATE_ON
                    await asyncio.sleep(2)  # Stabilization time
                else:
                    _LOGGER.error(f"Failed to enable dependency switch {main_sw_code}")
                    return

        if await self._connector._instance.setMessage(
            self._code, self._options[CONF_SERVICE_DATA][DATA_STATE_ON]
        ):
            self._connector._update_data[self._code] = self._options[CONF_SERVICE_DATA][
                DATA_STATE_ON
            ]
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        if await self._connector._instance.setMessage(
            self._code, self._options[CONF_SERVICE_DATA][DATA_STATE_OFF]
        ):
            self._connector._update_data[self._code] = self._options[CONF_SERVICE_DATA][
                DATA_STATE_OFF
            ]
            self.async_write_ha_state()

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
