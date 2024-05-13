"""Constants for the echonetlite integration."""

from homeassistant.const import (
    CONF_ICON,
    CONF_SERVICE,
    CONF_TYPE,
    CONF_SERVICE_DATA,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_MINIMUM,
    CONF_MAXIMUM,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.components.number.const import (
    NumberDeviceClass,
)
from pychonet.DistributionPanelMeter import (
    ENL_DPM_CHANNEL_SIMPLEX_CUMULATIVE_ENG,
    ENL_DPM_CHANNEL_SIMPLEX_INSTANT_ENG,
    ENL_DPM_DAY_GET_HISTORY,
    ENL_DPM_ENG_NOR,
    ENL_DPM_ENG_REV,
    ENL_DPM_ENG_UNIT,
    ENL_DPM_INSTANT_CUR,
    ENL_DPM_INSTANT_ENG,
    ENL_DPM_INSTANT_VOL,
)
from pychonet.ElectricBlind import (
    ENL_OPENING_LEVEL,
    ENL_BLIND_ANGLE,
    ENL_OPENCLOSE_STATUS,
)
from pychonet.GeneralLighting import ENL_BRIGHTNESS, ENL_COLOR_TEMP
from pychonet.HomeAirConditioner import (
    ENL_HVAC_MODE,
    ENL_FANSPEED,
    ENL_AIR_VERT,
    ENL_AIR_HORZ,
    ENL_AUTO_DIRECTION,
    ENL_HVAC_OUT_TEMP,
    ENL_HVAC_ROOM_HUMIDITY,
    ENL_HVAC_ROOM_TEMP,
    ENL_HVAC_SET_HUMIDITY,
    ENL_HVAC_SET_TEMP,
    ENL_HVAC_SILENT_MODE,
    ENL_SWING_MODE,
    FAN_SPEED,
    AIRFLOW_VERT,
    AIRFLOW_HORIZ,
    AUTO_DIRECTION,
    SWING_MODE,
)
from pychonet.EchonetInstance import ENL_STATUS, ENL_ON, ENL_OFF
from pychonet.LightingSystem import ENL_SCENE, ENL_SCENE_MAX
from pychonet.LowVoltageSmartElectricEnergyMeter import (
    ENL_LVSEEM_COEF,
    ENL_LVSEEM_ENG_NOR,
    ENL_LVSEEM_ENG_REV,
    ENL_LVSEEM_ENG_UNIT,
    ENL_LVSEEM_INSTANT_CUR,
    ENL_LVSEEM_INSTANT_ENG,
)
from pychonet.lib.const import ENL_CUMULATIVE_POWER, ENL_INSTANTANEOUS_POWER
from pychonet.lib.epc_functions import DATA_STATE_CLOSE, DATA_STATE_OPEN

DOMAIN = "echonetlite"
CONF_STATE_CLASS = ATTR_STATE_CLASS
CONF_ENSURE_ON = "ensureon"
CONF_OTHER_MODE = "other_mode"
CONF_FORCE_POLLING = "force_polling"
CONF_ENABLE_SUPER_ENERGY = "super_energy"
CONF_BATCH_SIZE_MAX = "batch_size_max"
CONF_ON_VALUE = "on_val"
CONF_OFF_VALUE = "off_val"
CONF_DISABLED_DEFAULT = "disabled_default"
CONF_MULTIPLIER = "multiplier"
CONF_MULTIPLIER_OPCODE = "multiplier_opcode"
CONF_MULTIPLIER_OPTIONAL_OPCODE = "multiplier_optional_opcode"
CONF_ICON_POSITIVE = "icon_positive"
CONF_ICON_NEGATIVE = "icon_negative"
CONF_ICON_ZERO = "icon_zero"
CONF_ICONS = "icons"
CONF_AS_ZERO = "as_zero"
CONF_MAX_OPC = "max_opc"
CONF_BYTE_LENGTH = "byte_len"

DATA_STATE_ON = "on"
DATA_STATE_OFF = "off"
TYPE_SWITCH = "switch"
TYPE_SELECT = "select"
TYPE_TIME = "time"
TYPE_NUMBER = "number"
TYPE_DATA_DICT = "type_data_dict"
TYPE_DATA_ARRAY_WITH_SIZE_OPCODE = "type_data_array_with_size_opcode"
SERVICE_SET_ON_TIMER_TIME = "set_on_timer_time"
SERVICE_SET_INT_1B = "set_value_int_1b"
OPEN = "open"
CLOSE = "close"
STOP = "stop"
DEVICE_CLASS_ECHONETLITE_LIGHT_SCENE = "echonetlite_light_scene"
SWITCH_POWER = {DATA_STATE_ON: ENL_ON, DATA_STATE_OFF: ENL_OFF}
SWITCH_BINARY = {DATA_STATE_ON: 0x41, DATA_STATE_OFF: 0x42}
SWITCH_BINARY_INVERT = {DATA_STATE_ON: 0x42, DATA_STATE_OFF: 0x41}

HVAC_SELECT_OP_CODES = {
    0xA0: FAN_SPEED,
    0xA1: AUTO_DIRECTION,
    0xA3: SWING_MODE,
    0xA5: AIRFLOW_HORIZ,
    0xA4: AIRFLOW_VERT,
}

FAN_SELECT_OP_CODES = {0xA0: FAN_SPEED}

COVER_SELECT_OP_CODES = {0xE0: {OPEN: 0x41, CLOSE: 0x42, STOP: 0x43}}

ENL_TIMER_SETTING = 0x97
ENL_SUPER_CODES = {
    ENL_INSTANTANEOUS_POWER: {
        CONF_TYPE: SensorDeviceClass.POWER,
        CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    ENL_CUMULATIVE_POWER: {
        CONF_TYPE: SensorDeviceClass.ENERGY,
        CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        CONF_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
        CONF_MULTIPLIER: 0.001,
    },
    ENL_TIMER_SETTING: {
        CONF_ICON: "mdi:clock-outline",
        TYPE_TIME: True,
    },
}

ENL_SUPER_ENERGES = {ENL_INSTANTANEOUS_POWER, ENL_CUMULATIVE_POWER}

ENL_OP_CODES = {
    0x00: {  # Sensor-related Device
        0x11: {  # Temperature sensor
            0xE0: {
                CONF_ICON: "mdi:thermometer",
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
        }
    },
    0x01: {  # Air Conditioner-related Device
        0x30: {  # Home air conditioner
            # 0xB3: {  # for develop test
            #     CONF_TYPE: SensorDeviceClass.TEMPERATURE,
            #     CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            #     TYPE_NUMBER: {  # Make Number input entity if settable value
            #         CONF_TYPE: NumberDeviceClass.TEMPERATURE,  # NumberDeviceClass.x
            #         CONF_AS_ZERO: 0x1,  # Value as zero
            #         CONF_MINIMUM: 0x0,  # Minimum value
            #         CONF_MAXIMUM: 0x32,  # Maximum value
            #         CONF_MAX_OPC: None,  # OPC of max value
            #         CONF_BYTE_LENGTH: 0x1,  # Data byte length
            #         TYPE_SWITCH: {  #  Additional switch
            #             CONF_NAME: "Auto",  # Additionale name
            #             CONF_ICON: "mdi:thermometer",
            #             CONF_SERVICE_DATA: {DATA_STATE_ON: 23, DATA_STATE_OFF: 22},
            #         },
            #     },
            # },
            0xB4: {  # Humidity setting in dry mode
                CONF_TYPE: SensorDeviceClass.HUMIDITY,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.HUMIDITY,
                    CONF_MINIMUM: 30,
                    CONF_MAXIMUM: 90,
                },
                CONF_SERVICE: [
                    SERVICE_SET_INT_1B
                ],  # For backward compatibility (Deprecated)
            },
            0xBA: {
                CONF_TYPE: SensorDeviceClass.HUMIDITY,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xBE: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xBB: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xA0: {
                CONF_ICON: "mdi:fan",
            },
            0xA1: {
                CONF_ICON: "mdi:shuffle-variant",
            },
            0xA3: {
                CONF_ICON: "mdi:arrow-oscillating",
            },
            0xA5: {
                CONF_ICON: "mdi:tailwind",
            },
            0xA4: {
                CONF_ICON: "mdi:tailwind",
            },
        },
        0x35: {  # Air cleaner
            0xE1: {
                CONF_ICON: "mdi:air-filter",
            },
            0xA0: {
                CONF_ICON: "mdi:fan",
            },
            0xC1: {
                CONF_ICON: "mdi:smoking",
            },
            0xC2: {
                CONF_ICON: "mdi:weather-sunny",
            },
            0xC0: {
                CONF_ICON: "mdi:flower-pollen",
            },
        },
    },
    0x02: {  # Housing/Facilities-related Device
        0x60: {  # Electrically operated blind/shade
            0xE0: {  # Configured as Cover but left for backward compatibility
                CONF_ICON: "mdi:roller-shade",
                CONF_ICONS: {
                    OPEN: "mdi:roller-shade",
                    CLOSE: "mdi:roller-shade-closed",
                    STOP: "mdi:roller-shade",
                },
                CONF_DISABLED_DEFAULT: True,
            },
            0xD2: {
                CONF_UNIT_OF_MEASUREMENT: UnitOfTime.SECONDS,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0x00,
                    CONF_MAXIMUM: 0xFD,
                },
            },  # Operation time
        },
        0x61: {  # Electrically operated shutter
            0xE0: {  # Configured as Cover but left for backward compatibility
                CONF_ICON: "mdi:window-shutter-open",
                CONF_ICONS: {
                    OPEN: "mdi:window-shutter-open",
                    CLOSE: "mdi:window-shutter",
                    STOP: "mdi:window-shutter-open",
                },
                CONF_DISABLED_DEFAULT: True,
            },
            0xD2: {
                CONF_UNIT_OF_MEASUREMENT: UnitOfTime.SECONDS,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0x00,
                    CONF_MAXIMUM: 0xFD,
                },
            },  # Operation time
        },
        0x62: {  # Electrically operated curtain
            0xE0: {  # Configured as Cover but left for backward compatibility
                CONF_ICON: "mdi:curtains",
                CONF_ICONS: {
                    OPEN: "mdi:curtains",
                    CLOSE: "mdi:curtains-closed",
                    STOP: "mdi:curtains",
                },
                CONF_DISABLED_DEFAULT: True,
            },
            0xD2: {
                CONF_UNIT_OF_MEASUREMENT: UnitOfTime.SECONDS,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0x00,
                    CONF_MAXIMUM: 0xFD,
                },
            },  # Operation time
        },
        0x63: {  # Electrically operated rain sliding door/shutter
            0xE0: {  # Configured as Cover but left for backward compatibility
                CONF_ICON: "mdi:door-sliding-open",
                CONF_ICONS: {
                    OPEN: "mdi:door-sliding-open",
                    CLOSE: "mdi:door-sliding",
                    STOP: "mdi:door-sliding-open",
                },
                CONF_DISABLED_DEFAULT: True,
            },
            0xD2: {
                CONF_UNIT_OF_MEASUREMENT: UnitOfTime.SECONDS,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0x00,
                    CONF_MAXIMUM: 0xFD,
                },
            },  # Operation time
        },
        0x64: {  # Electrically operated gate
            0xE0: {  # Configured as Cover but left for backward compatibility
                CONF_ICON: "mdi:boom-gate-up-outline",
                CONF_ICONS: {
                    OPEN: "mdi:boom-gate-up-outline",
                    CLOSE: "mdi:boom-gate-outline",
                    STOP: "mdi:boom-gate-up-outline",
                },
                CONF_DISABLED_DEFAULT: True,
            },
            0xD2: {
                CONF_UNIT_OF_MEASUREMENT: UnitOfTime.SECONDS,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0x00,
                    CONF_MAXIMUM: 0xFD,
                },
            },  # Operation time
        },
        0x65: {  # Electrically operated window
            0xE0: {  # Configured as Cover but left for backward compatibility
                CONF_ICON: "mdi:window-open-variant",
                CONF_ICONS: {
                    OPEN: "mdi:window-open-variant",
                    CLOSE: "mdi:window-closed-variant",
                    STOP: "mdi:window-open-variant",
                },
                CONF_DISABLED_DEFAULT: True,
            },
            0xD2: {
                CONF_UNIT_OF_MEASUREMENT: UnitOfTime.SECONDS,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0x00,
                    CONF_MAXIMUM: 0xFD,
                },
            },  # Operation time
        },
        0x66: {  # Automatically operated entrance door/sliding door
            0xE0: {  # Configured as Cover but left for backward compatibility
                CONF_ICON: "mdi:door-sliding-open",
                CONF_ICONS: {
                    OPEN: "mdi:door-sliding-open",
                    CLOSE: "mdi:door-sliding",
                    STOP: "mdi:door-sliding-open",
                },
                CONF_DISABLED_DEFAULT: True,
            },
            0xD2: {
                CONF_UNIT_OF_MEASUREMENT: UnitOfTime.SECONDS,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0x00,
                    CONF_MAXIMUM: 0xFD,
                },
            },  # Operation time
        },
        0x6B: {  # Electric water heater
            # 0xB0: , # "Automatic water heating setting",
            # 0xB1: , # "Automatic water temperature control setting",
            # 0xB2: , # "Water heater status",
            0xB3: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: 30,
                    CONF_MAXIMUM: 90,
                },
            },  # "Water heating temperature setting",
            0xB4: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },  # "Manual water heating stop days setting",
            # 0xB5: , # "Relative time setting value for manual water heating OFF",
            # 0xB6: , # Tank operation mode setting",
            # 0xC0: , # Daytime reheating permission setting",
            0xC1: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },  # Measured temperature of water in water heater",
            # 0xC2: , # Alarm status",
            # 0xC3: , # Hot water supply status",
            # 0xC4: , # Relative time setting for keeping bath temperature",
            0xD1: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: 30,
                    CONF_MAXIMUM: 90,
                },
            },  # Temperature of supplied water setting",
            0xD3: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: 30,
                    CONF_MAXIMUM: 90,
                },
            },  # Bath water temperature setting",
            0xE0: {
                CONF_UNIT_OF_MEASUREMENT: PERCENTAGE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 100,
                },
            },  # Bath water volume setting",
            0xE1: {
                CONF_TYPE: SensorDeviceClass.WATER,
                CONF_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS,
            },  # Measured amount of water remaining in tank",
            0xE2: {
                CONF_TYPE: SensorDeviceClass.WATER,
                CONF_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS,
            },  # Tank capacity",
            # 0xE3: , # Automatic bath water heating mode setting",
            # 0xE9: , # Bathroom priority setting",
            # 0xEA: , # Bath operation status monitor",
            # 0xE4: , # Manual bath reheating operation setting",
            # 0xE5: , # Manual bath hot water addition function setting",
            # 0xE6: , # Manual slight bath water temperature lowering function setting",
            0xE7: {
                CONF_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0xFD,
                },
            },  # Bath water volume setting 1",
            0xE8: {
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_AS_ZERO: 0x30,
                    CONF_MINIMUM: 0x31,
                    CONF_MAXIMUM: 0x38,
                },
            },  # Bath water volume setting 2",
            0xEE: {
                CONF_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0xFFFD,
                    CONF_BYTE_LENGTH: 2,
                },
            },  # Bath water volume setting 3",
            0xD4: {
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_MINIMUM: 0x01,
                    CONF_MAXIMUM: 0xFF,
                    CONF_MAX_OPC: 0xD5,
                },
            },  # Bath water volume setting 4",
            0x90: {
                CONF_ICON: "mdi:timer",
            },  # ON timer reservation setting",
            0x91: {
                CONF_ICON: "mdi:timer-outline",
            },  # ON timer setting",
            0xD6: {
                CONF_UNIT_OF_MEASUREMENT: PERCENTAGE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0x64,
                },
            },  # Volume setting",
            # 0xD7: , # Mute setting",
            0xD8: {
                CONF_TYPE: SensorDeviceClass.WATER,
                CONF_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS,
            },  # Remaining hot water volume",
            0xDB: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },  # Rated power consumption of H/P unit in wintertime",
            0xDC: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },  # Rated power consumption of H/P unit in in-between seasons",
            0xDD: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },  # Rated power consumption of H/P unit in summertime",
            0xCB: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_DATA_DICT: ["10:00", "13:00", "15:00", "17:00"],
            },
            0xCC: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_DATA_DICT: ["10:00", "13:00", "15:00", "17:00"],
            },
            0xCE: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_DATA_DICT: ["13:00", "15:00", "17:00"],
            },
            0xCF: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_DATA_DICT: ["13:00", "15:00", "17:00"],
            },
        },
        0x6F: {  # Electric lock
            0xE0: {
                CONF_ICON: "mdi:lock",
                CONF_ENSURE_ON: ENL_STATUS,
            },
            0xE1: {
                CONF_ICON: "mdi:lock",
                CONF_ENSURE_ON: ENL_STATUS,
            },
            0xE6: {
                CONF_ICON: None,
                CONF_ENSURE_ON: ENL_STATUS,
            },
        },
        0x72: {  # Hot water generator
            0x90: {
                CONF_ICON: "mdi:timer",
            },
            0x91: {  # Sensor with service
                CONF_ICON: "mdi:timer-outline",
                CONF_SERVICE: [
                    SERVICE_SET_ON_TIMER_TIME
                ],  # For backward compatibility (Deprecated)
            },
            0xD1: {  # Sensor
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: 30,
                    CONF_MAXIMUM: 90,
                },
                CONF_SERVICE: [
                    SERVICE_SET_INT_1B
                ],  # For backward compatibility (Deprecated)
            },
            0xE1: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: 30,
                    CONF_MAXIMUM: 90,
                },
                CONF_SERVICE: [
                    SERVICE_SET_INT_1B
                ],  # For backward compatibility (Deprecated)
            },
            0xE3: {
                CONF_ICON: "mdi:bathtub-outline",
            },
            0xE4: {
                CONF_ICON: "mdi:heat-wave",
            },
            0xE7: {
                CONF_TYPE: SensorDeviceClass.WATER,
                CONF_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS,
            },
            0xEE: {
                CONF_TYPE: SensorDeviceClass.WATER,
                CONF_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS,
            },
        },
        0x79: {  # Home solar power generation
            0xA0: {
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                CONF_UNIT_OF_MEASUREMENT: PERCENTAGE,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0x64,
                },
            },
            0xA1: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.POWER,
                    CONF_MAXIMUM: 0xFFFD,
                    CONF_BYTE_LENGTH: 0x02,
                },
            },
            0xE0: {
                CONF_ICON: "mdi:solar-power-variant-outline",
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                CONF_ICON_POSITIVE: "mdi:solar-power-variant",
                CONF_ICON_NEGATIVE: "mdi:solar-power-variant-outline",
                CONF_ICON_ZERO: "mdi:solar-power-variant-outline",
            },
            0xE1: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
            },
            0xE3: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
            },
            0xE5: {
                CONF_ICON: "mdi:percent",
                CONF_UNIT_OF_MEASUREMENT: PERCENTAGE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0x64,
                },
            },
            0xE6: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.POWER,
                    CONF_MAXIMUM: 0xFFFD,
                    CONF_BYTE_LENGTH: 0x02,
                },
            },
            0xE7: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.POWER,
                    CONF_MAXIMUM: 0xFFFD,
                    CONF_BYTE_LENGTH: 0x02,
                },
            },
            0xE8: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.POWER,
                    CONF_MAXIMUM: 0xFFFD,
                    CONF_BYTE_LENGTH: 0x02,
                },
            },
            0xE9: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.POWER,
                    CONF_MAXIMUM: 0xFFFD,
                    CONF_BYTE_LENGTH: 0x02,
                },
            },
        },
        0x7B: {  # Floor heater
            0xE0: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: 16,
                    CONF_MAXIMUM: 40,
                    TYPE_SWITCH: {
                        CONF_NAME: "Auto",
                        CONF_SERVICE_DATA: {DATA_STATE_ON: 0x41, DATA_STATE_OFF: 16},
                    },
                },
            },
            0xE1: {
                CONF_ICON: "mdi:thermometer",
                CONF_TYPE: None,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_AS_ZERO: 0x30,
                    CONF_MINIMUM: 0x31,
                    CONF_MAXIMUM: 0x3F,
                    CONF_MAX_OPC: 0xD1,
                    TYPE_SWITCH: {
                        CONF_NAME: "Auto",
                        CONF_SERVICE_DATA: {DATA_STATE_ON: 0x41, DATA_STATE_OFF: 0x31},
                    },
                },
            },
            0xE2: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xE3: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0x90: {
                CONF_ICON: "mdi:timer",
            },
            0x91: {
                CONF_ICON: "mdi:timer-outline",
            },
            0x94: {
                CONF_ICON: "mdi:timer",
            },
            0x95: {
                CONF_ICON: "mdi:timer-outline",
            },
        },
        0x7C: {  # Fuel cell
            0xC2: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xC4: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xC5: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
            },
            0xCC: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xCD: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
            },
            0xC7: {
                CONF_TYPE: SensorDeviceClass.GAS,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                CONF_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            },
            0xC8: {
                CONF_TYPE: SensorDeviceClass.GAS,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                CONF_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS,
            },
        },
        0x7D: {  # Storage battery
            0xA0: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
            0xA1: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
            0xA2: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
            0xA3: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
            0xA4: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
            0xA5: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
            0xA6: {
                CONF_TYPE: SensorDeviceClass.BATTERY,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.BATTERY,
                    CONF_MAXIMUM: 0x64,
                },
            },
            0xA7: {
                CONF_TYPE: SensorDeviceClass.BATTERY,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.BATTERY,
                    CONF_MAXIMUM: 0x64,
                },
            },
            0xA8: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
            },
            0xA9: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
            },
            0xAA: {
                CONF_ICON: "mdi:battery",
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.ENERGY,
                    CONF_MAXIMUM: 0x3B9AC9FF,
                    CONF_BYTE_LENGTH: 0x04,
                },
            },
            0xAB: {
                CONF_ICON: "mdi:battery",
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.ENERGY,
                    CONF_MAXIMUM: 0x3B9AC9FF,
                    CONF_BYTE_LENGTH: 0x04,
                },
            },
            0xD0: {
                CONF_ICON: "mdi:battery",
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
            0xD3: {
                CONF_ICON_POSITIVE: "mdi:battery-arrow-up",
                CONF_ICON_NEGATIVE: "mdi:battery-arrow-down",
                CONF_ICON_ZERO: "mdi:battery",
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xD6: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
            },
            0xD8: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
            },
            0xE0: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
            0xE2: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
            },
            0xE4: {
                CONF_TYPE: SensorDeviceClass.BATTERY,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xE5: {
                CONF_TYPE: SensorDeviceClass.BATTERY,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xE7: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.ENERGY,
                    CONF_MAXIMUM: 0x3B9AC9FF,
                    CONF_BYTE_LENGTH: 0x04,
                },
            },
            0xE8: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.ENERGY,
                    CONF_MAXIMUM: 0x3B9AC9FF,
                    CONF_BYTE_LENGTH: 0x04,
                },
            },
            0xEB: {
                CONF_ICON: "mdi:battery",
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.POWER,
                    CONF_MAXIMUM: 0x3B9AC9FF,
                    CONF_BYTE_LENGTH: 0x04,
                },
            },
            0xEC: {
                CONF_ICON: "mdi:battery",
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.POWER,
                    CONF_MAXIMUM: 0x3B9AC9FF,
                    CONF_BYTE_LENGTH: 0x04,
                },
            },
        },
        0x80: {  # Electric energy meter
            0xE0: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                CONF_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
                CONF_MULTIPLIER_OPCODE: 0xE2,
            },
            0xE2: {
                CONF_DISABLED_DEFAULT: True,
            },
        },
        0x81: {  # Water flow meter
            0xE0: {
                # CONF_ICON: "mdi:water",
                CONF_TYPE: SensorDeviceClass.WATER,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                CONF_MULTIPLIER_OPCODE: 0xE1,
            },
            0xE1: {
                CONF_DISABLED_DEFAULT: True,
            },
        },
        0x82: {  # Gas meter
            0xE0: {
                # CONF_ICON: "mdi:gas-burner",
                CONF_TYPE: SensorDeviceClass.GAS,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                CONF_MULTIPLIER: 0.001,
            }
        },
        0x87: {  # Distribution panel metering
            0xC2: {
                CONF_DISABLED_DEFAULT: True,
            },
            0xB3: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                CONF_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
                TYPE_DATA_ARRAY_WITH_SIZE_OPCODE: 0xB1,
                CONF_MULTIPLIER_OPCODE: 0xC2,
            },
            0xB7: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_DATA_ARRAY_WITH_SIZE_OPCODE: 0xB1,
            },
            0xC0: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                CONF_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
                CONF_MULTIPLIER_OPCODE: 0xC2,
            },
            0xC1: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                CONF_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
                CONF_MULTIPLIER_OPCODE: 0xC2,
            },
            0xC6: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xC7: {
                CONF_TYPE: SensorDeviceClass.CURRENT,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_DATA_DICT: ["r_phase_amperes", "t_phase_amperes"],
                CONF_DISABLED_DEFAULT: True,
            },
            0xC8: {
                CONF_TYPE: SensorDeviceClass.VOLTAGE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_DATA_DICT: ["r_sn_voltage", "sn_t_voltage"],
                CONF_DISABLED_DEFAULT: True,
            },
        },
        0x88: {  # Low voltage smart electric energy meter
            0xD3: {
                CONF_DISABLED_DEFAULT: True,
            },
            0xE0: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                CONF_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
                CONF_MULTIPLIER_OPCODE: 0xE1,
                CONF_MULTIPLIER_OPTIONAL_OPCODE: 0xD3,
            },
            0xE1: {
                CONF_DISABLED_DEFAULT: True,
            },
            0xE3: {
                CONF_TYPE: SensorDeviceClass.ENERGY,
                CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
                CONF_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
                CONF_MULTIPLIER_OPCODE: 0xE1,
                CONF_MULTIPLIER_OPTIONAL_OPCODE: 0xD3,
            },
            0xE7: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
            0xE8: {
                CONF_TYPE: SensorDeviceClass.CURRENT,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_DATA_DICT: ["r_phase_amperes", "t_phase_amperes"],
            },
            # 0xEA: {
            #     TYPE_DATA_DICT: ["time", "culmative_value"],
            # },
            # 0xEB: {
            #     TYPE_DATA_DICT: ["time", "culmative_value"],
            # },
            0xD3: {CONF_DISABLED_DEFAULT: True},
            0xE1: {CONF_DISABLED_DEFAULT: True},
        },
        0xA3: {  # Lighting system
            0xC0: {  # Set scene
                CONF_ICON: "mdi:palette",
                CONF_TYPE: DEVICE_CLASS_ECHONETLITE_LIGHT_SCENE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_MAXIMUM: 0xFD,
                    CONF_MAX_OPC: 0xC1,
                },
            },
        },
    },
    0x03: {  # Cooking/housework-related device class group
        0xB7: {  # Refrigerator
            0xB0: {
                CONF_ICON: "mdi:door",
                CONF_ICONS: {
                    DATA_STATE_OPEN: "mdi:door-open",
                    DATA_STATE_CLOSE: "mdi:door-closed",
                },
            },  # "Door open/close status",
            0xB1: {
                CONF_ICON: "mdi:door",
                CONF_ICONS: {
                    DATA_STATE_OPEN: "mdi:door-open",
                    DATA_STATE_CLOSE: "mdi:door-closed",
                },
            },  # "Door open warning",
            0xB2: {
                CONF_ICON: "mdi:door",
                CONF_ICONS: {
                    DATA_STATE_OPEN: "mdi:door-open",
                    DATA_STATE_CLOSE: "mdi:door-closed",
                },
            },  # "Refrigerator compartment door status",
            0xB3: {
                CONF_ICON: "mdi:door",
                CONF_ICONS: {
                    DATA_STATE_OPEN: "mdi:door-open",
                    DATA_STATE_CLOSE: "mdi:door-closed",
                },
            },  # "Freezer compartment door status",
            0xB4: {
                CONF_ICON: "mdi:door",
                CONF_ICONS: {
                    DATA_STATE_OPEN: "mdi:door-open",
                    DATA_STATE_CLOSE: "mdi:door-closed",
                },
            },  # "Ice compartment door status",
            0xB5: {
                CONF_ICON: "mdi:door",
                CONF_ICONS: {
                    DATA_STATE_OPEN: "mdi:door-open",
                    DATA_STATE_CLOSE: "mdi:door-closed",
                },
            },  # "Vegetable compartment door status",
            0xB6: {
                CONF_ICON: "mdi:door",
                CONF_ICONS: {
                    DATA_STATE_OPEN: "mdi:door-open",
                    DATA_STATE_CLOSE: "mdi:door-closed",
                },
            },  # "Multi-refrigera-ting mode compartment door",
            0xE0: {
                TYPE_DATA_DICT: [
                    "refrigerator",
                    "freezer",
                    "ice",
                    "vegetable",
                    "multi_refrigerating",
                ]
            },  # "Maximum allowable temperature setting level",
            0xE2: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: -127,
                    CONF_MAXIMUM: 126,
                },
            },  # "Refrigerator compartment temperature setting",
            0xE3: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: -127,
                    CONF_MAXIMUM: 126,
                },
            },  # "Freezer compartment temperature setting",
            0xE4: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: -127,
                    CONF_MAXIMUM: 126,
                },
            },  # "Ice temperature setting",
            0xE5: {
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: -127,
                    CONF_MAXIMUM: 126,
                },
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
            },  # "Vegetable compartment temperature setting",
            0xE6: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: -127,
                    CONF_MAXIMUM: 126,
                },
            },  # "Multi-refrigera-ting mode compartment temperature setting",
            0xE9: {
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: 1,
                    CONF_MAXIMUM: 0xFF,
                    CONF_MAX_OPC: [0xE0, "refrigerator"],
                },
            },  # "Refrigerator compartment temperature level setting",
            0xEA: {
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: 1,
                    CONF_MAXIMUM: 0xFF,
                    CONF_MAX_OPC: [0xE0, "freezer"],
                },
            },  # "Freezer compartment temperature level setting",
            0xEB: {
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: 1,
                    CONF_MAXIMUM: 0xFF,
                    CONF_MAX_OPC: [0xE0, "ice"],
                },
            },  # "ice compartment temperature level setting",
            0xEC: {
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: 1,
                    CONF_MAXIMUM: 0xFF,
                    CONF_MAX_OPC: [0xE0, "vegetable"],
                },
            },  # "Vegetable compartment temperature level setting",
            0xED: {
                TYPE_NUMBER: {
                    CONF_TYPE: NumberDeviceClass.TEMPERATURE,
                    CONF_MINIMUM: 1,
                    CONF_MAXIMUM: 0xFF,
                    CONF_MAX_OPC: [0xE0, "multi_refrigerating"],
                },
            },  # "Multi-refrigera-ting mode compartment temperature level setting",
            0xD1: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
            },  # "Measured refrigerator compartment temperature",
            0xD2: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
            },  # "Measured freezer compartment temperature",
            0xD3: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
            },  # "Measured subzero-fresh compartment temperature",
            0xD4: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
            },  # "Measured vegetable compartment temperature",
            0xD5: {
                CONF_TYPE: SensorDeviceClass.TEMPERATURE,
            },  # "Measured multi-refrigeratin g mode compartment temperature",
            0xD8: {
                TYPE_DATA_DICT: ["maximum_rotation_speed", "rotation_speed"]
            },  # "Compressor rotation speed",
            0xDA: {
                CONF_TYPE: SensorDeviceClass.CURRENT,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
                CONF_MULTIPLIER: 0.1,
            },  # "Measured electric current consumption",
            0xDC: {
                CONF_TYPE: SensorDeviceClass.POWER,
                CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },  # "Rated power consumption",
            0xA0: {
                CONF_ICON: "mdi:snowflake-check"
            },  # "Quick freeze function setting",
            0xA1: {
                CONF_ICON: "mdi:fridge-bottom"
            },  # "Quick refrigeration function setting",
            0xA4: {CONF_ICON: "mdi:dice-1-outline"},  # "Icemaker setting",
            0xA5: {CONF_ICON: "mdi:dice-1-outline"},  # "Icemaker operation status",
            0xA6: {CONF_ICON: "mdi:water-alert-outline"},  # "Icemaker tank status",
            0xA8: {
                CONF_ICON: "mdi:water-thermometer"
            },  # "Refrigerator compartment humidification function setting",
            0xA9: {
                CONF_ICON: "mdi:water-thermometer"
            },  # "Vegetable compartment humidification function setting",
            0xAD: {CONF_ICON: "mdi:scent"},  # "Deodorization function setting",
        },  # Refrigerator
    },
    "default": {
        CONF_ICON: None,
        CONF_TYPE: None,
        CONF_STATE_CLASS: None,
    },
}

