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
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
from pychonet.HomeAirConditioner import ENL_FANSPEED, ENL_AIR_VERT, ENL_AIR_HORZ

from .const import DOMAIN, USER_OPTIONS


_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("title"): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    import pychonet as echonet

    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )
    
    # First confirm device exists:
    _LOGGER.warning(f"IP address is {data['host']}")
    discover = await hass.async_add_executor_job(echonet.discover, data["host"])

    # Then build default object and grab static such as UID and property maps...
    for instance in discover:
        device = await hass.async_add_executor_job(echonet.EchonetInstance, instance['eojgc'], instance['eojcc'], instance['eojci'], instance['netaddr'])
        # probaby need to make this a bit more robust - per
        device_data = await hass.async_add_executor_job(device.update, [0x83,0x9f,0x9e])
        instance['getPropertyMap'] = device_data[0x9f]
        instance['setPropertyMap'] = device_data[0x9e]
        if device_data[0x83]:
            instance['UID'] = await hass.async_add_executor_job(device.getIdentificationNumber)
        else:
            instance['UID'] = f'{instance["netaddr"]}-{instance["eojgc"]}{instance["eojcc"]}{instance["eojci"]}'
    
    # if not await hub.authenticate(data["username"], data["password"]):
    #    raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return {"host": data["host"], "title": data["title"], "instances": discover}

# class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
#     VERSION = 1
#     task_one = None





class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for echonetlite."""
    discover_task = None
    polling_maps_task = None
    info = None
    VERSION = 1
    
    async def _async_do_task(self, task):
        self.info = await task  # A task that take some time to complete.
        self.hass.async_create_task(
             self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
        )
        return self.info

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
            
        # Commence discovery task... 
        _LOGGER.debug("Step 1 - test discovery task")
        return await self.async_step_discover(user_input)
    
    async def async_step_discover(self, user_input=None):
        _LOGGER.debug("Step 2")
        if not self.discover_task:
            _LOGGER.debug("Step 3")
            self.discover_task = self.hass.async_create_task(self._async_do_task(validate_input(self.hass, user_input)))
            return self.async_show_progress(step_id="discover", progress_action="user")
        
        return self.async_show_progress_done(next_step_id="finish")
    
    async def async_step_finish(self, user_input=None):
        _LOGGER.debug("Step 4")
        return self.async_create_entry(title=self.info["title"], data=self.info)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


    
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
