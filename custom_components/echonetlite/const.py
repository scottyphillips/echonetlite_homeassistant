"""Constants for the echonetlite integration."""
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE
from pychonet.HomeAirConditioner import FAN_SPEED, AIRFLOW_VERT, AIRFLOW_HORIZ, AUTO_DIRECTION, SWING_MODE

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