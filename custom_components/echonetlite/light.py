import logging

from pychonet.GeneralLighting import ENL_STATUS, ENL_BRIGHTNESS, ENL_COLOR_TEMP
from pychonet.CeilingFan import (
    ENL_FAN_LIGHT_STATUS,
    ENL_FAN_LIGHT_BRIGHTNESS,
    ENL_FAN_LIGHT_COLOR_TEMP,
)


from pychonet.lib.const import ENL_ON
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.epc_functions import _swap_dict

from homeassistant.components.light import (
    ATTR_EFFECT,
    LightEntity,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
)

from . import get_device_name
from .const import DATA_STATE_ON, DOMAIN, CONF_FORCE_POLLING

_LOGGER = logging.getLogger(__name__)

DEFAULT_BRIGHTNESS_SCALE = 255
MIN_MIREDS = 153  # 6500k
MAX_MIREDS = 500  # 2000k
DEVICE_SCALE = 100


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        if (eojgc == 0x02 and eojcc in (0x90, 0x91, 0xA3)) or (
            eojgc == 0x01
            and eojcc == 0x3A
            and ENL_FAN_LIGHT_STATUS in entity["echonetlite"]._setPropertyMap
        ):
            custom_options = {}
            # General Lighting (0x90), Mono Functional Lighting (0x91), Lighting System (0xA3)
            if eojgc == 0x02 and eojcc in (0x90, 0x91, 0xA3):
                custom_options = {
                    ENL_STATUS: ENL_STATUS,
                    ENL_BRIGHTNESS: ENL_BRIGHTNESS,
                    ENL_COLOR_TEMP: ENL_COLOR_TEMP,
                    "echonet_color": {
                        0x44: "daylight_color",
                        0x43: "daylight_white",
                        0x42: "white",
                        0x40: "other",
                        0x41: "incandescent_lamp_color",
                    },
                    "echonet_mireds_int": {
                        0x44: 153,  # 6500K
                        0x43: 200,  # 5000K
                        0x42: 238,  # 4200K
                        0x40: 285,  # 3500K
                        0x41: 370,  # 2700K
                    },  # coolest to warmest value is mired
                    "on": "on",
                    "off": "off",
                }
                custom_options["echonet_int_color"] = _swap_dict(
                    custom_options["echonet_color"]
                )
            # Ceiling Fan (0x01-0x3A)
            elif eojgc == 0x01 and eojcc == 0x3A:
                custom_options = {
                    ENL_STATUS: ENL_FAN_LIGHT_STATUS,
                    ENL_BRIGHTNESS: ENL_FAN_LIGHT_BRIGHTNESS,
                    ENL_COLOR_TEMP: ENL_FAN_LIGHT_COLOR_TEMP,
                    "echonet_color": None,
                    "echonet_mireds_int": None,
                    "on": "light_on",
                    "off": "light_off",
                }
            _LOGGER.debug("Configuring ECHONETlite Light entity")
            entities.append(
                EchonetLight(
                    entity["echonetlite"],
                    config_entry,
                    custom_options,
                )
            )
    _LOGGER.debug(f"Number of light devices to be added: {len(entities)}")
    async_add_devices(entities, True)


