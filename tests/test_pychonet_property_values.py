from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.exceptions import HomeAssistantError
from pychonet.lib.epc_functions import DICT_30_ON_OFF, _hh_mm, _int

from custom_components.echonetlite.connectors import (
    ECHONETConnector,
    regist_as_binary_sensor,
    regist_as_inputs,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("epc", "value"),
    [
        (0xA1, {"day": 1, "readings_48_half_hourly": [12]}),
        (0xCE, {"time": "2026-11-26T12:30", "readings_w": [-10, 20]}),
    ],
)
async def test_single_epc_keeps_structured_value_in_each_ha_path(epc, value):
    connector = SimpleNamespace(
        _instance=SimpleNamespace(update=AsyncMock(return_value=value)),
        _host="192.0.2.10",
        _singleton_poll_epcs=[],
        _ntfPropertyMap=[epc],
        _eojgc=0x02,
        _eojcc=0x8E,
        _eojci=1,
        data={},
        async_update_listeners=Mock(),
    )

    assert await ECHONETConnector.poll_pychonet(connector, batches_override=[[epc]]) == {
        epc: value,
    }
    assert await ECHONETConnector.poll_pychonet_specific(connector, [epc]) == {epc: value}
    await ECHONETConnector.async_update_callback(connector, isPush=True)
    assert connector.data == {epc: value}
    connector.async_update_listeners.assert_called_once()


@pytest.mark.asyncio
async def test_failed_write_is_reported_without_scheduling_verification():
    connector = SimpleNamespace(
        _host="192.0.2.10", hass=SimpleNamespace(async_create_task=Mock())
    )
    set_command = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError, match="write was not confirmed"):
        await ECHONETConnector.async_set_and_verify(connector, [0xBD], set_command())
    connector.hass.async_create_task.assert_not_called()


def test_entity_classification_accepts_decoders_without_an_enum():
    assert not regist_as_binary_sensor([_int])
    assert not regist_as_inputs([_int])
    assert regist_as_inputs([_hh_mm])
    assert regist_as_binary_sensor([_int, DICT_30_ON_OFF])
    assert regist_as_inputs([_int, DICT_30_ON_OFF])
