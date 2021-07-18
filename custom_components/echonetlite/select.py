import functools
import logging
_LOGGER = logging.getLogger(__name__)

import voluptuous as vol

from homeassistant.components import select
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_NAME
from .const import HVAC_SELECT_OP_CODES, DOMAIN
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.epc import EPC_CODE

async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        if entity['instance_data']['eojgc'] == 1 and entity['instance_data']['eojcc'] == 48: #Home Air Conditioner
            for op_code in entity['instance_data']['setPropertyMap']:
                if op_code in HVAC_SELECT_OP_CODES:
                     entities.append(EchonetSelect(hass, 
                     entity['API'], 
                     config, 
                     op_code, 
                     HVAC_SELECT_OP_CODES[op_code]))
    async_add_entities(entities, True)

class EchonetSelect(SelectEntity):
    def __init__(self, hass, instance, config, code, options):
        """Initialize the select."""
        self._instance = instance
        self._config = config
        self._code = code
        self._optimistic = False
        self._sub_state = None
        self._options = options
        _LOGGER.warning(f"flags set are {self._instance._user_options}")
        self._attr_options = list(self._options.keys())
        if self._code in list(self._instance._user_options.keys()):
           if self._instance._user_options[code] is not False:
               self._attr_options = self._instance._user_options[code]
        self._attr_current_option = self._instance._update_data[self._code]
        self._attr_name = f"{config.data['title']} {EPC_CODE[self._instance._api.eojgc][self._instance._api.eojcc][self._code]}"
        self._uid = f'{self._instance._uid}-{self._code}'
    
    @property
    def unique_id(self):
         """Return a unique ID."""
         return self._uid    
         
    @property
    def device_info(self):
        return {
            "identifiers": {
                  (DOMAIN, self._instance._uid, self._instance._api.eojgc, self._instance._api.eojcc, self._instance._api.instance)
            },
            "name": EOJX_CLASS[self._instance._api.eojgc][self._instance._api.eojcc]
            #"manufacturer": "Mitsubishi",
            #"model": "",
            #"sw_version": "",
        }
    
    
    async def async_select_option(self, option: str):
        self.hass.async_add_executor_job(self._instance._api.setMessage, [{'EPC': self._code, 'PDC': 0x01, 'EDT': self._options[option]}])
        self._attr_current_option = option
        
    async def async_update(self):
        """Retrieve latest state."""
        await self._instance.async_update()
        self._attr_current_option = self._instance._update_data[self._code]
        self._attr_options = list(self._options.keys())
        if self._code in list(self._instance._user_options.keys()):
           if self._instance._user_options[self._code] is not False:
                self._attr_options = self._instance._user_options[self._code]