ENABLE_SUPER_ENERGY_DEFAULT = {
    # If False is not specified here, the default is True.
    # 0x01: {
    #     0x35: False,
    # },
}

# Some entities that overlap with control entities are excluded from setup
NON_SETUP_SINGLE_ENYITY = {
    0x01: {
        # Home Air Conditioner
        0x30: {ENL_HVAC_MODE, ENL_HVAC_SET_TEMP, ENL_HVAC_SILENT_MODE},
    },
    0x02: {
        0x60: {ENL_OPENING_LEVEL, ENL_BLIND_ANGLE, ENL_OPENCLOSE_STATUS},
        0x61: {ENL_OPENING_LEVEL, ENL_BLIND_ANGLE, ENL_OPENCLOSE_STATUS},
        0x62: {ENL_OPENING_LEVEL, ENL_BLIND_ANGLE, ENL_OPENCLOSE_STATUS},
        0x63: {ENL_OPENING_LEVEL, ENL_BLIND_ANGLE, ENL_OPENCLOSE_STATUS},
        0x64: {ENL_OPENING_LEVEL, ENL_BLIND_ANGLE, ENL_OPENCLOSE_STATUS},
        0x65: {ENL_OPENING_LEVEL, ENL_BLIND_ANGLE, ENL_OPENCLOSE_STATUS},
        0x66: {ENL_OPENING_LEVEL, ENL_BLIND_ANGLE, ENL_OPENCLOSE_STATUS},
        # General Lighting
        0x90: {ENL_BRIGHTNESS, ENL_COLOR_TEMP},
        # Single Function Lighting
        0x91: {ENL_BRIGHTNESS, ENL_COLOR_TEMP},
    },
}

