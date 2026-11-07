# SPDX-License-Identifier: AGPL-3.0-only
"""The colourful HST icon style (hst_modern / hst_modern_dark): sources, spec checks, recolouring.

Masters live in icon-themes-src/hst-modern/glyphs/<stage dir>/<glyph>.svg under the classic
master's name, on the same 24-unit grid and with the same silhouette. Ink is currentColor; every
other colour is the light value of a token in metadata/palette.json, swapped for its dark value in
hst_modern_dark. violations() lists every way a master breaks that contract, so a delivered batch
can be checked before it enters the tree.
"""
from functools import lru_cache
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from hst_icon_snap import snap_svg
from hst_svg_math import SnapError

MODERN = Path(__file__).resolve().parents[2] / "icon-themes-src/hst-modern"
SVG = "{http://www.w3.org/2000/svg}"
TAGS = {"svg", "title", "desc", "g", "path", "rect", "circle", "ellipse"}
ATTRIBUTES = {
    "svg": {"width", "height", "viewBox"},
    "g": {"fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "fill-opacity", "stroke-opacity",
          "opacity", "transform"},
}
SHAPE = ATTRIBUTES["g"] | {"d", "x", "y", "width", "height", "rx", "ry", "cx", "cy", "r", "data-state"}
HEX = re.compile(r"#[0-9A-Fa-f]{6}")
TRANSFORM = re.compile(r"^(\s*(translate|scale|rotate|matrix)\s*\([^)]*\)\s*)+$")


@lru_cache(maxsize=None)
def palette(source=MODERN):
    """{LIGHT_HEX: DARK_HEX} from metadata/palette.json, validated."""
    tokens = json.loads((source / "metadata/palette.json").read_text(encoding="utf-8"))
    result = {}
    for token, values in tokens.items():
        light, dark = values.get("light", ""), values.get("dark", "")
        if not (HEX.fullmatch(light) and HEX.fullmatch(dark)):
            raise ValueError(f"palette token {token!r} needs #RRGGBB light and dark values")
        result[light.upper()] = dark.upper()
    return result


def violations(text, colours):
    """Spec breaches of one modern master (empty when it may enter the tree)."""
    problems = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        return [f"not well-formed XML: {error}"]
    if (root.get("width"), root.get("height"), root.get("viewBox")) != ("24", "24", "0 0 24 24"):
        problems.append('root must be width="24" height="24" viewBox="0 0 24 24"')
    if "SPDX-License-Identifier: CC-BY-4.0; Copyright 2026 HASON TECH" not in text:
        problems.append("missing the CC-BY-4.0 HASON TECH SPDX comment")
    if not (root.findtext(f"{SVG}title") or "").startswith("HST "):
        problems.append("missing <title>HST <glyph></title>")
    for element in root.iter():
        tag = element.tag.replace(SVG, "")
        if tag not in TAGS:
            problems.append(f"forbidden element <{tag}>")
            continue
        allowed = ATTRIBUTES.get(tag, SHAPE if tag not in ("title", "desc") else set())
        for name, value in element.attrib.items():
            if name not in allowed:
                problems.append(f"<{tag}> attribute {name!r} is not allowed")
            elif name in ("fill", "stroke") and value not in ("none", "currentColor") and value.upper() not in colours:
                problems.append(f"<{tag}> {name}={value!r} is not currentColor, none or a palette light value")
            elif name == "stroke-linecap" and value != "round" or name == "stroke-linejoin" and value != "round":
                problems.append(f"<{tag}> {name}={value!r}: only round caps and joins")
            elif name == "transform" and not TRANSFORM.match(value):
                problems.append(f"<{tag}> transform {value!r} is not translate/scale/rotate/matrix")
    if not problems:
        for size in (16, 24, 32):
            try:
                snap_svg(text, size)
            except (SnapError, ValueError) as error:
                problems.append(f"does not snap at {size} px: {error}")
    return problems


def master(classic):
    """Modern counterpart of a classic master path, or None while it is not drawn yet."""
    path = MODERN / "glyphs" / classic.parent.name / classic.name
    return path if path.is_file() else None


def recolour(svg, colours, dark):
    """Palette light values become their dark values in the dark theme."""
    if not dark:
        return svg
    return HEX.sub(lambda m: colours.get(m.group().upper(), m.group()), svg)
