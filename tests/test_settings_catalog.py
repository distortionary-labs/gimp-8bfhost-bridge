import json
import os

from gimp_8bfhost_bridge import settings as settings_module
from gimp_8bfhost_bridge.catalog import MENU_ROOT, Catalog, Filter, menu_text, procedure_name


def test_settings_round_trip(tmp_path):
    path = str(tmp_path / "bridge" / "settings.json")
    original = settings_module.Settings(
        host_path="/opt/8bf-host",
        folders=["/a", "/b c"],
        new_layer=True,
        allow_8bit_fallback=False,
        last_filter="8c8224326f39",
    )
    settings_module.save(original, path)
    assert json.load(open(path))["folders"] == ["/a", "/b c"]
    assert settings_module.load(path) == original


def test_missing_settings_are_the_defaults(tmp_path):
    assert settings_module.load(str(tmp_path / "none.json")) == settings_module.Settings()


def test_settings_ignore_garbage(tmp_path, capsys):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"folders": "not a list", "allow_8bit_fallback": "no", "x": 1}))
    loaded = settings_module.load(str(path))
    assert loaded.allow_8bit_fallback is False
    assert loaded.folders == []

    path.write_text("{not json")
    assert settings_module.load(str(path)) == settings_module.Settings()
    path.write_text("[]")
    assert settings_module.load(str(path)) == settings_module.Settings()
    assert "ignoring" in capsys.readouterr().err


def test_paths():
    paths = settings_module.Paths(os.path.join("profile"))
    assert paths.settings == os.path.join("profile", "8bfhost-bridge", "settings.json")
    assert paths.catalog == os.path.join("profile", "8bfhost-bridge", "filters.json")
    assert paths.presets == os.path.join("profile", "8bfhost-bridge", "presets")


def test_folder_lists():
    assert settings_module.parse_folders("/a:/b c\n/d::/a", separator=":") == ["/a", "/b c", "/d"]
    assert settings_module.parse_folders(r"C:\f;D:\g", separator=";") == [r"C:\f", r"D:\g"]
    home = os.path.expanduser("~")
    assert settings_module.parse_folders("~/filters", separator=":") == [
        os.path.join(home, "filters")
    ]
    assert settings_module.format_folders(["/a", "/b"], separator=":") == "/a:/b"


def test_preset_store(tmp_path):
    store = settings_module.PresetStore(str(tmp_path / "presets"))
    assert store.existing("1a2b3c4d5e6f") is None
    path = store.path("1a2b3c4d5e6f")
    assert path == str(tmp_path / "presets" / "1a2b3c4d5e6f.json")
    open(path, "w").write("{}")
    assert store.existing("1a2b3c4d5e6f") == path
    # Never let an id name a path outside the folder, or share a preset.
    assert os.path.dirname(store.path("../x")) == str(tmp_path / "presets")
    assert settings_module.preset_name("a/b") != settings_module.preset_name("a_b")


def summary(**values):
    payload = {
        "id": "8c8224326f39",
        "name": "Invert",
        "category": "Wine",
        "path": "/f/invert.8bf",
        "format": "pe",
        "archs": ["win-x64"],
        "modes": ["rgb8", "gray8"],
        "has_about_box": True,
        "runs": "under Wine (win-x64)",
        "problem": None,
    }
    payload.update(values)
    return payload


def test_filter_from_list_json():
    entry = Filter.from_json(summary())
    assert entry.id == "8c8224326f39"
    assert entry.runnable
    assert entry.has_about_box
    assert entry.procedure_name == "plug-in-8bfhost-filter-8c8224326f39"
    assert entry.menu_path == MENU_ROOT + "/Wine"
    assert entry.menu_label == "Invert..."
    blocked = Filter.from_json(summary(runs=None, problem="needs Wine"))
    assert not blocked.runnable
    assert blocked.problem == "needs Wine"
    assert blocked.menu_label == "Invert (cannot run)"
    assert Filter.from_json(summary(category="")).category == "Other"


def test_menu_text_and_procedure_names():
    assert menu_text("Sharp_en/Plus") == "Sharp__en-Plus"
    assert menu_text("  ") == "Other"
    assert procedure_name("AB_c") == "plug-in-8bfhost-filter-ab-c"


def test_catalog():
    catalog = Catalog()
    catalog.load(
        [
            summary(id="b", name="zeta", category="Two"),
            summary(id="a", name="Alpha", category="one"),
            summary(id="c", name="beta", category="Two"),
            summary(id="C", name="same procedure as c", category="Two"),
            {"name": "no id"},
        ],
        [{"path": "/f/broken.8bf", "message": "no PiPL"}],
    )
    assert [entry.id for entry in catalog.filters] == ["a", "c", "b"]
    assert catalog.find("c").name == "beta"
    assert catalog.find("missing") is None
    assert catalog.find_procedure("plug-in-8bfhost-filter-b").name == "zeta"
    assert list(catalog.by_category()) == ["one", "Two"]
    assert catalog.problems == [("/f/broken.8bf", "no PiPL")]
    assert catalog.error is None

    catalog.fail("8bf-host was not found")
    assert catalog.filters == []
    assert catalog.error == "8bf-host was not found"


def test_catalog_cache_round_trip(tmp_path):
    path = str(tmp_path / "bridge" / "filters.json")
    catalog = Catalog()
    catalog.load([summary(), summary(id="x", name="Blocked", runs=None, problem="no")])
    catalog.save(path)
    again = Catalog.read(path)
    assert again.filters == catalog.filters
    assert again.error is None

    catalog.fail("8bf-host was not found")
    catalog.save(path)
    assert Catalog.read(path).error == "8bf-host was not found"


def test_unreadable_catalog_cache(tmp_path):
    path = tmp_path / "filters.json"
    assert Catalog.read(str(path)) is None
    path.write_text("nope")
    assert Catalog.read(str(path)) is None
    path.write_text('{"filters": 3}')
    assert Catalog.read(str(path)) is None
