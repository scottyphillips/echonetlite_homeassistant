import logging
import math
import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pychonet.HomeAirConditioner import (
    AIRFLOW_VERT,
    ENL_AIR_VERT,
    ENL_AUTO_DIRECTION,
    ENL_FANSPEED,
    ENL_HVAC_MODE,
    ENL_HVAC_ROOM_TEMP,
    ENL_HVAC_SET_HUMIDITY,
    ENL_HVAC_SET_TEMP,
    ENL_HVAC_SILENT_MODE,
    ENL_STATUS,
    ENL_SWING_MODE,
    FAN_SPEED,
    SILENT_MODE,
)
from pychonet.lib.eojx import EOJX_CLASS

from . import get_device_name
from .const import DATA_STATE_ON, DOMAIN, OPTION_HA_UI_SWING

_LOGGER = logging.getLogger(__name__)

# Constants and Defaults
DEFAULT_FAN_MODES = list(FAN_SPEED.keys())
DEFAULT_HVAC_MODES = [
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
    HVACMode.HEAT_COOL,
    HVACMode.OFF,
]
DEFAULT_SWING_MODES = ["auto-vert"] + list(AIRFLOW_VERT.keys())
DEFAULT_PRESET_MODES = list(SILENT_MODE.keys())

SERVICE_SET_HUMIDIFER_DURING_HEATER = "set_humidifier_during_heater"
ATTR_STATE = "state"
ATTR_HUMIDITY = "humidity"


async def async_setup_entry(hass, config_entry, async_add_devices):
    entities = []
    for entity in hass.data[DOMAIN][config_entry.entry_id]:
        if entity["instance"]["eojgc"] == 0x01 and entity["instance"]["eojcc"] == 0x30:
            entities.append(EchonetClimate(entity["coordinator"], config_entry))

    async_add_devices(entities, False)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_HUMIDIFER_DURING_HEATER,
        {vol.Required(ATTR_STATE): cv.boolean, vol.Required(ATTR_HUMIDITY): cv.byte},
        "async_set_humidifier_during_heater",
    )


