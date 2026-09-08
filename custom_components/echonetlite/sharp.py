"""Sharp FPS42Y proprietary fields and commands, verified against device readback."""

SHARP_MODES = {
    "auto": 0x20,
    "low": 0x14,
    "medium": 0x15,
    "high": 0x16,
    "sleep": 0x11,
    "pollen": 0x13,
    "anti_dust": 0x40,
}
SHARP_FIELDS = {
    "temperature": (0xF1, "Temperature", "mdi:thermometer"),
    "humidity": (0xF1, "Humidity", "mdi:water-percent"),
    "pm25": (0xF1, "PM2.5", "mdi:air-filter"),
    "plasmacluster": (0xF2, "Plasmacluster", "mdi:creation"),
    "led": (0xF3, "LED", "mdi:led-on"),
    "child-lock": (0xF3, "Child lock", "mdi:lock"),
}


def sharp_raw(value):
    """Keep proprietary bytes for shared polling; reject unexpected types."""
    return value if isinstance(value, bytes) else None


def sharp_value(data, key):
    """Decode a proven field; malformed, unsupported and sentinel data are None."""
    epc = 0xF3 if key == "mode" else SHARP_FIELDS[key][0]
    raw = data.get(epc)
    # This model has 40-byte F1/F2 and 27-byte F3. Never accept a short
    # response or a SET command (nonzero F3 mask) as reported state.
    if not isinstance(raw, bytes) or len(raw) != (27 if epc == 0xF3 else 40):
        return None
    if epc == 0xF3 and raw[:4] != bytes(4):
        return None
    if key == "mode":
        return next(
            (name for name, code in SHARP_MODES.items() if code == raw[4]), None
        )
    if key == "temperature":
        value = int.from_bytes(raw[3:4], "big", signed=True)
        # Official app clips <=-1 and >=51 rather than showing exact data.
        return value if 0 <= value <= 50 else None
    if key == "humidity":
        # App floor/ceiling readings are not precise measured humidity.
        return raw[4] if 6 < raw[4] < 99 else None
    if key == "pm25":
        word = int.from_bytes(raw[27:29], "big")
        value = word & 0x03FF
        return value if not word & 0x8000 and 0 < value < 500 else None
    offset, on = {
        "plasmacluster": (25, 0xFF),
        "led": (26, 0xF0),
        "child-lock": (18, 0xFF),
    }[key]
    return {0: False, on: True}.get(raw[offset])


def sharp_command(key, value):
    """Build a fresh narrow command, never replay a GET or unknown field."""
    payload = bytearray(27)
    if key == "mode" and value in SHARP_MODES:
        payload[:4] = bytes.fromhex("01010000")
        payload[4] = SHARP_MODES[value]
    elif key in ("led", "child-lock") and type(value) is bool:
        mask, offset, on = {
            "led": ("00004000", 26, 0xF0),
            "child-lock": ("00400000", 18, 0xFF),
        }[key]
        payload[:4] = bytes.fromhex(mask)
        payload[offset] = on if value else 0
    else:
        raise ValueError("Unverified Sharp command")
    return bytes(payload)
