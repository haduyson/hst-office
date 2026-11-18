# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức: a converted MathType equation keeps the size Word shows it at. An equation resized in Word keeps
MathType's point sizes in its data; the resize lives only in the object's shown size (.docx shape style, .rtf
\\picscalex, .doc PICF scale), and the MathType import writes those point sizes into the formula ("size 12{em}").
The same rule as the open path in C++ (sw/source/core/hst/formulashownsize.cxx)."""
import re

CONTENT = 1  # com.sun.star.embed.Aspects.MSOLE_CONTENT
TOLERANCE = 0.1  # within 10 % of the shown height the formula keeps MathType's own size
# com.sun.star.embed.EmbedMapUnits -> mm100 per unit; a formula's visible area is in twips
MM100_PER_UNIT = {0: 1, 1: 10, 2: 100, 3: 1000, 4: 2.54, 5: 25.4, 6: 254, 7: 2540, 8: 2540 / 72, 9: 127 / 72}
SIZE = re.compile(r"(?<![A-Za-z0-9])size[ \t]+(\d+(?:\.\d+)?)")


def visual_size(embedded):
    """The object's visible area in mm100, the unit of Writer frames and shapes."""
    size = embedded.getVisualAreaSize(CONTENT)
    factor = MM100_PER_UNIT.get(embedded.getMapUnit(CONTENT), 1)
    size.Width, size.Height = round(size.Width * factor), round(size.Height * factor)
    return size


def scale_sizes(formula, ratio):
    """The formula text drawn ratio times as large: each absolute "size N" outside quoted text is multiplied, and the
    text is wrapped in "size *ratio" for the parts without a size."""
    parts = formula.split('"')
    for i in range(0, len(parts), 2):  # even parts are outside "quoted text"
        parts[i] = SIZE.sub(lambda m: "size %g" % max(1.0, round(float(m.group(1)) * ratio, 1)), parts[i])
    return "size *%g {%s}" % (round(ratio, 3), '"'.join(parts))


def keep_shown_size(model, embedded, shown_height):
    """Scale the new formula to shown_height (mm100) when its own height is more than TOLERANCE off.
    Returns the ratio applied, 1.0 when the formula is left as it is."""
    natural = visual_size(embedded).Height
    if natural <= 0 or shown_height <= 0:
        return 1.0
    ratio = shown_height / natural
    if abs(ratio - 1) <= TOLERANCE:
        return 1.0
    model.Formula = scale_sizes(model.Formula, ratio)
    return ratio
