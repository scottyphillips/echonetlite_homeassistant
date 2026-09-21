"""Sharp FP-S42Y air cleaner properties, verified against device readback."""

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
