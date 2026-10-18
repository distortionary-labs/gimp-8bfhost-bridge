import struct
import sys

import pytest

from gimp_8bfhost_bridge import images

# Gimp.Precision values, as GIMP 3 defines them.
U8_LINEAR, U8_NON_LINEAR, U8_PERCEPTUAL = 100, 150, 175
U16_LINEAR, U16_NON_LINEAR = 200, 250
U32_LINEAR, HALF_LINEAR, FLOAT_LINEAR, DOUBLE_NON_LINEAR = 300, 500, 600, 750


@pytest.mark.parametrize(
    "base, alpha, precision, expected",
    [
        ("rgb", True, U8_NON_LINEAR, images.Layout(4, 1, "R'G'B'A u8")),
        ("rgb", False, U8_LINEAR, images.Layout(3, 1, "R'G'B' u8")),
        ("rgb", True, U8_PERCEPTUAL, images.Layout(4, 1, "R'G'B'A u8")),
        ("rgb", True, U16_LINEAR, images.Layout(4, 2, "R'G'B'A u16")),
        ("gray", True, U8_NON_LINEAR, images.Layout(2, 1, "Y'A u8")),
        ("gray", False, U16_NON_LINEAR, images.Layout(1, 2, "Y' u16")),
    ],
)
def test_supported_layouts(base, alpha, precision, expected):
    assert images.drawable_layout(base, alpha, precision) == expected


def test_channels_and_masks_keep_their_coverage_values():
    assert images.drawable_layout("gray", False, U8_NON_LINEAR, is_channel=True) == (
        images.Layout(1, 1, "Y u8")
    )
    assert images.drawable_layout("rgb", True, U16_LINEAR, is_channel=True) == (
        images.Layout(1, 2, "Y u16")
    )


def test_unsupported_drawables():
    with pytest.raises(images.UnsupportedDrawable, match="Indexed"):
        images.drawable_layout("indexed", False, U8_NON_LINEAR)
    with pytest.raises(images.UnsupportedDrawable, match="16-bit grayscale layers with an alpha"):
        images.drawable_layout("gray", True, U16_NON_LINEAR)
    with pytest.raises(images.UnsupportedDrawable, match="32-bit floating point"):
        images.drawable_layout("rgb", True, FLOAT_LINEAR)
    with pytest.raises(images.UnsupportedDrawable, match="16-bit floating point"):
        images.drawable_layout("rgb", True, HALF_LINEAR)
    with pytest.raises(images.UnsupportedDrawable, match="64-bit floating point"):
        images.drawable_layout("gray", False, DOUBLE_NON_LINEAR)
    with pytest.raises(images.UnsupportedDrawable, match=r"32-bit\. Convert"):
        images.drawable_layout("rgb", False, U32_LINEAR)


def test_layout_sizes():
    assert images.Layout(4, 2, "R'G'B'A u16").bytes_per_pixel == 8


def test_8bit_samples_are_left_alone():
    raw = bytes([1, 2, 3, 4])
    assert images.gegl_to_pam(raw, 1) == raw


def test_16bit_samples_become_big_endian():
    raw = struct.pack("=3H", 1, 0x1234, 0xABCD)
    assert images.gegl_to_pam(raw, 2) == struct.pack(">3H", 1, 0x1234, 0xABCD)
    assert images.pam_to_gegl(images.gegl_to_pam(raw, 2), 2) == raw


@pytest.mark.skipif(sys.byteorder != "little", reason="checks the little-endian swap")
def test_16bit_swap_on_little_endian_machines():
    assert images.gegl_to_pam(b"\x01\x02", 2) == b"\x02\x01"


def test_pam_round_trip(tmp_path):
    path = str(tmp_path / "image.pam")
    data = bytes(range(24))
    images.write_pam(path, 3, 2, 4, 1, data)
    assert open(path, "rb").read().startswith(b"P7\nWIDTH 3\nHEIGHT 2\nDEPTH 4\nMAXVAL 255\n")
    assert images.read_pam(path) == (3, 2, 4, 1, data)

    images.write_pam(path, 1, 1, 3, 2, bytes(6))
    assert b"TUPLTYPE RGB\n" in open(path, "rb").read()
    assert images.read_pam(path) == (1, 1, 3, 2, bytes(6))

    images.write_pam(path, 1, 1, 1, 1, b"\x80")
    assert b"TUPLTYPE GRAYSCALE\n" in open(path, "rb").read()


def test_pam_comments_are_skipped(tmp_path):
    path = tmp_path / "image.pam"
    path.write_bytes(
        b"P7\n# a comment\nWIDTH 1\nHEIGHT 1\nDEPTH 2\nMAXVAL 255\n"
        b"TUPLTYPE GRAYSCALE_ALPHA\nENDHDR\n\x10\x20"
    )
    assert images.read_pam(str(path)) == (1, 1, 2, 1, b"\x10\x20")


@pytest.mark.parametrize(
    "content, message",
    [
        (b"P6\n1 1\n255\n\0\0\0", "not a PAM"),
        (b"P7\nWIDTH 1\n", "no PAM header end"),
        (b"P7\nWIDTH 1\nENDHDR\n", "incomplete"),
        (b"P7\nWIDTH 1\nHEIGHT 1\nDEPTH 4\nMAXVAL 255\nENDHDR\n\0", "expected 4"),
    ],
)
def test_broken_pam_files(tmp_path, content, message):
    path = tmp_path / "broken.pam"
    path.write_bytes(content)
    with pytest.raises(ValueError, match=message):
        images.read_pam(str(path))


def test_mask_is_a_pgm(tmp_path):
    path = tmp_path / "mask.pgm"
    images.write_pgm(str(path), 2, 1, b"\xff\x00")
    assert path.read_bytes() == b"P5\n2 1\n255\n\xff\x00"


def test_srgb_encoding():
    assert images.srgb_bytes(0.0, 1.0, 0.5) == (0, 255, 188)
    assert images.encode_srgb(0.002) == 7
    assert images.encode_srgb(-1) == 0
    assert images.encode_srgb(2) == 255
