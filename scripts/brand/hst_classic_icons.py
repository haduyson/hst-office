# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The "Cổ điển" icon style (hst_classic / hst_classic_dark): upstream Colibre with HST glyphs on top
only for what Colibre does not draw, and for the few requests of FORCED.

The archive is an overlay. It holds the HST glyphs for every icon request that the SVG Colibre of
the same LibreOffice tree cannot resolve (the org.hst.office.vi commands, the statistics dialogs and
others), and VCL falls back to colibre_svg / colibre_dark_svg for every other request
(hst-icon-theme-classic-colibre.patch). Coverage is computed from the tree's own Colibre the way
postprocess/images packs it and VCL resolves names (one links.txt step, PNG spelling first, the
lc_ -> 32/ link variants), so a Colibre icon is never shadowed. Overlay files live under hst/, a
directory Colibre does not use, and every request reaches them through links.txt. The HST glyphs
take Colibre's ink so the two layers read as one set. Standard library only.
"""
from pathlib import Path, PurePosixPath

# theme -> (HST theme whose glyphs form the overlay, Colibre theme it falls back to, ink)
CLASSIC = {
    "hst_classic": ("hst", "colibre_svg", "#3A3A38"),
    "hst_classic_dark": ("hst_dark", "colibre_dark_svg", "#FAFAFA"),
}
PREFIX = "hst/"
# Requests the HST glyph answers although Colibre draws them: the ribbon's Find and Replace stand one above the
# other in Writer's Editing group, and Colibre's pair differs in ink and weight (a thin blue magnifier beside a
# dark one with letters). The HST 16 px pair is drawn with the same 1 px pen (owner decision of 15/11/2026).
FORCED = frozenset({"cmd/sc_recsearch", "cmd/sc_searchdialog"})
# Colibre icons the Cổ điển style redraws in place, with every Colibre link to them: Clear Direct Formatting
# (ResetAttributes, SetDefault) keeps Colibre's letter but erases with a white eraser instead of a red one,
# because white reads as "wiped clean" (owner decision of 21/11/2026; scripts/brand/draw-hst-classic-eraser.py).
REDRAWN = Path(__file__).resolve().parents[2] / "icon-themes-src/hst-classic"
REDRAWN_MODE = {"hst_classic": "light", "hst_classic_dark": "dark"}
EXTRA = ("links.txt", "LICENSE-CC-BY-4.0.txt", "COPYING.txt")


def _stem(name):
    return str(PurePosixPath(name).with_suffix(""))


def _lc_to_32(path):
    head, _, tail = path.rpartition("/")
    return f"{head}/32/{tail[3:]}" if head and tail.startswith("lc_") else ""


def parse_links(text):
    """{link: original} as VCL reads links.txt, with the derived lc_ -> 32/ entries."""
    links = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[0].startswith("#"):
            continue
        link, original = parts[0], parts[1]
        links[link] = original
        if _lc_to_32(link) and _lc_to_32(original):
            links[_lc_to_32(link)] = _lc_to_32(original)
    return links


def _links_text(icon_themes, theme):
    """links.txt of `theme` as postprocess/CustomTarget_images.mk assembles it."""
    own = icon_themes / theme / "links.txt"
    if own.is_file():
        return own.read_text(encoding="utf-8")
    text = ""
    base = icon_themes / theme.replace("_svg", "") / "links.txt"
    if base.is_file():
        text = base.read_text(encoding="utf-8").replace(".png", ".svg")
    light = icon_themes / theme.replace("_dark", "") / "links.txt"
    if light.is_file():
        text = light.read_text(encoding="utf-8")
    return text


class Coverage:
    """Which icon requests a Colibre theme of a LibreOffice source tree resolves."""

    def __init__(self, icon_themes, theme):
        root = Path(icon_themes) / theme
        if not root.is_dir():
            raise ValueError(f"no {theme} icon theme in {icon_themes}")
        self.files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        self.links = parse_links(_links_text(Path(icon_themes), theme))

    def covers(self, request):
        stem = _stem(request)
        real = self.links.get(stem + ".png") or self.links.get(stem + ".svg") or request
        real = _stem(real)
        return real + ".png" in self.files or real + ".svg" in self.files


def redrawn(theme):
    """{archive name: bytes} of the Colibre icons `theme` redraws (icon-themes-src/hst-classic/<mode>/)."""
    root = REDRAWN / REDRAWN_MODE[theme]
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*.svg"))}


def overlay(files, coverage, notice, own=None):
    """Overlay archive files of an HST theme's `files` for the requests `coverage` misses.

    `own` ({name: bytes}, from redrawn()) replaces Colibre icons: each answers its own request and every
    Colibre link that resolves to it (sc_setdefault -> sc_resetattributes)."""
    links = parse_links(files["links.txt"].decode("utf-8"))
    requests = {_stem(link) for link in links}
    requests |= {_stem(name) for name in files if name not in EXTRA and "@" not in name}
    variants = {}  # display-scale variants (cmd/lc_x@150.svg) travel with their glyph
    for name in files:
        if "@" in name:
            variants.setdefault(name.split("@")[0], []).append(name)
    result, aliases = {}, {}
    for request in sorted(requests):
        if coverage.covers(request) and request not in FORCED:
            continue
        target = links.get(request + ".png") or links.get(request + ".svg")
        if target is None:
            target = next((request + ext for ext in (".svg", ".png") if request + ext in files), None)
        if target is None or target not in files:
            continue  # a derived 32/ link of a size HST serves under another name
        result[PREFIX + target] = files[target]
        for name in variants.get(_stem(target), ()):
            result[PREFIX + name] = files[name]
        for ext in (".png", ".svg"):
            aliases[request + ext] = PREFIX + target
    for name, data in sorted((own or {}).items()):
        stem = _stem(name)
        result[PREFIX + name] = data
        requests = {stem} | {_stem(link) for link, target in coverage.links.items() if _stem(target) == stem}
        for request in requests:
            for ext in (".png", ".svg"):
                aliases[request + ext] = PREFIX + name
    result["links.txt"] = ("# HST Office Cổ điển: HST glyphs for requests Colibre does not resolve\n" + "".join(
        f"{key} {value}\n" for key, value in sorted(aliases.items()))).encode("utf-8")
    result["LICENSE-CC-BY-4.0.txt"] = files["LICENSE-CC-BY-4.0.txt"]
    result["COPYING.txt"] = notice.encode("utf-8") + files["COPYING.txt"]
    return result


NOTICE = (
    "HST Office \"Cổ điển\" icon style: the LibreOffice Colibre icons (colibre_svg /\n"
    "colibre_dark_svg, installed alongside, CC0 1.0, see their COPYING-ICONS) with the HST glyphs\n"
    "below for the commands Colibre does not draw. This archive holds only those HST glyphs,\n"
    "recoloured to Colibre's ink, and Colibre's Clear Direct Formatting icon redrawn with a white\n"
    "eraser (its letter and baseline stay Colibre's CC0 paths); everything else is loaded from Colibre.\n\n"
)
