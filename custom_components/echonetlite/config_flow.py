"""Config flow for echonetlite integration."""

from __future__ import annotations

import logging
import asyncio
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import selector
from pychonet.lib.const import (
    ENL_STATMAP,
    ENL_SETMAP,
    ENL_GETMAP,
    GET,
)

# from aioudp import UDPServer
from pychonet.lib.udpserver import UDPServer
from pychonet.lib.epc_functions import _null_padded_optional_string

# from pychonet import Factory
from pychonet import ECHONETAPIClient

from pychonet.HomeAirConditioner import (
    ENL_AIR_VERT,
    ENL_AUTO_DIRECTION,
    ENL_SWING_MODE,
)

from .const import (
    DOMAIN,
    USER_OPTIONS,
    TEMP_OPTIONS,
    MISC_OPTIONS,
    ENL_HVAC_MODE,
    CONF_OTHER_MODE,
    OPTION_HA_UI_SWING,
)

_LOGGER = logging.getLogger(__name__)

WORD_OF_AUTO_DISCOVERY = "[Auto Discovery]"

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host", default=WORD_OF_AUTO_DISCOVERY): str,
        vol.Required("title", default=WORD_OF_AUTO_DISCOVERY): str,
    }
)

_detected_hosts = {}
_init_server = None


