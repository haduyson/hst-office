# SPDX-License-Identifier: AGPL-3.0-only
"""Verify HST brand assets and scan an install tree for leftover upstream product names.

Usage:
  python3 scripts/check-branding.py                       # asset checks only
  python3 scripts/check-branding.py --install-root DIR --allowlist branding/brand-audit-allowlist.json
  python3 scripts/check-branding.py --install-root DIR --release 1.0.1   # also the OS-visible version fields
Exit 0 = clean, 1 = problems (asset errors or non-allowlisted name hits), 2 = bad arguments.
A text scan cannot detect embedded third-party logos; review rendered screens separately.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brand.audit import check_assets, check_version_fields, load_allowlist, scan_tree  # noqa: E402
from brand.common import ROOT, SPEC_PATH  # noqa: E402

DEFAULT_ALLOWLIST = os.path.join(ROOT, "branding", "brand-audit-allowlist.json")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install-root", help="directory tree to scan (build instdir or install dir)")
    parser.add_argument("--allowlist", default=DEFAULT_ALLOWLIST)
    parser.add_argument("--root", default=ROOT, help="repo root holding the generated assets")
    parser.add_argument("--max-report", type=int, default=50, help="max hits printed")
    parser.add_argument("--release", help="HST release id the OS-visible version fields must carry "
                                          "(.desktop, AppStream metainfo, macOS Info.plist); needs --install-root")
    args = parser.parse_args(argv)
    if args.release and not args.install_root:
        print("--release needs --install-root", file=sys.stderr)
        return 2

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
        if args.release:
            problems = check_version_fields(args.install_root, args.release)
            for problem in problems[:args.max_report]:
                print(f"VERSION: {problem}", file=sys.stderr)
            print("version fields: " + ("FAIL" if problems else "ok"))
            failed |= bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
