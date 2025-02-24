from homeassistant.const import CONF_ICON, CONF_NAME
from pychonet.lib.epc_functions import _int

QUIRKS = {
    0xF1: {
        "EPC_FUNCTION": [
            _int,
            {
                0x3C: "High",
                0x32: "Medium",
                0x28: "Low",
                0x00: "Off",
            },
        ],
        "ENL_OP_CODE": {
            CONF_NAME: "Humidity setting",
            CONF_ICON: "mdi:air-humidifier",
        },
    },
}
