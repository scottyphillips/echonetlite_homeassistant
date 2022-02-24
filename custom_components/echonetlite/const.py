"""Constants for the echonetlite integration."""
from homeassistant.const import CONF_ICON, CONF_TYPE, DEVICE_CLASS_POWER, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_ENERGY, DEVICE_CLASS_HUMIDITY
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

USER_OPTIONS = {
    ENL_FANSPEED:   {'option': 'fan_settings', 'option_list': FAN_SPEED_OPTIONS},
    ENL_AIR_HORZ:   {'option': 'swing_horiz', 'option_list': AIRFLOW_HORIZ_OPTIONS},
    ENL_AIR_VERT:   {'option': 'swing_vert', 'option_list': AIRFLOW_VERT_OPTIONS},
    ENL_AUTO_DIRECTION: {'option': 'auto_direction', 'option_list': AUTO_DIRECTION_OPTIONS},
    ENL_SWING_MODE:     {'option': 'swing_mode', 'option_list': SWING_MODE_OPTIONS},
}

TEMP_OPTIONS = {"min_temp_heat": {"min":15, "max":20},
                "max_temp_heat": {"min":25, "max":35},
                "min_temp_cool": {"min":15, "max":20},
                "max_temp_cool": {"min":25, "max":35},
                "min_temp_auto": {"min":15, "max":20},
                "max_temp_auto": {"min":25, "max":35},
}
