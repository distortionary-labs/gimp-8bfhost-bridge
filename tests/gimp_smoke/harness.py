# Run by tests/gimp_smoke/run.sh inside a headless GIMP 3 (python-fu-eval).
#
# Drives the installed plug-in through the PDB, as a script would: the
# native test filter inverts colors, so each check can say exactly which
# pixels should change. Prints one "ok"/"FAIL" line per check and
# "SMOKE PASSED" at the end, or "SMOKE FAILED".
import json
import os
import traceback

import gi

gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gegl, Gimp  # noqa: E402

CATALOG = os.path.join(Gimp.directory(), "8bfhost-bridge", "filters.json")
SETTINGS = os.path.join(Gimp.directory(), "8bfhost-bridge", "settings.json")
PDB = Gimp.get_pdb()
failures = []


def check(name, condition, detail=""):
    print("%-4s %s" % ("ok" if condition else "FAIL", name))
    if not condition:
        print("      %s" % detail)
        failures.append(name)


def filter_procedure(name):
    with open(CATALOG) as handle:
        filters = json.load(handle)["filters"]
    entry = next(f for f in filters if f["name"] == name)
    return "plug-in-8bfhost-filter-" + entry["id"]


def call(name, image=None, drawables=(), **arguments):
    procedure = PDB.lookup_procedure(name)
    config = procedure.create_config()
    config.set_property("run-mode", arguments.pop("run_mode", Gimp.RunMode.NONINTERACTIVE))
    if image is not None:
        config.set_property("image", image)
        config.set_core_object_array("drawables", list(drawables))
    for key, value in arguments.items():
        config.set_property(key.replace("_", "-"), value)
    result = procedure.run(config)
    status = result.index(0)
    # GIMP 3 returns the error message as a string.
    error = result.index(1) if status != Gimp.PDBStatusType.SUCCESS else None
    return status, str(error or "")


IMAGES = []


def new_image(base, image_type, precision, width, height, fmt, pixels):
    image = Gimp.Image.new_with_precision(width, height, base, precision)
    IMAGES.append(image)
    layer = Gimp.Layer.new(image, "layer", width, height, image_type, 100, Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, None, 0)
    layer.get_buffer().set(Gegl.Rectangle.new(0, 0, width, height), fmt, bytes(pixels))
    return image, layer


def pixels(drawable, fmt):
    rect = Gegl.Rectangle.new(0, 0, drawable.get_width(), drawable.get_height())
    return list(drawable.get_buffer().get(rect, 1.0, fmt, Gegl.AbyssPolicy.NONE))


def u16(raw):
    return [int.from_bytes(bytes(raw[i : i + 2]), "little") for i in range(0, len(raw), 2)]


