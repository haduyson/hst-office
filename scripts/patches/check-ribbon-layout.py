#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check the layout of the four HST ribbons (owner decision of 13/11/2026).

Usage: scripts/patches/check-ribbon-layout.py --tree DIR      (a tree with the whole series applied)
       scripts/patches/check-ribbon-layout.py --shots DIR     (ribbon screenshots [win-]<app>-w<width>-<tab>.png)

--tree checks the widget tree of the Tabbed notebookbar.ui of Writer, Sheets, Slides and Draw against the
rules of ribbon_layout_rules.py: a group of one to three commands shows large buttons filling its height, no
small button sits alone in its column, small items keep to the two rows of their group.
--shots checks that the HST banner is drawn at the right end of the ribbon in every screenshot, at least
--min-banner pixels wide (default 200: the banner never hides and never turns compact; it narrows down to
260 logical px, measured a little narrower where its artwork is white), and warns where at least --warn-room px
(default 150) stay empty right of the groups: a folded group there would break the regrow rule (a group is never
a "Caption ▾" button beside room enough to show it; enforced on the algorithm by tests/unit/test_ribbon_regrow.py).
Exit code 0 when everything holds, 1 otherwise, 2 on a usage or read error.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ribbon_layout_rules as R  # noqa: E402

SHOT = re.compile(r"^(?:win-)?(?P<app>[a-z]+)-w(?P<width>\d+)-.+\.png$")  # win-: shots taken on Windows
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


def page_colour(image):
    """Background colour of the ribbon page (white with the Linux theme, a light grey on Windows): the commonest
    colour of its left margin, before the first group (a gallery's white box may fill much of the page)."""
    from collections import Counter
    pixels = image.load()
    top, bottom = BAND
    return Counter(pixels[x, y][:3] for x in range(9, 15) for y in range(top, bottom)).most_common(1)[0][0]


def plain_column(image, x, colour):
    pixels = image.load()
    top, bottom = BAND
    return all(pixels[x, y][:3] == colour for y in range(top, bottom, 2))


def page_end(image):
    """x of the last column of the ribbon page (page colour all down the group band), left of the banner."""
    width, _ = image.size
    colour = page_colour(image)
    x = width - 2
    while x > 0 and not plain_column(image, x, colour):
        x -= 1
    return x


def banner_width(image):
    """Width of the banner right of the ribbon page: the columns there in which some pixel of the group band
    differs from the window's background (the colour at the right edge). The banner is drawn on the window's
    background, right of the page; its artwork may be white inside (as on Windows), its edges and text are not."""
    width, _ = image.size
    pixels = image.load()
    top, bottom = BAND
    background = pixels[width - 2, top][:3]
    rows = range(top, bottom, 2)
    return sum(1 for x in range(page_end(image) + 1, width - 1)
               if any(pixels[x, y][:3] != background for y in rows))


def free_room(image):
    """Empty width at the right end of the ribbon page, left of the banner: the run of all-white columns of the
    group band that ends where the page ends."""
    colour = page_colour(image)
    x = end = page_end(image)
    while x > 0 and plain_column(image, x, colour):
        x -= 1
    return end - x


def check_shots(folder, minimum, room):
    try:
        from PIL import Image
    except ImportError:
        print("--shots needs Pillow (python3-pil)", file=sys.stderr)
        return None
    failures = checked = warnings = 0
    for name in sorted(os.listdir(folder)):
        if not SHOT.match(name):
            continue
        checked += 1
        with Image.open(os.path.join(folder, name)) as image:
            rgb = image.convert("RGB")
            width, empty = banner_width(rgb), free_room(rgb)
        if width < minimum:
            failures += 1
            print(f"{name}: banner {width} px wide (at least {minimum})")
        if empty >= room:  # a warning: a tab whose groups are all open may leave room; one with a folded group
            warnings += 1  # should not (fitByPriority opens every folded group that fits)
            print(f"{name}: warning: {empty} px empty right of the groups")
    print(f"ribbon banner: {failures} of {checked} screenshot(s) without the banner; "
          f"{warnings} with at least {room} px empty right of the groups (look for a folded group there)")
    return failures if checked else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree")
    parser.add_argument("--shots")
    parser.add_argument("--min-banner", type=int, default=200)
    parser.add_argument("--warn-room", type=int, default=150)
    args = parser.parse_args()
    if not args.tree and not args.shots:
        parser.error("give --tree, --shots or both")
    failures = 0
    try:
        if args.tree:
            failures += check_tree(args.tree)
        if args.shots:
            result = check_shots(args.shots, args.min_banner, args.warn_room)
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
