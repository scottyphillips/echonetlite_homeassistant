import logging

from pychonet.EchonetInstance import ENL_GETMAP
from pychonet.lib.eojx import EOJX_CLASS
from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    FanEntity,
)
from homeassistant.const import (
    PRECISION_WHOLE,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ENL_FANSPEED = 0xA0
SUPPORT_FLAGS = 0

DEFAULT_FAN_MODES = ['auto', 'minimum', 'low', 'medium-low', 'medium', 'medium-high', 'high', 'very-high', 'max']


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        if entity['instance']['eojgc'] == 0x01 and entity['instance']['eojcc'] == 0x35:  # Home Air Cleaner
            entities.append(EchonetFan(config_entry.title, entity['echonetlite']))
    async_add_devices(entities, True)


class EchonetFan(FanEntity):
    """Representation of an ECHONETLite Fan device (eg Air purifier)."""
    def __init__(self, name, connector):
        """Initialize the climate device."""
        self._name = name
        self._device_name = name
        self._connector = connector  # new line
        self._uid = self._connector._uidi if self._connector._uidi else self._connector._uid
        self._precision = 1.0
        self._target_temperature_step = 1
        self._support_flags = SUPPORT_FLAGS
        self._support_flags = self._support_flags |  SUPPORT_PRESET_MODE
        self._olddata = {}
        self._should_poll = True

    async def async_update(self):
        await self._connector.async_update()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def precision(self) -> float:
        return PRECISION_WHOLE

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._uid

    @property
    def device_info(self):
        return {
            "identifiers": {(
                DOMAIN, self._connector._uid,
                self._connector._instance._eojgc,
                self._connector._instance._eojcc,
                self._connector._instance._eojci
            )},
            "name": self._device_name,
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
        """Return the name of the climate device."""
        return self._name

    @property
    def is_on(self):
        """Return true if the device is on."""
        return True if self._connector._update_data[0x80] == "On" else False

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ):
        """Turn on."""
        await self._connector._instance.on()

    async def async_turn_off(self):
        """Turn off."""
        await self._connector._instance.off()

    @property
    def preset_mode(self):
        """Return the fan setting."""
        return self._connector._update_data[ENL_FANSPEED] if ENL_FANSPEED in self._connector._update_data else "unavailable"

    @property
    def preset_modes(self):
        """Return the list of available fan modes."""
        if ENL_FANSPEED in list(self._connector._user_options.keys()):
            if self._connector._user_options[ENL_FANSPEED] is not False:
                return self._connector._user_options[ENL_FANSPEED]
        return DEFAULT_FAN_MODES

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new fan mode."""
        await self._connector._instance.setFanSpeed(preset_mode)
        self._connector._update_data[ENL_FANSPEED] = preset_mode

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._connector.register_async_update_callbacks(self.async_update_callback)

    async def async_update_callback(self, isPush = False):
        changed = self._olddata != self._connector._update_data
        if (changed):
            self._olddata = self._connector._update_data.copy()
            self.async_schedule_update_ha_state()
