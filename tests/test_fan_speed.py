"""HVAC fan labels through real entities and an offline ECHONET wire."""

import asyncio
from types import SimpleNamespace

import pytest
import pytest_asyncio
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import frame
from pychonet import ECHONETAPIClient
from pychonet.lib.const import GETRES, SETC, SETRES
from pychonet.lib.functions import decodeEchonetMsg

from custom_components.echonetlite.climate import EchonetClimate
from custom_components.echonetlite.connectors import ECHONETConnector
from custom_components.echonetlite.fan_speed import FanSpeedOptions
from custom_components.echonetlite.select import EchonetSelect

HOST = "hvac-test.invalid"
FIVE_SPEEDS = ["auto", "low", "medium", "high", "minimum", "medium-high"]
FIVE_LABELS = ["auto", "1 bar", "2 bars", "3 bars", "4 bars", "5 bars"]


class Wire:
    """Loop synthetic responses through pychonet without opening a socket."""

    def __init__(self):
        self.frames = []
        self.speed = 0x41
        self.direction = 0x42
        self.swing = 0x31
        self.position = 0x41

    def subscribe(self, callback):
        self.callback = callback

    def send(self, packet, addr):
        self.frames.append(bytes(packet))
        request = decodeEchonetMsg(packet)
        setter = request["ESV"] == SETC
        values = {
            0x80: b"\x31",
            0xA0: bytes([self.speed]),
            0xA1: bytes([self.direction]),
            0xA3: bytes([self.swing]),
            0xA4: bytes([self.position]),
            0xB0: b"\x42",
            0xB3: b"\x17",
            0xBB: b"\x16",
        }
        body = bytearray()
        for prop in request["OPC"]:
            epc = prop["EPC"]
            if setter:
                field = {
                    0xA0: "speed",
                    0xA1: "direction",
                    0xA3: "swing",
                    0xA4: "position",
                }[epc]
                setattr(self, field, prop["EDT"][0])
                value = b""
            else:
                value = values[epc]
            body.extend(bytes([epc, len(value)]) + value)
        response = (
            packet[:4]
            + packet[7:10]
            + packet[4:7]
            + bytes([SETRES if setter else GETRES, len(request["OPC"])])
            + body
        )
        asyncio.create_task(self.callback(bytes(response), addr))


@pytest_asyncio.fixture
async def device(tmp_path):
    wire = Wire()
    api = ECHONETAPIClient(wire)
    api._logger = lambda *args: None
    hass = HomeAssistant(str(tmp_path))
    frame.async_setup(hass)
    hass.data["echonetlite"] = {"api": api}
    config = SimpleNamespace(
        title="Synthetic HVAC",
        options={"fan_settings": FIVE_SPEEDS, "numbered_fan_speeds": True},
        entry_id="test",
    )
    api._state[HOST] = {
        "available": True,
        "product_code": "synthetic",
        "instances": {1: {0x30: {1: {}}}},
    }
    data = dict(
        host=HOST,
        uid="synthetic-node",
        uidi="synthetic-object",
        eojgc=1,
        eojcc=0x30,
        eojci=1,
        manufacturer="Synthetic",
        host_product_code="synthetic",
        ntfmap=[0x80, 0xA0],
        getmap=[0x80, 0xA0, 0xA1, 0xA3, 0xA4, 0xB0, 0xB3, 0xBB],
        setmap=[0x80, 0xA0, 0xA1, 0xA3, 0xA4, 0xB0, 0xB3],
    )
    props = api._state[HOST]["instances"][1][0x30][1]
    props[0x9F], props[0x9E] = data["getmap"], data["setmap"]
    c = ECHONETConnector(data, hass, config)
    c._user_options = {0xA0: FIVE_SPEEDS}
    c.data = {
        0x80: "off",
        0xA0: "auto",
        0xA1: "non-auto",
        0xA3: "not-used",
        0xA4: "upper",
        0xB0: "cool",
        0xB3: 23,
        0xBB: 22,
    }
    yield c, wire, api, hass, config
    await hass.async_stop()


@pytest.mark.parametrize(
    "value, label",
    [
        ("auto", "auto"),
        (0x31, "1 bar"),
        ("low", "2 bars"),
        ("medium", "3 bars"),
        (0x35, "4 bars"),
        ("high", "5 bars"),
        (0x33, None),
        ("max", None),
        (0x99, None),
        (None, None),
    ],
)
def test_configured_levels_do_not_guess_missing_speeds(value, label):
    speeds = FanSpeedOptions(FIVE_SPEEDS, True)
    assert speeds.options == FIVE_LABELS
    assert speeds.label_for_value(value) == label


def test_default_names_order_and_numbering_without_auto():
    assert FanSpeedOptions(FIVE_SPEEDS).options == FIVE_SPEEDS
    assert FanSpeedOptions(["high", "low"], True).options == ["1 bar", "2 bars"]
    assert FanSpeedOptions(numbered=True).options[-1] == "8 bars"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label, code",
    [
        ("auto", 0x41),
        ("1 bar", 0x31),
        ("2 bars", 0x32),
        ("3 bars", 0x34),
        ("4 bars", 0x35),
        ("5 bars", 0x36),
        ("medium-high", 0x35),
    ],
)
@pytest.mark.parametrize("kind", ["climate", "select"])
async def test_entities_translate_commands_and_confirm_reads(device, label, code, kind):
    c, wire, _, hass, config = device
    entity = (
        EchonetClimate(c, config)
        if kind == "climate"
        else EchonetSelect(c, config, {}, 0xA0)
    )
    assert (entity.fan_modes if kind == "climate" else entity.options) == FIVE_LABELS
    assert (entity.fan_mode if kind == "climate" else entity.current_option) == "auto"
    if kind == "climate":
        await entity.async_set_fan_mode(label)
    else:
        await entity.async_select_option(label)
    assert wire.speed == code
    for packet in wire.frames:
        if decodeEchonetMsg(packet)["ESV"] == SETC:
            assert [p["EPC"] for p in decodeEchonetMsg(packet)["OPC"]] == [0xA0]
    await hass.async_block_till_done()
    expected = FanSpeedOptions(FIVE_SPEEDS, True).label_for_value(code)
    assert (entity.fan_mode if kind == "climate" else entity.current_option) == expected
    assert len(wire.frames) == 2


@pytest.mark.asyncio
async def test_external_updates_options_reload_and_invalid_commands(device):
    c, wire, _, _, config = device
    climate = EchonetClimate(c, config)
    select = EchonetSelect(c, config, {}, 0xA0)
    c.data[0xA0] = "medium-high"
    assert climate.fan_mode == select.current_option == "4 bars"
    c.data[0xA0] = "medium-low"
    assert climate.fan_mode is None and select.current_option is None
    for invalid in ["6 bars", "max", "nonsense"]:
        with pytest.raises(HomeAssistantError):
            await climate.async_set_fan_mode(invalid)
        with pytest.raises(HomeAssistantError):
            await select.async_select_option(invalid)
    assert wire.frames == []
    config.options["numbered_fan_speeds"] = False
    climate.update_option_listener()
    assert climate.fan_modes == select.options == FIVE_SPEEDS
    assert climate.fan_mode == select.current_option == "medium-low"
    assert climate.unique_id == "synthetic-object"
    assert select.unique_id == "synthetic-object-160"
