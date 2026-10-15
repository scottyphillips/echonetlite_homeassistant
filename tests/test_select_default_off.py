"""Default-off select options, readback and command compatibility."""

from unittest.mock import AsyncMock, Mock, sentinel

import pytest

from custom_components.echonetlite import select as selected
from custom_components.echonetlite.select import EchonetSelect
from pychonet.HomeAirConditioner import AIRFLOW_VERT, FAN_SPEED
from test_fan_speed import device  # noqa: F401
from test_sharp_fps42y import device as sharp_device  # noqa: F401
from custom_components.echonetlite.sharp import SHARP_MODES, sharp_value

CONTROLS = [(0xA0, "numbered_fan_speeds"), (0xA4, "numbered_vane_positions")]
UNSET = object()


def configured_select(c, config, code, setting, present, subset):
    config.options.pop("numbered_fan_speeds", None)
    config.options.pop("numbered_vane_positions", None)
    if present:
        config.options[setting] = False
    if subset is UNSET:
        c._user_options.pop(code, None)
    else:
        c._user_options[code] = subset
    return EchonetSelect(c, config, {}, code)


@pytest.mark.asyncio
@pytest.mark.parametrize("code,setting", CONTROLS)
@pytest.mark.parametrize("present", [False, True], ids=["missing", "false"])
@pytest.mark.parametrize(
    "subset",
    [UNSET, False, [], ["low"], ["high", "unknown", "low", "high"]],
    ids=["unset", "disabled", "empty", "subset", "duplicates-unknown"],
)
async def test_disabled_options_and_readings_do_not_construct_helpers(
    device, monkeypatch, code, setting, present, subset
):
    c, _, _, _, config = device
    candidate = configured_select(c, config, code, setting, present, subset)

    def forbidden(*args, **kwargs):
        raise AssertionError("Disabled numbering must not construct a mapping helper")

    monkeypatch.setattr(selected, "FanSpeedOptions", forbidden)
    monkeypatch.setattr(selected, "VanePositionOptions", forbidden)
    protocol_options = FAN_SPEED if code == 0xA0 else AIRFLOW_VERT
    expected_options = subset if isinstance(subset, list) else list(protocol_options)
    assert candidate.options == expected_options
    if isinstance(subset, list):
        assert candidate.options is subset
    for value in [
        None,
        "auto",
        "low",
        "high",
        "upper",
        "outside-subset",
        "unknown",
        0x31,
        0x41,
        0x99,
    ]:
        c.data[code] = value
        expected = next(
            (name for name, raw in protocol_options.items() if raw == value), value
        )
        assert candidate.current_option == expected
        assert type(candidate.current_option) is type(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("code,setting", CONTROLS)
@pytest.mark.parametrize("present", [False, True], ids=["missing", "false"])
@pytest.mark.parametrize(
    "subset",
    [False, [], ["not-the-command"]],
    ids=["disabled", "empty", "outside-configured-subset"],
)
@pytest.mark.parametrize(
    "response", [True, False, None], ids=["accepted", "failed", "empty-response"]
)
async def test_generic_set_message_payload_and_failed_readback(
    device, code, setting, present, subset, response
):
    c, wire, _, _, config = device
    candidate = configured_select(c, config, code, setting, present, subset)
    option = "low" if code == 0xA0 else "upper"
    previous = "high" if code == 0xA0 else "lower"
    c.data[code] = previous
    generic = AsyncMock(return_value=response)
    c._instance.setMessage = generic
    c._instance.setFanSpeed = Mock(
        side_effect=AssertionError("Named fan setter must be bypassed")
    )
    c._instance.setAirflowVert = Mock(
        side_effect=AssertionError("Named vane setter must be bypassed")
    )
    c.async_set_and_verify = AsyncMock(
        side_effect=AssertionError("New readback path must be bypassed")
    )
    await candidate.async_select_option(option)
    generic.assert_awaited_once_with(code, 0x32 if code == 0xA0 else 0x41)
    assert candidate._attr_current_option == (option if response else previous)
    assert candidate.current_option == previous
    assert wire.frames == []


@pytest.mark.asyncio
@pytest.mark.parametrize("code,setting", CONTROLS)
async def test_failed_response_restores_fresh_generic_reading(device, code, setting):
    c, wire, _, _, config = device
    candidate = configured_select(c, config, code, setting, True, [])
    option = "low" if code == 0xA0 else "upper"
    reading = 0x99

    async def failed(*args):
        c.data[code] = reading
        return False

    c._instance.setMessage = AsyncMock(side_effect=failed)
    await candidate.async_select_option(option)
    c._instance.setMessage.assert_awaited_once_with(
        code, 0x32 if code == 0xA0 else 0x41
    )
    assert candidate._attr_current_option == reading
    assert candidate.current_option == reading
    assert wire.frames == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fan_enabled,vane_enabled",
    [(False, False), (True, False), (False, True), (True, True)],
)
async def test_settings_independently_select_generic_or_numbered_path(
    device, fan_enabled, vane_enabled
):
    c, wire, _, _, config = device
    config.options.update(
        numbered_fan_speeds=fan_enabled, numbered_vane_positions=vane_enabled
    )
    c._user_options[0xA0] = ["low"]
    c._user_options[0xA4] = ["upper"]
    c.async_set_and_verify = AsyncMock()
    c._instance.setFanSpeed = Mock(return_value=sentinel.fan_operation)
    c._instance.setAirflowVert = Mock(return_value=sentinel.vane_operation)
    c._instance.setMessage = AsyncMock(return_value=True)
    for code, enabled, canonical, label, operation in [
        (0xA0, fan_enabled, "low", "1 bar", sentinel.fan_operation),
        (0xA4, vane_enabled, "upper", "Position 1", sentinel.vane_operation),
    ]:
        entity = EchonetSelect(c, config, {}, code)
        c.data[code] = canonical
        assert entity.options == ([label] if enabled else [canonical])
        assert entity.current_option == (label if enabled else canonical)
        c.async_set_and_verify.reset_mock()
        c._instance.setMessage.reset_mock()
        await entity.async_select_option(label if enabled else canonical)
        if enabled:
            c.async_set_and_verify.assert_awaited_once_with([code], operation)
            c._instance.setMessage.assert_not_awaited()
        else:
            c._instance.setMessage.assert_awaited_once_with(
                code, entity._options[canonical]
            )
            c.async_set_and_verify.assert_not_awaited()
    assert wire.frames == []


