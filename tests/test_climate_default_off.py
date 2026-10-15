"""Climate compatibility with synthetic state and explicit expected outcomes."""

from itertools import product
from unittest.mock import AsyncMock, Mock, call, sentinel

import pytest
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.exceptions import HomeAssistantError
from pychonet.HomeAirConditioner import (
    AIRFLOW_VERT,
    AIRFLOW_HORIZ,
    FAN_SPEED,
    ENL_AIR_HORZ,
    ENL_AIR_VERT,
    ENL_AUTO_DIRECTION,
    ENL_FANSPEED,
    ENL_SWING_MODE,
)

from custom_components.echonetlite import climate as current
from custom_components.echonetlite.climate import EchonetClimate
from test_fan_speed import device  # noqa: F401

FLAGS = list(product([None, False, True], repeat=2))
CONFIGURED = [
    {},
    {ENL_FANSPEED: [], ENL_AIR_VERT: [], "ha_ui_swing": []},
    {ENL_FANSPEED: False, ENL_AIR_VERT: False},
    {
        ENL_FANSPEED: ["high", "low", "high", "unknown"],
        "ha_ui_swing": ["upper", "unknown", "upper", "auto-vert", "vert"],
    },
    {
        ENL_FANSPEED: ["low"],
        ENL_AIR_VERT: ["lower", "unknown", "lower"],
        "ha_ui_swing": [],
    },
]


# Expected outcomes are repository-local data, independent of either implementation.
VERTICAL = ["upper", "upper-central", "central", "lower-central", "lower"]
VANE_LABELS = {
    "auto-vert": "Auto", "vert": "Swing",
    **{mode: f"Position {n}" for n, mode in enumerate(VERTICAL, 1)},
}
CANONICAL_FANS = [
    list(FAN_SPEED), list(FAN_SPEED), list(FAN_SPEED),
    ["high", "low", "high", "unknown"], ["low"],
]
NUMBERED_FANS = [
    ["auto", "1 bar", *[f"{n} bars" for n in range(2, 9)]],
    ["auto", "1 bar", *[f"{n} bars" for n in range(2, 9)]],
    ["auto", "1 bar", *[f"{n} bars" for n in range(2, 9)]],
    ["1 bar", "2 bars"], ["1 bar"],
]
CANONICAL_VANES = [
    ["vert", "auto-vert", *AIRFLOW_VERT],
    ["vert", "auto-vert", *AIRFLOW_VERT],
    ["vert", "auto-vert", *AIRFLOW_VERT],
    ["upper", "unknown", "upper", "auto-vert", "vert"],
    ["lower", "unknown", "lower"],
]
NUMBERED_VANES = [
    ["Auto", "Swing", *[f"Position {n}" for n in range(1, 6)]],
    ["Auto", "Swing", *[f"Position {n}" for n in range(1, 6)]],
    ["Auto", "Swing", *[f"Position {n}" for n in range(1, 6)]],
    ["Auto", "Swing", "Position 1", "unknown"],
    ["Position 5", "unknown"],
]
FAN_READINGS = [None, "auto", "low", "medium-low", "not-configured", 0x31, 0x99]
NUMBERED_FAN_READINGS = [
    [None, "auto", "2 bars", "3 bars", None, "1 bar", None],
    [None, "auto", "2 bars", "3 bars", None, "1 bar", None],
    [None, "auto", "2 bars", "3 bars", None, "1 bar", None],
    [None, None, "1 bar", None, None, None, None],
    [None, None, "1 bar", None, None, None, None],
]


def expected_features(setmap):
    features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    )
    if ENL_AIR_VERT in setmap or ENL_SWING_MODE in setmap:
        features |= ClimateEntityFeature.SWING_MODE
    if ENL_AIR_HORZ in setmap:
        features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE
    return features


def assert_reading(actual, expected):
    assert actual == expected
    assert type(actual) is type(expected)


def set_flags(config, fan, vane):
    config.options.pop("numbered_fan_speeds", None)
    config.options.pop("numbered_vane_positions", None)
    if fan is not None:
        config.options["numbered_fan_speeds"] = fan
    if vane is not None:
        config.options["numbered_vane_positions"] = vane


