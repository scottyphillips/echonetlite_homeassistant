import asyncio
import logging
from homeassistant.const import CONF_ICON, CONF_SERVICE_DATA
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN, ENL_OP_CODES, CONF_ON_VALUE, CONF_OFF_VALUE, DATA_STATE_ON, DATA_STATE_OFF, SWITCH_POWER, CONF_ENSURE_ON, TYPE_SWITCH, ENL_STATUS, ENL_ON, ENL_OFF, CONF_FORCE_POLLING
from pychonet.lib.epc import EPC_CODE
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.const import ENL_SETMAP

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        eojgc = entity['instance']['eojgc']
        eojcc = entity['instance']['eojcc']
        set_enl_status = False
        # configure switch entities by looking up full ENL_OP_CODE dict
        for op_code in list(entity['echonetlite']._update_flags_full_list):
            if eojgc in ENL_OP_CODES.keys():
                if eojcc in ENL_OP_CODES[eojgc].keys():
                    if op_code in ENL_OP_CODES[eojgc][eojcc].keys():
                        if TYPE_SWITCH in ENL_OP_CODES[eojgc][eojcc][op_code].keys():
                            entities.append(
                                EchonetSwitch(
                                    hass,
                                    entity['echonetlite'],
                                    config,
                                    op_code,
                                    ENL_OP_CODES[eojgc][eojcc][op_code],
                                    config.title
                                )
                            )
                            if op_code == ENL_STATUS:
                                set_enl_status = True
        # Auto configure of the power switch
        if (eojgc == 0x01 and eojcc in (0x30, 0x35)) or (eojgc == 0x02 and eojcc == 0x90):
            # Home air conditioner, Air cleaner, General Lighting
            continue
        if not set_enl_status and ENL_STATUS in entity['instance']['setmap']:
            entities.append(
                EchonetSwitch(
                    hass,
                    entity['echonetlite'],
                    config,
                    ENL_STATUS,
                    {
                        CONF_ICON: "mdi:power-settings",
                        CONF_SERVICE_DATA: SWITCH_POWER,
                    },
                    config.title
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
        self._on_value = options.get(CONF_ON_VALUE, DATA_STATE_ON)
        self._on_vals = [self._on_value, self._options[CONF_SERVICE_DATA][DATA_STATE_ON], hex(self._options[CONF_SERVICE_DATA][DATA_STATE_ON])[2:]]
        self._attr_name = f"{config.title} {EPC_CODE[self._connector._eojgc][self._connector._eojcc][self._code]}"
        self._attr_icon = options[CONF_ICON]
        self._uid = f'{self._connector._uidi}-{self._code}' if self._connector._uidi else f'{self._connector._uid}-{self._connector._eojgc}-{self._connector._eojcc}-{self._connector._eojci}-{self._code}'
        self._device_name = name
        self._should_poll = True
        self.update_option_listener()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._uid

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._attr_icon

    @property
    def should_poll(self):
        return self._should_poll

    @property
    def device_info(self):
        return {
            "identifiers": {(
                DOMAIN,
                self._connector._uid,
                self._connector._instance._eojgc,
                self._connector._instance._eojcc,
                self._connector._instance._eojci
            )},
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._instance._eojgc][self._connector._instance._eojcc]
        }

    @property
    def is_on(self):
        return self._connector._update_data[self._code] in self._on_vals

    async def async_turn_on(self, **kwargs) -> None:
        """Turn switch on."""
        main_sw_code = None
        # Check ensure turn on switch.
        # For some devices this ensures the main switch is switched on firs
        if (CONF_ENSURE_ON in self._options):
            main_sw_code = self._options[CONF_ENSURE_ON]
        # Turn on the specified switch
        if main_sw_code is not None and self._connector._update_data[main_sw_code] != DATA_STATE_ON:
            await self._connector._instance.setMessage(main_sw_code, SWITCH_POWER[DATA_STATE_ON])
            cnt = 0
            while(self._connector._update_data[main_sw_code] != DATA_STATE_ON and cnt < 100):
                cnt += 1
                await asyncio.sleep(0.1)

        if main_sw_code is None or self._connector._update_data[main_sw_code] == DATA_STATE_ON:
            await self._connector._instance.setMessage(self._code, self._options[CONF_SERVICE_DATA][DATA_STATE_ON])

    async def async_turn_off(self, **kwargs) -> None:
        """Turn switch off."""
        await self._connector._instance.setMessage(self._code, self._options[CONF_SERVICE_DATA][DATA_STATE_OFF])

    async def async_update(self):
        """Retrieve latest state."""
        await self._connector.async_update()

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush = False):
        self.async_schedule_update_ha_state()

    def update_option_listener(self):
        self._should_poll = self._connector._user_options.get(CONF_FORCE_POLLING, False) or self._code not in self._connector._ntfPropertyMap
        _LOGGER.info(f"{self._device_name}({self._code}): _should_poll is {self._should_poll}")
