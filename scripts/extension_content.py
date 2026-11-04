# SPDX-License-Identifier: AGPL-3.0-only
"""Package structure and resource validation helpers."""
import hashlib
import json
import os
import plistlib
import re
import sys
from xml.dom import minidom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED = ("description.xml", "META-INF/manifest.xml", "license/LICENSE.txt", "license/NOTICES.txt", "data/provenance.json", "data/solutions.json",
            "data/release.json", "data/pkcs11-modules.json", "data/banners.json", "banners.xcs")
SHARED_DATA = ("nd30.json", "number-formats.json", "encoding-maps.json", "provenance.json")
GUIDE_SUPPORT_GROUP = "https://www.facebook.com/share/g/1TvVaU6q4V/"  # the one link outside hasontech.vn in the guide
HOST_ALLOW = ("openoffice.org", "libreoffice.org", "w3.org", "hasontech.vn", "sun.com")
NETWORK_IMPORT = re.compile(r"^\s*(?:import|from)\s+(socket|urllib(?!\.parse\b)|http|ftplib|smtplib|requests|ssl|xmlrpc|subprocess|ctypes)\b", re.M)
# HTTPS is confined to transport helpers; only the deadline supervisor may spawn its private helper.
BANNER_FETCH = "python/hst_office/banner_http.py"  # isolated, bounded HTTPS helper
BANNER_DEADLINE = "python/hst_office/banner_fetch.py"  # fixed Python helper; no shell or network imports
UPDATE_FETCH = "python/hst_office/update_fetch.py"
UPDATE_DOWNLOAD = "python/hst_office/update_download.py"  # installer download after the user's click
UPDATE_LAUNCH = "python/hst_office/update_launch.py"  # starts the external update helper
USB_TOKEN_WORKER = "python/hst_office/usb_token_worker.py"
USB_TOKEN_NSS = "python/hst_office/usb_token_nss.py"  # local NSS tools only; no shell, elevation or credentials
UPDATE_LAUNCH_IMPORT = re.compile(r"^\s*(?:import|from)\s+(socket|urllib(?!\.parse\b)|http|ftplib|smtplib|requests|ssl|xmlrpc|ctypes)\b", re.M)
USB_WORKER_IMPORT = re.compile(r"^\s*(?:import|from)\s+(socket|urllib(?!\.parse\b)|http|ftplib|smtplib|requests|ssl|xmlrpc|subprocess)\b", re.M)
UPDATE_FETCH_IMPORT = re.compile(r"^\s*(?:import|from)\s+(socket|ftplib|smtplib|requests|xmlrpc|subprocess|ctypes)\b", re.M)
MEDIA = ("application/vnd.sun.star.uno-component;type=Python", "application/vnd.sun.star.configuration-data", "application/vnd.sun.star.configuration-schema")
MAX_LINES = 199
# Downloadable update-lock templates of the user guide (help/cap-nhat.html), made by build-update-policy-oxt.py.
HELP_FILES = ("help/files/", (".reg", ".xcd", ".mobileconfig"))


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
            for host in re.findall(r"(?:https?:)?//([^/\s\"'<>)]+)", text.replace(GUIDE_SUPPORT_GROUP, "")):
                if not host.endswith("hasontech.vn"):
                    errors.append("remote link in %s: %s" % (name, host))
            if re.search(r"github|libreoffice|document foundation", text, re.I):
                errors.append("%s names GitHub or the upstream project" % name)
            for ref in re.findall(r"""src=["']([^"':]+)["']""", text):
                target = os.path.normpath(os.path.join(os.path.dirname(name), ref)).replace(os.sep, "/")
                if target not in names:
                    errors.append("%s references missing %s" % (name, target))
            for ref in re.findall(r"""href=["'](files/[^"'#:]+)["']""", text):  # template downloads
                if "help/" + ref not in names:
                    errors.append("%s links missing help/%s" % (name, ref))
        if name.startswith(HELP_FILES[0]):
            if not name.endswith(HELP_FILES[1]):
                errors.append("unexpected file in the guide downloads: %s" % name)
            elif name.endswith(".xcd"):
                parse_xml(data, errors, name)
            elif name.endswith(".mobileconfig"):
                try:
                    plistlib.loads(data)
                except Exception as exc:  # noqa: BLE001 - any parse failure is a validation error
                    errors.append("%s: not a property list (%s)" % (name, exc))
            elif not data.startswith(b"Windows Registry Editor Version 5.00\r\n") or not data.isascii():
                errors.append("%s: not an ASCII Windows .reg file" % name)
        if name.endswith(".py"):
            text = data.decode("utf-8")
            if (USB_WORKER_IMPORT if name == USB_TOKEN_WORKER else UPDATE_FETCH_IMPORT if name in (UPDATE_FETCH, UPDATE_DOWNLOAD, BANNER_FETCH) else UPDATE_LAUNCH_IMPORT
                    if name in (UPDATE_LAUNCH, USB_TOKEN_NSS, BANNER_DEADLINE) else NETWORK_IMPORT).search(text):
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
    src = os.path.join(ROOT, "data", "hst", "pkcs11-modules.json")
    if "data/pkcs11-modules.json" in names and zf.read("data/pkcs11-modules.json") != open(src, "rb").read():
        errors.append("data/pkcs11-modules.json is stale compared with data/hst/pkcs11-modules.json")
