"""Config flow for echonetlite integration."""
from __future__ import annotations

import logging
import asyncio
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
from pychonet.HomeAirConditioner import ENL_FANSPEED, ENL_AIR_VERT, ENL_AIR_HORZ
import pychonet as echonet
from .const import DOMAIN, USER_OPTIONS


_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("title"): str,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    _LOGGER.warning(f"IP address is {data['host']}")
    instances = await hass.async_add_executor_job(echonet.discover, data["host"])
    if len(instances) == 0:
        raise CannotConnect
    return {"host": data["host"], "title": data["title"], "instances": instances}


async def discover_devices(hass: HomeAssistant, discovery_info: list):
    # Then build default object and grab static such as UID and property maps...
    for instance in discovery_info['instances']:
         device = await hass.async_add_executor_job(echonet.EchonetInstance, instance['eojgc'], instance['eojcc'], instance['eojci'], instance['netaddr'])
         device_data = await hass.async_add_executor_job(device.update, [0x83,0x9f,0x9e])
         instance['getPropertyMap'] = device_data[0x9f]
         instance['setPropertyMap'] = device_data[0x9e]
         if device_data[0x83]:
             instance['UID'] = await hass.async_add_executor_job(device.getIdentificationNumber)
         else:
             instance['UID'] = f'{instance["netaddr"]}-{instance["eojgc"]}{instance["eojcc"]}{instance["eojci"]}'
    _LOGGER.debug(discovery_info)
    # Return info that you want to store in the config entry.
    return discovery_info

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for echonetlite."""
    discover_task = None
    discovery_info = {}
    instances = None
    VERSION = 1
            
    async def _async_do_task(self, task):
        self.discovery_info = await task  # A task that take some time to complete.
        self.hass.async_create_task(
             self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
        )
        return self.discovery_info        
            
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        
        try:
            self.discovery_info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return await self.async_step_discover(user_input)
            
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
    
    async def async_step_discover(self, user_input=None):
        errors = {}
        if not self.discover_task:
             _LOGGER.debug('Step 1')
             try: 
                 self.discover_task = self.hass.async_create_task(self._async_do_task(discover_devices(self.hass, self.discovery_info)))
             except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
             else:
                 return self.async_show_progress(step_id="discover", progress_action="user")
        
        return self.async_show_progress_done(next_step_id="finish")
        
    async def async_step_finish(self, user_input=None):
        #_LOGGER.debug("Step 4")
        return self.async_create_entry(title=self.discovery_info["title"], data=self.discovery_info)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config):
        self._config_entry = config
        
    async def async_step_init(self, user_input=None):
        """Manage the options."""
        data_schema_structure = {}
        
        # Handle HVAC User configurable options
        for instance in self._config_entry.data["instances"]:
           if instance['eojgc'] == 0x01 and instance['eojcc'] == 0x30:
                for option in list(USER_OPTIONS.keys()):
                    if option in instance['setPropertyMap']:
                       data_schema_structure.update({vol.Optional(
                           USER_OPTIONS[option]['option'],
                           default=self._config_entry.options.get(USER_OPTIONS[option]['option']) if self._config_entry.options.get(USER_OPTIONS[option]['option']) is not None else [] ,
                        ):cv.multi_select(USER_OPTIONS[option]['option_list'])})
               
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(data_schema_structure),
        )