class EchonetClimate(CoordinatorEntity, ClimateEntity):
    _attr_translation_key = DOMAIN

    def __init__(self, coordinator, config):
        super().__init__(coordinator)
        self._connector = coordinator.connector
        self._device_name = get_device_name(self._connector, config)
        self._attr_name = self._device_name
        self._attr_unique_id = self._connector._uidi or self._connector._uid

        # Static Climate Settings
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = PRECISION_WHOLE
        self._attr_target_temperature_step = 1
        self._attr_hvac_modes = DEFAULT_HVAC_MODES
        self._attr_preset_modes = DEFAULT_PRESET_MODES
        self._last_mode = HVACMode.OFF
        self._enable_turn_on_off_backwards_compatibility = False

        # Build Supported Features Bitmask
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if ENL_FANSPEED in self._connector._setPropertyMap:
            features |= ClimateEntityFeature.FAN_MODE
        if (
            ENL_AIR_VERT in self._connector._setPropertyMap
            or ENL_SWING_MODE in self._connector._setPropertyMap
        ):
            features |= ClimateEntityFeature.SWING_MODE
        if ENL_HVAC_SILENT_MODE in self._connector._setPropertyMap:
            features |= ClimateEntityFeature.PRESET_MODE
        self._attr_supported_features = features

        # Swing Mode Data
        self._opc_data = {
            ENL_AUTO_DIRECTION: list(
                self._connector._instance.EPC_FUNCTIONS.get(
                    ENL_AUTO_DIRECTION, [None, {}]
                )[1].values()
            ),
            ENL_SWING_MODE: list(
                self._connector._instance.EPC_FUNCTIONS.get(ENL_SWING_MODE, [None, {}])[
                    1
                ].values()
            ),
        }

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        if self._connector._update_data.get(ENL_STATUS) != DATA_STATE_ON:
            return HVACMode.OFF

        mode = self._connector._update_data.get(ENL_HVAC_MODE)
        if mode == "auto":
            res = HVACMode.HEAT_COOL
        elif mode == "other":
            res = (
                self._last_mode
                if self._connector._user_options.get(ENL_HVAC_MODE) == "as_idle"
                else HVACMode.OFF
            )
        else:
            res = mode

        if res != HVACMode.OFF:
            self._last_mode = res
        return res

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running action."""
        if self._connector._update_data.get(ENL_STATUS) != DATA_STATE_ON:
            return HVACAction.OFF

        mode = self._connector._update_data.get(ENL_HVAC_MODE)
        if mode == HVACMode.HEAT:
            return HVACAction.HEATING
        if mode == HVACMode.COOL:
            return HVACAction.COOLING
        if mode == HVACMode.DRY:
            return HVACAction.DRYING
        if mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN

        if mode in (HVACMode.HEAT_COOL, "auto"):
            target = self._connector._update_data.get(ENL_HVAC_SET_TEMP)
            room = self._connector._update_data.get(ENL_HVAC_ROOM_TEMP)
            if (
                target is not None
                and room is not None
                and room not in {0x7F, 0x80, 0x7E}
            ):
                if target < room:
                    return HVACAction.COOLING
                if target > room:
                    return HVACAction.HEATING
            return HVACAction.IDLE

        if (
            mode == "other"
            and self._connector._user_options.get(ENL_HVAC_MODE) == "as_idle"
        ):
            return HVACAction.IDLE

        return HVACAction.OFF

    @property
    def current_temperature(self):
        val = self._connector._update_data.get(ENL_HVAC_ROOM_TEMP)
        return None if val in {0x7F, 0x80, 0x7E} else val

    @property
    def target_temperature(self):
        val = self._connector._update_data.get(ENL_HVAC_SET_TEMP)
        return None if val in {-3, 0xFD} else val

    @property
    def min_temp(self):
        mode = self.hvac_mode
        if mode == HVACMode.HEAT:
            return self._connector._user_options.get("min_temp_heat")
        if mode == HVACMode.COOL:
            return self._connector._user_options.get("min_temp_cool")
        return self._connector._user_options.get("min_temp_auto")

    @property
    def max_temp(self):
        mode = self.hvac_mode
        if mode == HVACMode.HEAT:
            return self._connector._user_options.get("max_temp_heat")
        if mode == HVACMode.COOL:
            return self._connector._user_options.get("max_temp_cool")
        return self._connector._user_options.get("max_temp_auto")

    @property
    def fan_mode(self):
        return self._connector._update_data.get(ENL_FANSPEED)

    @property
    def fan_modes(self):
        return self._connector._user_options.get(ENL_FANSPEED, DEFAULT_FAN_MODES)

    @property
    def swing_mode(self):
        auto_dir = self._connector._update_data.get(ENL_AUTO_DIRECTION)
        if auto_dir in self.swing_modes:
            return auto_dir

        swing_m = self._connector._update_data.get(ENL_SWING_MODE)
        if swing_m in self.swing_modes:
            return swing_m

        return self._connector._update_data.get(ENL_AIR_VERT)

    @property
    def swing_modes(self):
        ui_swing = self._connector._user_options.get(OPTION_HA_UI_SWING)
        if ui_swing:
            return ui_swing
        return self._connector._user_options.get(ENL_AIR_VERT, DEFAULT_SWING_MODES)

    # ... keep async_set_ methods similar to original, but adding coordinator updates ...

    async def async_set_hvac_mode(self, hvac_mode):
        mode = "auto" if hvac_mode == HVACMode.HEAT_COOL else hvac_mode
        if await self._connector._instance.setMode(mode):
            self._connector._update_data[ENL_HVAC_MODE] = mode
            self._connector._update_data[ENL_STATUS] = DATA_STATE_ON
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        if (hvac_mode := kwargs.get("hvac_mode")) is not None:
            await self.async_set_hvac_mode(hvac_mode)

        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            target = self._normalize_settemp(temp)
            if await self._connector._instance.setOperationalTemperature(target):
                self._connector._update_data[ENL_HVAC_SET_TEMP] = target
                self.async_write_ha_state()

    def _normalize_settemp(self, req):
        # ... logic remains identical to your original snippet ...
        if req is None:
            return None
        if abs(req - round(req)) < 1e-9:
            return int(round(req))
        prev = self.target_temperature
        if abs((req - math.floor(req)) - 0.5) < 1e-9 and prev is not None:
            return math.ceil(req) if req >= prev else math.floor(req)
        return int(math.floor(req + 0.5))

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
            "name": self._device_name,
            "manufacturer": f"{self._connector._manufacturer} {self._connector._host_product_code or ''}".strip(),
            "model": EOJX_CLASS[self._connector._instance._eojgc][
                self._connector._instance._eojcc
            ],
        }
