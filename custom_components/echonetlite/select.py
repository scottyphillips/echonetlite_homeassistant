import logging
from homeassistant.components.select import SelectEntity
from .const import HVAC_SELECT_OP_CODES, DOMAIN, FAN_SELECT_OP_CODES, COVER_SELECT_OP_CODES
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
        self._attr_current_option = self._connector._update_data[self._code]
        self._attr_name = f"{config.title} {EPC_CODE[self._connector._eojgc][self._connector._eojcc][self._code]}"
        self._uid = f'{self._connector._uid}-{self._code}'
        self._device_name = name

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
        self._attr_current_option = option

    async def async_update(self):
        """Retrieve latest state."""
        await self._connector.async_update()
        self._attr_current_option = self._connector._update_data[self._code]
        self._attr_options = list(self._options.keys())
        if self._code in list(self._connector._user_options.keys()):
            if self._connector._user_options[self._code] is not False:
                self._attr_options = self._connector._user_options[self._code]
