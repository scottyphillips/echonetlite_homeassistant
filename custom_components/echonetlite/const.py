"""Constants for the echonetlite integration."""
from homeassistant.const import (
    CONF_ICON,
    CONF_TYPE,
    CONF_SERVICE_DATA,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_GAS,
    PERCENTAGE,
    VOLUME_CUBIC_METERS
)
from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT, STATE_CLASS_TOTAL_INCREASING
from pychonet.HomeAirConditioner import (
    ENL_FANSPEED,
    ENL_AIR_VERT,
    ENL_AIR_HORZ,
    ENL_AUTO_DIRECTION,
    ENL_SWING_MODE,
    FAN_SPEED,
    AIRFLOW_VERT,
    AIRFLOW_HORIZ,
    AUTO_DIRECTION,
    SWING_MODE
)

DOMAIN = "echonetlite"
CONF_STATE_CLASS = ATTR_STATE_CLASS
DATA_STATE_ON = "On"
DATA_STATE_OFF = "Off"
SWITH_POWER = {
    DATA_STATE_ON: 0x30,
    DATA_STATE_OFF: 0x31
}
SWITH_BINALY = {
    DATA_STATE_ON: 0x41,
    DATA_STATE_OFF: 0x42
}

HVAC_SELECT_OP_CODES = {
    0xA0: FAN_SPEED,
    0xA1: AUTO_DIRECTION,
    0xA3: SWING_MODE,
    0xA5: AIRFLOW_HORIZ,
    0xA4: AIRFLOW_VERT
}

FAN_SELECT_OP_CODES = {
    0xA0: FAN_SPEED
}

HOTWATER_SWITCH_CODES = {
    0x80: {
        CONF_ICON: "mdi:power-settings",
        CONF_SERVICE_DATA: SWITH_POWER
    },
    0x90: {
        CONF_ICON: "mdi:timer",
        CONF_SERVICE_DATA: SWITH_BINALY
    },
    0xE3: {
        CONF_ICON: "mdi:bathtub-outline",
        CONF_SERVICE_DATA: SWITH_BINALY
    },
    0xE4: {
        CONF_ICON: "mdi:heat-wave",
        CONF_SERVICE_DATA: SWITH_BINALY
    }
}

ENL_SENSOR_OP_CODES = {
    0x00: {
        0x11: {
            0xE0: {
                CONF_ICON: "mdi:thermometer",
                CONF_TYPE: DEVICE_CLASS_TEMPERATURE,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            },
        }
    },
    0x01: {
        0x30: {
            0x84: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_POWER,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            },
            0x85: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_ENERGY,
                CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING
            },
            0xBA: {
                CONF_ICON: "mdi:water-percent",
                CONF_TYPE: DEVICE_CLASS_HUMIDITY,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            },
            0xBE: {
                CONF_ICON: "mdi:thermometer",
                CONF_TYPE: DEVICE_CLASS_TEMPERATURE,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            },
            0xBB: {
                CONF_ICON: "mdi:thermometer",
                CONF_TYPE: DEVICE_CLASS_TEMPERATURE,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            }
        },
        0x35: {
            0x84: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_POWER,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            },
            0x85: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_ENERGY,
                CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING
            }
        }
    },
    0x02: {
        0x79:{
            0xE0: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_POWER,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            },
            0xE1: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_ENERGY,
                CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING
            },
            0xE5: {
                CONF_ICON: "mdi:percent",
                CONF_TYPE: PERCENTAGE,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            },
            0xE6: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_POWER,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            },
            0xE8: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_POWER,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            },
            0xE9: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_POWER,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            }
        },
        0x80: {
            0xE0: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_ENERGY,
                CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING
            }
        },
        0x81: {
            0xE0: {
                CONF_ICON: "mdi:water",
                CONF_TYPE: VOLUME_CUBIC_METERS,
                CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING
            }
        },
        0x82: {
            0xE0: {
                CONF_ICON: "mdi:gas-burner",
                CONF_TYPE: DEVICE_CLASS_GAS,
                CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING
            }
        },
        0x87 : {
            0xC0: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_ENERGY,
                CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING
            },
            0xC1: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_ENERGY,
                CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING
            },
            0xC6: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_POWER,
                CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT
            }
        },
        0x88: {
            0xE0: {
                CONF_ICON: "mdi:flash",
                CONF_TYPE: DEVICE_CLASS_ENERGY,
                CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING
            }
        },
    },
    'default':  {
        CONF_ICON: None,
        CONF_TYPE: None,
        CONF_STATE_CLASS: None,
    },
}

