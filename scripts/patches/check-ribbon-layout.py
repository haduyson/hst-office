#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Check the layout of the four HST ribbons (owner-locked 1.0.3 v3 design).

Usage: scripts/patches/check-ribbon-layout.py --tree DIR      (a tree with the whole series applied)
       scripts/patches/check-ribbon-layout.py --shots DIR     (ribbon screenshots [win-]<app>-w<width>-<tab>.png)

--tree checks the Tabbed notebookbar.ui of Writer, Sheets, Slides and Draw against data/ribbon/ribbon-v3.json
(ribbon_v3_tree_check.py: every tab, group and command of the design in its order and kind, each group's
"hst-ribbon-layout" valid, one command per cell, one caption, the 82 / 329 / 1,607 totals); the layout rules of the
running ribbon are checked on its dumps (tests/runtime/check-ribbon-v3-dumps.py). --shots measures every screenshot:
a body of --body px (default 106), the groups' caption line at one height (+-1 px) in every shot, separators 1 px
wide from 6 px under the body's top to 6 px over its bottom, the banner at least --min-banner px wide (default 340;
360 logical px, a little less where its artwork is white), and warns where --warn-room px (default 150) stay empty
right of the groups.
Exit code 0 when everything holds, 1 otherwise, 2 on a usage or read error.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ribbon_v3_tree_check as V3  # noqa: E402

SHOT = re.compile(r"^(?:win-)?(?P<app>[a-z]+)-w(?P<width>\d+)-.+\.png$")  # win-: shots taken on Windows
BAND = (62, 146)  # rows of the ribbon's group area in a screenshot of the window's top (tab row above)
SEPARATOR_INSET = 6  # px between a separator and the top or bottom of the body (mockup geometry_px)


# tabs, groups, commands of the v3 design: 1,604 of 1.0.2, the owner's "Công thức hoá học" (18/11/2026) in the
# Phông chữ group of Writer, Slides and Draw, the formula buttons and Writer's TeX toggle
EXPECTED_TOTALS = [82, 334, 1634]


def check_tree(tree):
    problems, totals = V3.check_tree(tree)
    for app, tab, group, text in problems:
        print(f"{app} {tab} {group}: {text}")
    failures = len(problems)
    if totals != EXPECTED_TOTALS:
        failures += 1
        print(f"v3 totals {totals} are not {EXPECTED_TOTALS} (tabs, groups, commands)")
    print(f"ribbon layout (v3): {failures} problem(s); {totals[0]} tabs, {totals[1]} groups, {totals[2]} commands")
    return failures


def page_colour(image):
    """Colour of the ribbon page (theme dependent): the commonest one of its left margin, before the first group."""
    from collections import Counter
    pixels = image.load()
    top, bottom = BAND
    return Counter(pixels[x, y][:3] for x in range(9, 15) for y in range(top, bottom)).most_common(1)[0][0]


def plain_column(image, x, colour):
    pixels, (top, bottom) = image.load(), BAND
    return all(pixels[x, y][:3] == colour for y in range(top, bottom, 2))


def page_end(image):
    """x of the last column of the ribbon page (page colour all down the group band), left of the banner."""
    colour, x = page_colour(image), image.size[0] - 2
    while x > 0 and not plain_column(image, x, colour):
        x -= 1
    return x


def banner_width(image):
    """Width of the banner right of the page: the columns there in which some pixel of the group band differs
    from the window's background (the colour at the right edge; the banner's artwork may be white inside)."""
    width, _ = image.size
    pixels = image.load()
    top, bottom = BAND
    background = pixels[width - 2, top][:3]
    rows = range(top, bottom, 2)
    return sum(1 for x in range(page_end(image) + 1, width - 1)
               if any(pixels[x, y][:3] != background for y in rows))


def free_room(image):
    """Empty width at the right end of the ribbon page: the run of plain columns that ends where the page ends."""
    colour = page_colour(image)
    x = end = page_end(image)
    while x > 0 and plain_column(image, x, colour):
        x -= 1
    return end - x


