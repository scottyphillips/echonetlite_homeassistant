"""Constants for the echonetlite integration."""
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE
from pychonet.HomeAirConditioner import ENL_FANSPEED, ENL_AIR_VERT, ENL_AIR_HORZ, ENL_AUTO_DIRECTION, ENL_SWING_MODE, FAN_SPEED, AIRFLOW_VERT, AIRFLOW_HORIZ, AUTO_DIRECTION, SWING_MODE

DOMAIN = "echonetlite"

SENSOR_TYPE_TEMPERATURE = "temperature"

HVAC_SELECT_OP_CODES = {
        0xA0: FAN_SPEED,
        0xA1: AUTO_DIRECTION,
        0xA3: SWING_MODE,
        0xA5: AIRFLOW_HORIZ,
        0xA4: AIRFLOW_VERT
        }

ENL_SENSOR_OP_CODES = {
        0x00: {
            0x11 : {
                0xE0: {CONF_ICON: "mdi:thermometer", CONF_TYPE: SENSOR_TYPE_TEMPERATURE},
            }
        },
        0x01: {
            0x30: {
                0xBE: {CONF_ICON: "mdi:thermometer", CONF_TYPE: SENSOR_TYPE_TEMPERATURE},
                0xBB: {CONF_ICON: "mdi:thermometer", CONF_TYPE: SENSOR_TYPE_TEMPERATURE}
            }
        },
        'default':  {CONF_ICON: None, CONF_TYPE: None},
    }

ATTR_STATE_ON = "on"
ATTR_STATE_OFF = "off"

FAN_SPEED_OPTIONS = {
	'auto':	        'Auto',
	'minimum':      'Minimum',
	'low':  		'Low',
	'medium-low': 	'Medium-Low',
	'medium':		'Medium',
	'medium-high': 	'Medium-High',
	'high':			'High',
	'very-high':    'Very-High',
	'max':			'Max'
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
    ENL_FANSPEED:   {'option' : 'fan_settings', 'option_list': FAN_SPEED_OPTIONS},
    ENL_AIR_HORZ:   {'option' : 'swing_horiz', 'option_list': AIRFLOW_HORIZ_OPTIONS},
    ENL_AIR_VERT:   {'option' : 'swing_vert', 'option_list': AIRFLOW_VERT_OPTIONS},
    ENL_AUTO_DIRECTION: {'option' : 'auto_direction', 'option_list': AUTO_DIRECTION_OPTIONS},
    ENL_SWING_MODE:     {'option' : 'swing_mode', 'option_list': SWING_MODE_OPTIONS},
}
