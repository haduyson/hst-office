#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check the layout of the four HST ribbons (owner decision of 13/11/2026).

Usage: scripts/patches/check-ribbon-layout.py --tree DIR      (a tree with the whole series applied)
       scripts/patches/check-ribbon-layout.py --shots DIR     (ribbon screenshots <app>-w<width>-<tab>.png)

--tree checks the widget tree of the Tabbed notebookbar.ui of Writer, Sheets, Slides and Draw against the
rules of ribbon_layout_rules.py: a group of one to three commands shows large buttons filling its height, no
small button sits alone in its column, small items keep to the two rows of their group.
--shots checks that the HST banner is drawn at the right end of the ribbon in every screenshot, at least
--min-banner pixels wide (default 200: the banner never hides and never turns compact; it narrows down to
260 logical px, measured a little narrower where its artwork is white).
Exit code 0 when everything holds, 1 otherwise, 2 on a usage or read error.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ribbon_layout_rules as R  # noqa: E402

SHOT = re.compile(r"^(?P<app>[a-z]+)-w(?P<width>\d+)-.+\.png$")
BAND = (62, 146)  # rows of the ribbon's group area in a screenshot of the window's top (tab row above)


def check_tree(tree):
    failures = 0
    for app, path in R.RIBBONS.items():
        full = os.path.join(tree, path)
        for group, rule, items, text in R.check_file(full):
            failures += 1
            print(f"{app} {group.tab} {group.id}: {rule}: {text} ({', '.join(item.id for item in items)})")
    print(f"ribbon layout: {failures} broken rule(s) in {len(R.RIBBONS)} ribbons")
    return failures


def banner_width(image):
    """Width of the banner at the right end of the ribbon: the run of columns, from the right, in which the
    group band is neither the window's background (the colour at the right edge) nor the white of the ribbon
    page; the banner is drawn on the window's background, right of the page."""
    width, _ = image.size
    pixels = image.load()
    top, bottom = BAND
    background = pixels[width - 2, top]
    rows = range(top, bottom, 2)
    run = 0
    for x in range(width - 2, max(0, width - 800), -1):
        column = [pixels[x, y][:3] for y in rows]
        plain = sum(1 for c in column if c == background) + sum(1 for c in column if c == (255, 255, 255))
        if plain * 10 <= len(column) * 8:
            run += 1
        elif run >= 40:
            break
        elif plain == len(column) and run:
            run = 0
    return run


def check_shots(folder, minimum):
    try:
        from PIL import Image
    except ImportError:
        print("--shots needs Pillow (python3-pil)", file=sys.stderr)
        return None
    failures = checked = 0
    for name in sorted(os.listdir(folder)):
        if not SHOT.match(name):
            continue
        checked += 1
        with Image.open(os.path.join(folder, name)) as image:
            width = banner_width(image.convert("RGB"))
        if width < minimum:
            failures += 1
            print(f"{name}: banner {width} px wide (at least {minimum})")
    print(f"ribbon banner: {failures} of {checked} screenshot(s) without the banner")
    return failures if checked else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree")
    parser.add_argument("--shots")
    parser.add_argument("--min-banner", type=int, default=200)
    args = parser.parse_args()
    if not args.tree and not args.shots:
        parser.error("give --tree, --shots or both")
    failures = 0
    try:
        if args.tree:
            failures += check_tree(args.tree)
        if args.shots:
            result = check_shots(args.shots, args.min_banner)
            if result is None:
                print(f"{args.shots}: no ribbon screenshot checked", file=sys.stderr)
                return 2
            failures += result
    except (OSError, ValueError) as error:
        print(f"cannot check the ribbon layout: {error}", file=sys.stderr)
        return 2
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
