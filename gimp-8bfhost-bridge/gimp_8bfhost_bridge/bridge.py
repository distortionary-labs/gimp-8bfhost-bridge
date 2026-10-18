"""One filter run on one drawable, without GIMP.

plugin.py reads the pixels and the selection out of GIMP and writes the
result back. Everything between those two steps lives here: writing the
files 8bf-host works on, choosing where the filter's settings come from,
building the command and checking what comes back.
"""

import os
from dataclasses import dataclass
from typing import Optional, Tuple

from . import host, images

INPUT_NAME = "layer.pam"
OUTPUT_NAME = "filtered.pam"
MASK_NAME = "selection.pgm"

# How the plug-in was asked to run, as GIMP's run modes say it.
INTERACTIVE = "interactive"
LAST_VALUES = "last-values"
NONINTERACTIVE = "noninteractive"


class BridgeError(RuntimeError):
    """The drawable cannot be filtered, or 8bf-host's output is unusable."""


@dataclass
class Job:
    filter_id: str
    layout: images.Layout
    width: int
    height: int
    input_path: str
    output_path: str
    mask_path: Optional[str] = None
    # (x, y, width, height) of the selection's bounds on the drawable, or None.
    rect: Optional[Tuple[int, int, int, int]] = None
    foreground: tuple = (0, 0, 0)
    background: tuple = (255, 255, 255)
    resolution: float = 72.0


def choose_settings(run_mode, last_preset=None, preset_file=""):
    """Return ``(preset, show dialog)`` for a run.

    - Interactive runs show the filter's dialog, starting from the last
      settings when there are any, as Photoshop does.
    - Runs with last values (Repeat, and GIMP's own Filters > Repeat Last)
      replay the last settings without the dialog. A filter that has never
      run shows its dialog instead.
    - Non-interactive runs, from scripts, use the preset file they name,
      or the filter's defaults.
    """
    preset_file = os.path.expanduser((preset_file or "").strip())
    if preset_file and not os.path.isfile(preset_file):
        raise BridgeError("The preset file %s does not exist." % preset_file)
    if run_mode == INTERACTIVE:
        return preset_file or last_preset, True
    if run_mode == LAST_VALUES:
        chosen = preset_file or last_preset
        return chosen, chosen is None
    if run_mode == NONINTERACTIVE:
        return preset_file or None, False
    raise BridgeError("Unknown run mode %r." % (run_mode,))


def selection_rect(non_empty, x, y, width, height):
    """The selection's bounds on the drawable, from ``Drawable.mask_intersect``."""
    if not non_empty or width <= 0 or height <= 0:
        return None
    return (int(x), int(y), int(width), int(height))


def prepare(directory, filter_id, layout, width, height, pixels, mask=None, rect=None, **extra):
    """Write the drawable, and the selection if any, into ``directory``.

    ``pixels`` are GEGL buffer bytes in ``layout``; ``mask`` is 8-bit
    coverage for every pixel of the drawable, or None without a selection.
    """
    if width <= 0 or height <= 0:
        raise BridgeError("The layer is empty (%dx%d)." % (width, height))
    expected = width * height * layout.bytes_per_pixel
    if len(pixels) != expected:
        raise BridgeError(
            "GIMP returned %d bytes of pixels, expected %d." % (len(pixels), expected)
        )
    job = Job(
        filter_id=filter_id,
        layout=layout,
        width=width,
        height=height,
        input_path=os.path.join(directory, INPUT_NAME),
        output_path=os.path.join(directory, OUTPUT_NAME),
        rect=rect,
        **extra,
    )
    try:
        images.write_pam(
            job.input_path,
            width,
            height,
            layout.channels,
            layout.sample_bytes,
            images.gegl_to_pam(pixels, layout.sample_bytes),
        )
        if mask is not None:
            if len(mask) != width * height:
                raise BridgeError("The selection mask does not match the layer's size.")
            job.mask_path = os.path.join(directory, MASK_NAME)
            images.write_pgm(job.mask_path, width, height, bytes(mask))
    except OSError as exc:
        raise BridgeError("Could not write the files 8bf-host works on: %s" % exc) from exc
    return job


def command(job, executable, folders, preset=None, dialog=True, save_preset=None, fallback=True):
    return host.run_command(
        executable,
        folders,
        job.filter_id,
        job.input_path,
        job.output_path,
        dialog=dialog,
        preset=preset,
        save_preset=save_preset,
        mask=job.mask_path,
        rect=job.rect,
        foreground=job.foreground,
        background=job.background,
        resolution=job.resolution,
        allow_8bit_fallback=fallback,
    )


def read_result(job):
    """Read 8bf-host's output back as GEGL buffer bytes in the job's layout."""
    try:
        width, height, channels, sample_bytes, data = images.read_pam(job.output_path)
    except (OSError, ValueError) as exc:
        raise BridgeError("Could not read the filtered image: %s" % exc) from exc
    layout = job.layout
    if (width, height, channels, sample_bytes) != (
        job.width,
        job.height,
        layout.channels,
        layout.sample_bytes,
    ):
        raise BridgeError(
            "8bf-host returned a %dx%d image with %d channels of %d bits for a %dx%d one "
            "with %d channels of %d bits."
            % (
                width,
                height,
                channels,
                8 * sample_bytes,
                job.width,
                job.height,
                layout.channels,
                8 * layout.sample_bytes,
            )
        )
    return images.pam_to_gegl(data, sample_bytes)
