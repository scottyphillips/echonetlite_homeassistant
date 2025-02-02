from homeassistant.components.sensor.const import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME, CONF_TYPE
from ....const import TYPE_DATA_DICT


def _16x2_int(edt):
    d1 = None
    d2 = None
    if len(edt) == 16:
        d1 = int.from_bytes(edt[0:8], "big")
        d2 = int.from_bytes(edt[8:16], "big")
    return [d1, d2]


def _02A5F5(edt):
    (v1, v2) = _16x2_int(edt)
    return {"household": v1, "grid": v2}


def _02A5F6(edt):
    (v1, v2) = _16x2_int(edt)
    return {"purchased": v1, "sold": v2}


QUIRKS = {
    0xF5: {
        "EPC_FUNCTION": _02A5F5,
        "ENL_OP_CODE": {
            CONF_NAME: "Instantaneous amount of energy",
            CONF_TYPE: SensorDeviceClass.POWER,
            CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            TYPE_DATA_DICT: ["household", "grid"],
        },
    },
    0xF6: {
        "EPC_FUNCTION": _02A5F6,
        "ENL_OP_CODE": {
            CONF_NAME: "Cumulative amount of energy",
            CONF_TYPE: SensorDeviceClass.ENERGY,
            CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
            TYPE_DATA_DICT: ["purchased", "sold"],
        },
    },
}