@pytest.mark.asyncio
async def test_generic_unknown_command_is_rejected_before_transport(device):
    c, wire, _, _, config = device
    entity = configured_select(c, config, 0xA0, "numbered_fan_speeds", True, [])
    c._instance.setMessage = AsyncMock()
    with pytest.raises(KeyError, match="unconfigured"):
        await entity.async_select_option("unconfigured")
    c._instance.setMessage.assert_not_awaited()
    assert wire.frames == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fan_enabled,vane_enabled", [(False, False), (True, False), (False, True), (True, True)])
async def test_numbering_does_not_change_sharp_select(sharp_device, monkeypatch, fan_enabled, vane_enabled):
    make, wire, _, _, config = sharp_device
    c = make()
    await c.startup()
    c.data = await c._instance.update([0xF1, 0xF2, 0xF3])
    c.last_update_success = True
    config.options.update(numbered_fan_speeds=fan_enabled, numbered_vane_positions=vane_enabled)
    entity = EchonetSelect(c, config, {}, 0xA0)

    def forbidden(*args, **kwargs):
        raise AssertionError("Sharp must bypass HVAC numbering helpers")

    monkeypatch.setattr(selected, "FanSpeedOptions", forbidden)
    monkeypatch.setattr(selected, "VanePositionOptions", forbidden)
    assert entity.options == list(SHARP_MODES)
    assert entity.current_option == sharp_value(c.data, "mode")
    c.async_set_sharp_fan_mode = AsyncMock()
    c._instance.setMessage = AsyncMock()
    frame_count = len(wire.frames)
    for option in SHARP_MODES:
        c.async_set_sharp_fan_mode.reset_mock()
        await entity.async_select_option(option)
        c.async_set_sharp_fan_mode.assert_awaited_once_with(option)
    c._instance.setMessage.assert_not_awaited()
    assert len(wire.frames) == frame_count
