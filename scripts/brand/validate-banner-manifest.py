#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Check a banner manifest (banners.json) and, optionally, its image files before publishing.

    validate-banner-manifest.py MANIFEST [--assets DIR] [--require-sizes] [--bundled]
    validate-banner-manifest.py --campaign DIR --id ID

MANIFEST mode runs the client's own parser (hst_office.banner_schema: schema 1, hosts, hashes, limits, and the
standard "sizes" variants), so whatever passes here is what an installed HST Office accepts. --assets DIR also
verifies every image whose file name (the last URL path segment, or the bundled relative path) exists in DIR:
exact byte size, SHA-256, static PNG/JPEG/WebP header and pixel dimensions; standard sizes must be PNG or JPEG.
Missing files are reported (pass --assets only when DIR holds the complete set). --require-sizes refuses items
without standard sizes (campaigns from 1.0.3 on must submit all of them).

--campaign mode checks an advertiser's submission before any manifest exists: DIR must contain
ID-360x96@1x, ID-360x96@2x, ID-640x96@1x, ID-640x96@2x, ID-960x96@1x and ID-960x96@2x (.png or .jpg), each at
most 300 KB with exact dimensions. Exit status 0 = valid, 1 = invalid (every problem is printed), 2 = usage.
"""
import argparse
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "extensions/hst-vietnamese-tools/python"))

from hst_office import banner_sizes  # noqa: E402
from hst_office.banner_image import inspect  # noqa: E402
from hst_office.banner_schema import image_specs, parse_manifest  # noqa: E402


def check_image(data, key, spec=None):
    """Problems of one image buffer for an image key ("1x", "c2x", "640@2x"); [] when valid."""
    problems = []
    if spec is not None:
        if len(data) != spec["size"]:
            problems.append("size %d bytes, manifest says %d" % (len(data), spec["size"]))
        if hashlib.sha256(data).hexdigest() != spec["sha256"]:
            problems.append("SHA-256 differs from the manifest")
    if len(data) > banner_sizes.MAX_IMAGE:
        problems.append("larger than 300 KB (%d bytes)" % len(data))
    try:
        suffix = inspect(data, key)
    except ValueError:
        want = banner_sizes.pixel_size(key)
        return problems + ["not a static PNG/JPEG/WebP of the required size%s" % (" %dx%d" % want if want else "")]
    if banner_sizes.pixel_size(key) and suffix not in banner_sizes.IMAGE_TYPES:
        problems.append("standard sizes must be PNG or JPEG")
    return problems


def check_manifest(path, assets=None, require_sizes=False, bundled=False):
    try:
        doc = parse_manifest(Path(path).read_bytes(), bundled=bundled)
    except (OSError, ValueError) as exc:
        return ["%s: %s" % (path, exc)]
    problems = []
    for item in doc["items"]:
        if require_sizes and not banner_sizes.has_sizes(item):
            problems.append("%s: no standard sizes (%s)" % (item["id"], ", ".join(map(str, banner_sizes.WIDTHS))))
        if assets is None:
            continue
        for key, spec in image_specs(item) + banner_sizes.size_specs(item):
            name = spec["url"] if bundled else spec["url"].rsplit("/", 1)[-1]
            file = Path(assets) / name
            if not file.is_file():
                problems.append("%s %s: missing file %s" % (item["id"], key, file))
                continue
            problems += ["%s %s: %s" % (item["id"], key, p) for p in check_image(file.read_bytes(), key, spec)]
    return problems


def check_campaign(directory, banner_id):
    problems = []
    for width in banner_sizes.WIDTHS:
        for scale in banner_sizes.SCALES:
            stem = "%s-%dx%d@%s" % (banner_id, width, banner_sizes.HEIGHT, scale)
            found = [Path(directory) / (stem + ext) for ext in (".png", ".jpg", ".jpeg")]
            found = [f for f in found if f.is_file()]
            if len(found) != 1:
                problems.append("%s: %s" % (stem, "missing (.png or .jpg)" if not found else "more than one file"))
                continue
            key = banner_sizes.size_key(width, scale)
            problems += ["%s: %s" % (found[0].name, p) for p in check_image(found[0].read_bytes(), key)]
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("manifest", nargs="?")
    parser.add_argument("--assets", help="directory holding the image files of the manifest")
    parser.add_argument("--require-sizes", action="store_true", help="every item must have standard sizes")
    parser.add_argument("--bundled", action="store_true", help="installed-defaults manifest (relative paths)")
    parser.add_argument("--campaign", help="directory of one advertiser submission")
    parser.add_argument("--id", help="banner id of the --campaign submission")
    args = parser.parse_args(argv)
    if bool(args.manifest) == bool(args.campaign) or (args.campaign and not args.id):
        parser.print_usage(sys.stderr)
        return 2
    if args.campaign:
        problems = check_campaign(args.campaign, args.id)
    else:
        problems = check_manifest(args.manifest, args.assets, args.require_sizes, args.bundled)
    for problem in problems:
        print(problem)
    print("OK" if not problems else "%d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
