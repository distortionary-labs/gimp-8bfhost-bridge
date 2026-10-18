"""The GIMP plug-in: procedures, menus and the glue between the parts.

GIMP asks a plug-in for its procedures in two ways. The fixed ones (Repeat,
Settings, Check Setup) come from ``do_query_procedures``, which GIMP caches.
The filters come from ``do_init_procedures``, which GIMP calls at every
start, so the menu follows whatever 8bf-host finds.
"""

import os
import shutil
import sys
import tempfile
import traceback

import gi

gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gegl, Gimp, GLib, GObject  # noqa: E402

from . import __version__, bridge, host, images  # noqa: E402
from . import settings as settings_module  # noqa: E402
from .catalog import MENU_ROOT, Catalog  # noqa: E402

REPEAT = "plug-in-8bfhost-repeat"
SETTINGS = "plug-in-8bfhost-settings"
CHECK = "plug-in-8bfhost-check-setup"

TITLE = "Photoshop Filters (8bf)"
AUTHOR = "Durable Programming, LLC"
DATE = "2026"
IMAGE_TYPES = "RGB*, GRAY*"
DEBUG_VARIABLE = "GIMP_8BFHOST_BRIDGE_DEBUG"

# How many lines of 8bf-host's log an error message quotes.
LOG_LINES = 12


def _log(message):
    if os.environ.get(DEBUG_VARIABLE):
        sys.stderr.write("gimp-8bfhost-bridge: %s\n" % message)


def _paths():
    return settings_module.Paths(Gimp.directory())


def _scan(settings, paths, rescan=False):
    """Ask 8bf-host for the filter list and keep a copy for later runs."""
    catalog = Catalog()
    try:
        executable = host.require_executable(settings.host_path)
        catalog.load(*host.list_filters(executable, settings.folders, rescan))
    except host.HostError as exc:
        catalog.fail(str(exc))
        sys.stderr.write("gimp-8bfhost-bridge: listing filters failed: %s\n" % exc)
    try:
        catalog.save(paths.catalog)
    except OSError as exc:
        _log("could not save %s: %s" % (paths.catalog, exc))
    return catalog


def _catalog():
    """The filter list for this process.

    When GIMP starts it, the plug-in asks 8bf-host. When GIMP runs one of
    its procedures, the list saved at startup is enough, and much faster.
    """
    paths = _paths()
    if "-run" in sys.argv:
        saved = Catalog.read(paths.catalog)
        if saved is not None:
            return saved
    return _scan(settings_module.load(paths.settings), paths)


def _run_mode(mode):
    if mode == Gimp.RunMode.INTERACTIVE:
        return bridge.INTERACTIVE
    if mode == Gimp.RunMode.WITH_LAST_VALS:
        return bridge.LAST_VALUES
    return bridge.NONINTERACTIVE


def _success(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def _cancel(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())


def _failure(procedure, message):
    sys.stderr.write("gimp-8bfhost-bridge: %s\n" % message)
    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(message))


def _guarded(run):
    """Wrap a procedure's run function so it always returns values to GIMP."""

    def wrapper(procedure, *args):
        try:
            return run(procedure, *args)
        except Exception:  # noqa: BLE001 - GIMP needs return values even after a bug
            return _failure(procedure, "The plug-in failed:\n\n" + traceback.format_exc())

    return wrapper


def _color(getter, fallback):
    """A context color as 8-bit sRGB, which is how filters receive it."""
    try:
        red, green, blue, _alpha = getter().get_rgba()
        return images.srgb_bytes(red, green, blue)
    except Exception:  # noqa: BLE001 - the colors are a nicety, never a reason to fail
        return fallback


def _resolution(image):
    try:
        values = image.get_resolution()
        x = values[1] if len(values) == 3 else values[0]
        return float(x) if x and x > 0 else 72.0
    except Exception:  # noqa: BLE001
        return 72.0


def _drawable_kind(drawable):
    if drawable.is_rgb():
        return "rgb"
    if drawable.is_indexed():
        return "indexed"
    return "gray"


def _is_channel(drawable):
    return drawable.is_channel() or drawable.is_layer_mask()


