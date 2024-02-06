import asyncio
import logging
from homeassistant.const import CONF_ICON, CONF_SERVICE_DATA, CONF_NAME
from homeassistant.components.switch import SwitchEntity
from .const import (
    DOMAIN,
    ENL_OP_CODES,
    CONF_ON_VALUE,
    CONF_OFF_VALUE,
    DATA_STATE_ON,
    DATA_STATE_OFF,
    SWITCH_POWER,
    CONF_ENSURE_ON,
    TYPE_SWITCH,
    TYPE_NUMBER,
    ENL_STATUS,
    CONF_FORCE_POLLING,
)
from pychonet.lib.epc import EPC_CODE
from pychonet.lib.eojx import EOJX_CLASS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        set_enl_status = False
        _enl_op_codes = ENL_OP_CODES.get(eojgc, {}).get(eojcc, {})
        # configure switch entities by looking up full ENL_OP_CODE dict
        for op_code in entity["instance"]["setmap"]:
            epc_function_data = entity["echonetlite"]._instance.EPC_FUNCTIONS.get(
                op_code, None
            )
            _by_epc_func = (
                type(epc_function_data) == list
                and type(epc_function_data[1]) == dict
                and len(epc_function_data[1]) == 2
            )
            if _by_epc_func or TYPE_SWITCH in _enl_op_codes.get(op_code, {}).keys():
                entities.append(
                    EchonetSwitch(
                        hass,
                        entity["echonetlite"],
                        config,
                        op_code,
                        ENL_OP_CODES[eojgc][eojcc][op_code],
                        entity["echonetlite"]._name or config.title,
                    )
                )
                if op_code == ENL_STATUS:
                    set_enl_status = True
            if (
                switch_conf := _enl_op_codes.get(op_code, {})
                .get(TYPE_NUMBER, {})
                .get(TYPE_SWITCH)
            ):
                switch_conf.update(_enl_op_codes[op_code].copy())
                entities.append(
                    EchonetSwitch(
                        hass,
                        entity["echonetlite"],
                        config,
                        op_code,
                        switch_conf,
                        entity["echonetlite"]._name or config.title,
                    )
                )
        # Auto configure of the power switch
        if (eojgc == 0x01 and eojcc in (0x30, 0x35)) or (
            eojgc == 0x02 and eojcc in (0x90, 0x91)
        ):
            # Home air conditioner, Air cleaner, General Lighting, Single Function Lighting
            continue
        if not set_enl_status and ENL_STATUS in entity["instance"]["setmap"]:
            entities.append(
                EchonetSwitch(
                    hass,
                    entity["echonetlite"],
                    config,
                    ENL_STATUS,
                    {
                        CONF_ICON: "mdi:power-settings",
                        CONF_SERVICE_DATA: SWITCH_POWER,
                    },
                    entity["echonetlite"]._name or config.title,
                )
            )
    async_add_entities(entities, True)


class EchonetSwitch(SwitchEntity):
    def __init__(self, hass, connector, config, code, options, name=None):
        """Initialize the switch."""
        self._connector = connector
        self._config = config
        self._code = code
        self._options = options
        epc_function_data = connector._instance.EPC_FUNCTIONS.get(code, None)
        if type(epc_function_data) == list:
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
        self._on_value = self._options.get(CONF_ON_VALUE, DATA_STATE_ON)
        self._on_vals = [
            self._on_value,
            self._options[CONF_SERVICE_DATA][DATA_STATE_ON],
            hex(self._options[CONF_SERVICE_DATA][DATA_STATE_ON])[2:],
        ]
        self._from_number = True if options.get(TYPE_NUMBER) else False
        self._attr_name = f"{config.title} {EPC_CODE[self._connector._eojgc][self._connector._eojcc][self._code]}"
        self._attr_icon = options.get(CONF_ICON)
        self._attr_unique_id = (
            f"{self._connector._uidi}-{self._code}"
            if self._connector._uidi
            else f"{self._connector._uid}-{self._connector._eojgc}-{self._connector._eojcc}-{self._connector._eojci}-{self._code}"
        )
        if self._from_number:
            self._attr_unique_id += "-switch"
            self._attr_name += " " + options.get(CONF_NAME, "Switch")
        self._device_name = name
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]
        self._attr_is_on = self._connector._update_data[self._code] in self._on_vals
        self._attr_should_poll = True
        self._attr_available = True

        self._real_should_poll = True

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
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Turn switch on."""
        main_sw_code = None
        # Check ensure turn on switch.
        # For some devices this ensures the main switch is switched on firs
        if CONF_ENSURE_ON in self._options:
            main_sw_code = self._options[CONF_ENSURE_ON]
        # Turn on the specified switch
        if (
            main_sw_code is not None
            and self._connector._update_data[main_sw_code] != DATA_STATE_ON
        ):
            if not await self._connector._instance.setMessage(
                main_sw_code, SWITCH_POWER[DATA_STATE_ON]
            ):
                # Can't turn on main switch
                return
            # Wait about 2 seconds until the On state is stabilized on the device side
            await asyncio.sleep(2)

        if (
            main_sw_code is None
            or self._connector._update_data[main_sw_code] == DATA_STATE_ON
        ):
            await self._connector._instance.setMessage(
                self._code, self._options[CONF_SERVICE_DATA][DATA_STATE_ON]
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn switch off."""
        await self._connector._instance.setMessage(
            self._code, self._options[CONF_SERVICE_DATA][DATA_STATE_OFF]
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
        new_val = self._connector._update_data[self._code] in self._on_vals
        changed = (
            self._attr_is_on != new_val
            or self._attr_available != self._server_state["available"]
        )
        if changed:
            _force = bool(not self._attr_available and self._server_state["available"])
            self._attr_is_on = new_val
            self._attr_available = self._server_state["available"]
            self._attr_should_poll = (
                self._real_should_poll if self._attr_available else False
            )
            self.async_schedule_update_ha_state(_force)

    def update_option_listener(self):
        _should_poll = self._code not in self._connector._ntfPropertyMap
        self._real_should_poll = (
            self._connector._user_options.get(CONF_FORCE_POLLING, False) or _should_poll
        )
        self._attr_should_poll = (
            self._real_should_poll if self._attr_available else False
        )
        self._attr_extra_state_attributes = {"notify": "No" if _should_poll else "Yes"}
        _LOGGER.debug(
            f"{self._device_name}({self._code}): _should_poll is {_should_poll}"
        )