async def enumerate_instances(
    hass: HomeAssistant, host: str, newhost: bool = False
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    _LOGGER.debug(f"IP address is {host}")
    server = None
    if DOMAIN in hass.data:  # maybe set up by config entry?
        _LOGGER.debug("API listener has already been setup previously..")
        server = hass.data[DOMAIN]["api"]
        for key in hass.data[DOMAIN]:
            if key != "api":
                entries = hass.data[DOMAIN][key]
                if len(entries):
                    inst = entries[0].get("instance")
                    if inst:
                        if inst.get("host") == host:
                            raise ErrorConnect("already_configured")
    elif _init_server:
        _LOGGER.debug("API listener has already been setup in init_discover()")
        server = _init_server
    else:
        udp = UDPServer()
        loop = asyncio.get_event_loop()
        udp.run("0.0.0.0", 3610, loop=loop)
        server = ECHONETAPIClient(server=udp)
        server._debug_flag = True
        server._logger = _LOGGER.debug
        server._message_timeout = 300

    # make sure multicast is registered with the local IP used to reach this host
    server._server.register_multicast_from_host(host)

    instance_list = []
    _LOGGER.debug("Beginning ECHONET node discovery")
    await server.discover(host)

    # Timeout after 10 seconds
    for x in range(0, 1000):
        await asyncio.sleep(0.01)
        if "discovered" in list(server._state[host]):
            _LOGGER.debug("ECHONET Node Discovery Successful!")
            break
    if "discovered" not in list(server._state[host]):
        _LOGGER.debug("ECHONET Node Discovery Failed!")
        raise ErrorConnect("cannot_connect")
    state = server._state[host]
    uid = state["uid"]

    # check ip addr changed
    if newhost:
        config_entry = None
        old_host = None
        entries = hass.config_entries.async_entries(DOMAIN)

        for entry in entries:
            instances = []
            _data = entry.data
            for _instance in _data.get("instances", []):
                instance = _instance.copy()
                if old_host or instance.get("uid") == uid:
                    old_host = instance["host"]
                    instance["host"] = host
                instances.append(instance)
            if old_host:
                config_entry = entry
                _LOGGER.debug(
                    f"ECHONET registed node found uid is {uid}, conig entry id is {entry.entry_id}."
                )
                break

        if old_host:
            _LOGGER.debug(
                f"ECHONET registed node IP changed from {old_host} to {host}."
            )
            _LOGGER.debug(f"New instances data is {instances}")
            if server._state.get(old_host):
                server._state[host] = server._state.pop(old_host)
            hass.config_entries.async_update_entry(
                config_entry, data={"host": host, "instances": instances}
            )

            # Wait max 30 secs for entry loaded
            for x in range(0, 300):
                await asyncio.sleep(0.1)
                if entry.state == ConfigEntryState.LOADED:
                    await hass.config_entries.async_reload(entry.entry_id)
                    break

            raise ErrorIpChanged(host)

    manufacturer = state["manufacturer"]
    host_product_code = state.get("product_code")
    if not isinstance(manufacturer, str):
        # If unable to resolve the manufacturer,
        # the raw identification number will be passed as int.
        _LOGGER.warn(
            f"{host} - Unable to resolve the manufacturer name - {manufacturer}. "
            + "Please report the manufacturer name of your device at the issue tracker on GitHub!"
        )
        manufacturer = f"Unknown({manufacturer})"

    for eojgc in list(state["instances"].keys()):
        for eojcc in list(state["instances"][eojgc].keys()):
            for instance in list(state["instances"][eojgc][eojcc].keys()):
                _LOGGER.debug(f"instance is {instance}")

                cnt = 0
                while (
                    await server.getAllPropertyMaps(host, eojgc, eojcc, instance)
                    is False
                ):
                    cnt += 1
                    if cnt > 2:
                        raise ErrorConnect("cannot_get_property_maps")

                _LOGGER.debug(
                    f"{host} - ECHONET Instance {eojgc}-{eojcc}-{instance} map attributes discovered!"
                )
                ntfmap = state["instances"][eojgc][eojcc][instance].get(ENL_STATMAP, [])
                getmap = state["instances"][eojgc][eojcc][instance][ENL_GETMAP]
                setmap = state["instances"][eojgc][eojcc][instance][ENL_SETMAP]

                uidi = f"{uid}-{eojgc}-{eojcc}-{instance}"
                name = None
                if host_product_code == "WTY2001" and eojcc == 0x91:
                    # Panasonic WTY2001 Advanced Series Link Plus Wireless Adapter
                    await server.echonetMessage(
                        host,
                        eojgc,
                        eojcc,
                        instance,
                        GET,
                        [{"EPC": 0xFD}, {"EPC": 0xFE}],
                    )
                    # Use Use HW ID because the instance number is uncertain
                    # https://github.com/scottyphillips/echonetlite_homeassistant/issues/117#issuecomment-1929151918
                    uidi = _null_padded_optional_string(
                        state["instances"][eojgc][eojcc][instance][0xFE]
                    )
                    name = _null_padded_optional_string(
                        state["instances"][eojgc][eojcc][instance][0xFD]
                    )

                instance_list.append(
                    {
                        "host": host,
                        "name": name,
                        "eojgc": eojgc,
                        "eojcc": eojcc,
                        "eojci": instance,
                        "ntfmap": ntfmap,
                        "getmap": getmap,
                        "setmap": setmap,
                        "uid": uid,  # Deprecated, for backwards compatibility
                        "uidi": uidi,
                        "manufacturer": manufacturer,
                        "host_product_code": host_product_code,
                    }
                )

    return instance_list


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for echonetlite."""

    host = None
    title = None
    discover_task = None
    instance_list = None
    instances = None
    VERSION = 1

    async def init_discover(self):
        async def discover_callback(host):
            await config_entries.HANDLERS[DOMAIN].async_discover_newhost(
                self.hass, host
            )

        if DOMAIN in self.hass.data:  # maybe set up by config entry?
            _LOGGER.debug("API listener has already been setup previously..")
            server = self.hass.data[DOMAIN]["api"]

            _init_server = None

        else:
            udp = UDPServer()
            loop = asyncio.get_event_loop()
            udp.run("0.0.0.0", 3610, loop=loop)
            server = ECHONETAPIClient(server=udp)
            server._debug_flag = True
            server._logger = _LOGGER.debug
            server._message_timeout = 300
            server._discover_callback = discover_callback

            _init_server = server

        await server.discover()

        # Timeout after 30 seconds
        for x in range(0, 3000):
            await asyncio.sleep(0.01)
            if len(_detected_hosts):
                _LOGGER.debug("ECHONET Any Node Discovery Successful!")
                break

        if _init_server:
            _init_server._server._sock.close()
            del _init_server
            _init_server = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        """Handle the initial step."""
        scm = STEP_USER_DATA_SCHEMA
        if user_input is None or user_input.get("host") == WORD_OF_AUTO_DISCOVERY:
            step = "user_man"
            if (
                user_input
                and user_input.get("host") == WORD_OF_AUTO_DISCOVERY
                and not len(_detected_hosts)
            ):
                await self.init_discover()
            if len(_detected_hosts):
                host = list(_detected_hosts.keys()).pop(0)
                title = _detected_hosts[host][0]["manufacturer"]
                if _detected_hosts[host][0]["host_product_code"]:
                    title += " " + _detected_hosts[host][0]["host_product_code"]
            else:
                if user_input is None:
                    host = title = WORD_OF_AUTO_DISCOVERY
                    step = "user"
                else:
                    host = ""
                    title = ""
                    errors["base"] = "not_found"
            scm = scm.extend(
                {
                    vol.Required("host", default=host): str,
                    vol.Required("title", default=title): str,
                }
            )
            return self.async_show_form(step_id=step, data_schema=scm, errors=errors)
        try:
            self.instance_list = await enumerate_instances(
                self.hass, user_input["host"]
            )
            _LOGGER.debug("Node detected")
        except ErrorConnect as e:
            errors["base"] = f"{e}"
        else:
            self.host = user_input["host"]
            self.title = user_input["title"]
            return await self.async_step_finish(user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_user_man(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_user(user_input)

    async def async_step_finish(self, user_input=None):
        if len(_detected_hosts) and self.host in _detected_hosts.keys():
            _detected_hosts.pop(self.host)
        return self.async_create_entry(
            title=self.title,
            data={"host": self.host, "instances": self.instance_list},
            options={"other_mode": "as_off"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

    @staticmethod
    @callback
    async def async_discover_newhost(hass, host):
        _LOGGER.debug(f"received newip discovery: {host}")
        if host not in _detected_hosts.keys():
            try:
                instance_list = await enumerate_instances(hass, host, newhost=True)
                _LOGGER.debug(f"ECHONET Node detected in {host}")
            except ErrorConnect as e:
                _LOGGER.debug(f"ECHONET Node Error Connect ({e})")
            except ErrorIpChanged as e:
                _LOGGER.debug(f"ECHONET Detected Node IP Changed to '{e}'")
            else:
                if len(instance_list):
                    _detected_hosts.update({host: instance_list})
                else:
                    _LOGGER.debug(f"ECHONET Node not found in {host}")


class ErrorConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class ErrorIpChanged(HomeAssistantError):
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
            if (
                instance["eojgc"] == 0x01 and instance["eojcc"] == 0x30
            ):  # HomeAirConditioner
                ha_swing_list = []
                for option in list(USER_OPTIONS.keys()):
                    if option in instance["setmap"]:
                        if option in [ENL_AIR_VERT, ENL_AUTO_DIRECTION, ENL_SWING_MODE]:
                            ha_swing_list.append(option)
                        if (
                            self._config_entry.options.get(
                                USER_OPTIONS[option]["option"]
                            )
                            is not None
                        ):
                            option_default = self._config_entry.options.get(
                                USER_OPTIONS[option]["option"]
                            )
                        else:
                            if isinstance(USER_OPTIONS[option]["option_list"], list):
                                # single select
                                option_default = USER_OPTIONS[option]["option_list"][0][
                                    "value"
                                ]
                            elif isinstance(USER_OPTIONS[option]["option_list"], dict):
                                # multi selectable
                                option_default = list(
                                    USER_OPTIONS[option]["option_list"].keys()
                                )
                            else:
                                option_default = []
                        data_schema_structure.update(
                            {
                                vol.Optional(
                                    USER_OPTIONS[option]["option"],
                                    default=option_default,
                                ): cv.multi_select(USER_OPTIONS[option]["option_list"])
                            }
                        )

                # Handle setting Climate entity UI swing mode
                if len(ha_swing_list) > 0:
                    option_list = {}
                    for opt in ha_swing_list:
                        option_list.update(USER_OPTIONS[opt]["option_list"])
                    if ENL_AIR_VERT in instance["setmap"]:
                        for del_key in [
                            "auto",
                            "non-auto",
                            "auto-horiz",
                            "not-used",
                            "horiz",
                            "vert-horiz",
                        ]:
                            option_list.pop(del_key, None)
                    if self._config_entry.options.get(OPTION_HA_UI_SWING) is not None:
                        option_default = self._config_entry.options.get(
                            OPTION_HA_UI_SWING
                        )
                    else:
                        option_default = list(option_list.keys())
                    data_schema_structure.update(
                        {
                            vol.Optional(
                                OPTION_HA_UI_SWING,
                                default=option_default,
                            ): cv.multi_select(option_list)
                        }
                    )

                # Handle setting temperature ranges for various modes of operation
                for option in list(TEMP_OPTIONS.keys()):
                    default_temp = TEMP_OPTIONS[option]["min"]
                    if self._config_entry.options.get(option) is not None:
                        default_temp = self._config_entry.options.get(option)
                    else:
                        default_temp = TEMP_OPTIONS[option]["default"]
                    data_schema_structure.update(
                        {
                            vol.Required(option, default=default_temp): vol.All(
                                vol.Coerce(int),
                                vol.Range(
                                    min=TEMP_OPTIONS[option]["min"],
                                    max=TEMP_OPTIONS[option]["max"],
                                ),
                            )
                        }
                    )

                # Handle setting for the operation mode "Other"
                option_default = "as_off"
                if self._config_entry.options.get(CONF_OTHER_MODE) is not None:
                    option_default = self._config_entry.options.get(CONF_OTHER_MODE)
                data_schema_structure.update(
                    {
                        vol.Optional(
                            USER_OPTIONS[ENL_HVAC_MODE]["option"],
                            default=option_default,
                        ): selector(
                            {
                                "select": {
                                    "options": USER_OPTIONS[ENL_HVAC_MODE][
                                        "option_list"
                                    ],
                                    "mode": "dropdown",
                                }
                            }
                        )
                    }
                )

            elif instance["eojgc"] == 0x01 and instance["eojcc"] == 0x35:  # AirCleaner
                for option in list(USER_OPTIONS.keys()):
                    if option in instance["setmap"]:
                        option_default = []
                        if (
                            self._config_entry.options.get(
                                USER_OPTIONS[option]["option"]
                            )
                            is not None
                        ):
                            option_default = self._config_entry.options.get(
                                USER_OPTIONS[option]["option"]
                            )
                        data_schema_structure.update(
                            {
                                vol.Optional(
                                    USER_OPTIONS[option]["option"],
                                    default=option_default,
                                ): cv.multi_select(USER_OPTIONS[option]["option_list"])
                            }
                        )

        for key, option in MISC_OPTIONS.items():
            if "min" in option and "max" in option:
                _type = vol.All(
                    vol.Coerce(option["type"]),
                    vol.Range(min=option["min"], max=option["max"]),
                )
            else:
                _type = option["type"]
            data_schema_structure.update(
                {
                    vol.Required(
                        key,
                        default=self._config_entry.options.get(key, option["default"]),
                    ): _type
                }
            )

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
