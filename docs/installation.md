# Installation

You need GIMP 3.0 or later and [8bf-host](https://github.com/distortionary-labs/8bf-host). The plug-in uses only the Python standard library and the Python bindings that come with GIMP 3. It does not load in GIMP 2.10.

## 1. Install 8bf-host

Install 8bf-host from its [releases page](https://github.com/distortionary-labs/8bf-host/releases) or with `cargo install`, and check that it starts:

```console
$ 8bf-host --version
8bf-host 0.1.0
```

On Linux, Windows filters also need Wine and the Windows build of 8bf-host; see 8bf-host's [Wine guide](https://github.com/distortionary-labs/8bf-host/blob/main/docs/wine.md), and run `8bf-host doctor` to confirm the setup. It's also worth checking your filters' licenses, since some commercial filters only permit use inside particular programs.

## 2. Install the plug-in

GIMP looks for plug-ins in the folders listed under **Edit > Preferences > Folders > Plug-ins**. Extract `gimp-8bfhost-bridge-<version>.zip` from a [release](https://github.com/distortionary-labs/gimp-8bfhost-bridge/releases) into the one in your own profile, so that you end up with `plug-ins/gimp-8bfhost-bridge/gimp-8bfhost-bridge.py`, and restart GIMP. On Linux and macOS, make sure `gimp-8bfhost-bridge.py` is executable.

From a checkout, `scripts/install.sh` (or `make install`) copies the plug-in into every GIMP 3 profile it finds:

```console
$ scripts/install.sh
Installed to /home/you/.config/GIMP/3.0/plug-ins/gimp-8bfhost-bridge
Restart GIMP and find the filters under Filters > Photoshop Filters (8bf).
```

The script knows the Linux, Flatpak, macOS and Windows (Git Bash) profile locations. GIMP 3.0 and 3.2 keep separate profiles, and the script updates each one. Set `GIMP_PLUGINS` to a plug-ins folder to install somewhere else.

### Linux notes

GIMP runs the plug-in with the `python3` on its `PATH`, which needs GIMP's GObject bindings. Distribution packages of GIMP 3 usually arrange that, since GIMP's own Python plug-ins need the same; the Flatpak and the Windows and macOS installers bring their own Python.

The Flatpak GIMP runs plug-ins inside its sandbox, so 8bf-host can only start programs the sandbox can see. A static 8bf-host in your home folder should work, but Wine installed on your system is usually not visible there, so for Windows filters on Linux a GIMP from your distribution is the simpler choice.

## 3. Point the plug-in at 8bf-host

Open **Filters > Photoshop Filters (8bf) > 8bf Filter Settings...** and set the location of 8bf-host. If you leave it empty, the plug-in uses the `EIGHTBF_HOST` environment variable, then searches `PATH`, `~/.cargo/bin` and `~/.local/bin`. GIMP started from a desktop menu often has a shorter `PATH` than your terminal, so setting it explicitly is more reliable. **Check 8bf-host Setup...** runs `8bf-host doctor` and shows the result.