def _check_drawable(drawable):
    if drawable.is_group_layer():
        raise bridge.BridgeError(
            "Layer groups cannot be filtered. Select a layer inside the group, or merge it."
        )
    if drawable.get_lock_content():
        raise bridge.BridgeError("The layer %s is locked." % drawable.get_name())


class Run:
    """One filter run over the selected drawables."""

    def __init__(self, entry, image, drawables, settings, paths):
        self.entry = entry
        self.image = image
        self.drawables = list(drawables)
        self.settings = settings
        self.paths = paths
        self.presets = settings_module.PresetStore(paths.presets)

    def capture(self, drawable, directory):
        """Write one drawable, and the selection on it, into ``directory``."""
        _check_drawable(drawable)
        layout = images.drawable_layout(
            _drawable_kind(drawable),
            drawable.has_alpha(),
            self.image.get_precision(),
            _is_channel(drawable),
        )
        width, height = drawable.get_width(), drawable.get_height()
        whole = Gegl.Rectangle.new(0, 0, width, height)
        pixels = drawable.get_buffer().get(whole, 1.0, layout.babl_format, Gegl.AbyssPolicy.NONE)

        mask = None
        rect = None
        if not Gimp.Selection.is_empty(self.image):
            rect = bridge.selection_rect(*drawable.mask_intersect())
            if rect is None:
                raise bridge.BridgeError("The selection does not overlap %s." % drawable.get_name())
            _ok, x, y = drawable.get_offsets()
            area = Gegl.Rectangle.new(x, y, width, height)
            selection = self.image.get_selection().get_buffer()
            mask = selection.get(area, 1.0, "Y u8", Gegl.AbyssPolicy.NONE)

        return bridge.prepare(
            directory,
            self.entry.id,
            layout,
            width,
            height,
            bytes(pixels),
            mask=None if mask is None else bytes(mask),
            rect=rect,
            foreground=_color(Gimp.context_get_foreground, (0, 0, 0)),
            background=_color(Gimp.context_get_background, (255, 255, 255)),
            resolution=_resolution(self.image),
        )

    def filter(self, run_mode, preset_file=""):
        """Run the filter on each drawable, then write all the results back.

        Returns None on success, "cancelled", or raises BridgeError.
        """
        executable = host.require_executable(self.settings.host_path)
        preset, dialog = bridge.choose_settings(
            run_mode, self.presets.existing(self.entry.id), preset_file
        )
        results = []
        for drawable in self.drawables:
            directory = tempfile.mkdtemp(prefix="gimp-8bfhost-bridge-")
            try:
                job = self.capture(drawable, directory)
                command = bridge.command(
                    job,
                    executable,
                    self.settings.folders,
                    preset=preset,
                    dialog=dialog,
                    save_preset=self.presets.path(self.entry.id),
                    fallback=self.settings.allow_8bit_fallback,
                )
                _log("running %s" % " ".join(command))
                Gimp.progress_init("Running %s..." % self.entry.name)
                try:
                    result = host.run(command, pump=Gimp.progress_pulse, cwd=directory)
                finally:
                    Gimp.progress_end()
                for line in result.log:
                    _log(line)
                if result.status == "cancelled":
                    return "cancelled"
                if not result.ok:
                    message = result.message or "The filter failed."
                    tail = [line for line in result.log if line.strip()][-LOG_LINES:]
                    if tail and not message.startswith("8bf-host exited"):
                        message += "\n\n8bf-host's log:\n" + "\n".join(tail)
                    raise bridge.BridgeError(message)
                results.append((drawable, job, bridge.read_result(job)))
            finally:
                shutil.rmtree(directory, ignore_errors=True)
            # Further drawables replay the settings this run saved.
            preset = self.presets.existing(self.entry.id) or preset
            dialog = False
        self.apply(results)
        return None

    def apply(self, results):
        """Write the results through the shadow buffers, as one undo step.

        8bf-host has already blended each result through the selection, as
        Photoshop's auto mask does. Merging a shadow buffer blends through
        the selection again, so the selection is set aside while merging and
        restored afterwards, all inside the undo group.
        """
        image = self.image
        image.undo_group_start()
        saved = None
        try:
            targets = []
            for drawable, job, data in results:
                target = drawable
                if self.settings.new_layer and drawable.is_layer():
                    target = drawable.copy()
                    image.insert_layer(
                        target, drawable.get_parent(), image.get_item_position(drawable)
                    )
                    target.set_name("%s (%s)" % (drawable.get_name(), self.entry.name))
                shadow = target.get_shadow_buffer()
                whole = Gegl.Rectangle.new(0, 0, job.width, job.height)
                shadow.set(whole, job.layout.babl_format, data)
                shadow.flush()
                targets.append((target, job))
            if not Gimp.Selection.is_empty(image):
                saved = Gimp.Selection.save(image)
                Gimp.Selection.none(image)
            for target, job in targets:
                target.merge_shadow(True)
                target.update(0, 0, job.width, job.height)
            if self.settings.new_layer and targets and targets[0][0].is_layer():
                image.set_selected_layers([t for t, _job in targets if t.is_layer()])
        finally:
            if saved is not None:
                image.select_item(Gimp.ChannelOps.REPLACE, saved)
                image.remove_channel(saved)
            image.undo_group_end()
        Gimp.displays_flush()