@pytest.mark.asyncio
@pytest.mark.parametrize("fan,vane", FLAGS)
@pytest.mark.parametrize(
    "configured",
    CONFIGURED,
    ids=["missing", "empty", "disabled", "duplicates-unknown", "epc-subset"],
)
async def test_options_and_readings_keep_independent_numbering_contracts(
    device, fan, vane, configured
):
    c, wire, _, _, config = device
    set_flags(config, fan, vane)
    c._user_options = {
        key: list(value) if isinstance(value, list) else value
        for key, value in configured.items()
    }
    entity = EchonetClimate(c, config)
    index = CONFIGURED.index(configured)
    expected_fan = (NUMBERED_FANS if fan else CANONICAL_FANS)[index]
    expected_vane = (NUMBERED_VANES if vane else CANONICAL_VANES)[index]
    assert entity.fan_modes == expected_fan
    assert entity.swing_modes == expected_vane
    assert entity.swing_horizontal_modes == ["vert-horiz", "horiz", "auto-horiz"]
    assert entity.supported_features == expected_features(c._setPropertyMap)
    if not fan and c._user_options.get(ENL_FANSPEED):
        assert entity.fan_modes is c._user_options[ENL_FANSPEED]
    if not fan:
        assert entity._fan_speed_options is None
    if not vane:
        assert entity._vane_positions is None
    for value, numbered_value in zip(FAN_READINGS, NUMBERED_FAN_READINGS[index]):
        c.data[ENL_FANSPEED] = value
        assert_reading(entity.fan_mode, numbered_value if fan else value)
    for auto, swing, vertical in [
        ("auto-vert", "vert", "upper"),
        ("non-auto", "vert", "upper"),
        ("non-auto", "not-used", "upper"),
        ("unknown", "unknown", "not-configured"),
        (None, None, None),
        (0x43, 0x41, 0x41),
        (0x99, 0x99, 0x99),
    ]:
        c.data.update(
            {ENL_AUTO_DIRECTION: auto, ENL_SWING_MODE: swing, ENL_AIR_VERT: vertical}
        )
        modes = CANONICAL_VANES[index]
        expected = auto if auto in modes else swing if swing in modes else vertical
        if vane:
            if isinstance(expected, int):
                expected = next((m for m, raw in AIRFLOW_VERT.items() if raw == expected), None)
            expected = VANE_LABELS.get(expected, expected) if expected in modes else None
        assert_reading(entity.swing_mode, expected)
    c.data.pop(ENL_FANSPEED)
    c.data.pop(ENL_AIR_VERT)
    assert entity.fan_mode is None
    assert entity.swing_mode is None
    assert wire.frames == []


async def assert_setter(entity, coordinator, method, argument, target, epc, translated):
    setters = ["setFanSpeed", "setAutoDirection", "setSwingMode", "setAirflowVert", "setAirflowHoriz"]
    for name in setters:
        setattr(coordinator._instance, name, Mock(return_value=sentinel.setter_operation))
    coordinator.async_set_and_verify = AsyncMock()
    if target is None:
        control = "Fan speed" if method == "async_set_fan_mode" else "Vertical vane position"
        with pytest.raises(HomeAssistantError) as error:
            await getattr(entity, method)(argument)
        assert str(error.value) == f"{control} {argument!r} is not configured"
        coordinator.async_set_and_verify.assert_not_awaited()
    else:
        await getattr(entity, method)(argument)
        coordinator.async_set_and_verify.assert_awaited_once_with([epc], sentinel.setter_operation)
    for name in setters:
        assert getattr(coordinator._instance, name).call_args_list == ([call(translated)] if name == target else [])


@pytest.mark.asyncio
@pytest.mark.parametrize("fan,vane", FLAGS)
async def test_setters_forward_or_validate_each_control_independently(
    device, fan, vane
):
    c, wire, _, _, config = device
    set_flags(config, fan, vane)
    c._user_options = {
        ENL_FANSPEED: ["low"],
        ENL_AIR_VERT: ["upper"],
        "ha_ui_swing": ["auto-vert", "vert", "upper"],
    }
    entity = EchonetClimate(c, config)
    for argument in ["low", "high", "1 bar", "unconfigured", 0x31, 0x99, None]:
        valid = not fan or argument in ("low", "1 bar")
        await assert_setter(entity, c, "async_set_fan_mode", argument,
                            "setFanSpeed" if valid else None, ENL_FANSPEED,
                            "low" if fan else argument)
    for argument in ["auto-vert", "vert", "not-used", "horiz", "upper", "lower",
                     "Position 1", "unconfigured", 0x43, 0x99, None]:
        valid = not vane or argument in ("auto-vert", "vert", "upper", "Position 1")
        translated = "upper" if vane and argument == "Position 1" else argument
        if translated == "auto-vert":
            target, epc = "setAutoDirection", ENL_AUTO_DIRECTION
        elif translated in ("vert", "not-used", "horiz"):
            target, epc = "setSwingMode", ENL_SWING_MODE
        else:
            target, epc = "setAirflowVert", ENL_AIR_VERT
        await assert_setter(entity, c, "async_set_swing_mode", argument,
                            target if valid else None, epc, translated)
    for argument in ["auto-horiz", "horiz", "vert-horiz", "unknown", 0x99, None]:
        if argument == "auto-horiz":
            target, epc = "setAutoDirection", ENL_AUTO_DIRECTION
        elif argument in ("horiz", "vert-horiz"):
            target, epc = "setSwingMode", ENL_SWING_MODE
        else:
            target, epc = "setAirflowHoriz", ENL_AIR_HORZ
        await assert_setter(entity, c, "async_set_swing_horizontal_mode", argument, target, epc, argument)
    assert wire.frames == []


SET_MAPS = [
    list(
        code
        for code, enabled in zip(
            [ENL_AUTO_DIRECTION, ENL_SWING_MODE, ENL_AIR_VERT, ENL_AIR_HORZ], bits
        )
        if enabled
    )
    for bits in product([False, True], repeat=4)
]


