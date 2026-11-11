#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build the bundled LibreOffice extensions (.oxt) deterministically.

Usage: python3 scripts/build-extensions.py --output dist/extensions [--verify-reproducible] [--update-test-mode]

Each extensions/<name>/ directory becomes <name>.oxt. Shared data from data/vietnamese/ (and data/hst/solutions.json for the welcome dialog) is copied into the
package (data/), the brand images of the welcome dialog and user guide into icons/, the AGPL licence and a generated notice file go into license/. ZIP entries are sorted, use a
fixed timestamp and permissions, so two builds of the same tree are byte-identical.
data/hst/release.json (release id, e.g. 1.0.0-beta.2; core must equal /VERSION) becomes data/release.json, read by
the update check. --update-test-mode marks that copy so the update check accepts a local http://127.0.0.1 test
server (HST_UPDATE_TEST_URL, and HST_ERROR_REPORT_TEST_URL for the error report); never use it for release packages
(scripts/check-extensions.py rejects them). The copy also carries the numeric build (scripts/write-hst-version.py).
"""
import argparse
import hashlib
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # also under python -I, which leaves it out
from extension_package_files import (ROOT, FIXED_TIME, ENTRY_TIME_SPAN, TEMPLATE_EXTENSION,  # noqa: E402,F401
                                     entry_time, notices_text, release_json, stamped_description, template_files)

EXT_DIR = os.path.join(ROOT, "extensions")
SHARED_DATA = ("nd30.json", "qppl.json", "dang.json", "document-types.json", "skeletons-hanh-chinh.json", "skeletons-qppl.json",
               "skeletons-dang.json", "skeletons-van-thu.json", "font-metrics-times.json",
               "number-formats.json", "encoding-maps.json", "provenance.json")
# Brand images shown by the welcome dialog and the offline user guide (help/index.html): copied from
# assets/brand at build time so the package always carries the current HST artwork.
BRAND_IMAGES = {
    "icons/hst-office-logo.png": "assets/brand/hst-office-logo.png",
    "icons/hst-writer-64.png": "assets/brand/icons/hst-writer-64.png",
    "icons/hst-sheets-64.png": "assets/brand/icons/hst-sheets-64.png",
    "icons/hst-slides-64.png": "assets/brand/icons/hst-slides-64.png",
}
SKIP_DIRS = {"__pycache__", ".git"}
SKIP_SUFFIX = (".pyc", ".pyo", "~", ".idl")  # IDL source: the compiled types/*.rdb is packaged


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
    files["data/banners.json"] = open(os.path.join(ROOT, "data", "hst", "banners.json"), "rb").read()
    files["data/pkcs11-modules.json"] = open(os.path.join(ROOT, "data", "hst", "pkcs11-modules.json"), "rb").read()
    files["data/release.json"] = release_json(test_mode)  # update check: installed release id
    files["description.xml"] = stamped_description(files)
    for name, src in BRAND_IMAGES.items():
        files[name] = open(os.path.join(ROOT, *src.split("/")), "rb").read()
    files["license/LICENSE.txt"] = open(os.path.join(ROOT, "LICENSE"), "rb").read()
    files["license/NOTICES.txt"] = notices_text().encode("utf-8")
    if os.path.basename(os.path.normpath(ext_root)) == TEMPLATE_EXTENSION:
        sys.path.insert(0, os.path.join(ext_root, "python"))
        from hst_office.banner_schema import image_specs
        from hst_office.banner_snapshot import encoded_items
        doc = json.loads(files["data/banners.json"])
        images = {i["id"]: {s: files[v["url"]] for s, v in image_specs(i)} for i in doc["items"]}
        encoded = encoded_items(doc, images, json.loads(files["data/solutions.json"])["utm"])
        files["data/banner-snapshots.json"] = json.dumps(encoded, sort_keys=True).encode("ascii")
        files.update(template_files())
    return files


def write_oxt(files, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, entry_time(files[name]))
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
