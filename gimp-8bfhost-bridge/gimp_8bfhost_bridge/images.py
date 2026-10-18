"""GIMP drawable pixels to and from the image files 8bf-host reads and writes.

GIMP hands out pixels through GEGL buffers in a format the caller names.
For RGB and grayscale those samples are already in PAM's channel order;
only 16-bit samples need swapping, from the machine's byte order to PAM's
big-endian. Nothing here imports GIMP, so the tests run without it.
"""

import array
import sys
from dataclasses import dataclass

TUPLE_TYPES = {1: "GRAYSCALE", 2: "GRAYSCALE_ALPHA", 3: "RGB", 4: "RGB_ALPHA"}

# Gimp.Precision values come in groups of 100 per sample type: 100-199 are
# 8-bit integers, 200-299 16-bit, then 32-bit integers, half, float and
# double.
PRECISION_BITS = {1: 8, 2: 16, 3: 32, 5: 16, 6: 32, 7: 64}


class UnsupportedDrawable(ValueError):
    """The drawable's mode or precision cannot be filtered."""


@dataclass(frozen=True)
class Layout:
    channels: int
    sample_bytes: int
    # The GEGL format to read and write pixels in.
    babl_format: str

    @property
    def bytes_per_pixel(self):
        return self.channels * self.sample_bytes


def precision_bits(precision):
    """Bits per sample for a ``Gimp.Precision`` value, as an int."""
    return PRECISION_BITS.get(int(precision) // 100, 0)


def is_integer_precision(precision):
    return int(precision) // 100 in (1, 2)


def drawable_layout(base, has_alpha, precision, is_channel=False):
    """Choose how a drawable's pixels travel to 8bf-host.

    ``base`` is "rgb", "gray" or "indexed"; ``precision`` the image's
    ``Gimp.Precision``. Layers are read as sRGB-encoded samples, which is
    what Photoshop filters expect, whatever precision the image uses; GIMP
    converts linear-light images on the way out and back. Channels and layer
    masks are read as they are stored, since their values are coverage.
    """
    if base == "indexed":
        raise UnsupportedDrawable(
            "Indexed images cannot be filtered. Convert the image to RGB first "
            "(Image > Mode > RGB)."
        )
    if base not in ("rgb", "gray"):
        raise UnsupportedDrawable("This kind of drawable cannot be filtered.")
    if not is_integer_precision(precision):
        raise UnsupportedDrawable(
            "Only 8-bit and 16-bit integer images can be filtered; this one is %d-bit%s. "
            "Convert it first (Image > Precision)."
            % (precision_bits(precision), "" if int(precision) // 100 == 3 else " floating point")
        )
    sample_bytes = 2 if int(precision) // 100 == 2 else 1
    encoding = "u%d" % (8 * sample_bytes)
    if is_channel:
        return Layout(1, sample_bytes, "Y " + encoding)
    if base == "gray" and has_alpha and sample_bytes == 2:
        raise UnsupportedDrawable(
            "16-bit grayscale layers with an alpha channel are not supported yet. Remove "
            "the alpha channel (Layer > Transparency > Remove Alpha Channel), or convert "
            "the image to 8-bit or to RGB first."
        )
    channels = (3 if base == "rgb" else 1) + (1 if has_alpha else 0)
    model = ("R'G'B'" if base == "rgb" else "Y'") + ("A" if has_alpha else "")
    return Layout(channels, sample_bytes, "%s %s" % (model, encoding))


def _swap_byte_order(data):
    if sys.byteorder == "big":
        return bytes(data)
    samples = array.array("H")
    samples.frombytes(bytes(data))
    samples.byteswap()
    return samples.tobytes()


def gegl_to_pam(raw, sample_bytes):
    """Convert GEGL buffer bytes to PAM sample order."""
    data = bytes(raw)
    if sample_bytes == 2:
        data = _swap_byte_order(data)
    return data


# Swapping undoes itself, so the way back is the same conversion.
pam_to_gegl = gegl_to_pam


def write_pam(path, width, height, channels, sample_bytes, data):
    header = "P7\nWIDTH %d\nHEIGHT %d\nDEPTH %d\nMAXVAL %d\nTUPLTYPE %s\nENDHDR\n" % (
        width,
        height,
        channels,
        255 if sample_bytes == 1 else 65535,
        TUPLE_TYPES[channels],
    )
    with open(path, "wb") as handle:
        handle.write(header.encode("ascii"))
        handle.write(data)


def read_pam(path):
    """Return ``(width, height, channels, bytes per sample, data)``."""
    with open(path, "rb") as handle:
        content = handle.read()
    if not content.startswith(b"P7\n"):
        raise ValueError("%s is not a PAM file" % path)
    end = content.find(b"ENDHDR\n")
    if end < 0:
        raise ValueError("%s has no PAM header end" % path)
    fields = {}
    for line in content[3:end].split(b"\n"):
        parts = line.split(None, 1)
        if len(parts) == 2 and not parts[0].startswith(b"#"):
            fields[parts[0].decode("ascii")] = parts[1].strip()
    try:
        width = int(fields["WIDTH"])
        height = int(fields["HEIGHT"])
        channels = int(fields["DEPTH"])
        maxval = int(fields["MAXVAL"])
    except (KeyError, ValueError) as exc:
        raise ValueError("%s has an incomplete PAM header" % path) from exc
    sample_bytes = 1 if maxval < 256 else 2
    data = content[end + len(b"ENDHDR\n") :]
    expected = width * height * channels * sample_bytes
    if len(data) != expected:
        raise ValueError("%s holds %d bytes of pixels, expected %d" % (path, len(data), expected))
    return width, height, channels, sample_bytes, data


def write_pgm(path, width, height, data):
    """Write an 8-bit grayscale image, used for selection masks."""
    with open(path, "wb") as handle:
        handle.write(b"P5\n%d %d\n255\n" % (width, height))
        handle.write(data)


def encode_srgb(linear):
    """Encode a linear-light value from 0 to 1 as an 8-bit sRGB sample."""
    value = min(max(float(linear), 0.0), 1.0)
    if value <= 0.0031308:
        encoded = 12.92 * value
    else:
        encoded = 1.055 * value ** (1 / 2.4) - 0.055
    return int(round(encoded * 255))


def srgb_bytes(red, green, blue):
    """An (r, g, b) tuple of 8-bit sRGB samples from linear-light components."""
    return (encode_srgb(red), encode_srgb(green), encode_srgb(blue))
