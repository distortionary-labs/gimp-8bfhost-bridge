# Changelog

## Unreleased

Initial version.

- Runs Photoshop-compatible filter plug-ins (`.8bf`) on GIMP 3 layers through 8bf-host,
  a separate program the user installs. On Linux, Windows filters run under Wine through
  8bf-host's own configuration.
- A **Filters > Photoshop Filters (8bf)** submenu grouped by filter category, built from
  `8bf-host list` each time GIMP starts. Filters 8bf-host cannot run are marked, and
  choosing one shows the reason.
- 8-bit and 16-bit RGB and grayscale layers, with or without alpha, plus layer masks and
  channels. 16-bit grayscale with alpha, indexed, 32-bit and floating-point images are
  refused with an explanation.
- Selections, feathered ones included, blended through the mask by 8bf-host as
  Photoshop's auto mask does.
- Each run is one undo step, written through the layer's shadow buffer. Results go into
  the layer, or optionally into a copy above it.
- Repeat Last 8bf Filter, which reruns the last filter with its 8bf-host preset and no
  dialog, including after a restart. GIMP's own Repeat Last and Re-Show Last work too.
- An 8-bit fallback for 16-bit layers with 8-bit-only filters, which can be turned off.
- A settings dialog for the 8bf-host location, extra filter folders and where results
  go, and a Check 8bf-host Setup entry that shows `8bf-host doctor` and `8bf-host list`.
- Every filter is a PDB procedure that scripts can run, with an optional preset file.
