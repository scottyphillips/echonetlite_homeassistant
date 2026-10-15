"""Keep climate construction compatible with older feature enumerations."""

from enum import IntFlag
from itertools import product

import pytest
from homeassistant.components.climate import ClimateEntityFeature

from custom_components.echonetlite import climate as current
from test_fan_speed import device  # noqa: F401


class LegacyClimateEntityFeature(IntFlag):
    """Climate feature values published by Home Assistant 2024.1.0."""

    TARGET_TEMPERATURE = 1
    TARGET_TEMPERATURE_RANGE = 2
    TARGET_HUMIDITY = 4
    FAN_MODE = 8
    PRESET_MODE = 16
    SWING_MODE = 32
    AUX_HEAT = 64


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [True, False], ids=["legacy", "current"])
@pytest.mark.parametrize("horizontal", [False, True], ids=["no-a5", "a5"])
@pytest.mark.parametrize("fan,vane", list(product([False, True], repeat=2)))
async def test_horizontal_feature_requires_platform_and_device_support(
    device, monkeypatch, legacy, horizontal, fan, vane
):
    coordinator, wire, _, _, config = device
    feature_enum = LegacyClimateEntityFeature if legacy else ClimateEntityFeature
    monkeypatch.setattr(current, "ClimateEntityFeature", feature_enum)
    config.options.update(
        numbered_fan_speeds=fan, numbered_vane_positions=vane
    )
    coordinator._setPropertyMap = [0xA0, 0xA1, 0xA3, 0xA4]
    if horizontal:
        coordinator._setPropertyMap.append(0xA5)
    coordinator.data[0xA5] = "left"
    entity = current.EchonetClimate(coordinator, config)

    expected = (
        feature_enum.TARGET_TEMPERATURE
        | feature_enum.FAN_MODE
        | feature_enum.SWING_MODE
    )
    if not legacy:
        expected |= feature_enum.TURN_ON | feature_enum.TURN_OFF
        if horizontal:
            expected |= feature_enum.SWING_HORIZONTAL_MODE
    assert entity.supported_features == expected
    assert isinstance(entity.supported_features, feature_enum)
    assert entity.swing_horizontal_mode == "left"
    assert ("left" in entity.swing_horizontal_modes) is horizontal
    assert wire.frames == []
