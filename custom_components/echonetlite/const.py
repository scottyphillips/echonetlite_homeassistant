"""Constants for the echonetlite integration."""
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE
from pychonet.HomeAirConditioner import FAN_SPEED, AIRFLOW_VERT, AIRFLOW_HORIZ, AUTO_DIRECTION, SWING_MODE

DOMAIN = "echonetlite"

SENSOR_TYPE_TEMPERATURE = "temperature"

HVAC_SELECT_OP_CODES = {
        0xA0: {"name": "Air flow rate setting", "options": FAN_SPEED},
        0xA1: {"name": "Automatic control of air flow direction setting", "options": AUTO_DIRECTION},
        0xA3: {"name": "Automatic swing of air flow setting", "options": SWING_MODE},
        0xA5: {"name": "Air flow direction (horizontal) setting", "options": AIRFLOW_HORIZ},
        0xA4: {"name": "Air flow direction (vertical) setting", "options": AIRFLOW_VERT}
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

