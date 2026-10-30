#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Validate built .oxt packages: structure, safe ZIP paths, registration, notices, no remote resources.

Usage: python3 scripts/check-extensions.py --directory dist/extensions
       python3 scripts/check-extensions.py --self-test      (proves the validator rejects broken packages)
Exit status is non-zero when any package fails any rule.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from xml.dom import minidom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED = ("description.xml", "META-INF/manifest.xml", "license/LICENSE.txt", "license/NOTICES.txt", "data/provenance.json", "data/solutions.json",
            "data/release.json")
SHARED_DATA = ("nd30.json", "number-formats.json", "encoding-maps.json", "provenance.json")
HOST_ALLOW = ("openoffice.org", "libreoffice.org", "w3.org", "hasontech.vn", "sun.com")
NETWORK_IMPORT = re.compile(r"^\s*(?:import|from)\s+(socket|urllib(?!\.parse\b)|http|ftplib|smtplib|requests|ssl|xmlrpc|subprocess|ctypes)\b", re.M)
# The update check (docs/UPDATE_CHECK.md) is the one module that may use HTTPS (urllib/ssl/http); never sockets or processes.
UPDATE_FETCH = "python/hst_office/update_fetch.py"
UPDATE_FETCH_IMPORT = re.compile(r"^\s*(?:import|from)\s+(socket|ftplib|smtplib|requests|xmlrpc|subprocess|ctypes)\b", re.M)
MEDIA = ("application/vnd.sun.star.uno-component;type=Python", "application/vnd.sun.star.configuration-data", "application/vnd.sun.star.configuration-schema")
MAX_LINES = 199


def parse_xml(data, errors, name):
    try:
        return minidom.parseString(data)
    except Exception as exc:  # noqa: BLE001 - any parse failure is a validation error
        errors.append("%s: not well-formed XML (%s)" % (name, exc))


def safe_name(name):
    parts = name.split("/")
    return not (name.startswith("/") or "\\" in name or ".." in parts or re.match(r"^[A-Za-z]:", name) or "" in parts[:-1] or "\x00" in name)


def check_zip(zf, errors):
    names = [i.filename for i in zf.infolist() if not i.filename.endswith("/")]
    if len(set(names)) != len(names):
        errors.append("duplicate entries")
    for info in zf.infolist():
        if not safe_name(info.filename):
            errors.append("unsafe path: %r" % info.filename)
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            errors.append("symlink entry: %r" % info.filename)
        if "__pycache__" in info.filename or info.filename.endswith((".pyc", ".pyo")):
            errors.append("compiled/cache file packaged: %r" % info.filename)
    bad = zf.testzip()
    if bad:
        errors.append("corrupt entry: %s" % bad)
    return set(names)


def check_registration(zf, names, errors):
    for need in REQUIRED:
        if need not in names:
            errors.append("missing required file: %s" % need)
    if "META-INF/manifest.xml" not in names:
        return
    dom = parse_xml(zf.read("META-INF/manifest.xml"), errors, "manifest.xml")
    entries = dom.getElementsByTagName("manifest:file-entry") if dom else []
    if not entries:
        errors.append("manifest.xml registers nothing")
    for entry in entries:
        path, media = entry.getAttribute("manifest:full-path"), entry.getAttribute("manifest:media-type")
        if path not in names:
            errors.append("manifest entry points to missing file: %s" % path)
        if media not in MEDIA:
            errors.append("unexpected media type %r for %s" % (media, path))
    if "description.xml" in names:
        dom = parse_xml(zf.read("description.xml"), errors, "description.xml")
        if dom and not (dom.getElementsByTagName("identifier") and dom.getElementsByTagName("version")):
            errors.append("description.xml lacks identifier/version")


def check_content(zf, names, errors):
    for name in sorted(names):
        data = zf.read(name)
        if name.endswith((".xml", ".xcu")):
            parse_xml(data, errors, name)
        if name.endswith((".xml", ".xcu", ".py")):
            text = data.decode("utf-8", "replace")
            for host in re.findall(r"https?://([^/\s\"'<>)]+)", text):
                if not host.endswith(HOST_ALLOW):
                    errors.append("remote resource in %s: %s" % (name, host))
        if name.endswith(".html"):  # bundled user guide: no remote resource, no upstream/GitHub naming
            text = data.decode("utf-8")
            for host in re.findall(r"(?:https?:)?//([^/\s\"'<>)]+)", text):
                if not host.endswith("hasontech.vn"):
                    errors.append("remote link in %s: %s" % (name, host))
            if re.search(r"github|libreoffice|document foundation", text, re.I):
                errors.append("%s names GitHub or the upstream project" % name)
            for ref in re.findall(r"""src=["']([^"':]+)["']""", text):
                target = os.path.normpath(os.path.join(os.path.dirname(name), ref)).replace(os.sep, "/")
                if target not in names:
                    errors.append("%s references missing %s" % (name, target))
        if name.endswith(".py"):
            text = data.decode("utf-8")
            if (UPDATE_FETCH_IMPORT if name == UPDATE_FETCH else NETWORK_IMPORT).search(text):
                errors.append("network/process module imported in %s" % name)
            if text.count("\n") + 1 > MAX_LINES:
                errors.append("%s exceeds %d lines" % (name, MAX_LINES))
            if "SPDX-License-Identifier: AGPL-3.0-only" not in text[:300]:
                errors.append("%s lacks the SPDX header" % name)
        if name.endswith(".json"):
            json.loads(data.decode("utf-8"))
        if name == "data/release.json" and json.loads(data.decode("utf-8")).get("update_test_mode"):
            errors.append("data/release.json is a test build (--update-test-mode): not for release")
    for name in SHARED_DATA:
        src = os.path.join(ROOT, "data", "vietnamese", name)
        if "data/" + name in names and os.path.exists(src):
            if hashlib.sha256(zf.read("data/" + name)).digest() != hashlib.sha256(open(src, "rb").read()).digest():
                errors.append("data/%s is stale compared with data/vietnamese/%s" % (name, name))
        elif "data/" + name not in names:
            errors.append("missing data/%s" % name)
    src = os.path.join(ROOT, "data", "hst", "solutions.json")
    if "data/solutions.json" in names and os.path.exists(src) and zf.read("data/solutions.json") != open(src, "rb").read():
        errors.append("data/solutions.json is stale compared with data/hst/solutions.json")