def run_filter(procedure, entry, run_mode, image, drawables, preset_file=""):
    if entry is None:
        return _failure(procedure, "That filter is no longer installed. Restart GIMP.")
    if not entry.runnable:
        return _failure(
            procedure,
            "%s cannot run on this computer: %s"
            % (entry.name, entry.problem or "8bf-host gave no reason."),
        )
    if not drawables:
        return _failure(procedure, "Select a layer to filter.")
    paths = _paths()
    settings = settings_module.load(paths.settings)
    try:
        outcome = Run(entry, image, drawables, settings, paths).filter(
            _run_mode(run_mode), preset_file
        )
    except (bridge.BridgeError, host.HostError, images.UnsupportedDrawable) as exc:
        return _failure(procedure, str(exc))
    if outcome == "cancelled":
        return _cancel(procedure)
    settings = settings_module.load(paths.settings)
    settings.last_filter = entry.id
    try:
        settings_module.save(settings, paths.settings)
    except OSError as exc:
        _log("could not save %s: %s" % (paths.settings, exc))
    return _success(procedure)


def _show_text(title, text):
    """Show long text, such as `8bf-host doctor`'s report, in a dialog."""
    gi.require_version("GimpUi", "3.0")
    gi.require_version("Gtk", "3.0")
    from gi.repository import GimpUi, Gtk, Pango

    GimpUi.init(CHECK)
    dialog = GimpUi.Dialog(title=title, role=CHECK)
    dialog.add_button("_Close", Gtk.ResponseType.CLOSE)
    view = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
    view.override_font(Pango.FontDescription.from_string("Monospace"))
    view.get_buffer().set_text(text)
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled.add(view)
    scrolled.set_border_width(12)
    dialog.get_content_area().pack_start(scrolled, True, True, 0)
    dialog.set_default_size(720, 520)
    dialog.show_all()
    dialog.run()
    dialog.destroy()


def check_setup_report(settings, paths):
    lines = [
        "gimp-8bfhost-bridge %s" % __version__,
        "Settings: %s" % paths.settings,
        "Presets:  %s" % paths.presets,
        "",
    ]
    executable = host.find_executable(settings.host_path)
    if not executable:
        lines.append("8bf-host was not found. Download it from %s," % host.DOWNLOAD_URL)
        lines.append("then set its location in 8bf Filter Settings.")
        return "\n".join(lines)
    lines.append("8bf-host: %s" % executable)
    lines.append("")
    for title, command in (
        ("8bf-host doctor", host.doctor_command(executable, settings.folders)),
        ("8bf-host list", host.list_command(executable, settings.folders, json_output=False)),
    ):
        result = host.run(command, pump=Gimp.progress_pulse, timeout=host.LIST_TIMEOUT)
        lines.append("$ " + title)
        text = (result.stdout + "\n".join(result.log)).strip()
        lines.append(text or result.message or "(no output)")
        lines.append("")
    lines.append("Filters that cannot run are listed with the reason. Changes to the filter")
    lines.append("list appear in the menu after GIMP restarts.")
    return "\n".join(lines)


