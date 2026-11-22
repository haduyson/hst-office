# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""HST Công thức: a converted MathType equation keeps the scale Word shows it at. An equation resized in Word keeps
MathType's point sizes in its data; the resize lives only in its shown size (.docx shape style, .rtf \\objh and
\\pichgoal, .doc PICF), while the object's own size and its preview picture stay at MathType's 100 %. The shown size
is not compared with the formula's: MathType's box is taller than Math's for the same point size.
The same rule as the open path in C++ (sw/source/core/hst/formulashownsize.cxx)."""
import os
import re
import struct
import tempfile

CONTENT = 1  # com.sun.star.embed.Aspects.MSOLE_CONTENT
TOLERANCE = 0.05  # Word's own rounding of a size at 100 %
# The WMF reader sizes an MM_ANISOTROPIC WMF smaller than its "inch" field to one inch on its longer side (emfio
# wmfreader), so a MathType preview under 1 inch is reported 2540 mm100 tall or wide whatever its size: its own
# placeable header (bounding box, units per inch) tells the size; without one the scale is unknown.
NORMALIZED_INCH, INCH_SLACK = 2540, 2
PLACEABLE_KEY = b"\xd7\xcd\xc6\x9a"
MM100_PER_INCH = 2540
# com.sun.star.embed.EmbedMapUnits -> mm100 per unit; a formula's visible area is in twips
MM100_PER_UNIT = {0: 1, 1: 10, 2: 100, 3: 1000, 4: 2.54, 5: 25.4, 6: 254, 7: 2540, 8: 2540 / 72, 9: 127 / 72}
SIZE = re.compile(r"(?<![A-Za-z0-9])size[ \t]+(\d+(?:\.\d+)?)")


def visual_size(embedded):
    """The object's visible area in mm100, the unit of Writer frames and shapes."""
    size = embedded.getVisualAreaSize(CONTENT)
    factor = MM100_PER_UNIT.get(embedded.getMapUnit(CONTENT), 1)
    size.Width, size.Height = round(size.Width * factor), round(size.Height * factor)
    return size


def native_height(old):
    """The equation's height at 100 % in mm100: the OLE object's own size (.doc), else its preview picture; 0 when
    neither tells it."""
    try:
        return visual_size(old.EmbeddedObject).Height
    except Exception:  # noqa: BLE001 - no own size (.docx, .rtf) or the object cannot tell
        pass
    for name in ("ReplacementGraphic", "Graphic"):  # Writer objects, shapes
        try:
            graphic = getattr(old, name)
            size = graphic.getPropertyValue("Size100thMM")
        except Exception:  # noqa: BLE001 - no such picture
            continue
        height = placeable_height(preview_data(graphic))
        if height:
            return height
        if abs(max(size.Width, size.Height) - NORMALIZED_INCH) <= INCH_SLACK:
            return 0  # the reader's size, not the equation's: the scale is unknown
        return size.Height
    return 0


def placeable_height(data):
    """The height in mm100 a WMF's placeable header gives (bounding box / units per inch), 0 without one."""
    if len(data) < 22 or not data.startswith(PLACEABLE_KEY):
        return 0
    _, top, _, bottom, inch = struct.unpack("<hhhhH", data[6:16])
    return round(abs(bottom - top) * MM100_PER_INCH / inch) if inch else 0


def preview_data(graphic):
    """The preview picture's own WMF bytes (the office writes a WMF it read as it was), b"" when it cannot."""
    try:
        import uno
        from com.sun.star.beans import PropertyValue
        ctx = uno.getComponentContext()
        provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.graphic.GraphicProvider", ctx)
        handle, path = tempfile.mkstemp(suffix=".wmf")
        os.close(handle)
        try:
            props = [PropertyValue(), PropertyValue()]
            props[0].Name, props[0].Value = "URL", uno.systemPathToFileUrl(path)
            props[1].Name, props[1].Value = "MimeType", "image/x-wmf"
            provider.storeGraphic(graphic, tuple(props))
            with open(path, "rb") as stream:
                return stream.read(64)
        finally:
            os.remove(path)
    except Exception:  # noqa: BLE001 - no office (tests) or a picture that cannot be written as WMF
        return b""


def scale_sizes(formula, ratio):
    """The formula text drawn ratio times as large: each absolute "size N" outside quoted text is multiplied, and the
    text is wrapped in "size *ratio" for the parts without a size."""
    parts = formula.split('"')
    for i in range(0, len(parts), 2):  # even parts are outside "quoted text"
        parts[i] = SIZE.sub(lambda m: "size %g" % max(1.0, round(float(m.group(1)) * ratio, 1)), parts[i])
    return "size *%g {%s}" % (round(ratio, 3), '"'.join(parts))


def keep_word_scale(model, old):
    """Draw the formula that replaces the equation old at the scale Word shows it at, unless that is within TOLERANCE
    of 100 %. Returns the scale applied, 1.0 when the formula is left as it is."""
    native = native_height(old)
    if native <= 0 or old.Size.Height <= 0:
        return 1.0
    scale = old.Size.Height / native
    if abs(scale - 1) <= TOLERANCE:
        return 1.0
    model.Formula = scale_sizes(model.Formula, scale)
    return scale
