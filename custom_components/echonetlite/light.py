import logging
import math
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pychonet.GeneralLighting import ENL_STATUS, ENL_BRIGHTNESS, ENL_COLOR_TEMP
from pychonet.CeilingFan import (
    ENL_FAN_LIGHT_STATUS,
    ENL_FAN_LIGHT_BRIGHTNESS,
    ENL_FAN_LIGHT_COLOR_TEMP,
)
from pychonet.lib.const import ENL_ON
from pychonet.lib.eojx import EOJX_CLASS
from pychonet.lib.epc_functions import _swap_dict

from . import get_device_name
from .const import DATA_STATE_ON, DOMAIN, CONF_FORCE_POLLING

_LOGGER = logging.getLogger(__name__)

DEFAULT_BRIGHTNESS_SCALE = 255
MIN_MIREDS = 153  # 6500k
MAX_MIREDS = 500  # 2000k
DEVICE_SCALE = 100

def _mireds_to_kelvin(mireds):
    return round(1000000 / mireds) if mireds else None

def _kelvin_to_mireds(kelvin):
    return round(1000000 / kelvin) if kelvin else None

async def async_setup_entry(hass, config_entry, async_add_devices):
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        eojgc = entity["instance"]["eojgc"]
        eojcc = entity["instance"]["eojcc"]
        
        # Identification logic remains the same
        if (eojgc == 0x02 and eojcc in (0x90, 0x91, 0xA3)) or (
            eojgc == 0x01 and eojcc == 0x3A and ENL_FAN_LIGHT_STATUS in entity["echonetlite"]._setPropertyMap
        ):
            custom_options = {}
            if eojgc == 0x02:  # Lighting Classes
                custom_options = {
                    ENL_STATUS: ENL_STATUS,
                    ENL_BRIGHTNESS: ENL_BRIGHTNESS,
                    ENL_COLOR_TEMP: ENL_COLOR_TEMP,
                    "echonet_color": {0x44: "daylight_color", 0x43: "daylight_white", 0x42: "white", 0x40: "other", 0x41: "incandescent_lamp_color"},
                    "echonet_mireds_int": {0x44: 153, 0x43: 200, 0x42: 238, 0x40: 285, 0x41: 370},
                    "on": "on",
                    "off": "off",
                }
                custom_options["echonet_int_color"] = _swap_dict(custom_options["echonet_color"])
            else:  # Ceiling Fan Light
                custom_options = {
                    ENL_STATUS: ENL_FAN_LIGHT_STATUS,
                    ENL_BRIGHTNESS: ENL_FAN_LIGHT_BRIGHTNESS,
                    ENL_COLOR_TEMP: ENL_FAN_LIGHT_COLOR_TEMP,
                    "echonet_color": None,
                    "echonet_mireds_int": None,
                    "on": "light_on",
                    "off": "light_off",
                }
            entities.append(EchonetLight(entity["echonetlite"], config_entry, custom_options))
    async_add_devices(entities, True)

class EchonetLight(CoordinatorEntity, LightEntity):
    """Representation of an ECHONETLite light device."""

    def __init__(self, connector, config, custom_options):
        super().__init__(connector)
        self._connector = connector
        self._custom_options = custom_options
        self._attr_name = get_device_name(connector, config)
        self._attr_unique_id = connector._uidi if connector._uidi else connector._uid
        
        # Supported Color Modes
        self._attr_supported_color_modes = set()
        if custom_options[ENL_COLOR_TEMP] in connector._setPropertyMap:
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
        if custom_options[ENL_BRIGHTNESS] in connector._setPropertyMap:
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
        
        if not self._attr_supported_color_modes:
            self._attr_supported_color_modes.add(ColorMode.ONOFF)

        # Mired/Kelvin Limits
        if mireds_int := custom_options.get("echonet_mireds_int"):
            mireds = mireds_int.values()
            self._attr_min_color_temp_kelvin = _mireds_to_kelvin(max(mireds))
            self._attr_max_color_temp_kelvin = _mireds_to_kelvin(min(mireds))
            self._min_mireds, self._max_mireds = min(mireds), max(mireds)
        else:
            self._attr_min_color_temp_kelvin = _mireds_to_kelvin(MAX_MIREDS)
            self._attr_max_color_temp_kelvin = _mireds_to_kelvin(MIN_MIREDS)
            self._min_mireds, self._max_mireds = MIN_MIREDS, MAX_MIREDS

        self._light_color_level_max = getattr(connector._instance, "getLightColorLevelMax", lambda: 100)()

    @property
    def is_on(self):
        return self._connector._update_data.get(self._custom_options[ENL_STATUS]) == DATA_STATE_ON

    @property
    def brightness(self):
        brightness = self._connector._update_data.get(self._custom_options[ENL_BRIGHTNESS])
        if brightness is not None:
            return min(round(float(brightness) / DEVICE_SCALE * DEFAULT_BRIGHTNESS_SCALE), 255)
        return None

    @property
    def color_temp_kelvin(self):
        enl_color_temp = self._custom_options[ENL_COLOR_TEMP]
        val = self._connector._update_data.get(enl_color_temp)
        if val is None: return None

        if self._custom_options["echonet_color"]:
            mired_val = self._custom_options["echonet_mireds_int"].get(
                self._custom_options["echonet_int_color"].get(val), 153
            )
        else:
            mired_val = (self._max_mireds - self._min_mireds) * (
                (self._light_color_level_max - val) / self._light_color_level_max
            ) + self._min_mired