def body(image):
    """(top, height) of the ribbon body: the longest run of the page colour down its left padding."""
    pixels, colour = image.load(), page_colour(image)
    x = 2 + next((x for x in range(image.size[0]) if pixels[x, sum(BAND) // 2][:3] == colour), 0)
    best, start = (0, 0), None
    for y in range(image.size[1] + 1):
        if y < image.size[1] and pixels[x, y][:3] == colour:
            start = y if start is None else start
        elif start is not None:
            best, start = max(best, (start, y - start), key=lambda run: run[1]), None
    return best


def caption_line(image, top, height):
    """Caption baseline (row from the body's top): the lowest row of the caption band with 40 % of the dark pixels
    of its darkest row (descenders hold few)."""
    pixels, end = image.load(), page_end(image)
    rows = range(top + height - 24, top + height)
    counts = [sum(1 for x in range(end) if sum(pixels[x, y][:3]) < 3 * 140) for y in rows]
    peak = max(counts, default=0)
    return max((y - top for y, n in zip(rows, counts) if peak and n >= 0.4 * peak), default=None)


def separators(image, top, height):
    """(x, width, first row, last row) of the group separators: lines of the page off its colour from 15 % to 85 %
    of the body's height (a gallery's border ends higher), not from its top to its bottom (the page's end)."""
    pixels, colour, end = image.load(), page_colour(image), page_end(image)
    left = next((x for x in range(end) if pixels[x, top + height // 2][:3] == colour), end)
    rows = range(top + height * 15 // 100, top + height * 85 // 100)
    out = []
    for x in (x for x in range(left, end) if all(pixels[x, y][:3] != colour for y in rows)):
        column = [pixels[x, y][:3] != colour for y in range(top, top + height)]
        if out and out[-1][0] + out[-1][1] == x:
            out[-1][1] += 1
        elif not (column[0] and column[-1]):
            out.append([x, 1, column.index(True), len(column) - 1 - column[::-1].index(True)])
    return [tuple(line) for line in out]


def geometry_failures(name, image, expected, captions):
    """Body and separator failures of one screenshot; its caption line goes into captions."""
    top, height = body(image)
    if abs(height - expected) > 1:
        return [f"{name}: ribbon body {height} px high (expected {expected})"]
    out = []
    for x, width, first, last in separators(image, top, height):
        if width != 1 or abs(first - SEPARATOR_INSET) > 1 or abs(height - 1 - last - SEPARATOR_INSET) > 1:
            out.append(f"{name}: separator at x {x}: {width} px wide, rows {first}-{last} of {height}")
    captions[name] = caption_line(image, top, height)
    return out


def caption_failures(captions):
    """Screenshots whose caption line is more than 1 px off the commonest one."""
    values = sorted(line for line in captions.values() if line is not None)
    common = max(set(values), key=values.count) if values else 0
    return [f"{name}: caption line at row {line} of the body (the others at {common})"
            for name, line in sorted(captions.items()) if line is not None and abs(line - common) > 1]


def check_shots(folder, minimum, room, expected_body=106):
    try:
        from PIL import Image
    except ImportError:
        print("--shots needs Pillow (python3-pil)", file=sys.stderr)
        return None
    failures = checked = warnings = 0
    captions, geometry = {}, []
    for name in sorted(os.listdir(folder)):
        if not SHOT.match(name):
            continue
        checked += 1
        with Image.open(os.path.join(folder, name)) as image:
            rgb = image.convert("RGB")
            width, empty = banner_width(rgb), free_room(rgb)
            geometry += geometry_failures(name, rgb, expected_body, captions)
        if width < minimum:
            failures += 1
            print(f"{name}: banner {width} px wide (at least {minimum})")
        if empty >= room:  # a warning: a tab whose groups are all open may leave room; one with a folded group
            warnings += 1  # should not (fitByPriority opens every folded group that fits)
            print(f"{name}: warning: {empty} px empty right of the groups")
    geometry += caption_failures(captions)
    print("\n".join(geometry + [f"ribbon geometry: {len(geometry)} failure(s) (body, caption line, separators)"]))
    print(f"ribbon banner: {failures} of {checked} screenshot(s) without the banner; "
          f"{warnings} with at least {room} px empty right of the groups (look for a folded group there)")
    return failures + len(geometry) if checked else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree")
    parser.add_argument("--shots")
    parser.add_argument("--min-banner", type=int, default=340)
    parser.add_argument("--warn-room", type=int, default=150)
    parser.add_argument("--body", type=int, default=106)
    args = parser.parse_args()
    if not args.tree and not args.shots:
        parser.error("give --tree, --shots or both")
    failures = 0
    try:
        if args.tree:
            failures += check_tree(args.tree)
        if args.shots:
            result = check_shots(args.shots, args.min_banner, args.warn_room, args.body)
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
