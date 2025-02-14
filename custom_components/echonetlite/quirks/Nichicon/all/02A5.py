from homeassistant.components.sensor.const import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    UnitOfEnergy,
)
from pychonet.lib.epc_functions import _int, _signed_int
from ....const import TYPE_DATA_DICT


def _sint_4(edt):
    res = _signed_int(edt)
    return res if res >= -2147483647 and res <= 2147483645 else None


def _02A5F5(edt):
    d1 = d2 = d3 = d4 = None
    try:
        d1 = _sint_4(edt[0:4])
        d2 = _sint_4(edt[4:8])
        d3 = _sint_4(edt[8:12])
        d4 = _sint_4(edt[12:16])
    except:
        pass
    finally:
        return {
            "From(-)/To(+) Grid": d1,
            "Household Consumption": d2,
            "Photovoltaic Origin": d3,
            "Other Origin": d4,
        }


def _02A5F6(edt):
    d1 = d2 = None
    try:
        d1 = float(_int(edt[0:4])) / 1000
        d2 = float(_int(edt[4:8])) / 1000
    except:
        pass
    finally:
        return {"normal_direction": d1, "reverse_direction": d2}


QUIRKS = {
    0xF5: {
        "EPC_FUNCTION": _02A5F5,
        "ENL_OP_CODE": {
            CONF_NAME: "Instantaneous Power",
            CONF_TYPE: SensorDeviceClass.POWER,
            CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            TYPE_DATA_DICT: [
                "From(-)/To(+) Grid",
                "Household Consumption",
                "Photovoltaic Origin",
                "Other Origin",
            ],
        },
    },
    0xF6: {
        "EPC_FUNCTION": _02A5F6,
        "ENL_OP_CODE": {
            CONF_NAME: "Cumulative energy",
            CONF_TYPE: SensorDeviceClass.ENERGY,
            CONF_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
            CONF_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            TYPE_DATA_DICT: ["normal_direction", "reverse_direction"],
        },
    },
}
