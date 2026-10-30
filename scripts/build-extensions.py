#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build the bundled LibreOffice extensions (.oxt) deterministically.

Usage: python3 scripts/build-extensions.py --output dist/extensions [--verify-reproducible] [--update-test-mode]

Each extensions/<name>/ directory becomes <name>.oxt. Shared data from data/vietnamese/ (and data/hst/solutions.json for the welcome dialog) is copied into the
package (data/), the brand images of the welcome dialog and user guide into icons/, the AGPL licence and a generated notice file go into license/. ZIP entries are sorted, use a
fixed timestamp and permissions, so two builds of the same tree are byte-identical.
data/hst/release.json (release id, e.g. 1.0.0-beta.2; core must equal /VERSION) becomes data/release.json, read by
the update check. --update-test-mode marks that copy so the update check accepts a local http://127.0.0.1 test
server (HST_UPDATE_TEST_URL); never use it for release packages (scripts/check-extensions.py rejects them).
"""
import argparse
import hashlib
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(ROOT, "extensions")
SHARED_DATA = ("nd30.json", "number-formats.json", "encoding-maps.json", "provenance.json")
# Brand images shown by the welcome dialog and the offline user guide (help/index.html): copied from
# assets/brand at build time so the package always carries the current HST artwork.
BRAND_IMAGES = {
    "icons/hst-office-logo.png": "assets/brand/hst-office-logo.png",
    "icons/hst-writer-64.png": "assets/brand/icons/hst-writer-64.png",
    "icons/hst-sheets-64.png": "assets/brand/icons/hst-sheets-64.png",
    "icons/hst-slides-64.png": "assets/brand/icons/hst-slides-64.png",
}
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
SKIP_DIRS = {"__pycache__", ".git"}
SKIP_SUFFIX = (".pyc", ".pyo", "~")


def notices_text():
    prov = json.load(open(os.path.join(ROOT, "data", "vietnamese", "provenance.json"), encoding="utf-8"))
    lines = ["HST Vietnamese tools - notices", "",
             "Code: GNU Affero General Public License v3.0 (license/LICENSE.txt). Based on LibreOffice (The Document Foundation).", "",
             "Legacy encoding tables (data/encoding-maps.json) were derived from, and cross-checked against, these sources",
             "(factual character mappings; see docs/ENCODING_SOURCES.md in the source tree for the procedure):"]
    for name, src in sorted(prov["sources"].items()):
        lines.append("  - %s: %s (sha256 %s)" % (name, src.get("url") or src.get("path"), src["sha256"]))
    lines += ["", "ND30 rules: Nghi dinh 30/2020/ND-CP, Phu luc I; legal validity in 2026 is unverified. Presentation helper only."]
    return "\n".join(lines) + "\n"


def release_json(test_mode=False):
    """data/hst/release.json for the package; refuses a release id whose core differs from /VERSION."""
    info = json.load(open(os.path.join(ROOT, "data", "hst", "release.json"), encoding="utf-8"))
    release = info["release"]
    version = open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()
    if release.split("+")[0].split("-")[0] != version:
        raise SystemExit("data/hst/release.json release %r does not match /VERSION %r" % (release, version))
    stamp = {"release": release}
    if test_mode:
        stamp["update_test_mode"] = True
    return (json.dumps(stamp, sort_keys=True, indent=1) + "\n").encode("utf-8")


def collect(ext_root, test_mode=False):
    """{archive_name: bytes} for one extension directory."""
    files = {}
    for base, dirs, names in os.walk(ext_root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(names):
            if name.endswith(SKIP_SUFFIX):
                continue
            path = os.path.join(base, name)
            files[os.path.relpath(path, ext_root).replace(os.sep, "/")] = open(path, "rb").read()
    for name in SHARED_DATA:
        files["data/" + name] = open(os.path.join(ROOT, "data", "vietnamese", name), "rb").read()
    files["data/solutions.json"] = open(os.path.join(ROOT, "data", "hst", "solutions.json"), "rb").read()  # welcome dialog content
    files["data/release.json"] = release_json(test_mode)  # update check: installed release id
    for name, src in BRAND_IMAGES.items():
        files[name] = open(os.path.join(ROOT, *src.split("/")), "rb").read()
    files["license/LICENSE.txt"] = open(os.path.join(ROOT, "LICENSE"), "rb").read()
    files["license/NOTICES.txt"] = notices_text().encode("utf-8")
    return files


def write_oxt(files, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type, info.external_attr, info.create_system = zipfile.ZIP_DEFLATED, 0o644 << 16, 3
            z.writestr(info, files[name])


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output", default=os.path.join(ROOT, "dist", "extensions"))
    ap.add_argument("--verify-reproducible", action="store_true", help="build twice and compare SHA-256")
    ap.add_argument("--update-test-mode", action="store_true", help="test packages only: allow HST_UPDATE_TEST_URL")
    args = ap.parse_args()
    names = sorted(d for d in os.listdir(EXT_DIR) if os.path.isfile(os.path.join(EXT_DIR, d, "description.xml")))
    if not names:
        print("no extensions found in %s" % EXT_DIR, file=sys.stderr)
        return 1
    for name in names:
        files = collect(os.path.join(EXT_DIR, name), args.update_test_mode)
        out = os.path.join(args.output, name + ".oxt")
        write_oxt(files, out)
        digest = sha256(out)
        print("built %s  %d files  sha256 %s" % (os.path.relpath(out, ROOT), len(files), digest))
        if args.verify_reproducible:
            second = out + ".verify"
            write_oxt(collect(os.path.join(EXT_DIR, name), args.update_test_mode), second)
            same = sha256(second) == digest
            os.remove(second)
            print("reproducible: %s" % ("yes" if same else "NO"))
            if not same:
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
