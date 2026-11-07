#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check a delivered batch of colourful HST masters and take the files that pass.

intake-hst-modern-batch.py BATCH_DIR [--apply]
BATCH_DIR has the delivery layout (glyphs/<stage dir>/<glyph>.svg, metadata/palette.json,
metadata/batch-<N>.json). Each master must replace an existing classic master of the same name
and pass hst_modern_icons.violations(). Without --apply nothing is written; with it, passing
masters (and the palette, when valid) are copied into icon-themes-src/hst-modern/. Prints a
JSON report; exit status 1 when any file was rejected.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hst_modern_icons as modern  # noqa: E402

CLASSIC = modern.MODERN.parent / "hst"
TUNED = {"stage-1-16": 16, "stage-1-24": 24}  # hand-tuned masters drawn in target pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("batch", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        colours = modern.palette.__wrapped__(args.batch)
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({"palette": f"rejected: {error}"}, indent=2))
        return 1
    known = modern.palette.__wrapped__(modern.MODERN) if (modern.MODERN / "metadata/palette.json").is_file() else {}
    changed = {k: (known[k], v) for k, v in colours.items() if k in known and known[k] != v}
    report = {"accepted": [], "rejected": {}, "palette_changes": changed}
    for path in sorted((args.batch / "glyphs").rglob("*.svg")):
        relative = path.relative_to(args.batch / "glyphs")
        tuned = TUNED.get(relative.parent.name)
        if tuned:
            # a hand-tuned size of any stage's master: the classic master may sit in any stage dir
            found = [p for p in (CLASSIC / "glyphs").glob(f"stage-[0-9]*/{relative.name}") if p.parent.name not in TUNED]
            found += list((CLASSIC / "glyphs/integration").glob(relative.name))
            classic = found[0] if found else CLASSIC / "glyphs" / relative
        else:
            classic = CLASSIC / "glyphs" / relative
        problems = [] if classic.is_file() else [f"no classic master glyphs/{relative} of that name"]
        problems += modern.violations(path.read_text(encoding="utf-8"), colours, tuned or 24, tuned=bool(tuned))
        if problems:
            report["rejected"][str(relative)] = problems
            continue
        report["accepted"].append(str(relative))
        if args.apply:
            target = modern.MODERN / "glyphs" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    if args.apply and report["accepted"]:
        (modern.MODERN / "metadata").mkdir(parents=True, exist_ok=True)
        merged = json.loads((modern.MODERN / "metadata/palette.json").read_text()) if known else {}
        merged.update(json.loads((args.batch / "metadata/palette.json").read_text()))
        (modern.MODERN / "metadata/palette.json").write_text(json.dumps(merged, indent=2) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["rejected"] else 0


if __name__ == "__main__":
    sys.exit(main())
