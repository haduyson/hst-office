#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Validate the 72-shot matrix and store lossless evidence without duplicate PNGs.

Needs Pillow. Raw PNGs move to --raw-cache only after decoded pixels compare equal.
No resizing, cropping, retouching or palette reduction is used for committed shots.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=Path, required=True)
    parser.add_argument("--raw-cache", type=Path, required=True)
    parser.add_argument("--installed", type=Path, required=True,
                        help="untouched baseline snapshot actually used for capture")
    parser.add_argument("--preview", type=Path, required=True)
    parser.add_argument("--source-tree", type=Path)
    args = parser.parse_args()
    expected = {"writer": 164, "calc": 164, "impress": 203}
    expected_tabs = {"writer": {"Trang đầu", "Chèn", "Bố cục"},
                     "calc": {"Trang đầu", "Chèn", "Dữ liệu"},
                     "impress": {"Trang đầu", "Chèn", "Thiết kế"}}
    rows, measurements = [], {}
    for variant, mode, scale in itertools.product(("baseline", "hst"), ("light", "dark"), (100, 200)):
        path = args.shots / f"{variant}-{mode}-{scale}.json"
        found = json.loads(path.read_text())
        if len(found) != 9:
            raise ValueError(f"Incomplete matrix: {path}: {len(found)} rows")
        if {(r["app"], r["tab"]) for r in found} != {
                (app, tab) for app, names in expected_tabs.items() for tab in names}:
            raise ValueError(f"Missing or repeated app/tab: {path}")
        if len({r["shot"] for r in found}) != 9:
            raise ValueError(f"Repeated screenshot: {path}")
        for row in found:
            if row["selected"] != [row["tab"]]:
                raise ValueError(f"Wrong tab: {row}")
            top, end, banner = row["geometry_atspi"]
            if end - top != expected[row["app"]] or banner != [1112, 46, 360, 107]:
                raise ValueError(f"Geometry changed: {row}")
            shot = args.shots / row["shot"]
            with Image.open(shot) as image:
                if image.size != (1485 * scale // 100, 900 * scale // 100):
                    raise ValueError(f"Wrong screenshot dimensions: {shot}: {image.size}")
            rows.append(dict(row, variant=variant, mode=mode))
        measurements[path.stem] = found
    if len(rows) != 72:
        raise ValueError("Expected 72 matrix shots")
    args.raw_cache.mkdir(parents=True, exist_ok=True)
    converted = []
    for source in sorted(args.shots.glob("*.png")):
        target = source.with_suffix(".webp")
        with Image.open(source) as original:
            original = original.convert("RGBA")
            original.save(target, "WEBP", lossless=True, method=6, exact=True)
            with Image.open(target) as packed:
                if original.tobytes() != packed.convert("RGBA").tobytes():
                    raise ValueError(f"Pixel comparison failed: {source}")
        converted.append({"png": source.name, "png_sha256": sha(source), "webp": target.name,
                          "webp_sha256": sha(target), "pixels_identical": True})
        shutil.move(str(source), str(args.raw_cache / source.name))
    for path in args.shots.glob("*.json"):
        data = json.loads(path.read_text())
        if isinstance(data, list) and data and isinstance(data[0], dict) and "shot" in data[0]:
            for row in data:
                row["shot"] = str(Path(row["shot"]).with_suffix(".webp"))
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    ui = {}
    for part, module in (("sw", "swriter"), ("sc", "scalc"), ("sd", "simpress")):
        rel = f"share/config/soffice.cfg/modules/{module}/ui/notebookbar.ui"
        ui[module] = {"installed_sha256": sha(args.installed / rel), "preview_sha256": sha(args.preview / rel)}
        if args.source_tree:
            ui[module]["patched_source_sha256"] = sha(args.source_tree / f"{part}/uiconfig/{module}/ui/notebookbar.ui")
    previous = args.shots / "evidence.json"
    conversions = {row["png"]: row for row in json.loads(previous.read_text()).get("lossless_conversion", [])} if previous.exists() else {}
    conversions.update({row["png"]: row for row in converted})
    baseline_binary = sha(args.installed / "program/libmergedlo.so")
    preview_binary = sha(args.preview / "program/libmergedlo.so")
    if baseline_binary != preview_binary:
        raise ValueError("Baseline and preview must use the same binary for resource comparisons")
    result = {"matrix_shots": 72, "geometry_matches_baseline": True, "logical_heights": expected,
              "logical_banner": [1112, 46, 360, 107], "dpi": "GDK_SCALE=1/2; AT-SPI logical, captures physical",
              "ui": ui, "installed_versionrc": (args.installed / "program/versionrc").read_text(),
              "baseline_snapshot": str(args.installed.resolve()),
              "baseline_binary_sha256": baseline_binary,
              "preview_binary_sha256": preview_binary,
              "cpp_selector_rebuilt": False, "native_installers_built": False,
              "repo_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "archives": {p.name: {"bytes": p.stat().st_size, "sha256": sha(p)} for p in
                           (args.preview / "share/config").glob("images_hst*.zip")},
              "lossless_conversion": list(conversions.values())}
    (args.shots / "evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"72 captures match the baseline geometry; {len(converted)} lossless conversions verified")


if __name__ == "__main__":
    main()
