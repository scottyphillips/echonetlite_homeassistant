"""Regression tests for the Rinnai gas meter's cumulative reading."""

import logging
from datetime import timedelta
from types import SimpleNamespace

import pytest
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import STATE_UNAVAILABLE, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry, restore_state
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pychonet.GasMeter import GasMeter

from custom_components.echonetlite import sensor
from custom_components.echonetlite.const import DOMAIN, ENL_OP_CODES

EPC = 0xE0
ENTITY_ID = "sensor.rinnai_gas"


async def make_meter(hass, monkeypatch, liters, manufacturer="Rinnai"):
    """Set up the gas entity using the sensor platform's normal entry point."""
    coordinator = DataUpdateCoordinator(
        hass, logging.getLogger(__name__), config_entry=None, name="gas meter"
    )
    host = "meter.invalid"
    coordinator._api = SimpleNamespace(
        _state={host: {"instances": {0x02: {0x82: {1: {}}}}}}
    )
    coordinator._instance = GasMeter(host, coordinator._api)
    coordinator._name = None
    coordinator._eojgc = 0x02
    coordinator._eojcc = 0x82
    coordinator._uidi = "test-meter"
    coordinator._manufacturer = manufacturer
    coordinator.is_sharp_air_cleaner = False
    coordinator._getPropertyMap = [EPC]
    coordinator._update_flags_full_list = [EPC]
    coordinator._user_options = {}
    coordinator._enl_op_codes = ENL_OP_CODES[0x02][0x82]
    coordinator.async_set_updated_data({EPC: liters})
    config = SimpleNamespace(entry_id="test", title="Hot water heater")
    hass.data[DOMAIN] = {
        config.entry_id: [
            {
                "echonetlite": coordinator,
                "instance": {"eojgc": 0x02, "eojcc": 0x82, "setmap": []},
            }
        ]
    }
    platform = EntityPlatform(
        hass=hass,
        logger=logging.getLogger(__name__),
        domain="sensor",
        platform_name=DOMAIN,
        platform=sensor,
        scan_interval=timedelta(seconds=30),
        entity_namespace=None,
    )
    monkeypatch.setattr(
        sensor.entity_platform, "async_get_current_platform", lambda: platform
    )
    entities = []
    await sensor.async_setup_entry(
        hass, config, lambda added, _: entities.extend(added)
    )
    (entity,) = entities
    entity.entity_id = ENTITY_ID
    if entity_registry.DATA_REGISTRY not in hass.data:
        await entity_registry.async_load(hass)
    entity.add_to_platform_start(hass, platform, None)
    await entity.add_to_platform_finish()
    return entity, coordinator


@pytest.mark.asyncio
async def test_reconnect_does_not_add_lifetime_total(tmp_path, monkeypatch):
    hass = HomeAssistant(str(tmp_path))
    try:
        entity, coordinator = await make_meter(hass, monkeypatch, 700_000)
        assert isinstance(entity, sensor.RinnaiGasSensor)
        assert entity.unique_id == f"test-meter-{EPC}"
        assert entity.state_class == SensorStateClass.TOTAL_INCREASING
        assert entity.native_unit_of_measurement == UnitOfVolume.CUBIC_METERS
        assert entity.native_value == 700

        coordinator.async_set_update_error(UpdateFailed("offline"))
        assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
        for reading in (None, 0xFFFFFFFE, 0, 0, 699_999):
            coordinator.async_set_updated_data({EPC: reading})
            assert float(hass.states.get(ENTITY_ID).state) == 700

        coordinator.async_set_updated_data({EPC: 700_240})
        assert float(hass.states.get(ENTITY_ID).state) == pytest.approx(700.240)
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_real_reset_and_restore_from_disk(tmp_path, monkeypatch):
    hass = HomeAssistant(str(tmp_path))
    try:
        entity, coordinator = await make_meter(hass, monkeypatch, 700_000)
        coordinator.async_set_updated_data({EPC: 0})
        coordinator.async_set_updated_data({EPC: 180})
        assert entity.native_value == pytest.approx(700.180)
        coordinator.async_set_update_error(UpdateFailed("offline"))
        await restore_state.async_get(hass).async_dump_states()
    finally:
        await hass.async_stop()

    hass = HomeAssistant(str(tmp_path))
    try:
        await restore_state.async_get(hass).async_load()
        entity, coordinator = await make_meter(hass, monkeypatch, 240)
        assert entity.native_value == pytest.approx(700.240)
        coordinator.async_set_updated_data({EPC: 700_300})
        assert entity.native_value == pytest.approx(700.300)
    finally:
        await hass.async_stop()


@pytest.mark.asyncio
async def test_other_gas_meter_uses_standard_sensor(tmp_path, monkeypatch):
    hass = HomeAssistant(str(tmp_path))
    try:
        entity, coordinator = await make_meter(hass, monkeypatch, 700_000, "Other")
        assert type(entity) is sensor.EchonetSensor
        assert entity.native_value == 700
        coordinator.async_set_updated_data({EPC: 0})
        assert entity.native_value == 0
    finally:
        await hass.async_stop()
