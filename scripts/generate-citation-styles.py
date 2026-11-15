#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Generate data/citation/styles/*.json from the style source in scripts/citation_styles_*.py.

Usage: python3 scripts/generate-citation-styles.py            (rewrite the JSON files)
       python3 scripts/generate-citation-styles.py --check    (fail when a committed file differs)
Edit the source modules, regenerate, then review the golden outputs (tests/unit/citation_golden.py).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # also under python -I
import citation_styles_apa_ieee  # noqa: E402
import citation_styles_chicago  # noqa: E402
import citation_styles_mla_iso  # noqa: E402
import citation_styles_nlm_harvard  # noqa: E402
import citation_styles_vn  # noqa: E402
from citation_styles_common import dump  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "citation", "styles")
ORDER = ("id", "name", "class", "description", "source", "options", "presets", "terms", "macros", "layouts",
         "alias", "notes")


def resolved_alias(data):
    """Alias table where every target is a layout of this style (chains and missing targets end in "default")."""
    result = {}
    for source, target in data.get("alias", {}).items():
        seen = set()
        while target not in data["layouts"] and target not in seen:
            seen.add(target)
            target = data["alias"].get(target, "default")
        if source not in data["layouts"]:
            result[source] = target if target in data["layouts"] else "default"
    return dict(sorted(result.items()))


def styles():
    found = {}
    for module in (citation_styles_vn, citation_styles_apa_ieee, citation_styles_nlm_harvard, citation_styles_chicago,
                   citation_styles_mla_iso):
        found.update(module.STYLES)
    return found


def rendered():
    """{file name: JSON text} of every style."""
    result = {}
    for style_id, data in styles().items():
        data = dict(data, presets=data.get("presets", []))
        data["layouts"] = {kind: [e for e in elements if e] for kind, elements in data["layouts"].items()}
        data["alias"] = resolved_alias(data)
        text = dump({key: data[key] for key in ORDER if key in data})
        json.loads(text)
        result[style_id + ".json"] = text
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare with the committed files instead of writing")
    parser.add_argument("--output", default=OUT)
    args = parser.parse_args()
    files = rendered()
    if args.check:
        on_disk = sorted(n for n in os.listdir(args.output) if n.endswith(".json"))
        stale = [n for n in files if not os.path.exists(os.path.join(args.output, n))
                 or open(os.path.join(args.output, n), encoding="utf-8").read() != files[n]]
        extra = sorted(set(on_disk) - set(files))
        for name in stale + extra:
            print("FAIL citation style out of date:", name)
        return 1 if stale or extra else 0
    os.makedirs(args.output, exist_ok=True)
    for name, text in files.items():
        with open(os.path.join(args.output, name), "w", encoding="utf-8") as handle:
            handle.write(text)
    print("wrote %d citation styles to %s" % (len(files), args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
