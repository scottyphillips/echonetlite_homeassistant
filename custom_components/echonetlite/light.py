import logging

from pychonet.GeneralLighting import (
    ENL_STATUS,
    ENL_BRIGHTNESS,
    ENL_COLOR_TEMP
)

from pychonet.lib.eojx import EOJX_CLASS

from homeassistant.components.light import LightEntity
from homeassistant.components.light import (
    COLOR_MODE_ONOFF,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = 0
DEFAULT_BRIGHTNESS_SCALE = 255
MIN_MIREDS = 153
MAX_MIREDS = 500
DEVICE_SCALE = 100


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        if entity['instance']['eojgc'] == 0x02 and entity['instance']['eojcc'] == 0x90:  # General Lighting
            _LOGGER.debug("Configuring ECHONETlite Light entity")
            entities.append(EchonetLight(config_entry.title, entity['echonetlite']))
    _LOGGER.debug(f"Number of light devices to be added: {len(entities)}")
    async_add_devices(entities, True)


class EchonetLight(LightEntity):

    """Representation of a ECHONET light device."""

    def __init__(self, name, connector):

        """Initialize the climate device."""
        self._name = name
        self._connector = connector  # new line
        self._uid = self._connector._uid
        self._support_flags = SUPPORT_FLAGS
        self._supported_color_modes = set()
        self._supports_color = False
        self._supports_rgbw = False
        self._supports_color_temp = False
        self._hs_color: tuple[float, float] | None = None
        self._rgbw_color: tuple[int, int, int, int] | None = None
        self._color_mode: str | None = None
        self._color_temp: int | None = None
        self._min_mireds = MIN_MIREDS
        self._max_mireds = MAX_MIREDS
        if ENL_BRIGHTNESS in list(self._connector._setPropertyMap):
            self._supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
        if ENL_COLOR_TEMP in list(self._connector._setPropertyMap):
            self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)

        self._echonet_mireds = ['daylight_color',
            'daylight_white', 'white', 'other', 'incandescent_lamp_color']  # coolest to warmest
        self._echonet_mireds_int = [68, 67, 66, 64, 65]  # coolest to warmest
        self._olddata = {}
        self._should_poll = True
        self._connector._instance.register_async_update_callbacks(self.async_update_callback)

    async def async_update(self):
        """Get the latest state from the Light."""
        await self._connector.async_update()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._uid

    @property
    def device_info(self):
        return {
            "identifiers": {
                  (DOMAIN, self._connector._uid, self._connector._instance._eojgc, self._connector._instance._eojcc, self._connector._instance._eojci)
            },
            "name": self._name,
            "manufacturer": self._connector._manufacturer,
            "model": EOJX_CLASS[self._connector._instance._eojgc][self._connector._instance._eojcc]
            # "sw_version": "",
        }

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the light device."""
        return self._name

    @property
    def is_on(self):
        """Return true if the device is on."""
        return True if self._connector._update_data[ENL_STATUS] == "On" else False

    async def async_turn_on(self, **kwargs):
        """Turn on."""
        await self._connector._instance.on()
        self._connector._update_data[ENL_STATUS] = "On"

        if ATTR_BRIGHTNESS in kwargs and COLOR_MODE_BRIGHTNESS in self._supported_color_modes:
            normalized_brightness = float(kwargs[ATTR_BRIGHTNESS]) / DEFAULT_BRIGHTNESS_SCALE
            device_brightness = round(normalized_brightness * DEVICE_SCALE)
            # Make sure the brightness is not rounded down to 0
            device_brightness = max(device_brightness, 1)

            # send the message to the lamp
            await self._connector._instance.setBrightness(device_brightness)
            self._connector._update_data[ENL_BRIGHTNESS] = hex(device_brightness)
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_COLOR_TEMP in kwargs and COLOR_MODE_COLOR_TEMP in self._supported_color_modes:
            # bring the selected color to something we can calculate on
            color_scale = (float(kwargs[ATTR_COLOR_TEMP]) - float(self._min_mireds)) / float(self._max_mireds - self._min_mireds)
            _LOGGER.debug(f"Set color to : {color_scale}")
            # bring the color to
            color_scale_echonet = color_scale * (len(self._echonet_mireds) - 1)
            # round it to an index
            echonet_idx = round(color_scale_echonet)
            color_temp = self._echonet_mireds[echonet_idx]
            color_temp_int = self._echonet_mireds_int[echonet_idx]

            _LOGGER.debug(f"New color temp of light: {color_temp} - {color_temp_int}")
            await self._connector._instance.setColorTemperature(color_temp_int)
            self._connector._update_data[ENL_COLOR_TEMP] = color_temp
            self._attr_color_temp = kwargs[ATTR_COLOR_TEMP]

    async def async_turn_off(self):
        """Turn off."""
        await self._connector._instance.off()
        self._connector._update_data[ENL_STATUS] = "Off"

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        _LOGGER.debug(f"Current brightness of light: {self._connector._update_data[ENL_BRIGHTNESS]}")
        brightness = int(self._connector._update_data[ENL_BRIGHTNESS], 16) if ENL_BRIGHTNESS in self._connector._update_data else -1
        if brightness >= 0:
            self._attr_brightness = min(round(float(brightness)/DEVICE_SCALE*DEFAULT_BRIGHTNESS_SCALE), 255)
        else:
            self._attr_brightness = 128
        return self._attr_brightness

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        _LOGGER.debug(f"Current color temp of light: {self._connector._update_data[ENL_COLOR_TEMP]}")

        # calculate some helper
        mired_steps = (self._max_mireds - self._min_mireds) / float(len(self._echonet_mireds))

        # get the current echonet mireds
        color_temp = self._connector._update_data[ENL_COLOR_TEMP] if ENL_COLOR_TEMP in self._connector._update_data else 0
        if color_temp in self._echonet_mireds:
            self._attr_color_temp = round(self._echonet_mireds.index(color_temp) * mired_steps) + MIN_MIREDS
        else:
            self._attr_color_temp = MIN_MIREDS
        return self._attr_color_temp

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        return self._color_mode

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return self._min_mireds

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return self._max_mireds

    @property
    def supported_color_modes(self) -> set:
        """Flag supported features."""
        return self._supported_color_modes

    async def async_update_callback(self, isPush = False):
        if isPush and self._should_poll:
            self._should_poll = False
        changed = self._olddata != self._connector._update_data
        if (changed):
            self._olddata = self._connector._update_data
            self.async_schedule_update_ha_state()
