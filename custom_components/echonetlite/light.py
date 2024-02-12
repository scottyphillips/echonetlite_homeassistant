import logging

from pychonet.GeneralLighting import ENL_STATUS, ENL_BRIGHTNESS, ENL_COLOR_TEMP

from pychonet.lib.eojx import EOJX_CLASS

from homeassistant.components.light import LightEntity, ColorMode, LightEntityFeature
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
)

from .const import DATA_STATE_ON, DOMAIN, CONF_FORCE_POLLING

_LOGGER = logging.getLogger(__name__)

DEFAULT_BRIGHTNESS_SCALE = 255
MIN_MIREDS = 153
MAX_MIREDS = 500
DEVICE_SCALE = 100


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        if eojgc == 0x02 and eojcc in (0x90, 0x91):
            # General Lighting (0x90), Mono Functional Lighting (0x91)
            _LOGGER.debug("Configuring ECHONETlite Light entity")
            entities.append(
                EchonetLight(
                    entity["echonetlite"]._name or config_entry.title,
                    entity["echonetlite"],
                )
            )
    _LOGGER.debug(f"Number of light devices to be added: {len(entities)}")
    async_add_devices(entities, True)


class EchonetLight(LightEntity):
    """Representation of a ECHONET light device."""

    def __init__(self, name, connector):
        """Initialize the climate device."""
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
        self._attr_min_mireds = MIN_MIREDS
        self._attr_max_mireds = MAX_MIREDS
        self._attr_supported_color_modes.add(ColorMode.ONOFF)
        self._attr_color_mode = ColorMode.ONOFF
        if ENL_BRIGHTNESS in list(self._connector._setPropertyMap):
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
            self._attr_color_mode = ColorMode.BRIGHTNESS
        if ENL_COLOR_TEMP in list(self._connector._setPropertyMap):
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.COLOR_TEMP

        self._echonet_mireds = [
            "daylight_color",
            "daylight_white",
            "white",
            "other",
            "incandescent_lamp_color",
        ]  # coolest to warmest
        self._echonet_mireds_int = [68, 67, 66, 64, 65]  # coolest to warmest
        self._olddata = {}
        self._attr_is_on = (
            True if self._connector._update_data[ENL_STATUS] == DATA_STATE_ON else False
        )
        self._attr_should_poll = True
        self._attr_available = True

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
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._instance._eojgc][
                self._connector._instance._eojcc
            ],
            # "sw_version": "",
        }

    async def async_turn_on(self, **kwargs):
        """Turn on."""
        await self._connector._instance.on()

        if (
            ATTR_BRIGHTNESS in kwargs
            and self._attr_supported_color_modes
            and ColorMode.BRIGHTNESS in self._attr_supported_color_modes
        ):
            normalized_brightness = (
                float(kwargs[ATTR_BRIGHTNESS]) / DEFAULT_BRIGHTNESS_SCALE
            )
            device_brightness = round(normalized_brightness * DEVICE_SCALE)
            # Make sure the brightness is not rounded down to 0
            device_brightness = max(device_brightness, 1)

            # send the message to the lamp
            await self._connector._instance.setBrightness(device_brightness)
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        if (
            ATTR_COLOR_TEMP in kwargs
            and self._attr_supported_color_modes
            and ColorMode.COLOR_TEMP in self._attr_supported_color_modes
        ):
            # bring the selected color to something we can calculate on
            color_scale = (
                float(kwargs[ATTR_COLOR_TEMP]) - float(self._attr_min_mireds)
            ) / float(self._attr_max_mireds - self._attr_min_mireds)
            _LOGGER.debug(f"Set color to : {color_scale}")
            # bring the color to
            color_scale_echonet = color_scale * (len(self._echonet_mireds) - 1)
            # round it to an index
            echonet_idx = round(color_scale_echonet)
            color_temp = self._echonet_mireds[echonet_idx]
            color_temp_int = self._echonet_mireds_int[echonet_idx]

            _LOGGER.debug(f"New color temp of light: {color_temp} - {color_temp_int}")
            await self._connector._instance.setColorTemperature(color_temp_int)
            self._attr_color_temp = kwargs[ATTR_COLOR_TEMP]

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        await self._connector._instance.off()

    def _set_attrs(self):
        if (
            self._attr_supported_color_modes
            and ColorMode.BRIGHTNESS in self._attr_supported_color_modes
        ):
            """brightness of this light between 0..255."""
            _LOGGER.debug(
                f"Current brightness of light: {self._connector._update_data[ENL_BRIGHTNESS]}"
            )
            brightness = (
                int(self._connector._update_data[ENL_BRIGHTNESS], 16)
                if ENL_BRIGHTNESS in self._connector._update_data
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
            and ColorMode.COLOR_TEMP in self._attr_supported_color_modes
        ):
            """color temperature in mired."""
            _LOGGER.debug(
                f"Current color temp of light: {self._connector._update_data[ENL_COLOR_TEMP]}"
            )

            # calculate some helper
            mired_steps = (self._attr_max_mireds - self._attr_min_mireds) / float(
                len(self._echonet_mireds)
            )

            # get the current echonet mireds
            color_temp = (
                self._connector._update_data[ENL_COLOR_TEMP]
                if ENL_COLOR_TEMP in self._connector._update_data
                else "white"
            )
            if color_temp in self._echonet_mireds:
                self._attr_color_temp = (
                    round(self._echonet_mireds.index(color_temp) * mired_steps)
                    + MIN_MIREDS
                )
            else:
                self._attr_color_temp = MIN_MIREDS

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.add_update_option_listener(self.update_option_listener)
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush=False):
        changed = (
            self._olddata != self._connector._update_data
            or self._attr_available != self._server_state["available"]
        )
        if changed:
            _force = bool(not self._attr_available and self._server_state["available"])
            self._olddata = self._connector._update_data.copy()
            self._attr_is_on = (
                True
                if self._connector._update_data[ENL_STATUS] == DATA_STATE_ON
                else False
            )
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
            ENL_STATUS not in self._connector._ntfPropertyMap
            or (
                self._attr_supported_color_modes
                and COLOR_MODE_BRIGHTNESS in self._attr_supported_color_modes
                and ENL_BRIGHTNESS not in self._connector._ntfPropertyMap
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
