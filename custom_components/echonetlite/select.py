import logging
from homeassistant.components.select import SelectEntity
from .const import HVAC_SELECT_OP_CODES, DOMAIN, FAN_SELECT_OP_CODES, COVER_SELECT_OP_CODES, CONF_FORCE_POLLING
from pychonet.lib.epc import EPC_CODE
from pychonet.lib.eojx import EOJX_CLASS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        if entity['instance']['eojgc'] == 1 and entity['instance']['eojcc'] == 48:  # Home Air Conditioner
            for op_code in entity['instance']['setmap']:
                if op_code in HVAC_SELECT_OP_CODES:
                    entities.append(
                        EchonetSelect(
                           hass,
                           entity['echonetlite'],
                           config,
                           op_code,
                           HVAC_SELECT_OP_CODES[op_code],
                           config.title
                        )
                    )
        elif entity['instance']['eojgc'] == 1 and entity['instance']['eojcc'] == 53:  # Home Air Cleaner
            for op_code in entity['instance']['setmap']:
                if op_code in FAN_SELECT_OP_CODES:
                    entities.append(
                        EchonetSelect(
                           hass,
                           entity['echonetlite'],
                           config,
                           op_code,
                           FAN_SELECT_OP_CODES[op_code],
                           config.title
                        )
                    )
        elif entity['instance']['eojgc'] == 0x02 and entity['instance']['eojcc'] in (0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66):
            # 0x60: "Electrically operated blind/shade"
            # 0x61: "Electrically operated shutter"
            # 0x62: "Electrically operated curtain"
            # 0x63: "Electrically operated rain sliding door/shutter"
            # 0x64: "Electrically operated gate"
            # 0x65: "Electrically operated window"
            # 0x66: "Automatically operated entrance door/sliding door"
            for op_code in entity['instance']['setmap']:
                if op_code in COVER_SELECT_OP_CODES:
                    entities.append(
                        EchonetSelect(
                           hass,
                           entity['echonetlite'],
                           config,
                           op_code,
                           COVER_SELECT_OP_CODES[op_code],
                           config.title
                        )
                    )
    async_add_entities(entities, True)


class EchonetSelect(SelectEntity):
    def __init__(self, hass, connector, config, code, options, name=None):
        """Initialize the select."""
        self._connector = connector
        self._config = config
        self._code = code
        self._optimistic = False
        self._sub_state = None
        self._options = options
        self._attr_options = list(self._options.keys())
        if self._code in list(self._connector._user_options.keys()):
            if self._connector._user_options[code] is not False:
                self._attr_options = self._connector._user_options[code]
        self._attr_current_option = self._connector._update_data.get(self._code)
        self._attr_name = f"{config.title} {EPC_CODE[self._connector._eojgc][self._connector._eojcc][self._code]}"
        self._uid = f'{self._connector._uidi}-{self._code}' if self._connector._uidi else f'{self._connector._uid}-{self._code}'
        self._device_name = name
        self._should_poll = True
        self.update_option_listener()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._uid

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
            # "sw_version": "",
        }

    async def async_select_option(self, option: str):
        await self._connector._instance.setMessage(self._code, self._options[option])
        self._connector._update_data[self._code] = option
        self._attr_current_option = option

    async def async_update(self):
        """Retrieve latest state."""
        await self._connector.async_update()

    def update_attr(self):
        self._attr_options = list(self._options.keys())
        if self._attr_current_option not in self._attr_options:
            # maybe data value is raw(int)
            keys = [k for k, v in self._options.items() if v == self._attr_current_option]
            if keys:
                self._attr_current_option = keys[0]
        if self._code in list(self._connector._user_options.keys()):
            if self._connector._user_options[self._code] is not False:
                self._attr_options = self._connector._user_options[self._code]

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush = False):
        new_val = self._connector._update_data.get(self._code)
        changed = new_val is not None and self._attr_current_option != new_val
        if (changed):
            self._attr_current_option = new_val
            self.update_attr()
            self.async_schedule_update_ha_state()

    def update_option_listener(self):
        self._should_poll = True
#        self._should_poll = self._connector._user_options.get(CONF_FORCE_POLLING, False) or self._code not in self._connector._ntfPropertyMap
#        _LOGGER.info(f"{self._device_name}({self._code}): _should_poll is {self._should_poll}")