EPC_CODES_FOR_UPDATE = {
    0x01: {
        0x30: [
            ENL_STATUS,
            ENL_FANSPEED,
            ENL_AUTO_DIRECTION,
            ENL_SWING_MODE,
            ENL_AIR_VERT,
            ENL_AIR_HORZ,
            ENL_HVAC_MODE,
            ENL_HVAC_SET_TEMP,
            ENL_HVAC_SET_HUMIDITY,
            ENL_HVAC_ROOM_HUMIDITY,
            ENL_HVAC_ROOM_TEMP,
            ENL_HVAC_OUT_TEMP,
            ENL_HVAC_SILENT_MODE,
        ],
    },
    0x02: {
        0x7D: [
            0xA0,
            0xA1,
            0xA8,
            0xA9,
            0xCF,
            0xD0,
            0xD3,
            0xD6,
            0xD8,
            0xE2,
            0xE4,
            0xE5,
            0xE6,
        ],
        0x87: [
            ENL_DPM_ENG_NOR,
            ENL_DPM_ENG_REV,
            ENL_DPM_ENG_UNIT,
            ENL_DPM_DAY_GET_HISTORY,
            ENL_DPM_INSTANT_ENG,
            ENL_DPM_INSTANT_CUR,
            ENL_DPM_INSTANT_VOL,
            ENL_DPM_CHANNEL_SIMPLEX_CUMULATIVE_ENG,
            ENL_DPM_CHANNEL_SIMPLEX_INSTANT_ENG,
        ],
        0x88: [
            ENL_LVSEEM_ENG_NOR,
            ENL_LVSEEM_ENG_REV,
            ENL_LVSEEM_INSTANT_ENG,
            ENL_LVSEEM_INSTANT_CUR,
            ENL_LVSEEM_COEF,
            ENL_LVSEEM_ENG_UNIT,
        ],
        0x90: [ENL_BRIGHTNESS, ENL_COLOR_TEMP],
        0x91: [ENL_BRIGHTNESS],
        0xA3: [ENL_SCENE, ENL_SCENE_MAX],
    },
}