class EchonetLight(LightEntity):
    """Representation of a ECHONET light device."""

    def __init__(self, connector, config, custom_options):
        """Initialize the climate device."""
        name = get_device_name(connector, config)
        self._attr_name = name
        self._connector = connector  # new line
        self._attr_unique_id = (
            self._connector._uidi if self._connector._uidi else self._connector._uid
        )
        self._attr_supported_features = LightEntityFeature(0)
        self._attr_supported_color_modes = set()
        self._server_state = self._connector._api._state[
            self._connector._instance._host
        ]
        if mireds_int := custom_options.get("echonet_mireds_int"):
            mireds = mireds_int.values()
            self._attr_min_mireds = min(mireds)
            self._attr_max_mireds = max(mireds)
        else:
            self._attr_min_mireds = MIN_MIREDS
            self._attr_max_mireds = MAX_MIREDS
        self._custom_options = custom_options
        if custom_options[ENL_COLOR_TEMP] in list(self._connector._setPropertyMap):
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.COLOR_TEMP
        if custom_options[ENL_BRIGHTNESS] in list(self._connector._setPropertyMap):
            if not self._attr_supported_color_modes:
                self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
                self._attr_color_mode = ColorMode.BRIGHTNESS
        if not self._attr_supported_color_modes:
            self._attr_supported_color_modes.add(ColorMode.ONOFF)
            self._attr_color_mode = ColorMode.ONOFF

        self._olddata = {}
        self._attr_is_on = (
            True
            if self._connector._update_data[custom_options[ENL_STATUS]] == DATA_STATE_ON
            else False
        )

        if hasattr(self._connector._instance, "getEffectList"):
            self._attr_effect_list = self._connector._instance.getEffectList()
            if self._attr_effect_list:
                self._attr_supported_features |= LightEntityFeature.EFFECT

        self._attr_should_poll = True
        self._attr_available = True

        self._set_attrs()

        self.update_option_listener()

    async def async_update(self):
        """Get the latest state from the Light."""
        try:
            await self._connector.async_update()
        except TimeoutError:
            pass

    @property
    def device_info(self):
        return {
            "identifiers": {
                (
                    DOMAIN,
                    self._connector._uid,
                    self._connector._instance._eojgc,
                    self._connector._instance._eojcc,
                    self._connector._instance._eojci,
                )
            },
            "name": self._attr_name,
            "manufacturer": self._connector._manufacturer
            + (
                " " + self._connector._host_product_code
                if self._connector._host_product_code
                else ""
            ),
            "model": EOJX_CLASS[self._connector._instance._eojgc][
                self._connector._instance._eojcc
            ],
            # "sw_version": "",
        }

    async def async_turn_on(self, **kwargs):
        states = {"status": ENL_ON}

        if (
            ATTR_BRIGHTNESS in kwargs
            and self._attr_supported_color_modes
            and self._attr_color_mode in {ColorMode.BRIGHTNESS, ColorMode.COLOR_TEMP}
        ):
            normalized_brightness = (
                float(kwargs[ATTR_BRIGHTNESS]) / DEFAULT_BRIGHTNESS_SCALE
            )
            device_brightness = round(normalized_brightness * DEVICE_SCALE)
            # Make sure the brightness is not rounded down to 0
            device_brightness = max(device_brightness, 1)

            # send the message to the lamp
            states["brightness"] = device_brightness
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        if (
            ATTR_COLOR_TEMP in kwargs
            and self._attr_supported_color_modes
            and self._attr_color_mode == ColorMode.COLOR_TEMP
        ):
            attr_color_tmp = float(kwargs[ATTR_COLOR_TEMP])
            if self._custom_options["echonet_color"]:
                color_temp_int = 0x41
                for i, mired in self._custom_options["echonet_mireds_int"].items():
                    if attr_color_tmp <= mired + 15:
                        color_temp_int = i
                        break
                color_temp = self._custom_options["echonet_color"].get(color_temp_int)
                _LOGGER.debug(
                    f"New color temp of light: {color_temp} - {color_temp_int}"
                )
                self._attr_color_temp = int(
                    self._custom_options["echonet_mireds_int"].get(color_temp_int)
                )
            else:
                color_scale = (attr_color_tmp - float(self._attr_min_mireds)) / float(
                    self._attr_max_mireds - self._attr_min_mireds
                )
                _LOGGER.debug(f"Set color to : {color_scale}")
                color_temp_int = (1 - color_scale) * 100
                _LOGGER.debug(
                    f"New color temp of light: {attr_color_tmp} mireds - {color_temp_int}"
                )
                self._attr_color_temp = int(attr_color_tmp)

            states["color_temperature"] = int(color_temp_int)

        if ATTR_EFFECT in kwargs and kwargs[ATTR_EFFECT] in self._attr_effect_list:
            states[ATTR_EFFECT] = kwargs[ATTR_EFFECT]

        if hasattr(self._connector._instance, "setLightStates"):
            return await self._connector._instance.setLightStates(states)
        else:
            """Turn on."""
            result = await getattr(
                self._connector._instance, self._custom_options["on"]
            )()

            if result:
                if states.get("brightness"):
                    result &= await self._connector._instance.setBrightness(
                        states["brightness"]
                    )

                if states.get("color_temperature"):
                    result &= await self._connector._instance.setColorTemperature(
                        states["color_temperature"]
                    )

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        await getattr(self._connector._instance, self._custom_options["off"])()

    def _set_attrs(self):
        if self._attr_supported_color_modes and self._attr_color_mode in {
            ColorMode.BRIGHTNESS,
            ColorMode.COLOR_TEMP,
        }:
            """brightness of this light between 0..255."""
            _LOGGER.debug(
                f"Current brightness of light: {self._connector._update_data[self._custom_options[ENL_BRIGHTNESS]]}"
            )
            brightness = (
                int(self._connector._update_data[self._custom_options[ENL_BRIGHTNESS]])
                if self._custom_options[ENL_BRIGHTNESS] in self._connector._update_data
                else -1
            )
            if brightness >= 0:
                self._attr_brightness = min(
                    round(float(brightness) / DEVICE_SCALE * DEFAULT_BRIGHTNESS_SCALE),
                    255,
                )
            else:
                self._attr_brightness = 128

        if (
            self._attr_supported_color_modes
            and self._attr_color_mode == ColorMode.COLOR_TEMP
        ):
            """color temperature in mired."""
            enl_color_temp = self._custom_options[ENL_COLOR_TEMP]
            _LOGGER.debug(
                f"Current color temp of light: {self._connector._update_data[enl_color_temp]}"
            )

            if self._custom_options["echonet_color"]:
                # get the current echonet mireds
                color_temp = (
                    self._connector._update_data[enl_color_temp]
                    if enl_color_temp in self._connector._update_data
                    else "white"
                )
                self._attr_color_temp = self._custom_options["echonet_mireds_int"].get(
                    self._custom_options["echonet_int_color"].get(color_temp), 153
                )
            else:
                self._attr_color_temp = (
                    self._attr_max_mireds - self._attr_min_mireds
                ) * (
                    (100 - self._connector._update_data[enl_color_temp]) / 100
                ) + self._attr_min_mireds

        if hasattr(self._connector._instance, "getEffect"):
            self._attr_effect = self._connector._instance.getEffect()

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush: bool = False):
        changed = (
            self._olddata != self._connector._update_data
            or self._attr_available != self._server_state["available"]
        )
        if changed:
            _force = bool(not self._attr_available and self._server_state["available"])
            self._olddata = self._connector._update_data.copy()
            self._attr_is_on = (
                True
                if self._connector._update_data[self._custom_options[ENL_STATUS]]
                == DATA_STATE_ON
                else False
            )
            if self._attr_available != self._server_state["available"]:
                if self._server_state["available"]:
                    self.update_option_listener()
                else:
                    self._attr_should_poll = True
            self._attr_available = self._server_state["available"]
            self._set_attrs()
            self.async_schedule_update_ha_state(_force)
            if isPush and self._attr_should_poll:
                try:
                    await self._connector.async_update()
                except TimeoutError:
                    pass

    def update_option_listener(self):
        _should_poll = (
            self._custom_options[ENL_STATUS] not in self._connector._ntfPropertyMap
            or (
                self._attr_supported_color_modes
                and COLOR_MODE_BRIGHTNESS in self._attr_supported_color_modes
                and self._custom_options[ENL_BRIGHTNESS]
                not in self._connector._ntfPropertyMap
            )
            or (
                self._attr_supported_color_modes
                and COLOR_MODE_COLOR_TEMP in self._attr_supported_color_modes
                and ENL_COLOR_TEMP not in self._connector._ntfPropertyMap
            )
        )
        self._attr_should_poll = bool(
            self._connector._user_options.get(CONF_FORCE_POLLING, False) or _should_poll
        )
        self._attr_extra_state_attributes = {"notify": "No" if _should_poll else "Yes"}
        _LOGGER.debug(f"{self._attr_name}: _should_poll is {_should_poll}")
