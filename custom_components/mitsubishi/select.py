import functools
import logging
_LOGGER = logging.getLogger(__name__)

import voluptuous as vol

from homeassistant.components import select
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_NAME

DOMAIN = "mitsubishi"
REQUIREMENTS = ['pychonet==1.0.7']
PARALLEL_UPDATES = 1

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    import pychonet as echonet
    from pychonet.HomeAirConditioner import FAN_SPEED
    echonet_api = echonet.HomeAirConditioner(config.get(CONF_IP_ADDRESS))
    echonet_set_properties = echonet_api.fetchSetProperties()
    vk_echonet_set_properties = {value:key for key, value in echonet_set_properties.items()}
    _LOGGER.debug(echonet_set_properties)
    entities = []
    if 160 in echonet_set_properties.values(): # fan speed
        entities.append(EchonetSelect(hass, echonet_api, config, 160, FAN_SPEED, vk_echonet_set_properties[160]))

    """Set up the Mitsubishi ECHONET climate devices."""

    # get supported entities - swing mode, horizontal swing, vertical swing.
    async_add_entities(entities)


class EchonetSelect(SelectEntity):
    def __init__(self, hass, echonet_api, config, code, options, echonet_property):
        """Initialize the select."""
        _LOGGER.debug(config)
        self._api = echonet_api
        self._config = config
        self._code = code
        self._optimistic = False
        self._sub_state = None
        self._vk_options = {value:key for key, value in options.items()}
        self._kv_options = options
        self._attr_options = list(options.keys())
        self._attr_current_option = self._vk_options.get(int.from_bytes(self._api.getSingleMessageResponse(self._code), 'big'))
        self._attr_name = f"{config.get(CONF_NAME)} {echonet_property}"

    async def async_select_option(self, option: str):
        _LOGGER.debug("option %s selected", option)
        self.hass.async_add_executor_job(self._api.setMessage, self._code, self._kv_options[option])
        self._attr_current_option = option

    async def async_update(self):
        """Retrieve latest state."""
        try:
            _LOGGER.debug("Requesting update from %s (%s)", self._attr_name, self._api.netif)
            self._attr_current_option = await self.hass.async_add_executor_job(self._vk_options.get, int.from_bytes(self._api.getSingleMessageResponse(self._code), 'big'))
            _LOGGER.debug("Received response from %s (%s)", self._attr_name, self._api.netif)
        except KeyError:
           _LOGGER.warning("HA requested an update from %s (%s) but no data was received", self._attr_name, self._api.netif)    
