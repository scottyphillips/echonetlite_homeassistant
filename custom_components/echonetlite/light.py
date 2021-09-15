import logging

_LOGGER = logging.getLogger(__name__)

from pychonet.GeneralLighting import (
    ENL_STATUS,
    ENL_BRIGHTNESS,
    ENL_COLOR_TEMP
)

from pychonet.EchonetInstance import ENL_SETMAP, ENL_GETMAP
from pychonet.lib.eojx import EOJX_CLASS

from homeassistant.components.light import LightEntity
from homeassistant.components.light import (
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP
)

from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME
)
from .const import DOMAIN
SUPPORT_FLAGS = 0

DEFAULT_BRIGHTNESS_SCALE = 255
MIN_MIREDS = 153
MAX_MIREDS = 500
DEVICE_SCALE = 100


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        if entity['instance']['eojgc'] == 0x02 and  entity['instance']['eojcc'] == 0x90 : #General Lighting
             entities.append(EchonetLight(config_entry.title, entity['echonetlite'], hass.config.units))
    async_add_devices(entities, True)


class EchonetLight(LightEntity):

    """Representation of a ECHONET light device."""

    def __init__(self, name, connector):

        """Initialize the climate device."""
        self._name = name
        self._connector = connector #new line
        self._uid = self._connector._uid
        self._support_flags = SUPPORT_FLAGS
        if ENL_BRIGHTNESS in list(self._connector._setPropertyMap):
            self._support_flags = self._support_flags | COLOR_MODE_BRIGHTNESS
        if ENL_COLOR_TEMP in list(self._connector._setPropertyMap):
            self._support_flags = self._support_flags | COLOR_MODE_COLOR_TEMP
        
        self._echonet_mireds = [68, 67, 66, 64, 65]  # coolest to warmest

    async def async_update(self):
        """Get the latest state from the HVAC."""
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
            "name": self._device_name,
            "manufacturer": self._connector._manufacturer
            #"model": "",
            #"sw_version": "",
        }

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def is_on(self):
        """Return true if the device is on."""
        return True if self._connector._update_data[ENL_STATUS] == "On" else False

    async def async_turn_on(self, kwargs):
        """Turn on."""
        await self._connector._instance.on()
        
        if ATTR_BRIGHTNESS in kwargs and self._brightness is not None:
            normalized_brightness = float(kwargs[ATTR_BRIGHTNESS]) / DEFAULT_BRIGHTNESS_SCALE
            device_brightness = round(normalized_brightness * DEVICE_SCALE)
            # Make sure the brightness is not rounded down to 0
            device_brightness = max(device_brightness, 1)
            
            # send the message to the lamp
            self._connector._instance.setBrightness(device_brightness)
            self._connector._update_data[ENL_BRIGHTNESS] = device_brightness
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
        
        if ATTR_COLOR_TEMP in kwargs and self._color_temp is not None:
            # send the message to the lamp
            color_scale = (float(kwargs[ATTR_COLOR_TEMP]) - float(self.min_mireds())) / float(self.max_mireds() - self.min_mireds())
            array_scale = 1.0 / float(len(self._echonet_mireds))
            color_temp = self._echonet_mireds[0]
            for i in range(len(self._echonet_mireds) - 1):
                if self._echonet_mireds[i] < color_scale and color_scale < self._echonet_mireds[i+1]:
                    color_temp = self._echonet_mireds[i]
            
            self._connector._instance.setColorTemperature(color_temp)
            self._connector._update_data[ENL_COLOR_TEMP] = color_temp
            self._attr_color_temp = kwargs[ATTR_COLOR_TEMP]

    async def async_turn_off(self):
        """Turn off."""
        await self._connector._instance.off()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        brightness = self._connector._update_data[ENL_BRIGHTNESS] if ENL_BRIGHTNESS in self._connector._update_data else -1
        if brightness >= 0:
            self._attr_brightness = min(round(float(brightness)/DEVICE_SCALE*DEFAULT_BRIGHTNESS_SCALE), 255)
        else:
            self._attr_brightness = 128
        return self._attr_brightness
    
    @property
    def color_temp(self):
        """Return the color temperature in mired."""

        # calculate some helper
        mired_steps = ( self.max_mireds() - self.min_mireds() ) / float(len(self._echonet_mireds))
        
        # get the current echonet mireds
        color_temp = self._connector._update_data[ENL_COLOR_TEMP] if ENL_COLOR_TEMP in self._connector._update_data else 0
        if color_temp in self._echonet_mireds:
            self._attr_color_temp = round( self._echonet_mireds.index(color_temp) * mired_steps ) + MIN_MIREDS
        else:
            self._attr_color_temp = MIN_MIREDS
        return self._attr_color_temp
