from homeassistant.components.sensor.const import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME, CONF_TYPE
from pychonet.lib.epc_functions import _int, _signed_int
from ....const import TYPE_DATA_DICT


def _02A5F5(edt):
    d1 = d2 = None
    try:
        d1 = _signed_int(edt[0:8])
        d2 = _signed_int(edt[8:16])
    except:
        pass
    finally:
        return {"household_consumption": d1, "from/to_grid": d2}


def _02A5F6(edt):
    d1 = d2 = None
    try:
        d1 = _int(edt[0:8])
        d2 = _int(edt[8:16])
    except:
        pass
    finally:
        return {"normal_direction": d1, "reverse_direction": d2}


QUIRKS = {
    0xF5: {
        "EPC_FUNCTION": _02A5F5,
        "ENL_OP_CODE": {
            CONF_NAME: "Instantaneous amount of energy",
            CONF_TYPE: SensorDeviceClass.POWER,
            CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            TYPE_DATA_DICT: ["household_consumption", "from/to_grid"],
        },
    },
    0xF6: {
        "EPC_FUNCTION": _02A5F6,
        "ENL_OP_CODE": {
            CONF_NAME: "Cumulative energy",
            CONF_TYPE: SensorDeviceClass.ENERGY,
            CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
            TYPE_DATA_DICT: ["normal_direction", "reverse_direction"],
        },
    },
}
