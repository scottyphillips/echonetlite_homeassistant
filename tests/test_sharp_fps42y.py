"""Offline Sharp contracts using real HA entities and pychonet's protocol stack.

Run with pytest, pytest-asyncio, Home Assistant and the manifest's pychonet
version installed. All device IDs and addresses below are synthetic; the wire
only loops packets into pychonet's receiver and never opens a socket.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pychonet import ECHONETAPIClient
from pychonet.lib.const import GETRES, GET_SNA, SETC, SETRES, SETC_SND
from pychonet.lib.functions import decodeEchonetMsg

from custom_components.echonetlite import binary_sensor, select, sensor, switch
from homeassistant.components.fan import FanEntityFeature
from custom_components.echonetlite.connectors import ECHONETConnector
from custom_components.echonetlite.fan import EchonetFan
from custom_components.echonetlite.select import EchonetSelect
from custom_components.echonetlite.sharp import SHARP_FIELDS, SHARP_MODES, sharp_value

HOST = "sharp-test.invalid"


class Wire:
    """Device responses through the actual pychonet encoder and receiver."""

    def __init__(self):
        self.frames = []
        self.mode = 0x20
        self.led = 0xF0
        self.lock = 0
        self.model = b"FPS42Y\0\0\0\0\0\0"
        self.nack = False
        self.mismatch = False
        self.get_nack = False

    def subscribe(self, callback):
        self.callback = callback

    def send(self, frame, addr):
        self.frames.append(bytes(frame))
        request = decodeEchonetMsg(frame)
        setter = request["ESV"] == SETC
        nack = self.nack or (not setter and self.get_nack)
        if setter and not nack and not self.mismatch:
            payload = request["OPC"][0]["EDT"]
            assert len(payload) == 27
            if payload[:4] == bytes.fromhex("01010000"):
                self.mode = payload[4]
            elif payload[:4] == bytes.fromhex("00004000"):
                self.led = payload[26]
            elif payload[:4] == bytes.fromhex("00400000"):
                self.lock = payload[18]
            else:
                raise AssertionError("Unexpected write mask")
        f1, f2, f3 = bytearray(40), bytearray(40), bytearray(27)
        f1[3], f1[4], f1[28] = 30, 43, 18
        f2[25] = 0xFF
        f3[4], f3[18], f3[26] = self.mode, self.lock, self.led
        values = {
            0x8C: self.model,
            0x80: b"\x30",
            0xA0: bytes([{0x14: 0x31, 0x15: 0x35, 0x16: 0x37}.get(self.mode, 0x41)]),
            0xF1: bytes(f1),
            0xF2: bytes(f2),
            0xF3: bytes(f3),
        }
        body = bytearray()
        for opc in request["OPC"]:
            epc = opc["EPC"]
            value = (
                opc["EDT"]
                if setter and nack
                else b"" if setter or nack else values[epc]
            )
            body.extend(bytes((epc, len(value))) + value)
        esv = (
            (SETC_SND if setter else GET_SNA)
            if nack
            else (SETRES if setter else GETRES)
        )
        response = (
            frame[:4]
            + frame[7:10]
            + frame[4:7]
            + bytes((esv, len(request["OPC"])))
            + body
        )
        asyncio.create_task(self.callback(bytes(response), addr))


@pytest_asyncio.fixture
async def device(tmp_path):
    wire = Wire()
    api = ECHONETAPIClient(wire)
    api._logger = lambda *args: None
    hass = HomeAssistant(str(tmp_path))
    hass.data["echonetlite"] = {"api": api}
    config = SimpleNamespace(title="Synthetic air cleaner", options={}, entry_id="test")
    api._state[HOST] = {
        "available": True,
        "product_code": "HW-A04",
        "instances": {1: {0x35: {}}},
    }

    def make(number=1, **overrides):
        props = {0x80: b"\x30", 0xA0: b"\x41"}
        api._state[HOST]["instances"][1][0x35][number] = props
        data = dict(
            host=HOST,
            uid=f"synthetic-node-{number}",
            uidi=f"synthetic-object-{number}",
            eojgc=1,
            eojcc=0x35,
            eojci=number,
            manufacturer="Sharp",
            host_product_code="HW-A04",
            ntfmap=[0x80, 0xF3],
            getmap=[0x80, 0xA0, 0x8C, 0xF1, 0xF2, 0xF3],
            setmap=[0x80, 0xA0, 0xF3],
        )
        data.update(overrides)
        props[0x9F], props[0x9E] = data["getmap"], data["setmap"]
        return ECHONETConnector(data, hass, config)

    yield make, wire, api, hass, config
    await hass.async_stop()


@pytest.mark.asyncio
async def test_object_model_discovery_and_instance_isolation(device):
    make, wire, api, _, _ = device
    one, two = make(), make(2)
    original_functions = dict(two._instance.EPC_FUNCTIONS)
    await one.startup()
    assert one.is_sharp_fps42y and not two.is_sharp_fps42y
    assert two._instance.EPC_FUNCTIONS == original_functions
    assert api._state[HOST]["instances"][1][0x35][1][0x8C] == "FPS42Y"
    assert one._host_product_code == api._state[HOST]["product_code"] == "HW-A04"
    assert wire.frames[0][7:10] == b"\x01\x35\x01"
    await two.startup()
    assert two.is_sharp_fps42y
    assert wire.frames[1][7:10] == b"\x01\x35\x02"
    for coordinator in (one, two):
        assert {0xF1, 0xF2, 0xF3} <= set(coordinator._update_flags_full_list)
        assert 0xF3 in sum(coordinator._update_flag_batches, [])
        assert 0xF3 not in sum(coordinator._statmap_flag_batches, [])
        data = await coordinator._instance.update([0xF1, 0xF2, 0xF3])
        assert sharp_value(data, "temperature") == 30
        assert sharp_value(data, "humidity") == 43
        assert sharp_value(data, "pm25") == 18
        assert sharp_value(data, "plasmacluster") is True
        assert all(isinstance(raw, bytes) for raw in data.values())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model",
    [None, False, b"FPS42Y", "", "HW-A04", "FPS42Y-other", "FPS42Y\0x", "fps42y"],
)
async def test_invalid_object_model_never_enables_node_model(device, model):
    make, _, _, _, _ = device
    c = make(host_product_code="FPS42Y")
    c._instance.getMessage = AsyncMock(return_value=model)
    await c.startup()
    assert not c.is_sharp_fps42y and c._quirk_product_code is None
    assert 0xF3 not in c._instance.EPC_FUNCTIONS
    with pytest.raises(HomeAssistantError):
        await c.async_set_sharp_fan_mode("low")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["manufacturer", "class", "missing_model", "timeout", "nak"]
)
async def test_unsupported_or_unreachable_model(device, change):
    make, wire, _, _, _ = device
    c = make()
    if change == "manufacturer":
        c._manufacturer = "Other"
    elif change == "class":
        c._eojcc = 0x30
    elif change == "missing_model":
        c._getPropertyMap.remove(0x8C)
    elif change == "timeout":
        c._instance.getMessage = AsyncMock(side_effect=TimeoutError)
    else:
        wire.nack = True
    await c._discover_sharp_model()
    assert not c.is_sharp_fps42y
    with pytest.raises(HomeAssistantError):
        await c.async_set_sharp_fan_mode("low")
    assert not any(frame[10] == SETC for frame in wire.frames)


@pytest.mark.asyncio
async def test_unrelated_sharp_model_keeps_existing_quirk_lookup(device):
    make, _, _, _, _ = device
    c = make(host_product_code="OTHER-MODEL")
    c._instance.getMessage = AsyncMock(return_value=None)
    await c._discover_sharp_model()
    assert c._quirk_product_code == "OTHER-MODEL"
    assert not c.is_sharp_fps42y


@pytest.mark.asyncio
@pytest.mark.parametrize("option,code", SHARP_MODES.items())
async def test_all_modes_send_exact_command_and_publish_get(device, option, code):
    make, wire, _, _, _ = device
    c = make()
    await c.startup()
    wire.frames.clear()
    await c.async_set_sharp_fan_mode(option)
    assert wire.frames[0][10:14] == bytes.fromhex("6101f31b")
    assert wire.frames[0][14:] == bytes.fromhex("01010000") + bytes([code]) + bytes(22)
    assert [frame[12] for frame in wire.frames[1:]] == [0xF3, 0x80, 0xA0]
    assert all(frame[10] == 0x62 for frame in wire.frames[1:])
    assert sharp_value(c.data, "mode") == option
    assert c.data[0x80] == "on"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key,mask,offset,on",
    [("led", "00004000", 26, 0xF0), ("child-lock", "00400000", 18, 0xFF)],
)
@pytest.mark.parametrize("requested", [True, False])
async def test_switch_commands_preserve_mode(device, key, mask, offset, on, requested):
    make, wire, _, _, _ = device
    c = make()
    await c.startup()
    wire.mode = 0x16
    wire.frames.clear()
    await c.async_set_sharp_setting(key, requested)
    payload = bytearray(27)
    payload[:4], payload[offset] = bytes.fromhex(mask), on if requested else 0
    assert wire.frames[0][14:] == bytes(payload)
    assert sharp_value(c.data, key) is requested
    assert sharp_value(c.data, "mode") == "high"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["nak", "get_nak", "busy", "timeout", "mismatch", "missing_setmap"]
)
async def test_failed_set_or_verification_never_publishes_command(device, failure):
    make, wire, api, _, _ = device
    c = make()
    await c.startup()
    c.data = {0xA0: "auto"}
    if failure == "nak":
        wire.nack = True
    elif failure == "get_nak":
        wire.get_nack = True
    elif failure == "busy":
        api._waiting[HOST] = 1
    elif failure == "timeout":
        c._instance.setMessage = AsyncMock(side_effect=TimeoutError)
    elif failure == "missing_setmap":
        c._setPropertyMap.remove(0xF3)
    else:
        wire.mismatch = True
    with pytest.raises(HomeAssistantError):
        await c.async_set_sharp_fan_mode("low")
    assert sharp_value(c.data, "mode") != "low"
    assert c.data[0xA0] == "auto"
    api._waiting[HOST] = 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key,value",
    [("plasmacluster", True), ("led", "dim"), ("mode", "unknown"), ("child-lock", 1)],
)
async def test_unverified_commands_do_not_reach_wire(device, key, value):
    make, wire, _, _, _ = device
    c = make()
    await c.startup()
    wire.frames.clear()
    with pytest.raises(HomeAssistantError):
        await c.async_set_sharp_setting(key, value)
    assert wire.frames == []


@pytest.mark.asyncio
async def test_real_entities_share_coordinator_and_reject_invalid_data(device):
    make, _, _, _, config = device
    c = make()
    await c.startup()
    c.data = await c._instance.update([0xF1, 0xF2, 0xF3])
    c.last_update_success = True
    for key, cls, expected in [
        ("temperature", sensor.SharpSensor, 30),
        ("humidity", sensor.SharpSensor, 43),
        ("pm25", sensor.SharpSensor, 18),
        ("plasmacluster", binary_sensor.SharpPlasmacluster, True),
        ("led", switch.SharpSwitch, True),
        ("child-lock", switch.SharpSwitch, False),
    ]:
        entity = cls(c, config, key)
        assert entity.unique_id == f"synthetic-object-1-sharp-{key}"
        assert entity.available and entity.sharp_state == expected
        if cls is sensor.SharpSensor:
            assert entity.native_value == expected
            assert entity.state_class == "measurement"
        else:
            assert entity.is_on is expected
        epc = SHARP_FIELDS[key][0]
        saved, c.data[epc] = c.data[epc], b"short"
        assert not entity.available and entity.sharp_state is None
        c.data[epc] = saved
        c.last_update_success = False
        assert not entity.available
        c.last_update_success = True
    assert not hasattr(binary_sensor.SharpPlasmacluster, "async_turn_on")
    fan = EchonetFan(c, config)
    select = EchonetSelect(c, config, {}, 0xA0)
    assert fan.preset_modes == select.options == list(SHARP_MODES)
    for option in SHARP_MODES:
        await select.async_select_option(option)
        assert fan.preset_mode == select.current_option == option
    await fan.async_set_preset_mode("low")
    assert fan.preset_mode == select.current_option == "low"
    c._object_product_code = None
    assert fan.preset_mode == select.current_option == c.data[0xA0]


@pytest.mark.parametrize("key", [*SHARP_FIELDS, "mode"])
@pytest.mark.parametrize("raw", [None, b"", bytes(26), bytes(41), "00", 0, []])
def test_malformed_fields_are_unknown(key, raw):
    epc = 0xF3 if key == "mode" else SHARP_FIELDS[key][0]
    assert sharp_value({epc: raw}, key) is None


@pytest.mark.parametrize(
    "key,offset,size,readings",
    [
        (
            "temperature",
            3,
            1,
            [
                (0, 0),
                (30, 30),
                (50, 50),
                (51, None),
                (127, None),
                (128, None),
                (255, None),
            ],
        ),
        (
            "humidity",
            4,
            1,
            [(0, None), (6, None), (7, 7), (43, 43), (98, 98), (99, None), (255, None)],
        ),
        (
            "pm25",
            27,
            2,
            [
                (0, None),
                (1, 1),
                (256, 256),
                (499, 499),
                (500, None),
                (1023, None),
                (0x8001, None),
                (0x0401, 1),
                (0xFFFF, None),
            ],
        ),
    ],
)
def test_sensor_ranges_and_sentinels(key, offset, size, readings):
    raw = bytearray(40)
    for encoded, expected in readings:
        raw[offset : offset + size] = encoded.to_bytes(size, "big")
        assert sharp_value({0xF1: bytes(raw)}, key) == expected


@pytest.mark.parametrize(
    "key,epc,size,offset,on",
    [
        ("led", 0xF3, 27, 26, 0xF0),
        ("child-lock", 0xF3, 27, 18, 0xFF),
        ("plasmacluster", 0xF2, 40, 25, 0xFF),
    ],
)
def test_binary_values_and_set_payload_are_not_inferred(key, epc, size, offset, on):
    raw = bytearray(size)
    for encoded, expected in [(0, False), (on, True), (0x10, None)]:
        raw[offset] = encoded
        assert sharp_value({epc: bytes(raw)}, key) is expected
    if epc == 0xF3:
        raw[0] = 1
        assert sharp_value({epc: bytes(raw)}, key) is None


@pytest.mark.asyncio
async def test_platform_registration_and_property_map_gates(device, monkeypatch):
    from unittest.mock import MagicMock

    make, _, _, hass, config = device
    c = make()
    await c.startup()
    c.data = await c._instance.update([0xF1, 0xF2, 0xF3])
    hass.data["echonetlite"][config.entry_id] = [
        {"echonetlite": c, "instance": c._instance_data}
    ]
    monkeypatch.setattr(
        sensor.entity_platform, "async_get_current_platform", MagicMock()
    )
    for platform, cls, count in [
        (sensor, sensor.SharpSensor, 3),
        (binary_sensor, binary_sensor.SharpPlasmacluster, 1),
        (switch, switch.SharpSwitch, 2),
    ]:
        added = []
        await platform.async_setup_entry(
            hass, config, lambda entities, *_: added.extend(entities)
        )
        assert len([entity for entity in added if isinstance(entity, cls)]) == count
        assert not any(
            isinstance(entity, sensor.EchonetSensor)
            and entity._code in (0xF1, 0xF2, 0xF3)
            for entity in added
        )
    c._getPropertyMap = [0x80, 0xA0]
    c._setPropertyMap = [0x80, 0xA0]
    for platform, cls in [
        (sensor, sensor.SharpSensor),
        (binary_sensor, binary_sensor.SharpPlasmacluster),
        (switch, switch.SharpSwitch),
    ]:
        added = []
        await platform.async_setup_entry(
            hass, config, lambda entities, *_: added.extend(entities)
        )
        assert not any(isinstance(entity, cls) for entity in added)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["get", "set"])
async def test_missing_f3_capability_hides_preset_controls(device, missing):
    make, _, _, hass, config = device
    c = make()
    await c.startup()
    getattr(c, f"_{missing}PropertyMap").remove(0xF3)
    fan = EchonetFan(c, config)
    assert not fan.supported_features & FanEntityFeature.PRESET_MODE
    hass.data["echonetlite"][config.entry_id] = [
        {"echonetlite": c, "instance": c._instance_data}
    ]
    added = []
    await select.async_setup_entry(
        hass, config, lambda entities, *_: added.extend(entities)
    )
    assert not any(entity._code == 0xA0 for entity in added)