ATTR_STATE_ON = "on"
ATTR_STATE_OFF = "off"

FAN_SPEED_OPTIONS = {
    'auto': 'Auto',
    'minimum': 'Minimum',
    'low': 'Low',
    'medium-low': 'Medium-Low',
    'medium': 'Medium',
    'medium-high': 'Medium-High',
    'high': 'High',
    'very-high': 'Very-High',
    'max': 'Max'
}

AIRFLOW_HORIZ_OPTIONS = {
    'rc-right':             'Right Center + Right',
    'left-lc':              'Left + Left Center',
    'lc-center-rc':         'Left + Center + Right Center',
    'left-lc-rc-right':     'Left + Left Center + Right Center + Right',
    'right':                'Right',
    'rc':                   'Right Center',
    'center':               'Center',
    'center-right':         'Center + Right',
    'center-rc':            'Center + Right Center',
    'center-rc-right':      'Center + Right Center + Right',
    'lc':                   'Left Center',
    'lc-right':             'Left Center + Right',
    'lc-rc':                'Left Center + Right Center',
    'left':                 'Left',
    'left-right':           'Left + Right',
    'left-rc':              'Left + Right Center',
    'left-rc-right':        'Left + Right Center + Right',
    'left-center':          'Left + Center',
    'left-center-right':    'Left + Center + Right',
    'left-center-rc':       'Left + Center + Right Center',
    'left-center-rc-right': 'Left + Center + Right Center + Right',
    'left-lc-right':        'Left + Left Center + Right',
    'left-lc-rc':           'Left + Left Center + Right Center'
}

AIRFLOW_VERT_OPTIONS = {
    'upper':            'Upper',
    'upper-central':    'Upper Central',
    'central':          'Central',
    'lower-central':    'Lower Central',
    'lower':            'Lower'
}

AUTO_DIRECTION_OPTIONS = {
    'auto':         'Auto',
    'non-auto':     'Non-Auto',
    'auto-vert':    'Auto-vert',
    'auto-horiz':   'Auto-horiz'
}

SWING_MODE_OPTIONS = {
    'not-used':     'Not Used (Off)',
    'vert':         'Vertical',
    'horiz':        'Horizontal',
    'vert-horiz':   'Vertical-Horizontal'
}

SILENT_MODE_OPTIONS = {
    'normal':       'Normal',
    'high-speed':   'High Speed',
    'silent':       'Silent',
}

USER_OPTIONS = {
    ENL_FANSPEED:   {'option': 'fan_settings', 'option_list': FAN_SPEED_OPTIONS},
    ENL_AIR_HORZ:   {'option': 'swing_horiz', 'option_list': AIRFLOW_HORIZ_OPTIONS},
    ENL_AIR_VERT:   {'option': 'swing_vert', 'option_list': AIRFLOW_VERT_OPTIONS},
    ENL_AUTO_DIRECTION: {'option': 'auto_direction', 'option_list': AUTO_DIRECTION_OPTIONS},
    ENL_SWING_MODE:     {'option': 'swing_mode', 'option_list': SWING_MODE_OPTIONS},
}

TEMP_OPTIONS = {"min_temp_heat": {"min":15, "max":25},
                "max_temp_heat": {"min":18, "max":30},
                "min_temp_cool": {"min":15, "max":25},
                "max_temp_cool": {"min":18, "max":30},
                "min_temp_auto": {"min":15, "max":25},
                "max_temp_auto": {"min":18, "max":30},
}