def check_labels(zf, names, errors):
    """Menu labels in Addons.xcu must equal locales/{en,vi}.json menu strings."""
    if "Addons.xcu" not in names:
        errors.append("missing Addons.xcu")
        return
    dom = parse_xml(zf.read("Addons.xcu"), errors, "Addons.xcu")
    if not dom:
        return
    labels = {"en-US": set(), "vi": set()}
    for value in dom.getElementsByTagName("value"):
        lang = value.getAttribute("xml:lang")
        if lang in labels and value.firstChild:
            labels[lang].add(value.firstChild.data)
    for lang, code in (("en-US", "en"), ("vi", "vi")):
        menu = json.loads(zf.read("locales/%s.json" % code).decode("utf-8"))["menu"]
        missing = set(menu.values()) - labels[lang]
        if missing:
            errors.append("Addons.xcu lacks %s labels from locales/%s.json: %s" % (lang, code, sorted(missing)))


def check_oxt(path):
    errors = []
    try:
        with zipfile.ZipFile(path) as zf:
            names = check_zip(zf, errors)
            check_registration(zf, names, errors)
            check_content(zf, names, errors)
            check_labels(zf, names, errors)
    except zipfile.BadZipFile as exc:
        errors.append("not a zip file: %s" % exc)
    return errors


def self_test():
    """Build deliberately broken packages from the real one; every defect must be reported."""
    source = os.path.join(ROOT, "dist", "extensions", "hst-vietnamese-tools.oxt")
    if not os.path.exists(source):
        print("BLOCKED: build the extension first (scripts/build-extensions.py)")
        return 2
    good = {n: zipfile.ZipFile(source).read(n) for n in zipfile.ZipFile(source).namelist()}
    cases = {
        "unsafe path": lambda d: d.update({"../evil.py": b"x"}),
        "missing notices": lambda d: d.pop("license/NOTICES.txt"),
        "remote resource": lambda d: d.update({"Addons.xcu": d["Addons.xcu"] + b"<!-- https://evil.example/x -->"}),
        "bad xml": lambda d: d.update({"ProtocolHandler.xcu": b"<oor:component-data"}),
        "missing registered file": lambda d: d.pop("python/hst_office_component.py"),
        "network import": lambda d: d.update({"python/hst_office/x.py": b"# SPDX-License-Identifier: AGPL-3.0-only\nimport socket\n"}),
        "urllib outside update_fetch": lambda d: d.update({"python/hst_office/x.py": b"# SPDX-License-Identifier: AGPL-3.0-only\nimport urllib.request\n"}),
        "socket in update_fetch": lambda d: d.update({UPDATE_FETCH: d[UPDATE_FETCH] + b"\nimport socket\n"}),
        "update test mode": lambda d: d.update({"data/release.json": b'{"release": "1.0.0", "update_test_mode": true}'}),
        "remote link in guide": lambda d: d.update({"help/index.html": d["help/index.html"] + b'<a href="https://evil.example/">x</a>'}),
        "stale data": lambda d: d.update({"data/nd30.json": b"{}"}), "stale solutions": lambda d: d.update({"data/solutions.json": b"{}"}),
    }
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for label, mutate in cases.items():
            data = dict(good)
            mutate(data)
            path = os.path.join(tmp, "case.oxt")
            with zipfile.ZipFile(path, "w") as z:
                for name, blob in data.items():
                    z.writestr(name, blob)
            found = check_oxt(path)
            print("%-4s self-test rejects %s%s" % ("PASS" if found else "FAIL", label, "" if found else " (NOT detected)"))
            failures += 0 if found else 1
        print("%-4s self-test accepts the real package" % ("PASS" if not check_oxt(source) else "FAIL"))
        failures += 1 if check_oxt(source) else 0
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--directory", default=os.path.join(ROOT, "dist", "extensions"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    packages = sorted(f for f in os.listdir(args.directory) if f.endswith(".oxt")) if os.path.isdir(args.directory) else []
    if not packages:
        print("BLOCKED: no .oxt files in %s" % args.directory)
        return 2
    status = 0
    for name in packages:
        errors = check_oxt(os.path.join(args.directory, name))
        print("%s %s" % ("FAIL" if errors else "PASS", name), *["\n   - " + e for e in errors], sep="")
        status |= 1 if errors else 0
    return status


if __name__ == "__main__":
    sys.exit(main())
