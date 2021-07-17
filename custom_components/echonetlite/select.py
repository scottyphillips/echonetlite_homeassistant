import functools
import logging
_LOGGER = logging.getLogger(__name__)

import voluptuous as vol

from homeassistant.components import select
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_NAME
from .const import HVAC_SELECT_OP_CODES, DOMAIN
from pychonet.lib.eojx import EOJX_CLASS

async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    entities = []
    for entity in hass.data[DOMAIN][config.entry_id]:
        if entity['instance_data']['eojgc'] == 1 and entity['instance_data']['eojcc'] == 48: #Home Air Conditioner
            echonet_set_properties = entity['API']._api.propertyMaps[158]
            vk_echonet_set_properties = {value:key for key, value in echonet_set_properties.items()} 
            for op_code in echonet_set_properties.values():
                if op_code in HVAC_SELECT_OP_CODES:
                     entities.append(EchonetSelect(hass, entity['API'], config, 
                     op_code, HVAC_SELECT_OP_CODES[op_code]['name'], 
                     HVAC_SELECT_OP_CODES[op_code]['options'], vk_echonet_set_properties[op_code]))
    async_add_entities(entities, True)


class EchonetSelect(SelectEntity):
    def __init__(self, hass, instance, config, code, codeword, options, echonet_property):
        """Initialize the select."""
        self._instance = instance
        self._config = config
        self._code = code
        self._optimistic = False
        self._sub_state = None
        self._vk_options = {value:key for key, value in options.items()} 
        self._kv_options = options
        self._codeword = codeword 
        self._attr_options = list(options.keys())
        self._attr_current_option = self._instance._update_data[self._code]
        self._attr_name = f"{config.data['title']} {echonet_property}"
        try:
           self._uid = f'{self._instance._uid}-{self._code}'
        except KeyError:
           self._uid = None
    
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
        _LOGGER.debug("option %s selected", self._kv_options[option])
        self.hass.async_add_executor_job(self._instance._api.setMessage, [{'EPC': self._code, 'PDC': 0x01, 'EDT': self._kv_options[option]}])
        self._attr_current_option = option
        
    async def async_update(self):
        """Retrieve latest state."""
        await self._instance.async_update()
        self._attr_current_option = self._instance._update_data[self._code]