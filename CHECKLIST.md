# GIMP Plug-in Checklist

## Project Setup

- [ ] `devenv.nix`, `devenv.yaml`, `devenv.lock` present
- [ ] `.envrc` created (`echo "use devenv" > .envrc && direnv allow`)
- [ ] `pyproject.toml` has `version`, `license`, `description`, `requires-python` and URLs
- [ ] `pyproject.toml` and `gimp_8bfhost_bridge/__init__.py` agree on the version

## Code Standards

- [ ] Only `plugin.py` imports GIMP; every other module runs under plain Python
- [ ] Only the Python standard library and what GIMP 3 ships are imported
- [ ] Every procedure returns values, including after an unexpected exception
- [ ] Pixel writes go through the shadow buffer inside an undo group
- [ ] No 8bf-host binary and no `.8bf` file is committed

## Testing

- [ ] Unit tests in `tests/` pass without GIMP (`make test`)
- [ ] Tests against a real 8bf-host pass (`EIGHTBF_HOST=... make test`)
- [ ] The headless GIMP run passes on GIMP 3.0 and the latest 3.x (`make gimp-smoke`)
- [ ] Tried by hand in GIMP with a filter that has a dialog

## Tooling

- [ ] `ruff check` exits 0
- [ ] `ruff format --check` exits 0
- [ ] `make package` builds `dist/gimp-8bfhost-bridge-<version>.zip`

## Release

- [ ] `CHANGELOG.md` updated under a dated heading
- [ ] Version bumped in `pyproject.toml` and `__init__.py` (semver)
- [ ] `bin/release <version>` ran: it tags `v<version>` and pushes
- [ ] CI published the GitHub release with the zip and `SHA256SUMS`
