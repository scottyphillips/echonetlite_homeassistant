"""Config flow for echonetlite integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, FAN_SPEED_OPTIONS

AIRFLOW_HORIZ = {
    'rc-right':             0x41,
    'left-lc':              0x42,
    'lc-center-rc':         0x43,
    'left-lc-rc-right':     0x44,
    'right':                0x51,
    'rc':                   0x52,
    'center':               0x54,
    'center-right':         0x55,
    'center-rc':            0x56,
    'center-rc-right':      0x57,
    'lc':                   0x58,
    'lc-right':             0x59,
    'lc-rc':                0x5A,
    'left':                 0x60,
    'left-right':           0x61,
    'left-rc':              0x62,
    'left-rc-right':        0x63,
    'left-center':          0x64,
    'left-center-right':    0x65,
    'left-center-rc':       0x66,
    'left-center-rc-right': 0x67,
    'left-lc-right':        0x69,
    'left-lc-rc':           0x6A
}

AIRFLOW_VERT = {
    'upper':            0x41,
    'upper-central':    0x44,
    'central':          0x43,
    'lower-central':    0x45,
    'lower':            0x42
}


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



class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for echonetlite."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=info)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
        
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
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "fan_settings",
                       default=self._config_entry.options.get("fan_settings") if self._config_entry.options.get("fan_settings") is not None else [] ,
                    ): cv.multi_select(FAN_SPEED_OPTIONS),
#                    vol.Optional(
#                        "swing_horiz",
#                        default = []# default=self._config_entry.options.get("swing_horiz"),
#                    ): cv.multi_select({'horizontal 1':'test', 'horizontal 2':2}),
#                    vol.Optional(
#                        "swing_vert",
#                        default = []
#                        # default=self._config_entry.options.get("swing_vert"),
#                    ): cv.multi_select({'vert 1':1, 'vert 2':2}),
                }
            ),
        )
