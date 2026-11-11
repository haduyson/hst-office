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
import datetime
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
ENTRY_TIME_SPAN = 180 * 86400  # seconds after FIXED_TIME over which entry times spread


def entry_time(data):
    """A reproducible ZIP time for one entry, derived from its content (2 s steps, the ZIP resolution).

    The office's Python keeps a bytecode cache in the user profile (hst-python-no-bytecode.patch) and trusts a cached
    .pyc while the source's mtime and size are unchanged. With one fixed time for every file in every build, a module
    edited without changing its size would keep the bytecode of the previous release; a content-derived time changes
    with the content."""
    offset = int(hashlib.sha256(data).hexdigest()[:12], 16) % (ENTRY_TIME_SPAN // 2) * 2
    return (datetime.datetime(*FIXED_TIME) + datetime.timedelta(seconds=offset)).timetuple()[:6]
# The HST templates (templates/*.json -> scripts/generate-templates.py) ship in the
# extension: Paths.xcu adds %origin%/template to the template paths, so the Template
# Manager lists them on every OS without installer changes. Folder -> group shown in the UI.
TEMPLATE_EXTENSION = "hst-vietnamese-tools"
TEMPLATE_GROUPS = (
    ("writer", "hst-van-ban", "HST \u2014 V\u0103n b\u1ea3n h\u00e0nh ch\u00ednh"),
    ("qppl", "hst-qppl", "HST \u2014 V\u0103n b\u1ea3n quy ph\u1ea1m ph\u00e1p lu\u1eadt"),
    ("dang", "hst-dang", "HST \u2014 V\u0103n b\u1ea3n c\u1ee7a \u0110\u1ea3ng"),
    ("van-thu", "hst-van-thu", "HST \u2014 Bi\u1ec3u m\u1eabu v\u0103n th\u01b0"),
    ("sheets", "hst-bang-tinh", "HST \u2014 B\u1ea3ng t\u00ednh"),
    ("slides", "hst-trinh-chieu", "HST \u2014 Tr\u00ecnh chi\u1ebfu"),
)
SKIP_DIRS = {"__pycache__", ".git"}
SKIP_SUFFIX = (".pyc", ".pyo", "~", ".idl")  # IDL source: the compiled types/*.rdb is packaged


def notices_text():
    prov = json.load(open(os.path.join(ROOT, "data", "vietnamese", "provenance.json"), encoding="utf-8"))
    lines = ["HST Vietnamese tools - notices", "",
             "Code: GNU Affero General Public License v3.0 (license/LICENSE.txt). Based on LibreOffice (The Document Foundation).", "",
             "Legacy encoding tables (data/encoding-maps.json) were derived from, and cross-checked against, these sources",
             "(factual character mappings; see docs/ENCODING_SOURCES.md in the source tree for the procedure):"]
    for name, src in sorted(prov["sources"].items()):
        lines.append("  - %s: %s (sha256 %s)" % (name, src.get("url") or src.get("path"), src["sha256"]))
    lines += ["", "ND30 rules: Nghi dinh 30/2020/ND-CP, Phu luc I; legal validity in 2026 is unverified. Presentation helper only."]
    lines += ["", "Banner fonts: Be Vietnam Pro, SIL Open Font License 1.1 (banners/fonts/OFL.txt).",
              "Solution logos: HASON TECH and respective product marks; source attribution: banners/SOURCES.md."]
    return "\n".join(lines) + "\n"


def release_json(test_mode=False):
    """data/hst/release.json for the package; refuses a release id whose core differs from /VERSION."""
    info = json.load(open(os.path.join(ROOT, "data", "hst", "release.json"), encoding="utf-8"))
    release = info["release"]
    version = open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()
    if release.split("+")[0].split("-")[0] != version:
        raise SystemExit("data/hst/release.json release %r does not match /VERSION %r" % (release, version))
    spec = importlib.util.spec_from_file_location("write_hst_version", os.path.join(ROOT, "scripts", "write-hst-version.py"))
    versions = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(versions)
    stamp = {"release": release, "build": versions.release_build(release)}  # error report: product.build
    if test_mode:
        stamp["update_test_mode"] = True
    return (json.dumps(stamp, sort_keys=True, indent=1) + "\n").encode("utf-8")


def template_files():
    """{archive_name: bytes}: generated templates under template/<group>/ and groupuinames.xml."""
    files = {}
    with tempfile.TemporaryDirectory() as out:
        env = dict(os.environ, SOURCE_DATE_EPOCH="1767225600")  # reproducible ODF packages
        subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "generate-templates.py"), "--out", out],
                       check=True, env=env, stdout=subprocess.DEVNULL)
        groups = []
        for module, folder, ui_name in TEMPLATE_GROUPS:
            for name in sorted(os.listdir(os.path.join(out, module))):
                if name.endswith((".ott", ".ots", ".otp")):
                    files["template/%s/%s" % (folder, name)] = open(os.path.join(out, module, name), "rb").read()
            groups.append(' <groupuinames:template-group groupuinames:name="%s" groupuinames:default-ui-name="%s"/>'
                          % (folder, ui_name))
    files["template/groupuinames.xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<groupuinames:template-group-list xmlns:groupuinames="http://openoffice.org/2006/groupuinames">\n'
        + "\n".join(groups) + "\n</groupuinames:template-group-list>\n").encode("utf-8")
    return files


def stamped_description(files):
    """description.xml with a version that changes with every build: <VERSION>.<release build>.<content number>.

    The office registers a bundled extension's UNO components again only when its identifier or version changed
    (desktop dp_manager.cxx synchronizeRemovedExtensions compares the version string). With "1.0.0" in every build, a
    profile an earlier build registered kept that build's component list after an upgrade: services added since
    (Tùy chọn page handlers, the start-up questions) could not be created. The content number (from the SHA-256 of
    every other file) keeps the build reproducible and differs between two builds of one release id."""
    release = json.loads(release_json())["release"]
    spec = importlib.util.spec_from_file_location("write_hst_version", os.path.join(ROOT, "scripts", "write-hst-version.py"))
    versions = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(versions)
    digest = hashlib.sha256()
    for name in sorted(files):
        if name != "description.xml":
            digest.update(name.encode("utf-8") + b"\0" + hashlib.sha256(files[name]).digest())
    content = int(digest.hexdigest()[:8], 16)
    version = "%s.%d.%d" % (release.split("+")[0].split("-")[0], versions.release_build(release), content)
    text = files["description.xml"].decode("utf-8")
    stamped, count = re.subn(r'<version value="[^"]*"/>', '<version value="%s"/>' % version, text, count=1)
    if count != 1:
        raise SystemExit("description.xml: no <version value=.../> to stamp")
    return stamped.encode("utf-8")


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
