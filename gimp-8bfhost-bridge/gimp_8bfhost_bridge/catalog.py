"""The filters 8bf-host found, as the menus use them.

GIMP registers a plug-in's procedures when it starts, so each filter
becomes one procedure, named after its 8bf-host id. The list is also kept
in a small cache file, so running a filter does not have to ask 8bf-host
for the whole list again.
"""

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import List, Optional

PROCEDURE_PREFIX = "plug-in-8bfhost-filter-"
MENU_ROOT = "<Image>/Filters/Photoshop Filters (8bf)"


@dataclass
class Filter:
    id: str
    name: str
    category: str
    path: str = ""
    archs: List[str] = field(default_factory=list)
    modes: List[str] = field(default_factory=list)
    has_about_box: bool = False
    # Where 8bf-host would run it, or None with ``problem`` saying why it cannot.
    runs: Optional[str] = None
    problem: Optional[str] = None

    @classmethod
    def from_json(cls, payload):
        return cls(
            id=str(payload["id"]),
            name=str(payload.get("name", "")) or str(payload["id"]),
            category=str(payload.get("category", "")) or "Other",
            path=str(payload.get("path", "")),
            archs=[str(arch) for arch in payload.get("archs") or []],
            modes=[str(mode) for mode in payload.get("modes") or []],
            has_about_box=bool(payload.get("has_about_box")),
            runs=payload.get("runs"),
            problem=payload.get("problem"),
        )

    @property
    def runnable(self):
        return self.runs is not None

    @property
    def procedure_name(self):
        return procedure_name(self.id)

    @property
    def menu_path(self):
        return "%s/%s" % (MENU_ROOT, menu_text(self.category))

    @property
    def menu_label(self):
        label = menu_text(self.name)
        return label + "..." if self.runnable else label + " (cannot run)"


def procedure_name(filter_id):
    """A PDB procedure name for a filter id.

    PDB names allow lowercase letters, digits and dashes. 8bf-host's ids
    are short lowercase hex strings, so this only guards against surprises.
    """
    return PROCEDURE_PREFIX + re.sub(r"[^a-z0-9-]", "-", filter_id.lower())


def menu_text(text):
    """Text for a menu label or path element.

    GIMP reads "_" as a mnemonic marker and "/" as a submenu separator.
    """
    return text.replace("_", "__").replace("/", "-").strip() or "Other"


class Catalog:
    def __init__(self):
        self.filters = []
        self.problems = []
        # Why the list could not be read at all (8bf-host missing or failing).
        self.error = None

    def load(self, filters, problems=()):
        entries = [Filter.from_json(payload) for payload in filters if payload.get("id")]
        entries.sort(key=lambda e: (e.category.lower(), e.name.lower()))
        # Two filters with one id would make two procedures with one name.
        seen = set()
        self.filters = []
        for entry in entries:
            if entry.procedure_name not in seen:
                seen.add(entry.procedure_name)
                self.filters.append(entry)
        self.problems = [(str(p.get("path", "")), str(p.get("message", ""))) for p in problems]
        self.error = None

    def fail(self, message):
        self.filters = []
        self.problems = []
        self.error = message

    def find(self, filter_id):
        for entry in self.filters:
            if entry.id == filter_id:
                return entry
        return None

    def find_procedure(self, name):
        for entry in self.filters:
            if entry.procedure_name == name:
                return entry
        return None

    def by_category(self):
        groups = {}
        for entry in self.filters:
            groups.setdefault(entry.category, []).append(entry)
        return groups

    def to_json(self):
        return {
            "filters": [asdict(entry) for entry in self.filters],
            "problems": [{"path": path, "message": message} for path, message in self.problems],
            "error": self.error,
        }

    def save(self, path):
        """Write the catalog to ``path``, replacing it in one step."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(self.to_json(), handle, indent=1)
        os.replace(temporary, path)

    @classmethod
    def read(cls, path):
        """Read a saved catalog, or return None when there is none or it is unreadable."""
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("filters"), list):
            return None
        catalog = cls()
        filters = [entry for entry in payload["filters"] if isinstance(entry, dict)]
        problems = [entry for entry in payload.get("problems") or [] if isinstance(entry, dict)]
        catalog.load(filters, problems)
        catalog.error = payload.get("error") if isinstance(payload.get("error"), str) else None
        return catalog
