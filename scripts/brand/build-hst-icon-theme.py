#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build deterministic HST icon archives with Python's standard library only.

--out DIR writes images_hst{,_dark}.zip and unpacked themes for inspection.
--tree DIR stages the same resources for postprocess/images and the installers.
--check verifies bytes without writing. No generated files belong in git.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hst_icon_snap import snap_svg  # noqa: E402  (sibling module, standard library only)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "icon-themes-src/hst"
# Hand-tuned 16 px masters (viewBox 0 0 16 16, whole-pixel pens) of the Home and quick-access
# families; every other glyph and size is snapped from its 24-unit master by hst_icon_snap.
TUNED_16 = SOURCE / "glyphs/stage-1-16"
PALETTES = {"hst": "#294159", "hst_dark": "#DBE7F1"}
# Families with a "trademark" master show the HASON TECH mark in its brand blue: #0072BB is the
# official colour, #1A91CF the light end of the same app-icon gradient, legible on the dark ribbon.
MARK_COLOURS = {"hst": "#0072BB", "hst_dark": "#1A91CF"}
SIZES = (16, 24, 32)


def sized(key, size):
    stem = re.sub(r"^cmd/(?:32/|(?:sc|lc)_)?", "", key)
    return ("cmd/32/" if size == 32 else "cmd/" + ("sc_" if size == 16 else "lc_")) + stem


def svg_key(key):
    return str(PurePosixPath(key).with_suffix(".svg"))


def glyph_svg(master, size, colour):
    """Shipped SVG of one glyph: pixel-snapped strokes painted as filled outlines."""
    tuned = TUNED_16 / master.name
    native = size == 16 and master.parent.name == "stage-1" and tuned.is_file()
    source = (tuned if native else master).read_text(encoding="utf-8")
    return snap_svg(source, size, native=native).replace("currentColor", colour).encode("utf-8")


def resources(theme):
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
                files[target] = glyph_svg(master, size, colour)
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
            files[key] = glyph_svg(SOURCE / "glyphs/integration" / (glyph + ".svg"), size, PALETTES[theme])
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
    files["COPYING.txt"] = (
        "HST Ribbon Icons — HASON TECH, 2026, CC BY 4.0\n"
        "Copyright (c) 2026 Công ty TNHH Công nghệ Hà Sơn (HASON TECH).\n"
        "Command glyphs: original HST artwork, see LICENSE-CC-BY-4.0.txt, except the marks below.\n"
        "Source: https://github.com/haduyson/hst-office/tree/main/icon-themes-src/hst\n"
        "Licence: https://creativecommons.org/licenses/by/4.0/\n"
        "Changes: palette exports of the original masters, pixel-snapped per size (16/24/32 px,\n"
        "whole-pixel pens) with strokes painted as filled outlines; hand-tuned 16 px masters\n"
        "for the Home and quick-access glyphs (glyphs/stage-1-16).\n"
        "res/mainapp_*: existing HST Office application marks, copied unchanged from\n"
        "branding/icon-themes; these are HASON TECH trademarks, not CC BY glyphs.\n"
        "cmd/sc_showsolutions.svg, cmd/lc_showsolutions.svg, cmd/32/showsolutions.svg:\n"
        "the HASON TECH mark of res/mainapp_* in brand blue (branding/icon-themes/\n"
        "hasontech-mark.svg); a HASON TECH trademark, not a CC BY glyph.\n"
        "The artwork and source licences grant no trademark rights (see product NOTICE).\n"
        "Generator and mapping code: AGPL-3.0-only, in the source repository.\n"
    ).encode("utf-8")
    return files


def archive(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def sync(directory, files, check=False):
    expected = set(files)
    existing = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    errors = []
    for name in sorted(existing - expected):
        if check:
            errors.append(f"unexpected: {directory / name}")
        else:
            (directory / name).unlink()
    for name, data in files.items():
        path = directory / name
        if path.is_file() and path.read_bytes() == data:
            continue
        if check:
            errors.append(f"missing or stale: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
    if errors:
        raise ValueError("\n".join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--out", type=Path)
    target.add_argument("--tree", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    sizes = {}
    output = {}
    for theme in PALETTES:
        files = resources(theme)
        packed = archive(files)
        sizes[theme] = {"bytes": len(packed), "sha256": hashlib.sha256(packed).hexdigest(),
                        "entries": len(files)}
        if args.tree:
            # These two new directories are wholly generated by this script.
            sync(args.tree / "icon-themes" / theme, dict(files, **{"images.zip": packed}), args.check)
        else:
            output[f"images_{theme}.zip"] = packed
            output.update({f"{theme}/{name}": data for name, data in files.items()})
    if args.out:
        output["sizes.json"] = (json.dumps(sizes, indent=2) + "\n").encode()
        sync(args.out, output, args.check)
    print(json.dumps(sizes, indent=2))


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        sys.exit(str(error))