def main():
    for name in (
        "plug-in-8bfhost-repeat",
        "plug-in-8bfhost-settings",
        "plug-in-8bfhost-check-setup",
    ):
        check("%s is registered" % name, PDB.lookup_procedure(name) is not None)
    invert = filter_procedure("Invert")
    error_filter = filter_procedure("Error")
    check("the filters are registered", PDB.lookup_procedure(invert) is not None, invert)

    # 8-bit RGBA, the whole layer.
    fmt = "R'G'B'A u8"
    source = [10, 20, 30, 255, 200, 100, 0, 128, 0, 0, 0, 0, 255, 255, 255, 64]
    image, layer = new_image(
        Gimp.ImageBaseType.RGB,
        Gimp.ImageType.RGBA_IMAGE,
        Gimp.Precision.U8_NON_LINEAR,
        4,
        1,
        fmt,
        source,
    )
    status, error = call(invert, image, [layer])
    check("8-bit RGBA run succeeds", status == Gimp.PDBStatusType.SUCCESS, error)
    expected = [v if i % 4 == 3 else 255 - v for i, v in enumerate(source)]
    check("8-bit RGBA is inverted, alpha kept", pixels(layer, fmt) == expected, pixels(layer, fmt))

    # Repeat Last 8bf Filter reruns Invert, which inverts back.
    status, error = call("plug-in-8bfhost-repeat", image, [layer])
    check("repeat succeeds", status == Gimp.PDBStatusType.SUCCESS, error)
    check("repeat ran the last filter", pixels(layer, fmt) == source, pixels(layer, fmt))

    # A feathered selection on an offset layer: 8bf-host blends through
    # the mask once, and the selection survives the run.
    fmt = "R'G'B' u8"
    source = [0, 0, 0] * 4
    image, layer = new_image(
        Gimp.ImageBaseType.RGB,
        Gimp.ImageType.RGB_IMAGE,
        Gimp.Precision.U8_NON_LINEAR,
        4,
        1,
        fmt,
        source,
    )
    image.resize(6, 1, 0, 0)
    layer.set_offsets(2, 0)
    image.select_rectangle(Gimp.ChannelOps.REPLACE, 3, 0, 2, 1)
    selection = image.get_selection()
    coverage = bytes([0, 0, 0, 255, 128, 0])
    selection.get_buffer().set(Gegl.Rectangle.new(0, 0, 6, 1), "Y u8", coverage)
    status, error = call(invert, image, [layer])
    check("run with a feathered selection succeeds", status == Gimp.PDBStatusType.SUCCESS, error)
    out = pixels(layer, fmt)
    check("outside the selection is unchanged", out[0:3] == [0, 0, 0] and out[9:12] == [0] * 3, out)
    check("fully selected pixel is inverted", out[3:6] == [255, 255, 255], out)
    check("half-selected pixel is blended once", all(abs(v - 128) <= 2 for v in out[6:9]), out)
    restored = list(
        selection.get_buffer().get(
            Gegl.Rectangle.new(0, 0, 6, 1), 1.0, "Y u8", Gegl.AbyssPolicy.NONE
        )
    )
    check("the selection is restored", restored == list(coverage), restored)
    check("no channel is left behind", len(image.get_channels()) == 0, image.get_channels())

    # 16-bit linear RGB: sent as 16-bit sRGB-encoded samples, inverted
    # through 8bf-host's 8-bit fallback, and converted back.
    fmt = "R'G'B' u16"
    values = [0, 16384, 65535]
    raw = b"".join(v.to_bytes(2, "little") for v in values)
    image, layer = new_image(
        Gimp.ImageBaseType.RGB,
        Gimp.ImageType.RGB_IMAGE,
        Gimp.Precision.U16_LINEAR,
        1,
        1,
        fmt,
        raw,
    )
    status, error = call(invert, image, [layer])
    check("16-bit linear RGB run succeeds", status == Gimp.PDBStatusType.SUCCESS, error)
    out = u16(pixels(layer, fmt))
    near = all(abs(out[i] - (65535 - values[i])) <= 400 for i in range(3))
    check("16-bit RGB is inverted", near, out)

    # 8-bit grayscale without alpha.
    fmt = "Y' u8"
    image, layer = new_image(
        Gimp.ImageBaseType.GRAY,
        Gimp.ImageType.GRAY_IMAGE,
        Gimp.Precision.U8_NON_LINEAR,
        3,
        1,
        fmt,
        [0, 100, 255],
    )
    status, error = call(invert, image, [layer])
    check("8-bit grayscale run succeeds", status == Gimp.PDBStatusType.SUCCESS, error)
    check("8-bit grayscale is inverted", pixels(layer, fmt) == [255, 155, 0], pixels(layer, fmt))

    # An interactive run asks 8bf-host for the filter's dialog; the test
    # filter has none, so it runs straight through.
    status, error = call(invert, image, [layer], run_mode=Gimp.RunMode.INTERACTIVE)
    check("an interactive run succeeds", status == Gimp.PDBStatusType.SUCCESS, error)
    check("an interactive run filters", pixels(layer, fmt) == [0, 100, 255])
    presets = os.path.join(Gimp.directory(), "8bfhost-bridge", "presets")
    check("the filter's settings are kept as a preset", len(os.listdir(presets)) >= 1)

    # GIMP's own Filters > Repeat Last runs with last values, which
    # replays the preset the run above saved.
    status, error = call(invert, image, [layer], run_mode=Gimp.RunMode.WITH_LAST_VALS)
    check("a run with last values succeeds", status == Gimp.PDBStatusType.SUCCESS, error)
    check("a run with last values filters", pixels(layer, fmt) == [255, 155, 0])

    # A layer mask is filtered as the coverage values it stores.
    image, layer = new_image(
        Gimp.ImageBaseType.RGB,
        Gimp.ImageType.RGBA_IMAGE,
        Gimp.Precision.U8_NON_LINEAR,
        2,
        1,
        "R'G'B'A u8",
        bytes(8),
    )
    mask = layer.create_mask(Gimp.AddMaskType.WHITE)
    layer.add_mask(mask)
    status, error = call(invert, image, [mask])
    check("layer mask run succeeds", status == Gimp.PDBStatusType.SUCCESS, error)
    check("the layer mask is inverted", pixels(mask, "Y u8") == [0, 0], pixels(mask, "Y u8"))

    # 16-bit grayscale without alpha.
    fmt = "Y' u16"
    image, layer = new_image(
        Gimp.ImageBaseType.GRAY,
        Gimp.ImageType.GRAY_IMAGE,
        Gimp.Precision.U16_NON_LINEAR,
        1,
        1,
        fmt,
        (1000).to_bytes(2, "little"),
    )
    status, error = call(invert, image, [layer])
    check("16-bit grayscale run succeeds", status == Gimp.PDBStatusType.SUCCESS, error)
    out = u16(pixels(layer, fmt))
    check("16-bit grayscale is inverted", abs(out[0] - 64535) <= 300, out)

    # 16-bit grayscale with alpha is refused with an explanation.
    fmt = "Y'A u16"
    image, layer = new_image(
        Gimp.ImageBaseType.GRAY,
        Gimp.ImageType.GRAYA_IMAGE,
        Gimp.Precision.U16_NON_LINEAR,
        1,
        1,
        fmt,
        bytes(4),
    )
    status, error = call(invert, image, [layer])
    message = error
    check(
        "16-bit grayscale with alpha is refused",
        status == Gimp.PDBStatusType.EXECUTION_ERROR and "alpha" in message,
        (status, message),
    )

    # A filter error comes back as the procedure's error.
    image, layer = new_image(
        Gimp.ImageBaseType.RGB,
        Gimp.ImageType.RGB_IMAGE,
        Gimp.Precision.U8_NON_LINEAR,
        1,
        1,
        "R'G'B' u8",
        bytes(3),
    )
    status, error = call(error_filter, image, [layer])
    message = error
    check(
        "filter errors are reported",
        status == Gimp.PDBStatusType.EXECUTION_ERROR and "failed on purpose" in message,
        (status, message),
    )

    # The new-layer setting filters a copy and leaves the layer alone.
    with open(SETTINGS) as handle:
        before = json.load(handle)
    status, error = call(
        "plug-in-8bfhost-settings",
        host_path=before["host_path"],
        folders=os.pathsep.join(before["folders"]),
        new_layer=True,
        allow_8bit_fallback=True,
    )
    check("settings can be set from a script", status == Gimp.PDBStatusType.SUCCESS, error)
    fmt = "R'G'B' u8"
    image, layer = new_image(
        Gimp.ImageBaseType.RGB,
        Gimp.ImageType.RGB_IMAGE,
        Gimp.Precision.U8_NON_LINEAR,
        1,
        1,
        fmt,
        [10, 20, 30],
    )
    status, error = call(invert, image, [layer])
    layers = image.get_layers()
    check("new-layer run succeeds", status == Gimp.PDBStatusType.SUCCESS, error)
    check("a new layer is added above", len(layers) == 2 and layers[1] == layer, layers)
    check("the original layer is unchanged", pixels(layer, fmt) == [10, 20, 30])
    check("the new layer is filtered", pixels(layers[0], fmt) == [245, 235, 225])
    check("the new layer is named", layers[0].get_name() == "layer (Invert)", layers[0].get_name())
    with open(SETTINGS) as handle:
        after = json.load(handle)
    check("settings were saved", after["new_layer"] is True, after)

    status, error = call("plug-in-8bfhost-check-setup")
    check("check setup runs", status == Gimp.PDBStatusType.SUCCESS, error)


try:
    main()
except Exception:
    traceback.print_exc()
    failures.append("exception")
for image in IMAGES:
    image.delete()
print("SMOKE FAILED" if failures else "SMOKE PASSED")
