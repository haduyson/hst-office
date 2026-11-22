# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The files the HST icon themes ship for the frame glyphs (icon-themes-src/hst-modern/glyphs/stage-frame).

Standard library only: build-hst-icon-theme.py adds frame_files(theme) to every HST archive.

Where a glyph lands is the LibreOffice image the frame element requests (metadata/frame-inventory.json):
  - a command icon ("cmd"): cmd/sc_, cmd/lc_ and cmd/32/ at the sizes the glyph is drawn for;
  - a fixed image of one square size ("svx/res/doc_modified_no", 16 px);
  - a native-size image (hst_icon_frame_glyphs.NATIVE): the hand-tuned masters as drawn;
  - a frame element LibreOffice draws without an image (the File tab's Home, the document tab marks):
    hst-frame/<size>/<name>.svg, for the phase that owns the element's code to load.
Every file comes with its @150/@250 variant. The Cổ điển overlay (hst_classic_icons.overlay) keeps
only the files of requests Colibre does not resolve, so the elements Colibre draws keep LibreOffice's
image in the default style and take the HST glyph in the Hiện đại style.
"""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hst_modern_icons as modern  # noqa: E402
from hst_icon_frame_glyphs import NATIVE, native_masters, sizes_of, square_masters  # noqa: E402
from hst_icon_glyph import FACTORS, variant_key  # noqa: E402
from hst_icon_snap import snap_svg  # noqa: E402

STAGE = modern.MODERN / "glyphs/stage-frame"
SIZES = (16, 24, 32)
PREFIX = {16: "cmd/sc_", 24: "cmd/lc_", 32: "cmd/32/"}
FRAME_DIR = "hst-frame"
# Square glyph -> the images it serves: "cmd" (the command icon of the same name), a fixed image path
# (without extension) of one size, or FRAME_DIR (no LibreOffice image).
REQUESTS = {
    "home": [FRAME_DIR], "tabclose": [FRAME_DIR], "tabnew": [FRAME_DIR],
    "saveas": ["cmd"], "about": ["cmd"], "setupusbtoken": ["cmd"], "previousversions": ["cmd"],
    "unsaveddocuments": ["cmd"], "toggleduplex": ["cmd"],
    "recent-pin": ["res/recentdoc_pin"],
    "sidebar-inspector": ["cmd/inspectordeck"], "sidebar-trackchanges": ["cmd/trackchangesbar"],
    "sidebar-design": ["cmd/designerdialog"],
    **{f"sidebar-{deck}": [f"sfx2/res/symphony/sidebar-{deck}-large"]
       for deck in ("property", "style", "navigator", "a11y", "gallery", "template", "animation", "transition",
                    "functions", "elements")},
    "signature-status": ["svx/res/signet_11x16"], "signature-broken": ["svx/res/caution_11x16"],
    "signature-notvalidated": ["svx/res/notcertificate_16"],
    "doc-modified-no": ["svx/res/doc_modified_no"], "doc-modified-yes": ["svx/res/doc_modified_yes"],
    "doc-modified-feedback": ["svx/res/doc_modified_feedback"],
    "a11y-check-ok": ["svx/res/a11y_check_issues_not_found"],
    "a11y-check-issues": ["svx/res/a11y_check_issues_found"],
}


def _theme(theme):
    dark = theme.endswith("_dark")
    return dark, modern.ink()["dark" if dark else "light"]


def shipped(name, theme):
    """{archive name: SVG text} of one square frame glyph in `theme` at cmd/{sc_,lc_,32/}<name>[@150|@250].svg,
    as hst_icon_glyph would ship it (hand-tuned 16 px master where there is one)."""
    dark, ink = _theme(theme)
    master = (STAGE / f"{name}.svg").read_text(encoding="utf-8")
    tuned_path = STAGE / "16" / f"{name}.svg"
    files = {}
    for size in SIZES:
        key = f"{PREFIX[size]}{name}.svg"
        native = size == 16 and tuned_path.is_file()
        text = modern.harmonise(tuned_path.read_text(encoding="utf-8") if native else master, dark)
        files[key] = snap_svg(text, size, native=native).replace("currentColor", ink)
        for percent, factor in FACTORS.items():
            files[variant_key(key, percent)] = snap_svg(modern.harmonise(master, dark), size,
                                                        factor=factor).replace("currentColor", ink)
    return files


def native_size(text):
    """(width, height) in px of a native master."""
    root = ET.fromstring(text)
    return int(root.get("width")), int(root.get("height"))


def shipped_native(name, theme):
    """{variant: SVG text} of a native-size frame glyph (native/<name>[@150|@250].svg) in `theme`:
    harmonised colours and the theme's ink, geometry as drawn (VCL draws these images at their own size),
    strokes painted as filled outlines like every shipped HST icon (VCL's renderer moves a stroke on a
    half-pixel centre line by half a pixel, which would blur it). Keys: "100", "150", "250"."""
    dark, ink = _theme(theme)
    files = {}
    for percent, suffix in (("100", ""), ("150", "@150"), ("250", "@250")):
        text = (STAGE / "native" / f"{name}{suffix}.svg").read_text(encoding="utf-8")
        files[percent] = snap_svg(modern.harmonise(text, dark), 0, native=True,
                                  box=native_size(text)).replace("currentColor", ink)
    return files


def _variants(source, key, target):
    """The 100 % file and @150/@250 variants of shipped `key`, renamed to archive name `target`."""
    files = {target: source[key]}
    for percent in FACTORS:
        files[variant_key(target, percent)] = source[variant_key(key, percent)]
    return files


def frame_files(theme):
    """{archive name: SVG bytes} of every frame glyph in `theme` (an hst* theme name)."""
    files = {}
    squares, natives = square_masters(STAGE), native_masters(STAGE)
    missing = sorted((set(squares) - set(REQUESTS)) | (set(natives) - set(NATIVE)))
    if missing:
        raise ValueError(f"frame glyphs without a target image: {missing}")

    def add(name, value):
        if name in files:
            raise ValueError(f"two frame glyphs ship {name}")
        files[name] = value.encode("utf-8")

    for name in squares:
        source, sizes = shipped(name, theme), sizes_of(name)
        for request in REQUESTS[name]:
            for size in sizes:
                key = f"{PREFIX[size]}{name}.svg"
                if request == FRAME_DIR:
                    target = f"{FRAME_DIR}/{size}/{name}.svg"
                elif request == "cmd":
                    target = key
                elif request.startswith("cmd/"):
                    target = f"{PREFIX[size]}{request[4:]}.svg"
                elif size == sizes[0]:  # a fixed image has the glyph's one (smallest) size
                    target = f"{request}.svg"
                else:
                    continue
                for archive_name, text in _variants(source, key, target).items():
                    add(archive_name, text)
    for name in natives:
        source = shipped_native(name, theme)
        add(f"{NATIVE[name]}.svg", source["100"])
        for percent in FACTORS:
            add(f"{NATIVE[name]}@{percent}.svg", source[str(percent)])
    return files