@pytest.mark.asyncio
@pytest.mark.parametrize("fan,vane", list(product([False, True], repeat=2)))
@pytest.mark.parametrize("setmap", SET_MAPS)
async def test_all_set_maps_preserve_options_and_horizontal_capabilities(
    device, fan, vane, setmap
):
    c, wire, _, _, config = device
    set_flags(config, fan, vane)
    c._user_options = {}
    c._setPropertyMap = [ENL_FANSPEED, *setmap]
    entity = EchonetClimate(c, config)
    protocol = {
        code: list(c._instance.EPC_FUNCTIONS[code][1].values())
        for code in (ENL_AUTO_DIRECTION, ENL_SWING_MODE)
    }
    assert entity._opc_data == protocol
    vertical = list(AIRFLOW_VERT) if ENL_AIR_VERT in setmap else []
    auto = ["auto-vert"] if ENL_AUTO_DIRECTION in setmap else []
    swing = []
    if ENL_SWING_MODE in setmap:
        swing = (["vert"] if ENL_AIR_VERT in setmap else list(reversed(protocol[ENL_SWING_MODE])))
    canonical = swing + auto + vertical or ["auto-vert", *AIRFLOW_VERT]
    expected = canonical
    if vane:
        ordered = [m for m in VANE_LABELS if m in canonical]
        ordered += [m for m in canonical if m not in VANE_LABELS]
        expected = list(dict.fromkeys(VANE_LABELS.get(m, m) for m in ordered))
    assert entity.swing_modes == expected
    horizontal = (["vert-horiz", "horiz"] if ENL_SWING_MODE in setmap else [])
    horizontal += (["auto-horiz"] if ENL_AUTO_DIRECTION in setmap else [])
    horizontal += list(AIRFLOW_HORIZ) if ENL_AIR_HORZ in setmap else []
    assert entity.swing_horizontal_modes == horizontal
    assert entity.supported_features == expected_features(setmap)
    assert wire.frames == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fan,vane", list(product([False, True], repeat=2)))
async def test_off_on_off_restores_original_lists_and_readback(device, fan, vane):
    c, wire, _, _, config = device
    set_flags(config, False, False)
    fan_modes = ["high", "low", "high", "unknown"]
    c._user_options = {
        ENL_FANSPEED: fan_modes,
        "ha_ui_swing": ["lower", "upper", "lower", "unknown", "vert", "auto-vert"],
    }
    entity = EchonetClimate(c, config)
    original = (
        list(entity.fan_modes),
        list(entity.swing_modes),
        list(entity.swing_horizontal_modes),
    )
    c.data.update(
        {
            ENL_FANSPEED: 0x99,
            ENL_AIR_VERT: "unknown",
            ENL_AUTO_DIRECTION: "non-auto",
            ENL_SWING_MODE: "not-used",
        }
    )
    for flags in [(fan, vane), (False, False), (fan, vane), (False, False)]:
        set_flags(config, *flags)
        entity.update_option_listener()
        assert entity.fan_modes == (["1 bar", "2 bars"] if flags[0] else fan_modes)
        assert entity.swing_modes == (["Auto", "Swing", "Position 1", "Position 5", "unknown"]
                                      if flags[1] else c._user_options["ha_ui_swing"])
    assert (
        entity.fan_modes,
        entity.swing_modes,
        entity.swing_horizontal_modes,
    ) == original
    assert entity.fan_modes is fan_modes
    assert entity.fan_mode == 0x99
    assert entity.swing_mode == "unknown"
    assert entity._fan_speed_options is entity._vane_positions is None
    assert wire.frames == []


@pytest.mark.asyncio
async def test_disabled_listener_never_constructs_mapping_helpers(device, monkeypatch):
    c, wire, _, _, config = device
    set_flags(config, False, False)

    def forbidden(*args, **kwargs):
        raise AssertionError("Disabled numbering must not construct a mapping helper")

    monkeypatch.setattr(current, "FanSpeedOptions", forbidden)
    monkeypatch.setattr(current, "VanePositionOptions", forbidden)
    entity = EchonetClimate(c, config)
    entity.update_option_listener()
    assert entity._fan_speed_options is entity._vane_positions is None
    assert wire.frames == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fan,vane", FLAGS)
async def test_horizontal_readings_ignore_numbering_flags(device, fan, vane):
    c, wire, _, _, config = device
    set_flags(config, fan, vane)
    c._setPropertyMap.append(ENL_AIR_HORZ)
    entity = EchonetClimate(c, config)
    for auto, swing, horizontal, expected in [
        ("auto-horiz", "horiz", "left", "auto-horiz"),
        ("non-auto", "horiz", "left", "horiz"),
        ("non-auto", "vert-horiz", "left", "vert-horiz"),
        ("non-auto", "not-used", "left", "left"),
        (None, None, None, None),
        (0x44, 0x42, 0x99, 0x99),
    ]:
        c.data.update({ENL_AUTO_DIRECTION: auto, ENL_SWING_MODE: swing, ENL_AIR_HORZ: horizontal})
        assert_reading(entity.swing_horizontal_mode, expected)
    c.data.pop(ENL_AIR_HORZ)
    assert entity.swing_horizontal_mode is None
    assert wire.frames == []
