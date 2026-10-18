#!/usr/bin/env bash
# Install the plug-in into the GIMP 3 profiles of the current user.
#
# Usage: scripts/install.sh
#
# Every GIMP 3 profile found is updated: GIMP 3.0 and 3.2 keep separate
# ones (GIMP/3.0, GIMP/3.2), as does the Flatpak GIMP. Set GIMP_PLUGINS to
# a plug-ins folder to install there instead.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="gimp-8bfhost-bridge"

profiles() {
  local base
  case "$(uname -s)" in
    Darwin) set -- "$HOME/Library/Application Support/GIMP" ;;
    MINGW* | MSYS* | CYGWIN*) set -- "${APPDATA:-$HOME/AppData/Roaming}/GIMP" ;;
    *)
      set -- "${XDG_CONFIG_HOME:-$HOME/.config}/GIMP" \
        "$HOME/.var/app/org.gimp.GIMP/config/GIMP"
      ;;
  esac
  for base in "$@"; do
    for profile in "$base"/3.*; do
      [ -d "$profile" ] && echo "$profile/plug-ins"
    done
  done
}

targets=()
if [ -n "${GIMP_PLUGINS:-}" ]; then
  targets=("$GIMP_PLUGINS")
else
  while IFS= read -r target; do
    targets+=("$target")
  done < <(profiles)
fi

if [ ${#targets[@]} -eq 0 ]; then
  echo "No GIMP 3 profile found. Start GIMP 3 once so it creates one, or set GIMP_PLUGINS" >&2
  echo "to the plug-ins folder listed under Edit > Preferences > Folders > Plug-ins." >&2
  exit 1
fi

for target in "${targets[@]}"; do
  mkdir -p "$target"
  rm -rf "${target:?}/$NAME"
  cp -r "$ROOT/$NAME" "$target/"
  find "$target/$NAME" -name __pycache__ -type d -prune -exec rm -rf {} +
  chmod +x "$target/$NAME/$NAME.py"
  echo "Installed to $target/$NAME"
done
echo "Restart GIMP and find the filters under Filters > Photoshop Filters (8bf)."
