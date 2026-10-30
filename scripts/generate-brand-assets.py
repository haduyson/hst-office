# SPDX-License-Identifier: AGPL-3.0-only
"""Generate HST Office brand assets from the owner-provided HASON TECH logo.

The blue "HS" triangle mark is copied pixel-for-pixel from the source; only the
"HASON TECH" wordmark is replaced by "HST OFFICE". Application icons are derived from the
tile masters in branding/icons/app. Outputs: logo/mark/plugin icons, desktop app icons,
LibreOffice --with-branding inputs, Windows .ico, macOS .icns, per-module Windows app icons
and the icon-theme window icon (mainapp).
All outputs are deterministic (no timestamps) so --check can compare bytes.

Usage:
  python3 scripts/generate-brand-assets.py          # write outputs
  python3 scripts/generate-brand-assets.py --check  # render, compare, exit 1 on drift
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brand.app_icons import build_app_icons, load_masters  # noqa: E402
from brand.common import ROOT, SPEC_PATH  # noqa: E402
from brand.legacy import build_core, load_source  # noqa: E402
from brand.lo_branding import build_lo_branding  # noqa: E402
from brand.platform_icons import build_platform_icons  # noqa: E402
from brand.start_center_banner import build_start_center_banner  # noqa: E402
from brand.windows_icons import build_windows_icons  # noqa: E402


def build_assets(spec):
    outputs, logo, mark, _square = build_core(spec, load_source(spec))
    masters = load_masters(spec)
    outputs.update(build_app_icons(spec, masters))
    outputs.update(build_lo_branding(spec, mark, logo))
    outputs.update(build_platform_icons(spec, masters))
    outputs.update(build_start_center_banner(spec, mark))
    outputs.update(build_windows_icons(spec, masters))
    return outputs


def _same(path, data):
    with open(path, "rb") as handle:
        return handle.read() == data


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify committed outputs are current")
    args = parser.parse_args()
    with open(SPEC_PATH, encoding="utf-8") as handle:
        spec = json.load(handle)
    outputs = build_assets(spec)

    drift = []
    for rel_path, data in sorted(outputs.items()):
        path = os.path.join(ROOT, rel_path)
        if args.check:
            if not os.path.exists(path) or _same(path, data) is False:
                drift.append(rel_path)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
        print(f"wrote {rel_path} {hashlib.sha256(data).hexdigest()[:16]}")
    if drift:
        print("Brand assets out of date:", ", ".join(drift), file=sys.stderr)
        return 1
    if args.check:
        print(f"brand assets up to date ({len(outputs)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