def check_setup(procedure, config, _data):
    paths = _paths()
    report = check_setup_report(settings_module.load(paths.settings), paths)
    if config.get_property("run-mode") == Gimp.RunMode.INTERACTIVE:
        _show_text("Check 8bf-host Setup", report)
    else:
        sys.stdout.write(report + "\n")
    return _success(procedure)


def configure(procedure, config, _data):
    paths = _paths()
    settings = settings_module.load(paths.settings)
    if config.get_property("run-mode") == Gimp.RunMode.INTERACTIVE:
        gi.require_version("GimpUi", "3.0")
        from gi.repository import GimpUi

        GimpUi.init(SETTINGS)
        config.set_property("host-path", settings.host_path)
        config.set_property("folders", settings_module.format_folders(settings.folders))
        config.set_property("new-layer", settings.new_layer)
        config.set_property("allow-8bit-fallback", settings.allow_8bit_fallback)
        dialog = GimpUi.ProcedureDialog(
            procedure=procedure, config=config, title="8bf Filter Settings"
        )
        dialog.fill(None)
        accepted = dialog.run()
        dialog.destroy()
        if not accepted:
            return _cancel(procedure)
    settings.host_path = (config.get_property("host-path") or "").strip()
    settings.folders = settings_module.parse_folders(config.get_property("folders") or "")
    settings.new_layer = bool(config.get_property("new-layer"))
    settings.allow_8bit_fallback = bool(config.get_property("allow-8bit-fallback"))
    try:
        settings_module.save(settings, paths.settings)
    except OSError as exc:
        return _failure(procedure, "Could not save the settings: %s" % exc)

    catalog = _scan(settings, paths, rescan=True)
    if catalog.error:
        message = "Settings saved, but 8bf-host could not list the filters:\n\n" + catalog.error
    else:
        runnable = sum(1 for entry in catalog.filters if entry.runnable)
        message = (
            "8bf-host found %d filters, %d of which can run here. Restart GIMP to update "
            "the %s menu." % (len(catalog.filters), runnable, TITLE)
        )
    if config.get_property("run-mode") == Gimp.RunMode.INTERACTIVE:
        Gimp.message(message)
    else:
        sys.stdout.write(message + "\n")
    return _success(procedure)


