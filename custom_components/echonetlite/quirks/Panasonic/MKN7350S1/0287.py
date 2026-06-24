"""Quirks for Panasonic MKN7350S1 DistributionPanelMeter (0x0287).

The Panasonic SmartCosmo MKN7350S1 has a possible firmware bug where the UDP response
buffer overflows when 0xB7 (measured instantaneous power consumption list,
simplex) is batched with other EPCs that also return multi-byte payloads.
The device silently drops the entire batch frame rather than returning a
partial response or GET_SNA.

Affected EPCs (both return ~118 bytes for 29 channels):
  0xB3 - Measured cumulative amount of electric power consumption list (simplex)
  0xB7 - Measured instantaneous power consumption list (simplex)

Both EPCs respond correctly when polled individually, so we declare them as
SINGLETON_POLL to ensure they always get their own dedicated request.
"""

QUIRKS = {
    0xB3: {
        "SINGLETON_POLL": True,
    },
    0xB7: {
        "SINGLETON_POLL": True,
    },
}
