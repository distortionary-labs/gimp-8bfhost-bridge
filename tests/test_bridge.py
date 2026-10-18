import struct

import pytest

from gimp_8bfhost_bridge import bridge, images

RGBA8 = images.Layout(4, 1, "R'G'B'A u8")
RGB16 = images.Layout(3, 2, "R'G'B' u16")


def test_interactive_runs_show_the_dialog_from_the_last_settings(tmp_path):
    assert bridge.choose_settings(bridge.INTERACTIVE) == (None, True)
    assert bridge.choose_settings(bridge.INTERACTIVE, "last.json") == ("last.json", True)


def test_last_values_replay_the_preset():
    assert bridge.choose_settings(bridge.LAST_VALUES, "last.json") == ("last.json", False)
    # A filter that never ran has nothing to replay, so it asks.
    assert bridge.choose_settings(bridge.LAST_VALUES, None) == (None, True)


def test_scripts_get_defaults_or_their_preset_file(tmp_path):
    assert bridge.choose_settings(bridge.NONINTERACTIVE, "last.json") == (None, False)
    preset = tmp_path / "mine.json"
    preset.write_text("{}")
    assert bridge.choose_settings(bridge.NONINTERACTIVE, "last.json", str(preset)) == (
        str(preset),
        False,
    )
    assert bridge.choose_settings(bridge.LAST_VALUES, "last.json", str(preset)) == (
        str(preset),
        False,
    )


def test_missing_preset_file_and_bad_run_mode(tmp_path):
    with pytest.raises(bridge.BridgeError, match="does not exist"):
        bridge.choose_settings(bridge.NONINTERACTIVE, None, str(tmp_path / "none.json"))
    with pytest.raises(bridge.BridgeError, match="Unknown run mode"):
        bridge.choose_settings("sometimes")


def test_selection_rect():
    assert bridge.selection_rect(True, 1, 2, 3, 4) == (1, 2, 3, 4)
    assert bridge.selection_rect(False, 0, 0, 3, 4) is None
    assert bridge.selection_rect(True, 0, 0, 0, 4) is None


def test_prepare_writes_layer_and_mask(tmp_path):
    pixels = bytes(range(8))
    job = bridge.prepare(
        str(tmp_path), "abc", RGBA8, 2, 1, pixels, mask=b"\xff\x80", rect=(0, 0, 2, 1)
    )
    assert images.read_pam(job.input_path) == (2, 1, 4, 1, pixels)
    assert open(job.mask_path, "rb").read() == b"P5\n2 1\n255\n\xff\x80"
    assert job.rect == (0, 0, 2, 1)
    assert job.output_path == str(tmp_path / "filtered.pam")


def test_prepare_converts_16bit_samples(tmp_path):
    pixels = struct.pack("=3H", 1, 2, 0xFFFE)
    job = bridge.prepare(str(tmp_path), "abc", RGB16, 1, 1, pixels)
    assert job.mask_path is None
    assert images.read_pam(job.input_path)[4] == struct.pack(">3H", 1, 2, 0xFFFE)


def test_prepare_checks_sizes(tmp_path):
    with pytest.raises(bridge.BridgeError, match="expected 8"):
        bridge.prepare(str(tmp_path), "abc", RGBA8, 2, 1, bytes(4))
    with pytest.raises(bridge.BridgeError, match="mask"):
        bridge.prepare(str(tmp_path), "abc", RGBA8, 2, 1, bytes(8), mask=b"\0")
    with pytest.raises(bridge.BridgeError, match="empty"):
        bridge.prepare(str(tmp_path), "abc", RGBA8, 0, 1, b"")


def test_command_passes_everything(tmp_path):
    job = bridge.prepare(
        str(tmp_path),
        "abc",
        RGBA8,
        2,
        1,
        bytes(8),
        mask=b"\xff\0",
        rect=(0, 0, 1, 1),
        foreground=(1, 2, 3),
        background=(4, 5, 6),
        resolution=300.0,
    )
    command = bridge.command(
        job, "8bf-host", ["/f"], preset="p.json", dialog=False, save_preset="s.json", fallback=False
    )
    assert command[:3] == ["8bf-host", "run", "--verbose"]
    for option in (
        "--plugin-dir=/f",
        "--preset=p.json",
        "--save-preset=s.json",
        "--mask=" + job.mask_path,
        "--rect=0,0,1,1",
        "--foreground=#010203",
        "--background=#040506",
        "--resolution=300",
        "--no-8bit-fallback",
    ):
        assert option in command
    assert "--dialog" not in command
    assert command[-4:] == ["--", "abc", job.input_path, job.output_path]


def test_read_result(tmp_path):
    job = bridge.prepare(str(tmp_path), "abc", RGB16, 1, 1, bytes(6))
    images.write_pam(job.output_path, 1, 1, 3, 2, struct.pack(">3H", 1, 2, 3))
    assert bridge.read_result(job) == struct.pack("=3H", 1, 2, 3)


def test_read_result_rejects_a_different_layout(tmp_path):
    job = bridge.prepare(str(tmp_path), "abc", RGB16, 1, 1, bytes(6))
    with pytest.raises(bridge.BridgeError, match="Could not read"):
        bridge.read_result(job)
    images.write_pam(job.output_path, 1, 1, 3, 1, bytes(3))
    with pytest.raises(bridge.BridgeError, match="3 channels of 8 bits for a 1x1 one"):
        bridge.read_result(job)
