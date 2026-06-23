"""Quirks for Panasonic MKN7350S1 DistributionPanelMeter (0x0287).

The Panasonic SmartCosmo MKN7350S1 has a possible firmware bug where the UDP response
buffer overflows when 0xB7 (measured instantaneous power consumption list,
simplex) is batched with other EPCs that also return multi-byte payloads.
The device silently drops the entire batch frame rather than returning a
partial response or GET_SNA.

0xB7 responds correctly when polled individually (88 bytes for 22 channels),
so we declare it as SINGLETON_POLL to ensure it always gets its own request.
"""

QUIRKS = {
    0xB7: {
        "SINGLETON_POLL": True,
    },
}