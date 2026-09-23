"""Sharp FX-S120V air cleaner properties, verified against device readback.

Byte-identical to the FP-S42Y: F1/F2 are 40 bytes, F3 is 27, and all seven
mode codes match. Confirmed by readback with the unit offline."""

from pychonet.lib.epc_functions import _int

from ....sharp import sharp_raw

QUIRKS = {
    0xF1: {"EPC_FUNCTION": sharp_raw},
    0xF2: {"EPC_FUNCTION": sharp_raw},
    0xF3: {"EPC_FUNCTION": sharp_raw},
    0xA0: {
        "EPC_FUNCTION": [
            _int,
            {0x41: "auto", 0x31: "low", 0x35: "medium", 0x37: "high"},
        ],
    },
}
