"""The plug-in's commands and image files against a real 8bf-host.

Opt-in: set EIGHTBF_HOST to a dynamically linked build (``cargo build``).
These cover everything between GIMP and 8bf-host; tests/gimp_smoke covers
GIMP itself.
"""

import json
import struct

from gimp_8bfhost_bridge import bridge, host, images
from gimp_8bfhost_bridge.catalog import Catalog


def _catalog(eightbf_host, folder):
    catalog = Catalog()
    catalog.load(*host.list_filters(eightbf_host, [folder], rescan=True))
    return catalog


def _filter(eightbf_host, folder, name):
    return next(e for e in _catalog(eightbf_host, folder).filters if e.name == name)


def _run(eightbf_host, folder, job, **options):
    options.setdefault("dialog", False)
    return host.run(bridge.command(job, eightbf_host, [folder], **options))


def test_filters_are_listed(eightbf_host, filter_folder):
    catalog = _catalog(eightbf_host, filter_folder)
    assert sorted(entry.name for entry in catalog.filters) == ["Error", "Invert"]
    assert all(entry.runnable for entry in catalog.filters)
    assert all(entry.procedure_name.startswith("plug-in-8bfhost-") for entry in catalog.filters)


def test_8bit_layer_round_trip_with_preset(eightbf_host, filter_folder, tmp_path):
    invert = _filter(eightbf_host, filter_folder, "Invert")
    layout = images.Layout(4, 1, "R'G'B'A u8")
    pixels = bytes(range(24))
    job = bridge.prepare(str(tmp_path), invert.id, layout, 3, 2, pixels)
    preset = str(tmp_path / "preset.json")

    result = _run(eightbf_host, filter_folder, job, save_preset=preset)
    assert result.ok, result.message
    out = bridge.read_result(job)
    assert list(out[:4]) == [255, 254, 253, 3]
    assert json.load(open(preset))["format"] == "8bf-host-preset"

    # Repeat: replay the preset without the dialog.
    result = _run(eightbf_host, filter_folder, job, preset=preset)
    assert result.ok, result.message


def test_16bit_layer_with_feathered_selection(eightbf_host, filter_folder, tmp_path):
    invert = _filter(eightbf_host, filter_folder, "Invert")
    layout = images.Layout(4, 2, "R'G'B'A u16")
    samples = [i * 1000 + 1 for i in range(12)]
    job = bridge.prepare(
        str(tmp_path),
        invert.id,
        layout,
        3,
        1,
        struct.pack("=12H", *samples),
        mask=b"\xff\x80\x00",
        rect=(0, 0, 2, 1),
    )
    result = _run(eightbf_host, filter_folder, job)
    assert result.ok, result.message
    out = struct.unpack("=12H", bridge.read_result(job))
    # The selected pixel is inverted (through the 8-bit fallback), alpha kept.
    assert all(abs(out[i] - (65535 - samples[i])) <= 300 for i in range(3))
    assert out[3] == samples[3]
    # The half-selected pixel is blended halfway.
    for i in range(4, 7):
        halfway = (samples[i] + (65535 - samples[i])) / 2
        assert abs(out[i] - halfway) <= 600, (i, out[i], halfway)
    # The unselected pixel is bit-for-bit unchanged.
    assert list(out[8:]) == samples[8:]


def test_8bit_fallback_can_be_turned_off(eightbf_host, filter_folder, tmp_path):
    invert = _filter(eightbf_host, filter_folder, "Invert")
    layout = images.Layout(3, 2, "R'G'B' u16")
    job = bridge.prepare(str(tmp_path), invert.id, layout, 1, 1, bytes(6))
    result = _run(eightbf_host, filter_folder, job, fallback=False)
    assert result.status == "error"


def test_grayscale_layouts(eightbf_host, filter_folder, tmp_path):
    invert = _filter(eightbf_host, filter_folder, "Invert")
    for layout, pixels in (
        (images.Layout(1, 1, "Y' u8"), b"\x10"),
        (images.Layout(2, 1, "Y'A u8"), b"\x10\x80"),
        (images.Layout(1, 2, "Y' u16"), struct.pack("=H", 1000)),
    ):
        job = bridge.prepare(str(tmp_path), invert.id, layout, 1, 1, pixels)
        result = _run(eightbf_host, filter_folder, job)
        assert result.ok, (layout, result.message)
        assert len(bridge.read_result(job)) == len(pixels)


def test_filter_errors_come_back_as_messages(eightbf_host, filter_folder, tmp_path):
    error = _filter(eightbf_host, filter_folder, "Error")
    job = bridge.prepare(str(tmp_path), error.id, images.Layout(4, 1, "R'G'B'A u8"), 1, 1, bytes(4))
    result = _run(eightbf_host, filter_folder, job)
    assert result.status == "error"
    assert "failed on purpose" in result.message


def test_doctor_runs(eightbf_host, filter_folder):
    result = host.run(host.doctor_command(eightbf_host, [filter_folder]), timeout=60)
    assert result.status in ("ok", "error")
    assert (result.stdout + "\n".join(result.log)).strip()