ATTR_STATE_ON = "on"
ATTR_STATE_OFF = "off"

FAN_SPEED_OPTIONS = {
    "auto": "Auto",
    "minimum": "Minimum",
    "low": "Low",
    "medium-low": "Medium-Low",
    "medium": "Medium",
    "medium-high": "Medium-High",
    "high": "High",
    "very-high": "Very-High",
    "max": "Max",
}

AIRFLOW_HORIZ_OPTIONS = {
    "rc-right": "Right Center + Right",
    "left-lc": "Left + Left Center",
    "lc-center-rc": "Left + Center + Right Center",
    "left-lc-rc-right": "Left + Left Center + Right Center + Right",
    "right": "Right",
    "rc": "Right Center",
    "center": "Center",
    "center-right": "Center + Right",
    "center-rc": "Center + Right Center",
    "center-rc-right": "Center + Right Center + Right",
    "lc": "Left Center",
    "lc-right": "Left Center + Right",
    "lc-rc": "Left Center + Right Center",
    "left": "Left",
    "left-right": "Left + Right",
    "left-rc": "Left + Right Center",
    "left-rc-right": "Left + Right Center + Right",
    "left-center": "Left + Center",
    "left-center-right": "Left + Center + Right",
    "left-center-rc": "Left + Center + Right Center",
    "left-center-rc-right": "Left + Center + Right Center + Right",
    "left-lc-right": "Left + Left Center + Right",
    "left-lc-rc": "Left + Left Center + Right Center",
}

