# gimp-8bfhost-bridge

gimp-8bfhost-bridge is a GIMP 3 plug-in that runs Photoshop-compatible filter plug-ins (`.8bf` files) on GIMP layers. It works on Windows, macOS and Linux; on Linux, Windows filters run under Wine.

8bf plugins, originally used by Photoshop, now work with a lot of programs. It's not the newest format, but it works, and many people have commercial plugins - some of which are no longer available - which are in 8bf format. GIMP 2.10 users could load many of them with the PSPI plug-in, but PSPI was never ported to GIMP 3. This plug-in is for GIMP 3.0 and later only; it does not load in GIMP 2.10.

This plug-in requires [8bf-host](https://github.com/distortionary-labs/8bf-host), which is a separate program you install yourself. The plug-in adds the menus, hands the layer and selection to 8bf-host, and puts the result back into your image. As a side benefit, a filter that crashes takes 8bf-host down with it, not GIMP.

It is the GIMP counterpart of [krita-8bfhost-bridge](https://github.com/distortionary-labs/krita-8bfhost-bridge) and [comfy-8bfhost-bridge-nodes](https://github.com/distortionary-labs/comfy-8bfhost-bridge-nodes), and works the same way.

## What works, and what doesn't

The plug-in supports:

- 8-bit and 16-bit RGB and grayscale layers, with or without alpha, in linear or perceptual precision. Layer masks and channels work too.
- Selections, including anti-aliased and feathered edges. The result is blended through the selection mask, as Photoshop's "auto mask" does.
- Undo. Each filter run is a single step in GIMP's undo history, so Ctrl+Z reverses it.
- Filter dialogs and previews, which 8bf-host displays.
- **Repeat Last 8bf Filter**, which reruns a filter with its saved settings and no dialog, even after a GIMP restart. GIMP's own **Filters > Repeat Last** and **Re-Show Last** work as well.
- 16-bit layers with filters that only handle 8-bit data. 8bf-host runs the filter on an 8-bit copy and keeps the original 16-bit values for any pixel the filter left unchanged. You can turn this off.
- Scripts. Each filter is a procedure in GIMP's procedure database, so Python and Script-Fu scripts can run it, with a preset file if they like.

There are a few limitations worth knowing before you depend on it:

- **Color modes.** Indexed images must be converted to RGB first, and 32-bit integer and floating-point images to 8 or 16 bits (**Image > Precision**). 16-bit grayscale layers with an alpha channel are not supported yet, because 8bf-host cannot write that layout back as PAM, the image format the plug-in exchanges with it.
- **Color profiles.** Filters receive sRGB-encoded samples. GIMP converts images in linear precision, or with a profile other than sRGB, on the way out and back, which can shift colors slightly in pixels the filter did not change.
- **The menu follows 8bf-host at startup.** GIMP registers a plug-in's menu entries when it starts, so filters you add, and changes to the settings, appear in the menu after a restart.
- **Filters that cannot run** on your system are listed with "(cannot run)" after their name. GIMP has no way to grey out a single plug-in entry, so choosing one shows 8bf-host's reason instead.
- **Filter windows.** The dialog belongs to the 8bf-host process, so it may open behind GIMP's window.
- **Progress.** 8bf-host does not report progress, so GIMP's progress bar only shows that a filter is running. Cancel a filter from its own dialog.
- **About boxes.** The plug-in has no menu entry for a filter's About box; `8bf-host about <filter id>` shows it.
- **Filter compatibility.** Everything in 8bf-host's [compatibility notes](https://github.com/distortionary-labs/8bf-host/blob/main/docs/compatibility.md) applies. Some commercial filters check for Photoshop specifically and refuse to run anywhere else.

## Installation

You need GIMP 3.0 or later and 8bf-host. The plug-in uses only the Python standard library and the Python bindings that come with GIMP 3.

First, install 8bf-host from its [releases page](https://github.com/distortionary-labs/8bf-host/releases) or with `cargo install`, and check that it starts:

```console
$ 8bf-host --version
8bf-host 0.1.0
```

On Linux, Windows filters also need Wine and the Windows build of 8bf-host; see 8bf-host's [Wine guide](https://github.com/distortionary-labs/8bf-host/blob/main/docs/wine.md), and run `8bf-host doctor` to confirm the setup. It's also worth checking your filters' licenses, since some commercial filters only permit use inside particular programs.

Next, install the plug-in. GIMP looks for plug-ins in the folders listed under **Edit > Preferences > Folders > Plug-ins**. Extract `gimp-8bfhost-bridge-<version>.zip` from a release into the one in your own profile, so that you end up with `plug-ins/gimp-8bfhost-bridge/gimp-8bfhost-bridge.py`, and restart GIMP. On Linux and macOS, make sure `gimp-8bfhost-bridge.py` is executable.

From a checkout, `scripts/install.sh` (or `make install`) copies the plug-in into every GIMP 3 profile it finds:

```console
$ scripts/install.sh
Installed to /home/you/.config/GIMP/3.0/plug-ins/gimp-8bfhost-bridge
Restart GIMP and find the filters under Filters > Photoshop Filters (8bf).
```

The script knows the Linux, Flatpak, macOS and Windows (Git Bash) profile locations. GIMP 3.0 and 3.2 keep separate profiles, and the script updates each one. Set `GIMP_PLUGINS` to a plug-ins folder to install somewhere else. `make package` builds the release zip into `dist/`.

On Linux, GIMP runs the plug-in with the `python3` on its `PATH`, which needs GIMP's GObject bindings. Distribution packages of GIMP 3 usually arrange that, since GIMP's own Python plug-ins need the same; the Flatpak and the Windows and macOS installers bring their own Python.

The Flatpak GIMP runs plug-ins inside its sandbox, so 8bf-host can only start programs the sandbox can see. A static 8bf-host in your home folder should work, but Wine installed on your system is usually not visible there, so for Windows filters on Linux a GIMP from your distribution is the simpler choice.

Finally, open **Filters > Photoshop Filters (8bf) > 8bf Filter Settings...** and set the location of 8bf-host. If you leave it empty, the plug-in uses the `EIGHTBF_HOST` environment variable, then searches `PATH`, `~/.cargo/bin` and `~/.local/bin`. Of course, GIMP started from a desktop menu often has a shorter `PATH` than your terminal, so setting it explicitly is more reliable. **Check 8bf-host Setup...** runs `8bf-host doctor` and shows the result.

## Using the plug-in

The plug-in adds a **Photoshop Filters (8bf)** submenu under **Filters**:

- The filters, grouped by their own categories.
- **Repeat Last 8bf Filter**, which reruns the last filter with its last settings.
- **8bf Filter Settings...**, for the 8bf-host location, extra filter folders, whether results go into a copy of the layer, and the 8-bit fallback.
- **Check 8bf-host Setup...**, which shows what 8bf-host finds and why a filter cannot run.

8bf-host searches `~/8bf-plugins`, the folders in its own configuration and, on Windows and macOS, the usual Adobe plug-in folders. You can add more folders in the settings, separated as in `PATH` (`:` on Linux and macOS, `;` on Windows).

To run a filter, select a layer, optionally make a selection, and pick the filter. Its dialog opens with the settings you used last. When it finishes, the result replaces the layer's pixels, and Ctrl+Z restores them. If you prefer to keep the original, turn on **Put results in a new layer** in the settings; the result then goes into a copy named *Layer (Filter)* above it. With several layers selected, the filter runs on each in turn, showing its dialog once.

**Repeat Last 8bf Filter** is a good candidate for a keyboard shortcut under **Edit > Keyboard Shortcuts**.

Scripts can run a filter by its procedure name, `plug-in-8bfhost-filter-<filter id>`, where the id is the one `8bf-host list` prints. Run non-interactively, a filter uses its defaults, or the 8bf-host preset file passed as `preset-file`:

```python
procedure = Gimp.get_pdb().lookup_procedure("plug-in-8bfhost-filter-8c8224326f39")
config = procedure.create_config()
config.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
config.set_property("image", image)
config.set_core_object_array("drawables", [layer])
config.set_property("preset-file", "/home/you/unsharp.json")
procedure.run(config)
```

Behind the scenes, the plug-in writes the layer (and the selection, as a grayscale mask) to a temporary folder as PAM files, then runs `8bf-host run --dialog --save-preset=<preset> -- <filter id> layer.pam filtered.pam` along with the selection bounds, GIMP's foreground and background colors, and the image resolution. Repeat runs pass `--preset` instead of `--dialog`. The result goes back through the layer's shadow buffer, which is what makes the run undoable. Settings, presets and the cached filter list live in GIMP's profile folder under `8bfhost-bridge/`.

## Troubleshooting

If the submenu has no filters, the plug-in could not find or run 8bf-host when GIMP started, or 8bf-host found no filters. **Check 8bf-host Setup...** shows which; set the location in the settings and restart GIMP. If a filter is listed as "(cannot run)", choosing it shows 8bf-host's reason. If a filter fails, the error quotes 8bf-host's log, and you can reproduce the run from a terminal (`8bf-host run --help` describes the options).

For more detail, start GIMP from a terminal with `GIMP_8BFHOST_BRIDGE_DEBUG=1` to print each 8bf-host command and its log.

## Project layout

```text
gimp-8bfhost-bridge/            The folder that goes into GIMP's plug-ins folder
  gimp-8bfhost-bridge.py        GIMP's entry point
  gimp_8bfhost_bridge/
    plugin.py                   Procedures, menus and the glue; the only module that imports GIMP
    bridge.py                   One filter run: files, settings choice, command, result
    host.py                     Finding 8bf-host, building its commands, running it
    images.py                   Pixel layouts and PAM files
    catalog.py                  The filter list from `8bf-host list --json`
    settings.py                 Settings, paths and per-filter presets
tests/
  fixtures/testfilter.c         A tiny filter for the tests, built natively
  gimp_smoke/                   Drives the plug-in in a real, headless GIMP 3
```

## Development

`devenv.nix` provides Python 3.12, pytest, a C compiler and ruff. Run the tests with `make test`. They do not need GIMP.

Some tests are skipped unless `EIGHTBF_HOST` points at a dynamically linked 8bf-host, since they load a native test filter built from `tests/fixtures/testfilter.c`. Linux release builds are static and cannot load `.so` filters, so we build one from an 8bf-host checkout:

```console
$ EIGHTBF_HOST=../8bf-host/target/release/8bf-host make test
```

`make gimp-smoke` uses the same variable and also needs GIMP 3's `gimp-console`; set `GIMP_CONSOLE` if it is not on `PATH` as `gimp-console-3.2`, `gimp-console-3.0` or `gimp-console`. It installs the plug-in into a temporary GIMP profile and runs the filters through GIMP's procedure database, checking the pixels for each layer type, selections, Repeat and the settings, leaving your own profile alone. For a GIMP whose Python is not the `python3` on `PATH`, such as a Nix one, the script finds GIMP's own Python from its bundled plug-ins; `GIMP_PYTHON` overrides that.

## Related projects

- [8bf-host](https://github.com/distortionary-labs/8bf-host), which runs the filters.
- [krita-8bfhost-bridge](https://github.com/distortionary-labs/krita-8bfhost-bridge), the same bridge for Krita.
- [comfy-8bfhost-bridge-nodes](https://github.com/distortionary-labs/comfy-8bfhost-bridge-nodes), the same bridge as ComfyUI nodes.

## License

MIT. See `LICENSE`. Photoshop is a trademark of Adobe.

8bf-host is a separate project, licensed under MIT or Apache-2.0. It is not included here; install it yourself as described above.

gimp-8bfhost-bridge is maintained by [Distortionary](https://distortionary.com).
