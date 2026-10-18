#!/usr/bin/env bash
# Run gimp-8bfhost-bridge inside a real, headless GIMP 3 with a throwaway profile.
#
# Needs: GIMP 3's gimp-console, a C compiler and a dynamically linked
# 8bf-host in $EIGHTBF_HOST (release builds for Linux are static and cannot
# load native test filters). Your own GIMP and 8bf-host settings are not
# touched: GIMP3_DIRECTORY, XDG_CACHE_HOME and the 8bf-host config point
# into a temporary directory for the run.
#
#   GIMP_CONSOLE   the gimp-console to run (default: the first GIMP 3 found)
#   GIMP_PYTHON    a Python 3 with GIMP's GObject bindings, for GIMPs whose
#                  own Python is not the python3 on PATH (default: the one
#                  GIMP's bundled Python plug-ins use)
set -euo pipefail

: "${EIGHTBF_HOST:?set EIGHTBF_HOST to a dynamically linked 8bf-host (cargo build)}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAME="gimp-8bfhost-bridge"

find_gimp() {
  local candidate
  for candidate in "${GIMP_CONSOLE:-}" gimp-console-3.2 gimp-console-3.0 gimp-console-3 gimp-console; do
    [ -n "$candidate" ] || continue
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" --version 2>/dev/null | grep -q 'version 3\.'; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

if ! GIMP="$(find_gimp)"; then
  echo "No GIMP 3 gimp-console found; set GIMP_CONSOLE." >&2
  exit 2
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/$NAME-smoke.XXXXXX")"
[ -n "${KEEP_WORK:-}" ] || trap 'rm -rf "$WORK"' EXIT
PROFILE="$WORK/gimp"
PLUGINS="$WORK/plugins"
mkdir -p "$PROFILE/plug-ins" "$PROFILE/interpreters" "$PROFILE/8bfhost-bridge" "$PLUGINS" "$WORK/cache"

cp -r "$ROOT/$NAME" "$PROFILE/plug-ins/"
find "$PROFILE/plug-ins" -name __pycache__ -type d -prune -exec rm -rf {} +

# GIMP runs Python plug-ins through their #! line, "/usr/bin/env python3".
# Packages that ship their own Python (Nix, Flatpak, Windows, macOS) point
# that at it through an interpreter file; do the same for this profile.
GIMP_PYTHON="${GIMP_PYTHON:-}"
if [ -z "$GIMP_PYTHON" ]; then
  prefix="$(dirname "$(dirname "$(readlink -f "$GIMP")")")"
  eval_plugin="$(ls "$prefix"/lib*/gimp/3.0/plug-ins/python-eval/python-eval.py 2>/dev/null | head -1 || true)"
  if [ -n "$eval_plugin" ]; then
    shebang="$(head -1 "$eval_plugin")"
    case "$shebang" in
      "#!/usr/bin/env"*) ;;
      "#!"*) GIMP_PYTHON="${shebang#\#!}" ;;
    esac
  fi
fi
if [ -n "$GIMP_PYTHON" ]; then
  printf 'python3=%s\n/usr/bin/env python3=%s\n' "$GIMP_PYTHON" "$GIMP_PYTHON" \
    >"$PROFILE/interpreters/smoke.interp"
fi

for name in Invert Error; do
  library="$PLUGINS/$(echo "$name" | tr '[:upper:]' '[:lower:]').so"
  "${CC:-cc}" -shared -fPIC -O1 -o "$library" "$ROOT/tests/fixtures/testfilter.c"
  PYTHONPATH="$ROOT/tests" python3 -c '
import sys
from fixture_pipl import pipl_sidecar

with open(sys.argv[1], "wb") as handle:
    handle.write(pipl_sidecar(sys.argv[2], "Smoke Tests", sys.argv[2] + "Main"))
' "$library.pipl" "$name"
done

EIGHTBF_HOST="$(realpath "$EIGHTBF_HOST")"
python3 - "$PROFILE/8bfhost-bridge/settings.json" "$EIGHTBF_HOST" "$PLUGINS" <<'EOF'
import json, sys

path, host, folder = sys.argv[1:]
with open(path, "w") as handle:
    json.dump({"host_path": host, "folders": [folder]}, handle)
EOF

export EIGHTBF_HOST_CONFIG="$WORK/8bf-host.toml"
touch "$EIGHTBF_HOST_CONFIG"
status=0
GIMP3_DIRECTORY="$PROFILE" XDG_CACHE_HOME="$WORK/cache" \
  timeout 300 "$GIMP" -i -n --batch-interpreter=python-fu-eval \
  -b "exec(open('$ROOT/tests/gimp_smoke/harness.py').read())" --quit \
  >"$WORK/gimp.log" 2>&1 || status=$?

grep -E '^(ok|FAIL|      ) ' "$WORK/gimp.log" || true
if grep -q '^SMOKE PASSED' "$WORK/gimp.log"; then
  echo "SMOKE PASSED ($("$GIMP" --version))"
  exit 0
fi
echo "SMOKE FAILED (gimp-console exited with $status). Last log lines:" >&2
grep -v -i 'gegl-warning' "$WORK/gimp.log" | tail -30 >&2
exit 1