AIRFLOW_VERT_OPTIONS = {
    "upper": "Upper",
    "upper-central": "Upper Central",
    "central": "Central",
    "lower-central": "Lower Central",
    "lower": "Lower",
}

AUTO_DIRECTION_OPTIONS = {
    "auto": "Auto",
    "non-auto": "Non-Auto",
    "auto-vert": "Auto-vert",
    "auto-horiz": "Auto-horiz",
}

SWING_MODE_OPTIONS = {
    "not-used": "Not Used (Off)",
    "vert": "Vertical",
    "horiz": "Horizontal",
    "vert-horiz": "Vertical-Horizontal",
}

SILENT_MODE_OPTIONS = {
    "normal": "Normal",
    "high-speed": "High Speed",
    "silent": "Silent",
}

HVAC_MODE_OPTIONS = {"as_off": "As Off", "as_idle": "As Idle"}

OPTION_HA_UI_SWING = "ha_ui_swing"

USER_OPTIONS = {
    ENL_FANSPEED: {"option": "fan_settings", "option_list": FAN_SPEED_OPTIONS},
    ENL_SWING_MODE: {"option": "swing_mode", "option_list": SWING_MODE_OPTIONS},
    ENL_AUTO_DIRECTION: {
        "option": "auto_direction",
        "option_list": AUTO_DIRECTION_OPTIONS,
    },
    ENL_AIR_VERT: {"option": "swing_vert", "option_list": AIRFLOW_VERT_OPTIONS},
    ENL_AIR_HORZ: {"option": "swing_horiz", "option_list": AIRFLOW_HORIZ_OPTIONS},
    ENL_HVAC_MODE: {
        "option": CONF_OTHER_MODE,
        "option_list": [
            {"value": "as_off", "label": "As Off"},
            {"value": "as_idle", "label": "As Idle"},
        ],
    },
    OPTION_HA_UI_SWING: {"option": OPTION_HA_UI_SWING, "option_list": []},
}

TEMP_OPTIONS = {
    "min_temp_heat": {"min": 10, "max": 25, "default": 16},
    "max_temp_heat": {"min": 18, "max": 30, "default": 30},
    "min_temp_cool": {"min": 15, "max": 25, "default": 16},
    "max_temp_cool": {"min": 18, "max": 30, "default": 30},
    "min_temp_auto": {"min": 15, "max": 25, "default": 16},
    "max_temp_auto": {"min": 18, "max": 30, "default": 30},
}

MISC_OPTIONS = {
    CONF_FORCE_POLLING: {"type": bool, "default": False},
    CONF_ENABLE_SUPER_ENERGY: {
        "type": bool,
        "default": [ENABLE_SUPER_ENERGY_DEFAULT, True],
    },
    CONF_BATCH_SIZE_MAX: {"type": int, "default": 10, "min": 1, "max": 30},
}
