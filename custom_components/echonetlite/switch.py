import time
import logging
from homeassistant.const import CONF_ICON, CONF_SERVICE_DATA
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN, HOTWATER_SWITCH_CODES, DATA_STATE_ON, DATA_STATE_OFF, SWITCH_POWER
from pychonet.lib.epc import EPC_CODE
from pychonet.lib.eojx import EOJX_CLASS

_LOGGER = logging.getLogger(__name__)
MAIN_POWER_CODE = 0x80

async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        if entity['instance']['eojgc'] == 2 and entity['instance']['eojcc'] == 114:  # Hot water generator
            for op_code in entity['instance']['setmap']:
                if op_code in HOTWATER_SWITCH_CODES:
                    entities.append(
                        EchonetSwitch(
                           hass,
                           entity['echonetlite'],
                           config,
                           op_code,
                           HOTWATER_SWITCH_CODES[op_code][CONF_SERVICE_DATA],
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
        self._attr_is_on = self._connector._update_data[self._code] == DATA_STATE_ON
        self._attr_name = f"{config.title} {EPC_CODE[self._connector._eojgc][self._connector._eojcc][self._code]}"
        self._attr_icon = HOTWATER_SWITCH_CODES[code][CONF_ICON]
        self._uid = f'{self._connector._uid}-{self._code}'
        self._device_name = name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._uid

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._attr_icon

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

    async def async_turn_on(self, **kwargs) -> None:
        """Turn switch on."""
        isMainPower = self._code == MAIN_POWER_CODE
        if not isMainPower and self._connector._update_data[MAIN_POWER_CODE] != DATA_STATE_ON:
            if await self._connector._instance.setMessage(MAIN_POWER_CODE, SWITCH_POWER[DATA_STATE_ON]):
                self._connector._update_data[MAIN_POWER_CODE] = DATA_STATE_ON
                time.sleep(5)

        if (isMainPower or self._connector._update_data[MAIN_POWER_CODE] == DATA_STATE_ON) and await self._connector._instance.setMessage(self._code, self._options[DATA_STATE_ON]):
            self._connector._update_data[self._code] = DATA_STATE_ON
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn switch off."""
        if await self._connector._instance.setMessage(self._code, self._options[DATA_STATE_OFF]):
            self._connector._update_data[self._code] = DATA_STATE_OFF
            self._attr_is_on = False
            self.async_write_ha_state()

    async def async_update(self):
        """Retrieve latest state."""
        await self._connector.async_update()
        self._attr_is_on = self._connector._update_data[self._code] == DATA_STATE_ON
