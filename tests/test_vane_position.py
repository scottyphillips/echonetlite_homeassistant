"""Vertical vane labels through real entities and an offline ECHONET wire."""

import pytest
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.exceptions import HomeAssistantError
from pychonet.lib.const import SETC
from pychonet.lib.functions import decodeEchonetMsg

from custom_components.echonetlite.climate import EchonetClimate
from custom_components.echonetlite.select import EchonetSelect
from custom_components.echonetlite.vane_position import VanePositionOptions
from test_fan_speed import device  # noqa: F401

POSITIONS = ["upper", "upper-central", "central", "lower-central", "lower"]
LABELS = [f"Position {n}" for n in range(1, 6)]


@pytest.mark.parametrize(
    "code, label",
    [
        (0x41, "Position 1"),
        (0x44, "Position 2"),
        (0x43, "Position 3"),
        (0x45, "Position 4"),
        (0x42, "Position 5"),
        (0x99, None),
        (None, None),
    ],
)
def test_positions_follow_physical_order(code, label):
    options = VanePositionOptions(list(reversed(POSITIONS)), True)
    assert options.options == LABELS
    assert options.label_for_value(code) == label


def test_only_configured_positions_and_default_names():
    assert VanePositionOptions(POSITIONS).options == POSITIONS
    options = VanePositionOptions(["central", "vert", "auto-vert"], True)
    assert options.options == ["Auto", "Swing", "Position 3"]
    assert options.label_for_value("upper") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label, canonical, epc, code",
    [
        ("Auto", "auto-vert", 0xA1, 0x43),
        ("Swing", "vert", 0xA3, 0x41),
        ("Position 1", "upper", 0xA4, 0x41),
        ("Position 2", "upper-central", 0xA4, 0x44),
        ("Position 3", "central", 0xA4, 0x43),
        ("Position 4", "lower-central", 0xA4, 0x45),
        ("Position 5", "lower", 0xA4, 0x42),
        ("lower", "lower", 0xA4, 0x42),
    ],
)
async def test_climate_routes_labels_to_correct_properties(
    device, label, canonical, epc, code
):
    c, wire, _, hass, config = device
    config.options.update(
        numbered_vane_positions=True, ha_ui_swing=["vert", "auto-vert", *POSITIONS]
    )
    c._user_options[0xA4] = POSITIONS
    c._user_options["ha_ui_swing"] = config.options["ha_ui_swing"]
    climate = EchonetClimate(c, config)
    assert climate.swing_modes == ["Auto", "Swing", *LABELS]
    assert not climate.supported_features & ClimateEntityFeature.SWING_HORIZONTAL_MODE
    await climate.async_set_swing_mode(label)
    setters = [
        decodeEchonetMsg(p) for p in wire.frames if decodeEchonetMsg(p)["ESV"] == SETC
    ]
    assert len(setters) == 1
    assert [(p["EPC"], p["EDT"][0]) for p in setters[0]["OPC"]] == [(epc, code)]
    await hass.async_block_till_done()
    assert c.data[epc] == canonical


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label, code",
    [
        ("Position 1", 0x41),
        ("Position 2", 0x44),
        ("Position 3", 0x43),
        ("Position 4", 0x45),
        ("Position 5", 0x42),
        ("upper-central", 0x44),
    ],
)
async def test_static_select_and_climate_share_readback(device, label, code):
    c, wire, _, hass, config = device
    config.options.update(
        numbered_vane_positions=True, ha_ui_swing=["vert", "auto-vert", *POSITIONS]
    )
    c._user_options[0xA4] = POSITIONS
    c._user_options["ha_ui_swing"] = config.options["ha_ui_swing"]
    climate = EchonetClimate(c, config)
    select = EchonetSelect(c, config, {}, 0xA4)
    assert select.options == LABELS
    await select.async_select_option(label)
    assert wire.position == code
    await hass.async_block_till_done()
    assert (
        climate.swing_mode
        == select.current_option
        == VanePositionOptions(POSITIONS, True).label_for_value(code)
    )
    assert select.unique_id == "synthetic-object-164"


@pytest.mark.asyncio
async def test_external_swing_auto_invalid_and_option_reload(device):
    c, wire, _, _, config = device
    config.options.update(
        numbered_vane_positions=True, ha_ui_swing=["vert", "auto-vert", *POSITIONS]
    )
    c._user_options[0xA4] = POSITIONS
    c._user_options["ha_ui_swing"] = config.options["ha_ui_swing"]
    climate = EchonetClimate(c, config)
    select = EchonetSelect(c, config, {}, 0xA4)
    c.data[0xA1] = "auto-vert"
    assert climate.swing_mode == "Auto"
    c.data[0xA1], c.data[0xA3] = "non-auto", "vert"
    assert climate.swing_mode == "Swing"
    c.data[0xA3], c.data[0xA4] = "not-used", "lower"
    assert climate.swing_mode == select.current_option == "Position 5"
    for label in ["Position 6", "horiz", "nonsense"]:
        with pytest.raises(HomeAssistantError):
            await climate.async_set_swing_mode(label)
    with pytest.raises(HomeAssistantError):
        await select.async_select_option("Swing")
    assert wire.frames == []
    config.options["numbered_vane_positions"] = False
    climate.update_option_listener()
    assert climate.swing_mode == select.current_option == "lower"
    assert select.options == POSITIONS
