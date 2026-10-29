# SPDX-License-Identifier: AGPL-3.0-only
"""Verify HST brand assets and scan an install tree for leftover upstream product names.

Usage:
  python3 scripts/check-branding.py                       # asset checks only
  python3 scripts/check-branding.py --install-root DIR --allowlist branding/brand-audit-allowlist.json
Exit 0 = clean, 1 = problems (asset errors or non-allowlisted name hits), 2 = bad arguments.
A text scan cannot detect embedded third-party logos; review rendered screens separately.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brand.audit import check_assets, load_allowlist, scan_tree  # noqa: E402
from brand.common import ROOT, SPEC_PATH  # noqa: E402

DEFAULT_ALLOWLIST = os.path.join(ROOT, "branding", "brand-audit-allowlist.json")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install-root", help="directory tree to scan (build instdir or install dir)")
    parser.add_argument("--allowlist", default=DEFAULT_ALLOWLIST)
    parser.add_argument("--root", default=ROOT, help="repo root holding the generated assets")
    parser.add_argument("--max-report", type=int, default=50, help="max hits printed")
    args = parser.parse_args(argv)

    with open(SPEC_PATH, encoding="utf-8") as handle:
        spec = json.load(handle)
    failed = False
    errors = check_assets(spec, args.root)
    for error in errors:
        print(f"ASSET: {error}", file=sys.stderr)
    failed |= bool(errors)
    print("assets: " + ("FAIL" if errors else "ok"))

    if args.install_root:
        if not os.path.isdir(args.install_root):
            print(f"not a directory: {args.install_root}", file=sys.stderr)
            return 2
        hits, scanned = scan_tree(args.install_root, load_allowlist(args.allowlist))
        for rel, line, excerpt in hits[:args.max_report]:
            print(f"NAME: {rel}:{line}: {excerpt}", file=sys.stderr)
        print(f"scan: {scanned} files, {len(hits)} non-allowlisted hits")
        failed |= bool(hits)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
