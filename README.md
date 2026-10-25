# gimp-8bfhost-bridge

A GIMP 3 plug-in that runs Photoshop-compatible filter plug-ins (`.8bf` files) on GIMP layers. It works on Windows, macOS and Linux; on Linux, Windows filters run under Wine.

GIMP 2.10 users could load many 8bf filters with PSPI, but PSPI was never ported to GIMP 3. This plug-in fills that gap. It hands the layer and selection to [8bf-host](https://github.com/distortionary-labs/8bf-host), a separate program you install yourself, and puts the result back into your image as one undo step.

## Quick start

1. Install GIMP 3.0 or later and [8bf-host](https://github.com/distortionary-labs/8bf-host/releases).
2. Extract `gimp-8bfhost-bridge-<version>.zip` from a [release](https://github.com/distortionary-labs/gimp-8bfhost-bridge/releases) into your GIMP profile's `plug-ins` folder (**Edit > Preferences > Folders > Plug-ins**), or run `scripts/install.sh` from a checkout.
3. Restart GIMP and set the 8bf-host location under **Filters > Photoshop Filters (8bf) > 8bf Filter Settings...**.

Your filters then appear under **Filters > Photoshop Filters (8bf)**.

## Documentation

- [Installation](docs/installation.md), including Linux, Flatpak and Wine notes
- [Using the plug-in](docs/usage.md): menus, scripting, troubleshooting
- [Limitations](docs/limitations.md)
- [Development](docs/development.md): tests and releases

## Related projects

- [8bf-host](https://github.com/distortionary-labs/8bf-host), which runs the filters.
- [krita-8bfhost-bridge](https://github.com/distortionary-labs/krita-8bfhost-bridge), the same bridge for Krita.
- [comfy-8bfhost-bridge-nodes](https://github.com/distortionary-labs/comfy-8bfhost-bridge-nodes), the same bridge as ComfyUI nodes.

## License

MIT. See `LICENSE`. Photoshop is a trademark of Adobe. 8bf-host is a separate project, licensed under MIT or Apache-2.0, and is not included here.

gimp-8bfhost-bridge is maintained by [Distortionary](https://distortionary.com).