class Bridge(Gimp.PlugIn):
    def __init__(self):
        super().__init__()
        self._filters = None

    @property
    def catalog(self):
        if self._filters is None:
            self._filters = _catalog()
        return self._filters

    # Gimp.PlugIn virtual methods ---------------------------------------------

    def do_set_i18n(self, _name):
        return False

    def do_query_procedures(self):
        return [REPEAT, SETTINGS, CHECK]

    def do_init_procedures(self):
        return [entry.procedure_name for entry in self.catalog.filters]

    def do_create_procedure(self, name):
        if name == REPEAT:
            return self._repeat_procedure(name)
        if name == SETTINGS:
            return self._settings_procedure(name)
        if name == CHECK:
            return self._check_procedure(name)
        entry = self.catalog.find_procedure(name)
        if entry is not None:
            return self._filter_procedure(name, entry)
        return None

    # Procedures ----------------------------------------------------------------

    def _filter_procedure(self, name, entry):
        def run(procedure, run_mode, image, drawables, config, _data):
            preset_file = config.get_property("preset-file") or ""
            return run_filter(procedure, entry, run_mode, image, drawables, preset_file)

        procedure = Gimp.ImageProcedure.new(
            self, name, Gimp.PDBProcType.PLUGIN, _guarded(run), None
        )
        procedure.set_image_types(IMAGE_TYPES)
        procedure.set_sensitivity_mask(
            Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES
        )
        procedure.set_menu_label(entry.menu_label)
        procedure.add_menu_path(entry.menu_path)
        if entry.runnable:
            blurb = "Run %s/%s through 8bf-host" % (entry.category, entry.name)
            help_text = (
                "Runs the Photoshop-compatible filter %s (%s) on the selected layers "
                "through 8bf-host, %s." % (entry.name, entry.path, entry.runs)
            )
        else:
            blurb = "Cannot run here: %s" % (entry.problem or "8bf-host gave no reason")
            help_text = blurb
        procedure.set_documentation(blurb, help_text, name)
        procedure.set_attribution(AUTHOR, AUTHOR, DATE)
        procedure.add_string_argument(
            "preset-file",
            "Preset file",
            "An 8bf-host preset file to run the filter with. Empty uses the last settings "
            "when run with last values, and the filter's defaults when run from a script.",
            "",
            GObject.ParamFlags.READWRITE,
        )
        return procedure

    def _repeat_procedure(self, name):
        def run(procedure, run_mode, image, drawables, _config, _data):
            settings = settings_module.load(_paths().settings)
            if not settings.last_filter:
                return _failure(procedure, "No 8bf filter has run yet.")
            entry = self.catalog.find(settings.last_filter)
            mode = Gimp.RunMode.WITH_LAST_VALS
            return run_filter(procedure, entry, mode, image, drawables)

        procedure = Gimp.ImageProcedure.new(
            self, name, Gimp.PDBProcType.PLUGIN, _guarded(run), None
        )
        procedure.set_image_types(IMAGE_TYPES)
        procedure.set_sensitivity_mask(
            Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES
        )
        procedure.set_menu_label("_Repeat Last 8bf Filter")
        procedure.add_menu_path(MENU_ROOT)
        procedure.set_documentation(
            "Rerun the last 8bf filter with its last settings",
            "Runs the 8bf filter that ran last again, with the settings it used, without "
            "its dialog. Unlike Filters > Repeat Last, this also works after GIMP restarts.",
            name,
        )
        procedure.set_attribution(AUTHOR, AUTHOR, DATE)
        return procedure

    def _plain_procedure(self, name, run):
        procedure = Gimp.Procedure.new(self, name, Gimp.PDBProcType.PLUGIN, _guarded(run), None)
        procedure.set_attribution(AUTHOR, AUTHOR, DATE)
        procedure.add_enum_argument(
            "run-mode",
            "Run mode",
            "The run mode",
            Gimp.RunMode,
            Gimp.RunMode.NONINTERACTIVE,
            GObject.ParamFlags.READWRITE,
        )
        return procedure

    def _settings_procedure(self, name):
        procedure = self._plain_procedure(name, configure)
        procedure.set_menu_label("8bf Filter _Settings...")
        procedure.add_menu_path(MENU_ROOT)
        procedure.set_documentation(
            "Set where 8bf-host is and where filters are",
            "Sets the 8bf-host program, extra filter folders and how results are applied, "
            "then asks 8bf-host for the filter list again.",
            name,
        )
        procedure.add_string_argument(
            "host-path",
            "_8bf-host program",
            "The 8bf-host program. Empty looks on PATH, in ~/.cargo/bin and in ~/.local/bin.",
            "",
            GObject.ParamFlags.READWRITE,
        )
        procedure.add_string_argument(
            "folders",
            "Extra filter _folders",
            "Folders with .8bf filters, besides the ones 8bf-host searches itself, "
            "separated by '%s'." % os.pathsep,
            "",
            GObject.ParamFlags.READWRITE,
        )
        procedure.add_boolean_argument(
            "new-layer",
            "Put results in a _new layer",
            "Filter a copy of the layer instead of the layer itself.",
            False,
            GObject.ParamFlags.READWRITE,
        )
        procedure.add_boolean_argument(
            "allow-8bit-fallback",
            "Run _8-bit-only filters on 16-bit images",
            "Let 8bf-host run filters that only handle 8-bit images on an 8-bit copy of a "
            "16-bit layer, keeping the 16-bit values of pixels the filter left unchanged.",
            True,
            GObject.ParamFlags.READWRITE,
        )
        return procedure

    def _check_procedure(self, name):
        procedure = self._plain_procedure(name, check_setup)
        procedure.set_menu_label("_Check 8bf-host Setup...")
        procedure.add_menu_path(MENU_ROOT)
        procedure.set_documentation(
            "Show what 8bf-host finds on this computer",
            "Runs `8bf-host doctor` and `8bf-host list` and shows their reports, including "
            "why a filter cannot run.",
            name,
        )
        return procedure


def main():
    Gimp.main(Bridge.__gtype__, sys.argv)
