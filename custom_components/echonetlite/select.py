import functools
import logging
_LOGGER = logging.getLogger(__name__)

import voluptuous as vol

from homeassistant.components import select
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_NAME
from .const import HVAC_OP_CODES, DOMAIN
from pychonet.HomeAirConditioner import FAN_SPEED, AIRFLOW_VERT, AIRFLOW_HORIZ


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    instance = hass.data[DOMAIN][config.entry_id]
    echonet_set_properties = instance._api.propertyMaps[158]
    vk_echonet_set_properties = {value:key for key, value in echonet_set_properties.items()}
    _LOGGER.debug(echonet_set_properties)

    # get supported entities - swing mode, horizontal swing, vertical swing.
    entities = []
    if HVAC_OP_CODES['fan_speed'] in echonet_set_properties.values(): # fan speed
        entities.append(EchonetSelect(hass, instance, config, HVAC_OP_CODES['fan_speed'], FAN_SPEED, vk_echonet_set_properties[HVAC_OP_CODES['fan_speed']]))
    if HVAC_OP_CODES['airflow_horizt'] in echonet_set_properties.values(): # Horizontal Airflow
        entities.append(EchonetSelect(hass, instance, config, HVAC_OP_CODES['airflow_horizt'], AIRFLOW_HORIZ, vk_echonet_set_properties[HVAC_OP_CODES['airflow_horizt']]))
    if HVAC_OP_CODES['airflow_vert'] in echonet_set_properties.values(): # Vertical Airflow
        entities.append(EchonetSelect(hass, instance, config, HVAC_OP_CODES['airflow_vert'], AIRFLOW_VERT, vk_echonet_set_properties[HVAC_OP_CODES['airflow_vert']]))

    async_add_entities(entities)


class EchonetSelect(SelectEntity):
    def __init__(self, hass, instance, config, code, options, echonet_property):
        """Initialize the select."""
        self._instance = instance
        self._config = config
        self._code = code
        self._optimistic = False
        self._sub_state = None
        self._vk_options = {value:key for key, value in options.items()}
        self._kv_options = options
        self._codeword = [key for key, value in HVAC_OP_CODES.items() if value == self._code][0]
        self._attr_options = list(options.keys())
        self._attr_current_option = self._instance._update_data[self._codeword]
        self._attr_name = f"{config.data['title']} {echonet_property}"
        try:
           self._uid = f'{self._instance._uid}-{self._code}'
        except KeyError:
           self._uid = None

    @property
    def unique_id(self):
         """Return a unique ID."""
         return self._uid

    async def async_select_option(self, option: str):
        _LOGGER.debug("option %s selected", option)
        self.hass.async_add_executor_job(self._instance._api.setMessage, self._code, self._kv_options[option])
        self._attr_current_option = option

    async def async_update(self):
        """Retrieve latest state."""
        await self._instance.async_update()
        self._attr_current_option = self._instance._update_data[self._codeword]
