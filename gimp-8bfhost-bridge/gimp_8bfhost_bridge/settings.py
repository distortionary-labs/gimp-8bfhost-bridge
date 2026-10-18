"""User settings and stored filter presets.

Settings live in a small JSON file in GIMP's profile folder, next to the
presets and the cached filter list:

    <GIMP profile>/8bfhost-bridge/settings.json
    <GIMP profile>/8bfhost-bridge/filters.json
    <GIMP profile>/8bfhost-bridge/presets/<filter id>.json

Every key is optional. A missing or unreadable file means the defaults.
"""

import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field, fields
from typing import List

FOLDER_NAME = "8bfhost-bridge"
SETTINGS_NAME = "settings.json"
CATALOG_NAME = "filters.json"
PRESETS_NAME = "presets"


@dataclass
class Settings:
    # The 8bf-host program. Empty means "look for it".
    host_path: str = ""
    # Extra filter folders. 8bf-host adds the usual Adobe folders and its own
    # configured ones by itself.
    folders: List[str] = field(default_factory=list)
    # GIMP can undo a filter run, so results go into the layer itself unless
    # this asks for a copy of the layer.
    new_layer: bool = False
    allow_8bit_fallback: bool = True
    # The id of the filter Repeat Last 8bf Filter runs.
    last_filter: str = ""

    def to_dict(self):
        return asdict(self)


class Paths:
    """Where the plug-in keeps its files inside GIMP's profile folder."""

    def __init__(self, gimp_directory):
        self.directory = os.path.join(gimp_directory, FOLDER_NAME)
        self.settings = os.path.join(self.directory, SETTINGS_NAME)
        self.catalog = os.path.join(self.directory, CATALOG_NAME)
        self.presets = os.path.join(self.directory, PRESETS_NAME)


def _boolean(raw):
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def load(path):
    """Read settings from ``path``, falling back to defaults key by key."""
    settings = Settings()
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return settings
    except (OSError, ValueError) as exc:
        sys.stderr.write("gimp-8bfhost-bridge: ignoring %s: %s\n" % (path, exc))
        return settings
    if not isinstance(payload, dict):
        sys.stderr.write("gimp-8bfhost-bridge: ignoring %s: not a JSON object\n" % path)
        return settings
    for item in fields(Settings):
        raw = payload.get(item.name)
        if raw is None:
            continue
        current = getattr(settings, item.name)
        if isinstance(current, bool):
            value = _boolean(raw)
        elif isinstance(current, list):
            if not isinstance(raw, list):
                continue
            value = [str(entry).strip() for entry in raw if str(entry).strip()]
        else:
            value = str(raw).strip()
        setattr(settings, item.name, value)
    return settings


def save(settings, path):
    """Write settings to ``path``, replacing the file in one step."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(settings.to_dict(), handle, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def parse_folders(text, separator=os.pathsep):
    """Split the folder list typed into the settings dialog.

    Folders are separated like PATH entries (":" on Linux and macOS, ";" on
    Windows) or by new lines. Leading "~" is expanded.
    """
    folders = []
    for line in str(text).splitlines():
        for part in line.split(separator):
            part = part.strip()
            if not part:
                continue
            folder = os.path.normpath(os.path.expanduser(part))
            if folder not in folders:
                folders.append(folder)
    return folders


def format_folders(folders, separator=os.pathsep):
    return separator.join(folders)


class PresetStore:
    """Where each filter's last settings live, as 8bf-host preset files.

    8bf-host writes the preset after a run (``--save-preset``) and reads it
    for the next one (``--preset``), which is what Repeat uses.
    """

    def __init__(self, directory):
        self.directory = directory

    def path(self, filter_id):
        os.makedirs(self.directory, exist_ok=True)
        return os.path.join(self.directory, preset_name(filter_id))

    def existing(self, filter_id):
        """Return the preset path when one was saved, else None."""
        path = os.path.join(self.directory, preset_name(filter_id))
        return path if os.path.isfile(path) and os.path.getsize(path) > 0 else None


def preset_name(filter_id):
    """A file name for a filter's preset, safe to use and unique per filter.

    8bf-host's ids are already safe. Anything that had to be changed gets a
    hash of the original, so two different ids never share a preset.
    """
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", filter_id)[:80]
    if safe != filter_id or not safe:
        safe += "-" + hashlib.sha256(filter_id.encode("utf-8")).hexdigest()[:12]
    return safe + ".json"
