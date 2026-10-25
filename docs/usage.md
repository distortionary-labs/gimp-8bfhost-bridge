# Using the plug-in

The plug-in adds a **Photoshop Filters (8bf)** submenu under **Filters**:

- The filters, grouped by their own categories.
- **Repeat Last 8bf Filter**, which reruns the last filter with its last settings.
- **8bf Filter Settings...**, for the 8bf-host location, extra filter folders, whether results go into a copy of the layer, and the 8-bit fallback.
- **Check 8bf-host Setup...**, which shows what 8bf-host finds and why a filter cannot run.

8bf-host searches `~/8bf-plugins`, the folders in its own configuration and, on Windows and macOS, the usual Adobe plug-in folders. You can add more folders in the settings, separated as in `PATH` (`:` on Linux and macOS, `;` on Windows).

## Running a filter

Select a layer, optionally make a selection, and pick the filter. Its dialog opens with the settings you used last. When it finishes, the result replaces the layer's pixels, and Ctrl+Z restores them. If you prefer to keep the original, turn on **Put results in a new layer** in the settings; the result then goes into a copy named *Layer (Filter)* above it. With several layers selected, the filter runs on each in turn, showing its dialog once.

**Repeat Last 8bf Filter** reruns a filter with its saved settings and no dialog, even after a GIMP restart, and is a good candidate for a keyboard shortcut under **Edit > Keyboard Shortcuts**. GIMP's own **Filters > Repeat Last** and **Re-Show Last** work as well.

## What is supported

- 8-bit and 16-bit RGB and grayscale layers, with or without alpha, in linear or perceptual precision. Layer masks and channels work too.
- Selections, including anti-aliased and feathered edges. The result is blended through the selection mask, as Photoshop's "auto mask" does.
- Undo. Each filter run is a single step in GIMP's undo history.
- Filter dialogs and previews, which 8bf-host displays.
- 16-bit layers with filters that only handle 8-bit data. 8bf-host runs the filter on an 8-bit copy and keeps the original 16-bit values for any pixel the filter left unchanged. You can turn this off.

See [limitations.md](limitations.md) for what does not work.

## Scripting

Each filter is a procedure in GIMP's procedure database, `plug-in-8bfhost-filter-<filter id>`, where the id is the one `8bf-host list` prints. Run non-interactively, a filter uses its defaults, or the 8bf-host preset file passed as `preset-file`:

```python
procedure = Gimp.get_pdb().lookup_procedure("plug-in-8bfhost-filter-8c8224326f39")
config = procedure.create_config()
config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
config.set_property("image", image)
config.set_core_object_array("drawables", [layer])
config.set_property("preset-file", "/home/you/unsharp.json")
procedure.run(config)
```

## How it works

The plug-in writes the layer (and the selection, as a grayscale mask) to a temporary folder as PAM files, then runs `8bf-host run --dialog --save-preset=<preset> -- <filter id> layer.pam filtered.pam` along with the selection bounds, GIMP's foreground and background colors, and the image resolution. Repeat runs pass `--preset` instead of `--dialog`. The result goes back through the layer's shadow buffer, which is what makes the run undoable. Settings, presets and the cached filter list live in GIMP's profile folder under `8bfhost-bridge/`.

Because filters run in the 8bf-host process, a filter that crashes takes 8bf-host down with it, not GIMP.

## Troubleshooting

If the submenu has no filters, the plug-in could not find or run 8bf-host when GIMP started, or 8bf-host found no filters. **Check 8bf-host Setup...** shows which; set the location in the settings and restart GIMP. If a filter is listed as "(cannot run)", choosing it shows 8bf-host's reason. If a filter fails, the error quotes 8bf-host's log, and you can reproduce the run from a terminal (`8bf-host run --help` describes the options).

For more detail, start GIMP from a terminal with `GIMP_8BFHOST_BRIDGE_DEBUG=1` to print each 8bf-host command and its log.
