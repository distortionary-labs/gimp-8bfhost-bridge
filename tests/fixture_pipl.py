"""PiPL sidecars for the native test filter.

8bf-host reads a native library's filter description from a ``.pipl``
file next to it. Kept apart from conftest.py so tests/gimp_smoke/run.sh can
use it without pytest.
"""

import struct


def _fourcc(text):
    return struct.unpack(">I", text.encode("ascii"))[0]


def _pascal(text):
    raw = text.encode("latin-1")
    return bytes([len(raw)]) + raw


def pipl_sidecar(name, category, entry):
    """A PiPL resource describing one filter, for a native library's .pipl file."""
    properties = [
        ("kind", struct.pack("<I", _fourcc("8BFM"))),
        ("name", _pascal(name)),
        ("catg", _pascal(category)),
        ("8664", entry.encode("ascii") + b"\0"),
    ]
    out = bytearray(struct.pack("<hii", 1, 0, len(properties)))
    for key, value in properties:
        out += struct.pack("<IIii", _fourcc("8BIM"), _fourcc(key), 0, len(value))
        out += value + b"\0" * (((len(value) + 3) & ~3) - len(value))
    return bytes(out)
