#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build deterministic HST icon archives with Python's standard library only.

--out DIR writes images_<theme>.zip and unpacked themes for inspection.
--tree DIR stages the same resources for postprocess/images and the installers.
--check verifies bytes without writing. No generated files belong in git.
Themes: hst* (HST glyphs), hst_modern* (colourful, the option), hst_classic* ("Cổ điển", the default: Colibre
plus HST glyphs where it has none; needs the tree, --tree or --lo-tree, for Colibre's coverage).
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hst_classic_icons as classic  # noqa: E402  (sibling modules, standard library only)
import hst_modern_icons as modern  # noqa: E402
from hst_icon_pack import COPYING, archive, sync  # noqa: E402,F401  (sync: also used by the tests)
from hst_icon_snap import snap_svg  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "icon-themes-src/hst"
# Ink per theme. hst_modern* is the colourful style: modern masters where drawn (missing ones are
# listed and substituted by the classic glyph until --require-modern gates the release).
# The colourful style takes its darker ink (and heavier 16 px pen) from hst-modern/metadata/ink.json.
PALETTES = {"hst": "#294159", "hst_dark": "#DBE7F1", "hst_modern": modern.ink()["light"],
            "hst_modern_dark": modern.ink()["dark"]}
PALETTES.update({theme: ink for theme, (_, _, ink) in classic.CLASSIC.items()})
FULL_THEMES = [theme for theme in PALETTES if theme not in classic.CLASSIC]  # self-contained archives
MISSING_MODERN = set()
# Families with a "trademark" master show the HASON TECH mark in its brand blue: #0072BB is the
# official colour, #1A91CF the light end of the same app-icon gradient, legible on the dark ribbon.
MARK_COLOURS = {"hst": "#0072BB", "hst_dark": "#1A91CF", "hst_modern": "#0072BB", "hst_modern_dark": "#1A91CF",
                "hst_classic": "#0072BB", "hst_classic_dark": "#1A91CF"}
SIZES = (16, 24, 32)


def sized(key, size):
    stem = re.sub(r"^cmd/(?:32/|(?:sc|lc)_)?", "", key)
    return ("cmd/32/" if size == 32 else "cmd/" + ("sc_" if size == 16 else "lc_")) + stem


def svg_key(key):
    return str(PurePosixPath(key).with_suffix(".svg"))


def glyph_svg(master, size, colour, theme="hst"):
    """Shipped SVG of one glyph: pixel-snapped strokes painted as filled outlines.

    Hand-tuned masters drawn in target pixels (glyphs/stage-1-16, glyphs/stage-1-24) replace the
    snapped 24-unit master for that size."""
    root, colours = SOURCE, None
    if theme.startswith("hst_modern"):
        drawn = modern.master(master)
        if drawn is None:
            MISSING_MODERN.add(master.stem)
        else:
            root, master, colours = modern.MODERN, drawn, modern.palette()
            problems = modern.violations(drawn.read_text(encoding="utf-8"), colours)
            if problems:
                raise ValueError(f"{drawn}: " + "; ".join(problems))
    tuned = root / f"glyphs/stage-1-{size}" / master.name
    if colours is not None and not tuned.is_file() and not modern.HEX.search(master.read_text(encoding="utf-8")):
        tuned = SOURCE / f"glyphs/stage-1-{size}" / master.name  # ink-only: the classic tuning is the same art
    native = size in (16, 24) and tuned.is_file()
    if native and colours is not None and tuned.is_relative_to(modern.MODERN):
        problems = modern.violations(tuned.read_text(encoding="utf-8"), colours, size, tuned=True)
        if problems:
            raise ValueError(f"{tuned}: " + "; ".join(problems))
    heavy = theme.startswith("hst_modern") and modern.ink()["heavy16"]
    svg = snap_svg((tuned if native else master).read_text(encoding="utf-8"), size, native=native, heavy=heavy)
    if colours is not None:
        svg = modern.recolour(svg, colours, theme.endswith("_dark"))
    return svg.replace("currentColor", colour).encode("utf-8")


def resources(theme, icon_themes=None):
    """Archive files of `theme`; icon_themes (the tree's icon-themes/) is needed for hst_classic*."""
    if theme in classic.CLASSIC:
        if icon_themes is None:
            raise ValueError(f"{theme} needs the LibreOffice tree (--tree or --lo-tree) for Colibre's coverage")
        coverage = classic.Coverage(icon_themes, classic.CLASSIC[theme][1])
        return classic.overlay(_resources(theme), coverage, classic.NOTICE)
    return _resources(theme)


def _resources(theme):
    families = json.loads((SOURCE / "metadata/families.json").read_text())
    lock = json.loads((ROOT / "upstream/libreoffice-lock.json").read_text())
    naming = json.loads((SOURCE / "metadata/upstream-paths.json").read_text())
    if lock["gitCommit"] != naming["commit"]:
        raise ValueError("Upstream pin changed; re-audit the icon names first")
    files, links = {}, {}
    for family in families:
        if family.get("skip"):
            continue
        if family.get("trademark"):
            master, colour = ROOT / family["trademark"], MARK_COLOURS[theme]
        else:
            master, colour = SOURCE / f'glyphs/stage-{family["stage"]}/{family["glyph"]}.svg', PALETTES[theme]
        source = master.read_text(encoding="utf-8")
        xml = ET.fromstring(source)
        if xml.get("viewBox") != "0 0 24 24":
            raise ValueError(f"Unexpected viewBox: {master}")
        for size in SIZES:
            target = svg_key(sized(family["family"], size))
            if family.get("trademark"):
                # The HASON TECH mark is a filled logo, shipped as drawn (not CC BY artwork).
                files[target] = source.replace("currentColor", colour).replace(
                    'width="24" height="24"', f'width="{size}" height="{size}"', 1).encode("utf-8")
            else:
                files[target] = glyph_svg(master, size, colour, theme)
            keys = [sized(key, size) for key in family["keys"]]
            keys += [key for key, native in family.get("fixed_aliases", {}).items() if int(native) == size]
            # VCL tries PNG first, then SVG. Keep both request spellings, with
            # direct targets only (packimages and VCL do not follow link chains).
            for key in keys + [sized(family["family"], size)]:
                for alias in (key, svg_key(key)):
                    if alias == target:
                        continue
                    if alias in links and links[alias] != target:
                        raise ValueError(f"Conflicting alias: {alias}")
                    links[alias] = target
    integration = json.loads((SOURCE / "metadata/integration-map.json").read_text())
    for glyph in integration["command_glyphs"]:
        for size in SIZES:
            key = sized("cmd/" + glyph + ".svg", size)
            files[key] = glyph_svg(SOURCE / "glyphs/integration" / (glyph + ".svg"), size, PALETTES[theme], theme)
    for alias, target in integration["command_aliases"].items():
        for size in SIZES:
            for ext in ("png", "svg"):
                links[sized("cmd/" + alias + "." + ext, size)] = sized("cmd/" + target + ".svg", size)
    for alias, target in integration["fixed_aliases"].items():
        links[alias] = target
        links[svg_key(alias)] = target
    for key, glyph in integration["fixed_glyphs"].items():
        files[key] = (SOURCE / "glyphs/integration" / (glyph + ".svg")).read_text(encoding="utf-8").replace(
            "currentColor", PALETTES[theme]).encode()
    for size in (16, 24, 32, 48):
        files[f"res/mainapp_{size}.svg"] = (ROOT / f"branding/icon-themes/mainapp-{size}.svg").read_text(encoding="utf-8").encode()
    for alias, target in links.items():
        if target not in files or target in links or alias in files:
            raise ValueError(f"Invalid alias: {alias} -> {target}")
    files["links.txt"] = ("# HST Office: direct VCL resource aliases\n" + "".join(
        f"{key} {value}\n" for key, value in sorted(links.items()))).encode()
    files["LICENSE-CC-BY-4.0.txt"] = (SOURCE / "LICENSE-CC-BY-4.0.txt").read_text(encoding="utf-8").encode()
    files["COPYING.txt"] = COPYING.encode("utf-8")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--out", type=Path)
    target.add_argument("--tree", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--lo-tree", type=Path,
                        help="LibreOffice source tree whose Colibre the Cổ điển themes overlay (--out only)")
    parser.add_argument("--require-modern", action="store_true",
                        help="release gate: fail unless every HST master has its colourful version")
    args = parser.parse_args()
    sizes = {}
    output = {}
    icon_themes = next((tree / "icon-themes" for tree in (args.tree, args.lo_tree) if tree), None)
    themes = list(PALETTES) if icon_themes else FULL_THEMES
    if not icon_themes:
        print("hst_classic*: skipped, pass --lo-tree to build them", file=sys.stderr)
    for theme in themes:
        files = resources(theme, icon_themes)
        packed = archive(files)
        sizes[theme] = {"bytes": len(packed), "sha256": hashlib.sha256(packed).hexdigest(),
                        "entries": len(files)}
        if args.tree:
            # These theme directories are wholly generated by this script.
            sync(args.tree / "icon-themes" / theme, dict(files, **{"images.zip": packed}), args.check)
        else:
            output[f"images_{theme}.zip"] = packed
            output.update({f"{theme}/{name}": data for name, data in files.items()})
    if args.out:
        output["sizes.json"] = (json.dumps(sizes, indent=2) + "\n").encode()
        sync(args.out, output, args.check)
    print(json.dumps(sizes, indent=2))
    if MISSING_MODERN:
        message = f"hst_modern: {len(MISSING_MODERN)} masters still use the classic glyph"
        if args.require_modern:
            raise ValueError(message + ": " + " ".join(sorted(MISSING_MODERN)))
        print(message, file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        sys.exit(str(error))
