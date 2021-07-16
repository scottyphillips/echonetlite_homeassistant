"""Constants for the echonetlite integration."""
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE
from pychonet.HomeAirConditioner import FAN_SPEED, AIRFLOW_VERT, AIRFLOW_HORIZ, AUTO_DIRECTION, SWING_MODE

DOMAIN = "echonetlite"

SENSOR_TYPE_TEMPERATURE = "temperature"

HVAC_SELECT_OP_CODES = {
        0xA0: {"name": "Air flow rate setting", "options": FAN_SPEED},
        0xA1: {"name": "Automatic control of air flow direction setting": AUTO_DIRECTION}
        0xA3: {"name": "Automatic swing of air flow setting", "options": SWING_MODE}
        0xA5: {"name": "Air flow direction (horizontal) setting", "options": AIRFLOW_HORIZ},
        0xA4: {"name": "Air flow direction (vertical) setting", "options": AIRFLOW_VERT}

        }

HVAC_SENSOR_OP_CODES = {
        0xBE: {CONF_NAME: "Measured outdoor air temperature", CONF_ICON: "mdi:thermometer", CONF_TYPE: SENSOR_TYPE_TEMPERATURE},
        0xBB: {CONF_NAME: "Measured value of room temperature", CONF_ICON: "mdi:thermometer", CONF_TYPE: SENSOR_TYPE_TEMPERATURE}
        }

ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_INSIDE_TEMPERATURE = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"

ATTR_STATE_ON = "on"
ATTR_STATE_OFF = "off"
