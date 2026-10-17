# import logging
# _LOGGER = logging.getLogger(__name__)

from homeassistant.components.sensor.const import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.climate.const import (
    HVACAction,
    HVACMode,
    ATTR_HVAC_MODE,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_TYPE,
    CONF_ICON,
    CONF_SERVICE_DATA,
)
from pychonet.lib.epc_functions import _int, _to_string
from ....const import (
    TYPE_DATA_DICT,
    TYPE_SELECT,
    TYPE_SWITCH,
    CONF_DISABLED_DEFAULT,
)
from ....sensor import EchonetSensor


def _0130F0(edt):
    return _int(
        edt[1:2],
        {
            0x30: "off",
            0x31: "on",
        },
    )


def _0130F1(edt):
    z1p = z1t = z1f = u11 = u12 = u13 = z1r = None
    z2p = z2t = z2f = u21 = u22 = u23 = z2r = None
    z3p = z3t = z3f = u31 = u32 = u33 = z3r = None
    try:
        z1p = _int(
            edt[0:1],
            {
                0x30: "off",
                0x31: "on",
                0x32: "keep",
            },
        )
        z1t = _int(edt[1:2])
        z1f = _int(
            edt[2:3],
            {
                0x31: "low",
                0x32: "high",
                0x41: "auto",
            },
        )
        u11 = _int(edt[3:4])
        u12 = _int(edt[4:5])
        u13 = _int(edt[5:6])
        z1r = _int(
            edt[6:7],
            {
                0x30: "off",
                0x31: "timer1",
                0x32: "timer2",
                0x33: "timer3",
            },
        )
        z2p = _int(
            edt[7:8],
            {
                0x30: "off",
                0x31: "on",
                0x32: "keep",
            },
        )
        z2t = _int(edt[8:9])
        z2f = _int(
            edt[9:10],
            {
                0x31: "low",
                0x32: "high",
                0x41: "auto",
            },
        )
        u21 = _int(edt[10:11])
        u22 = _int(edt[11:12])
        u23 = _int(edt[12:13])
        z2r = _int(
            edt[13:14],
            {
                0x30: "off",
                0x31: "timer1",
                0x32: "timer2",
                0x33: "timer3",
            },
        )
        z3p = _int(
            edt[14:15],
            {
                0x30: "off",
                0x31: "on",
                0x32: "keep",
            },
        )
        z3t = _int(edt[15:16])
        z3f = _int(
            edt[16:17],
            {
                0x31: "low",
                0x32: "high",
                0x41: "auto",
            },
        )
        u31 = _int(edt[17:18])
        u32 = _int(edt[18:19])
        u33 = _int(edt[19:20])
        z3r = _int(
            edt[20:21],
            {
                0x30: "off",
                0x31: "timer1",
                0x32: "timer2",
                0x33: "timer3",
            },
        )
    except Exception:
        pass
    return {
        "zone1Status": z1p,
        "zone1TargetTemp": z1t,
        "zone1AirFlow": z1f,
        "unknown1-1": u11,
        "unknown1-2": u12,
        "unknown1-3": u13,
        "zone1ProgramOperation": z1r,
        "zone2Status": z2p,
        "zone2TargetTemp": z2t,
        "zone2AirFlow": z2f,
        "unknown2-1": u21,
        "unknown2-2": u22,
        "unknown2-3": u23,
        "zone2ProgramOperation": z2r,
        "zone3Status": z3p,
        "zone3TargetTemp": z3t,
        "zone3AirFlow": z3f,
        "unknown3-1": u31,
        "unknown3-2": u32,
        "unknown3-3": u33,
        "zone3ProgramOperation": z3r,
    }


def _0130F2(edt):
    return {"zoneGrouping": _int(edt[0:1])}


def _0130FA(edt):
    t1 = t2 = t3 = ot = u1 = u2 = u3 = None
    try:
        t1 = _int(edt[0:1])
        t2 = _int(edt[1:2])
        t3 = _int(edt[2:3])
        u1 = _int(edt[3:4])
        u2 = _int(edt[4:5])
        ot = _int(edt[5:6])
        u3 = _int(edt[6:7])
    except Exception:
        pass
    return {
        "zone1Temp": t1,
        "zone2Temp": t2,
        "zone3Temp": t3,
        # "unknown1": u1,
        # "unknown2": u2,
        "outsideTemp": ot,
        # "unknown3": u3,
    }


QUIRKS = {
    0x80: {
        "EPC_FUNCTION": _int,
        "ENL_OP_CODE": {
            CONF_NAME: "Power setting",
            CONF_ICON: "mdi:power",
            TYPE_SWITCH: True,
            CONF_SERVICE_DATA: {"on": 0x30, "off": 0x31},
        },
    },
    0x8F: {
        # Required: ENL_OP_CODE is only applied when EPC_FUNCTION is present
        "EPC_FUNCTION": _int,
        "ENL_OP_CODE": {
            CONF_NAME: "Power-saving operation setting",
            CONF_DISABLED_DEFAULT: True,
        },
    },
    0xB0: {
        "EPC_FUNCTION": _int,
        "ENL_OP_CODE": {
            CONF_NAME: "Operation mode setting",
            CONF_ICON: "mdi:air-conditioner",
            TYPE_SELECT: {
                "Cooling": 0x42,
                "Heating": 0x43,
                "Dehumidification": 0x44,
            },
        },
    },
    0xB4: {
        "EPC_FUNCTION": _int,
        "ENL_OP_CODE": {
            CONF_NAME: "Humidity setting",
            CONF_ICON: "mdi:air-humidifier",
            TYPE_SELECT: {
                "Low": 0x32,
                "Medium": 0x3C,
                "High": 0x46,
            },
        },
    },
    0xF0: {
        "EPC_FUNCTION": _0130F0,
        "ENL_OP_CODE": {
            CONF_NAME: "Away Mode",
            CONF_ICON: "mdi:walk",
            TYPE_SELECT: {
                "off": 0x30,
                "on": 0x31,
            },
        },
    },
    0xF1: {
        "EPC_FUNCTION": _0130F1,
        "ALWAYS_POLL": True,
        "ENL_OP_CODE": {
            CONF_NAME: "Zone Configuration",
            TYPE_DATA_DICT: [
                "zone1Status",
                "zone1TargetTemp",
                "zone1AirFlow",
                #'unknown1-1',
                #'unknown1-2',
                #'unknown1-3',
                "zone1ProgramOperation",
                "zone2Status",
                "zone2TargetTemp",
                "zone2AirFlow",
                #'unknown2-1',
                #'unknown2-2',
                #'unknown2-3',
                "zone2ProgramOperation",
                "zone3Status",
                "zone3TargetTemp",
                "zone3AirFlow",
                #'unknown3-1',
                #'unknown3-2',
                #'unknown3-3',
                #'zone3ProgramOperation',
            ],
        },
    },
    0xF2: {
        "EPC_FUNCTION": _0130F2,
        "ENL_OP_CODE": {
            CONF_NAME: "Preferences",
            TYPE_DATA_DICT: [
                #'zoneGrouping',
            ],
        },
    },
    0xFA: {
        "EPC_FUNCTION": _0130FA,
        "ENL_OP_CODE": {
            CONF_NAME: "Zone Room Tempertures",
            CONF_TYPE: SensorDeviceClass.TEMPERATURE,
            CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            CONF_ICON: "mdi:thermometer",
            TYPE_DATA_DICT: [
                "zone1Temp",
                "zone2Temp",
                "zone3Temp",
                # "unknown1",
                # "unknown2",
                "outsideTemp",
                # "unknown3",
            ],
        },
    },
}
