"""Support for ECHONETLite lights."""

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
    ATTR_COLOR_TEMP_KELVIN,
)
from homeassistant.core import callback
from .base_entity import EchonetEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_device_name
from .const import DATA_STATE_ON, DOMAIN, CONF_FORCE_POLLING

_LOGGER = logging.getLogger(__name__)

DEFAULT_BRIGHTNESS_SCALE = 255
MIN_MIREDS = 153  # 6500k
MAX_MIREDS = 500  # 2000k
DEVICE_SCALE = 100


def _mireds_to_kelvin(mireds):
    """Convert mireds to kelvin."""
    return round(1000000 / mireds) if mireds else None


def _kelvin_to_mireds(kelvin):
    """Convert kelvin to mireds."""
    return round(1000000 / kelvin) if kelvin else None


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


class EchonetLight(EchonetEntity, LightEntity):
    """Representation of a ECHONET light device."""

    def __init__(self, coordinator, config, options):
        """Initialize the light device.

        Args:
            coordinator: The ECHONETConnector instance which is also a DataUpdateCoordinator.
            config: The config entry for this integration.
            options: Custom configuration options for the light.
        """
        super().__init__(coordinator, config)
        name = get_device_name(coordinator, config)
        self._attr_name = name
        self._device_name = name
        self._custom_options = options
        self._attr_unique_id = (
            self.coordinator._uidi if self.coordinator._uidi else self.coordinator._uid 
        )
        self._attr_supported_color_modes = set()

        # Set temperature limits for color temp conversion
        if mireds_int := options.get("echonet_mireds_int"):
            mireds = mireds_int.values()
            self._attr_min_color_temp_kelvin = _mireds_to_kelvin(max(mireds))
            self._attr_max_color_temp_kelvin = _mireds_to_kelvin(min(mireds))
        else:
            self._attr_min_color_temp_kelvin = _mireds_to_kelvin(MAX_MIREDS)
            self._attr_max_color_temp_kelvin = _mireds_to_kelvin(MIN_MIREDS)

        # Keep mired limits for internal calculations
        if mireds_int := options.get("echonet_mireds_int"):
            mireds = mireds_int.values()
            self._min_mireds = min(mireds)
            self._max_mireds = max(mireds)
        else:
            self._min_mireds = MIN_MIREDS
            self._max_mireds = MAX_MIREDS

        # Determine supported color modes based on device capabilities
        if options[ENL_COLOR_TEMP] in list(self.coordinator._setPropertyMap):
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.COLOR_TEMP

        if options[ENL_BRIGHTNESS] in list(self.coordinator._setPropertyMap):
            if not self._attr_supported_color_modes:
                self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
                self._attr_color_mode = ColorMode.BRIGHTNESS

        if not self._attr_supported_color_modes:
            self._attr_supported_color_modes.add(ColorMode.ONOFF)
            self._attr_color_mode = ColorMode.ONOFF

        # Set effect list if device supports it
        if hasattr(self.coordinator._instance, "getEffectList"):
            self._attr_effect_list = self.coordinator._instance.getEffectList()
            if self._attr_effect_list:
                self._attr_supported_features |= LightEntityFeature.EFFECT

        # Set max color level for color temperature calculation
        if hasattr(self.coordinator._instance, "getLightColorLevelMax"):
            self._light_color_level_max = self.coordinator._instance.getLightColorLevelMax()
        else:
            self._light_color_level_max = 100

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        return (
            self.coordinator.data.get(self._custom_options[ENL_STATUS]) == DATA_STATE_ON
        )

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        brightness = self.coordinator.data.get(self._custom_options[ENL_BRIGHTNESS])
        if brightness is not None and brightness >= 0:
            return min(
                round(float(brightness) / DEVICE_SCALE * DEFAULT_BRIGHTNESS_SCALE), 255
            )
        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        enl_color_temp = self._custom_options[ENL_COLOR_TEMP]
        _val = self.coordinator.data.get(enl_color_temp)

        if self._custom_options["echonet_color"]:
            # Use custom mired mapping for known color temperatures
            color_temp = _val if _val else "white"
            mired_val = self._custom_options["echonet_mireds_int"].get(
                self._custom_options["echonet_int_color"].get(color_temp, 0x42), 153
            )
            return _mireds_to_kelvin(mired_val)
        else:
            # Calculate mired value from color level
            mired_val = (
                (self._max_mireds - self._min_mireds)
                * ((self._light_color_level_max - _val) / self._light_color_level_max)
                + self._min_mireds
                if _val is not None
                else None
            )
            return _mireds_to_kelvin(mired_val) if mired_val else None

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if hasattr(self.coordinator._instance, "getEffect"):
            return self.coordinator._instance.getEffect()
        return None

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
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
            states["brightness"] = max(device_brightness, 1)

        if (
            ATTR_COLOR_TEMP_KELVIN in kwargs
            and self._attr_supported_color_modes
            and self._attr_color_mode == ColorMode.COLOR_TEMP
        ):
            # Convert kelvin from HA to mireds for internal device logic
            attr_color_tmp = float(_kelvin_to_mireds(kwargs[ATTR_COLOR_TEMP_KELVIN]))

            if self._custom_options["echonet_color"]:
                # Use custom color temperature mapping
                color_temp_int = 0x41
                for i, mired in self._custom_options["echonet_mireds_int"].items():
                    if attr_color_tmp <= mired + 15:
                        color_temp_int = i
                        break
                _LOGGER.debug(
                    f"New color temp of light: {self._custom_options['echonet_color'].get(color_temp_int)} - {color_temp_int}"
                )
            else:
                # Calculate color temperature level
                color_scale = (attr_color_tmp - float(self._min_mireds)) / float(
                    self._max_mireds - self._min_mireds
                )
                _LOGGER.debug(f"Set color to : {color_scale}")
                color_temp_int = min(
                    self._light_color_level_max,
                    max(1, (1 - color_scale) * self._light_color_level_max),
                )
                _LOGGER.debug(
                    f"New color temp of light: {attr_color_tmp} mireds - {color_temp_int}"
                )

            states["color_temperature"] = int(color_temp_int)

        if ATTR_EFFECT in kwargs and kwargs[ATTR_EFFECT] in self._attr_effect_list:
            states[ATTR_EFFECT] = kwargs[ATTR_EFFECT]

        # Execute the appropriate method based on device capabilities
        if hasattr(self.coordinator._instance, "setLightStates"):
            return await self.coordinator._instance.setLightStates(states)
        else:
            """Turn on."""
            result = await getattr(
                self.coordinator._instance, self._custom_options["on"]
            )()

            if result:
                if states.get("brightness"):
                    result &= await self.coordinator._instance.setBrightness(
                        states["brightness"]
                    )

                if states.get("color_temperature"):
                    result &= await self.coordinator._instance.setColorTemperature(
                        states["color_temperature"]
                    )

    async def async_turn_off(self, **kwargs):
        """Turn off the light."""
        await getattr(self.coordinator._instance, self._custom_options["off"])()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
