#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Validate built .oxt packages: structure, safe ZIP paths, registration, notices, no remote resources.

Usage: python3 scripts/check-extensions.py --directory dist/extensions
       python3 scripts/check-extensions.py --self-test      (proves the validator rejects broken packages)
Exit status is non-zero when any package fails any rule.
"""
import argparse
import os
import sys
import tempfile
import zipfile

from extension_content import (ROOT, BANNER_FETCH, BANNER_DEADLINE, UPDATE_FETCH, UPDATE_DOWNLOAD,
                               UPDATE_LAUNCH, USB_TOKEN_WORKER, USB_TOKEN_NSS,
                               check_zip, check_registration, check_content)
from extension_contract import check_banners, check_labels, banner_key


def check_oxt(path, require_banner_key=False):
    errors = []
    try:
        with zipfile.ZipFile(path) as zf:
            names = check_zip(zf, errors)
            check_registration(zf, names, errors)
            check_content(zf, names, errors)
            check_labels(zf, names, errors)
            check_banners(zf, names, errors)
            if require_banner_key:
                from hst_office.banner_verify import valid_key
                try:
                    if not valid_key(banner_key(zf)):
                        errors.append("release requires a valid separate banner public key")
                except (KeyError, ValueError):
                    errors.append("release banner key unavailable")
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
        "invalid banner key": lambda d: d.update({"python/hst_office/banner_verify.py":
            d["python/hst_office/banner_verify.py"].replace(b'PUBLIC_KEY = b""', b'PUBLIC_KEY = bytes.fromhex("01' + b'00' * 31 + b'")')}),
        "stale banners": lambda d: d.update({"data/banners.json": b"{}"}),
        "missing banner image": lambda d: d.pop("banners/aios@1x.png"),
        "missing banner snapshots": lambda d: d.pop("data/banner-snapshots.json"),
        "stale banner snapshots": lambda d: d.update({"data/banner-snapshots.json": b"{}"}),
        "missing banner font license": lambda d: d.pop("banners/fonts/OFL.txt"),
        "network in banner deadline": lambda d: d.update({BANNER_DEADLINE: d[BANNER_DEADLINE] + b"\nimport urllib.request\n"}),
        "subprocess in banner HTTP": lambda d: d.update({BANNER_FETCH: d[BANNER_FETCH] + b"\nimport subprocess\n"}),
        "socket in banner fetch": lambda d: d.update({BANNER_FETCH: d[BANNER_FETCH] + b"\nimport socket\n"}),
        "network import": lambda d: d.update({"python/hst_office/x.py": b"# SPDX-License-Identifier: AGPL-3.0-only\nimport socket\n"}),
        "urllib outside update_fetch": lambda d: d.update({"python/hst_office/x.py": b"# SPDX-License-Identifier: AGPL-3.0-only\nimport urllib.request\n"}),
        "socket in update_fetch": lambda d: d.update({UPDATE_FETCH: d[UPDATE_FETCH] + b"\nimport socket\n"}),
        "subprocess in update_download": lambda d: d.update({UPDATE_DOWNLOAD: d.get(UPDATE_DOWNLOAD, b"") + b"\nimport subprocess\n"}),
        "urllib in update_launch": lambda d: d.update({UPDATE_LAUNCH: d.get(UPDATE_LAUNCH, b"") + b"\nimport urllib.request\n"}),
        "network in USB worker": lambda d: d.update({USB_TOKEN_WORKER: d[USB_TOKEN_WORKER] + b"\nimport socket\n"}),
        "network in USB setup": lambda d: d.update({USB_TOKEN_NSS: d[USB_TOKEN_NSS] + b"\nimport urllib.request\n"}),
        "update test mode": lambda d: d.update({"data/release.json": b'{"release": "1.0.0", "update_test_mode": true}'}),
        "remote link in guide": lambda d: d.update({"help/index.html": d["help/index.html"] + b'<a href="https://evil.example/">x</a>'}),
        "broken guide download": lambda d: d.update({"help/index.html": d["help/index.html"] + b'<a href="files/missing.reg">x</a>'}),
        "unexpected guide download": lambda d: d.update({"help/files/tool.exe": b"MZ"}),
        "broken mobileconfig": lambda d: d.update({"help/files/x.mobileconfig": b"<plist"}),
        "stale data": lambda d: d.update({"data/nd30.json": b"{}"}), "stale solutions": lambda d: d.update({"data/solutions.json": b"{}"}),
        "stale PKCS11 catalog": lambda d: d.update({"data/pkcs11-modules.json": b"{}"}),
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
    ap.add_argument("--require-banner-key", action="store_true", help="release gate: reject the empty placeholder")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    packages = sorted(f for f in os.listdir(args.directory) if f.endswith(".oxt")) if os.path.isdir(args.directory) else []
    if not packages:
        print("BLOCKED: no .oxt files in %s" % args.directory)
        return 2
    status = 0
    for name in packages:
        errors = check_oxt(os.path.join(args.directory, name), args.require_banner_key)
        print("%s %s" % ("FAIL" if errors else "PASS", name), *["\n   - " + e for e in errors], sep="")
        status |= 1 if errors else 0
    return status


if __name__ == "__main__":
    sys.exit(main())
