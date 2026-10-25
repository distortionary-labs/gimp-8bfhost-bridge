# Development

`devenv.nix` provides Python 3.12, pytest, a C compiler, ruff and zip. Run the tests with `make test`. They do not need GIMP.

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

## Tests against a real 8bf-host

Some tests are skipped unless `EIGHTBF_HOST` points at a dynamically linked 8bf-host, since they load a native test filter built from `tests/fixtures/testfilter.c`. Linux release builds are static and cannot load `.so` filters, so build one from an 8bf-host checkout:

```console
$ EIGHTBF_HOST=../8bf-host/target/release/8bf-host make test
```

## Headless GIMP

`make gimp-smoke` uses the same variable and also needs GIMP 3's `gimp-console`; set `GIMP_CONSOLE` if it is not on `PATH` as `gimp-console-3.2`, `gimp-console-3.0` or `gimp-console`. It installs the plug-in into a temporary GIMP profile and runs the filters through GIMP's procedure database, checking the pixels for each layer type, selections, Repeat and the settings, leaving your own profile alone. For a GIMP whose Python is not the `python3` on `PATH`, such as a Nix one, the script finds GIMP's own Python from its bundled plug-ins; `GIMP_PYTHON` overrides that.

CI cannot run this, since its runners do not package GIMP 3, so run it before a release.

## Releasing

Add the release's changes under `## Unreleased` in `CHANGELOG.md`, then, on an up-to-date `main`:

```console
$ bin/release 0.2.0
```

The script sets the version in `pyproject.toml` and `__init__.py`, dates the changelog section, runs `make lint test package`, commits, tags `v0.2.0` and pushes both.

The tag starts the [Release workflow](../.github/workflows/release.yml). It runs every CI check, including the tests against a real 8bf-host, checks that the tag matches the version, builds `gimp-8bfhost-bridge-<version>.zip` with `SHA256SUMS` and a build provenance attestation, and publishes a GitHub release with the changelog section as its notes. Versions with a suffix, such as `0.2.0-rc.1`, become pre-releases.

If the workflow fails before publishing, fix the problem, delete the tag (`git push --delete origin v0.2.0 && git tag -d v0.2.0`) and run `bin/release` again. To retry a failed run without changes, rerun it from the Actions tab.
