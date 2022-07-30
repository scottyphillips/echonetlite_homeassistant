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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import selector
from pychonet.lib.const import ENL_STATMAP, ENL_SETMAP, ENL_GETMAP, ENL_UID, ENL_MANUFACTURER
#from aioudp import UDPServer
from pychonet.lib.udpserver import UDPServer
# from pychonet import Factory
from pychonet import ECHONETAPIClient
from .const import DOMAIN, USER_OPTIONS, TEMP_OPTIONS, CONF_FORCE_POLLING, MISC_OPTIONS, ENL_HVAC_MODE, CONF_OTHER_MODE

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("title"): str,
    }
)


async def validate_input(hass: HomeAssistant,  user_input: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    _LOGGER.debug(f"IP address is {user_input['host']}")
    host = user_input['host']
    server = None
    finished_instances = {}
    if DOMAIN in hass.data:  # maybe set up by config entry?
        _LOGGER.debug("API listener has already been setup previously..")
        server = hass.data[DOMAIN]['api']
    else:
        udp = UDPServer()
        loop = asyncio.get_event_loop()
        udp.run("0.0.0.0", 3610, loop=loop)
        server = ECHONETAPIClient(server=udp)

    instance_list = []
    _LOGGER.debug("Beginning ECHONET node discovery")
    await server.discover(host)

    # Timeout after 3 seconds
    for x in range(0, 300):
        await asyncio.sleep(0.01)
        if 'discovered' in list(server._state[host]):
            _LOGGER.debug("ECHONET Node Discovery Successful!")
            break
    if 'discovered' not in list(server._state[host]):
        _LOGGER.debug("ECHONET Node Discovery Failed!")
        raise CannotConnect("ECHONET node is not online")
    state = server._state[host]
    uid = state['uid']
    manufacturer = state['manufacturer']
    if not isinstance(manufacturer, str):
        # If unable to resolve the manufacturer,
        # the raw identification number will be passed as int.
        _LOGGER.warn(
            f"{host} - Unable to resolve the manufacturer name - {manufacturer}. " +
            "Please report the manufacturer name of your device at the issue tracker on GitHub!"
        )
        manufacturer = f"Unknown({manufacturer})"

    for eojgc in list(state['instances'].keys()):
        for eojcc in list(state['instances'][eojgc].keys()):
            for instance in list(state['instances'][eojgc][eojcc].keys()):
                _LOGGER.debug(f"instance is {instance}")

                await server.getAllPropertyMaps(host, eojgc, eojcc, instance)
                _LOGGER.debug(f"{host} - ECHONET Instance {eojgc}-{eojcc}-{instance} map attributes discovered!")
                ntfmap = state['instances'][eojgc][eojcc][instance].get(ENL_STATMAP, [])
                getmap = state['instances'][eojgc][eojcc][instance][ENL_GETMAP]
                setmap = state['instances'][eojgc][eojcc][instance][ENL_SETMAP]

                _LOGGER.debug(f"{host} - ECHONET Instance {eojgc}-{eojcc}-{instance} Identification number discovered!")
                instance_list.append({
                    "host": host,
                    "eojgc": eojgc,
                    "eojcc": eojcc,
                    "eojci": instance,
                    "ntfmap": ntfmap,
                    "getmap": getmap,
                    "setmap": setmap,
                    "uid": uid,
                    "manufacturer": manufacturer
                })

    return instance_list


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for echonetlite."""
    host = None
    title = None
    discover_task = None
    instance_list = None
    instances = None
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        try:
            self.instance_list = await validate_input(self.hass, user_input)
            _LOGGER.debug("Node detected")
        except CannotConnect:
            errors["base"] = "cannot_connect"
        else:
            self.host = user_input["host"]
            self.title = user_input["title"]
            return await self.async_step_finish(user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_finish(self, user_input=None):
        return self.async_create_entry(title=self.title, data={"instances": self.instance_list}, options={"other_mode": "as_off"})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config):
        self._config_entry = config
        self._data = {}

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        data_schema_structure = {}

        # Handle HVAC and Air Cleaner User configurable options
        for instance in self._config_entry.data["instances"]:
            if instance['eojgc'] == 0x01 and instance['eojcc'] == 0x30:  # HomeAirConditioner
                for option in list(USER_OPTIONS.keys()):
                    if option in instance['setmap']:
                        option_default = []
                        if self._config_entry.options.get(USER_OPTIONS[option]['option']) is not None:
                            option_default = self._config_entry.options.get(USER_OPTIONS[option]['option'])
                        data_schema_structure.update({
                            vol.Optional(
                                USER_OPTIONS[option]['option'],
                                default=option_default
                            ): cv.multi_select(
                                USER_OPTIONS[option]['option_list']
                            )
                        })

                # Handle setting temperature ranges for various modes of operation
                for option in list(TEMP_OPTIONS.keys()):
                    default_temp = TEMP_OPTIONS[option]['min']
                    if self._config_entry.options.get(option) is not None:
                        default_temp = self._config_entry.options.get(option)
                    data_schema_structure.update({
                            vol.Required(
                                option,
                                default=default_temp
                            ): vol.All(vol.Coerce(int), vol.Range(min=TEMP_OPTIONS[option]['min'], max=TEMP_OPTIONS[option]['max']))
                    })

                # Handle setting for the operation mode "Other"
                option_default = 'as_off'
                if self._config_entry.options.get(CONF_OTHER_MODE) is not None:
                    option_default = self._config_entry.options.get(CONF_OTHER_MODE)
                data_schema_structure.update({
                    vol.Optional(
                        USER_OPTIONS[ENL_HVAC_MODE]['option'],
                        default=option_default
                    ): selector({
                        "select": {
                            "options": USER_OPTIONS[ENL_HVAC_MODE]['option_list'],
                            "mode": "dropdown"
                        }
                    })
                })

            elif instance['eojgc'] == 0x01 and instance['eojcc'] == 0x35:  # AirCleaner
                for option in list(USER_OPTIONS.keys()):
                    if option in instance['setmap']:
                        option_default = []
                        if self._config_entry.options.get(USER_OPTIONS[option]['option']) is not None:
                            option_default = self._config_entry.options.get(USER_OPTIONS[option]['option'])
                        data_schema_structure.update({
                            vol.Optional(
                                USER_OPTIONS[option]['option'],
                                default=option_default
                            ): cv.multi_select(
                                USER_OPTIONS[option]['option_list']
                            )
                        })

        for key, option in MISC_OPTIONS.items():
            data_schema_structure.update({
                vol.Required(
                    CONF_FORCE_POLLING,
                    default=self._config_entry.options.get(key, option['default'])
                ): option['type']
            })


        if user_input is not None or not any(data_schema_structure):
            if user_input is not None:
                self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)
            # return await self.async_step_misc()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(data_schema_structure),
        )

    async def async_step_misc(self, user_input=None):
        """Manage the options."""
        data_schema_structure = {}

        # for key, option in MISC_OPTIONS.items():
        #     data_schema_structure.update({
        #         vol.Required(
        #             CONF_FORCE_POLLING,
        #             default=self._config_entry.options.get(key, option['default'])
        #         ): option['type']
        #     })

        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)
        return self.async_show_form(
            step_id="misc",
            data_schema=vol.Schema(data_schema_structure),
        )
