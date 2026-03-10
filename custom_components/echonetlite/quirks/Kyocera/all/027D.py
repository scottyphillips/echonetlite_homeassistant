# 0x027D 蓄電池 (Storage Battery)
# Kyocera (Enerezza Plus) 
# https://echonet.jp/introduce/gz-001033/

from homeassistant.const import CONF_NAME, CONF_ICON
from pychonet.lib.epc_functions import _int

# 0x02: "Standby (待機)",
# 0x04: "Auto-Sell (売電モード)",
# 0x05: "Auto-Green (グリーンモード)",
# 0x07: "Auto-FullGreen (フルグリーンモード)",
# 0x08: "Force Charge (強制充電)",
# 0x09: "Force Discharge (強制放電)",

QUIRKS = {
    0xF0: { # Kyocera Special Operation mode setting
        "EPC_FUNCTION": [
            _int, 
            {
                0x02: "Standby",
                0x04: "Sell Mode",
                0x05: "Green Mode",
                0x07: "FullGreen Mode",
                0x08: "Charge Mode",
                0x09: "Discharge Mode",
            },
        ],
        "ENL_OP_CODE": {
            CONF_NAME: "Special Operation mode setting",
            CONF_ICON: "mdi:format-list-bulleted",
        },
    }
}