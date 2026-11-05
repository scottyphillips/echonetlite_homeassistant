# import logging
# _LOGGER = logging.getLogger(__name__)

from homeassistant.components.sensor.const import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_TYPE,
    CONF_ICON,
    CONF_SERVICE_DATA,
)
from pychonet.lib.epc_functions import _int, _signed_int
from ....const import (
    TYPE_DATA_DICT,
    TYPE_SELECT,
    TYPE_SWITCH,
    CONF_DISABLED_DEFAULT,
)

DICT_30_OFF_ON = {0x30: "off", 0x31: "on"}
_ZONE_STATUS = {
    0x30: "off",
    0x31: "on",
    0x32: "keep",
}
_ZONE_AIRFLOW = {
    0x31: "low",
    0x32: "high",
    0x41: "auto",
}
_ZONE_PROGRAM = {
    0x30: "off",
    0x31: "timer1",
    0x32: "timer2",
    0x33: "timer3",
}
# EDT layout of 0xF1: 3 zones x 7 bytes (21 bytes in total).
_F1_ZONE_COUNT = 3
_F1_ZONE_SIZE = 7


def _0130F0(edt):
    F01 = F02 = F03 = F04 = None
    try:
        F01 = _int(edt[0:1], DICT_30_OFF_ON)
        F02 = _int(edt[1:2], DICT_30_OFF_ON)
        F03 = _int(edt[2:3], DICT_30_OFF_ON)
        F04 = _int(edt[3:4], DICT_30_OFF_ON)
    except Exception:
        pass
    return {
        "unknown1": F01,
        "awayMode": F02,
        "unknown2": F03,
        "unknown3": F04,
    }


def _0130F1(edt):
    # unknowns are kept for future analysis
    result = {}
    for zone in range(1, _F1_ZONE_COUNT + 1):
        base = (zone - 1) * _F1_ZONE_SIZE
        # Every key defaults to None so a short or broken frame
        # still yields the full key set (same as the previous behaviour).
        values = {
            f"zone{zone}Status": None,
            f"zone{zone}TargetTemp": None,
            f"zone{zone}AirFlow": None,
            f"unknown{zone}-1": None,
            f"unknown{zone}-2": None,
            f"unknown{zone}-3": None,
            f"zone{zone}ProgramOperation": None,
        }
        try:
            # Offsets within a zone block: 0=status, 1=target temp, 2=airflow,
            # 3-5=unknown, 6=program operation.
            values[f"zone{zone}Status"] = _int(
                edt[base : base + 1], _ZONE_STATUS
            )
            values[f"zone{zone}TargetTemp"] = _int(edt[base + 1 : base + 2])
            values[f"zone{zone}AirFlow"] = _int(
                edt[base + 2 : base + 3], _ZONE_AIRFLOW
            )
            for i in range(1, 4):
                values[f"unknown{zone}-{i}"] = _int(
                    edt[base + 2 + i : base + 3 + i]
                )
            values[f"zone{zone}ProgramOperation"] = _int(
                edt[base + 6 : base + 7], _ZONE_PROGRAM
            )
        except Exception:
            # Keep whatever was decoded before the failure, as before.
            pass
        result.update(values)
    return result


def _0130F2(edt):
    return {"zoneGrouping": _int(edt[0:1])}


# Raw byte this unit reports when a temperature sensor has no valid reading.
# Seen as 200 when decoded unsigned and -56 when decoded signed.
_INVALID_TEMP_RAW = 0xC8


def _temp_unsigned(edt):
    """Decode an unsigned temperature byte, returning None for the invalid marker."""
    if len(edt) < 1 or edt[0] == _INVALID_TEMP_RAW:
        return None
    return edt[0]


def _temp_signed(edt):
    """Decode a signed temperature byte, returning None for the invalid marker."""
    if len(edt) < 1 or edt[0] == _INVALID_TEMP_RAW:
        return None
    return _signed_int(edt)


def _0130FA(edt):
    # unknowns are kept for future analysis
    t1 = t2 = t3 = ot = u1 = u2 = u3 = None
    try:
        t1 = _int(edt[0:1])
        t2 = _int(edt[1:2])
        t3 = _int(edt[2:3])
        u1 = _int(edt[3:4])
        u2 = _int(edt[4:5])
        ot = _temp_unsigned(edt[5:6])
        u3 = _int(edt[6:7])
    except Exception:
        pass
    return {
        "zone1Temp": t1,
        "zone2Temp": t2,
        "zone3Temp": t3,
        "unknown1": u1,
        "unknown2": u2,
        "outsideTemp": ot,
        "unknown3": u3,
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
                "cooling": 0x42,
                "heating": 0x43,
                "dehumidification": 0x44,
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
    0xBE: {
        "EPC_FUNCTION": _temp_signed,
    },
    0xF0: {
        "EPC_FUNCTION": _0130F0,
        "ENL_OP_CODE": {
            CONF_NAME: "Away Mode",
            TYPE_DATA_DICT: [],
        },
    },
    0xF1: {
        "EPC_FUNCTION": _0130F1,
        "ALWAYS_POLL": True,
        "ENL_OP_CODE": {
            CONF_NAME: "Zone Configuration",
            TYPE_DATA_DICT: [
                # "zone1Status",
                # "zone1TargetTemp",
                # "zone1AirFlow",
                "unknown1-1",
                "unknown1-2",
                "unknown1-3",
                # "zone1ProgramOperation",
                # "zone2Status",
                # "zone2TargetTemp",
                # "zone2AirFlow",
                "unknown2-1",
                "unknown2-2",
                "unknown2-3",
                # "zone2ProgramOperation",
                # "zone3Status",
                # "zone3TargetTemp",
                # "zone3AirFlow",
                "unknown3-1",
                "unknown3-2",
                "unknown3-3",
                # "zone3ProgramOperation",
            ],
        },
    },
    0xF2: {
        "EPC_FUNCTION": _0130F2,
        "ENL_OP_CODE": {
            CONF_NAME: "Preferences",
            TYPE_DATA_DICT: [],
        },
    },
    0xFA: {
        "EPC_FUNCTION": _0130FA,
        "ENL_OP_CODE": {
            CONF_NAME: "Zone Room Temperatures",
            CONF_TYPE: SensorDeviceClass.TEMPERATURE,
            CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
            CONF_ICON: "mdi:thermometer",
            TYPE_DATA_DICT: [
                "zone1Temp",
                "zone2Temp",
                "zone3Temp",
                "unknown1",
                "unknown2",
                "outsideTemp",
                "unknown3",
            ],
        },
    },
}
