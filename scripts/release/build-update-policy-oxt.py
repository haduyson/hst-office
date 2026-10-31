#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build hst-update-policy.oxt (or a share/registry .xcd): an administrator lock of the HST Office update check.

  build-update-policy-oxt.py [--output dist/hst-update-policy.oxt] [--xcd FILE] [--reg FILE] [--mobileconfig FILE]
                             [--enable] [--no-install] [--keep-autocheck] [--no-manual-check] [--channel stable|beta]
  build-update-policy-oxt.py --templates DIR    (the downloadable templates of the user guide, see PROFILES)

The settings live in the core schema /org.openoffice.Office.HSTUpdate (hst-update-config.patch). The lock sets
AutoCheck (false, or true with --enable) with oor:finalized="true", so user profiles cannot change it. --no-install
also locks AllowInstall=false ("Cập nhật ngay" disappears, only "Tải về" remains); --no-manual-check locks
ManualCheck=false (the "Kiểm tra cập nhật…" menu entries are disabled); --channel locks Channel (stable: only
final releases are offered); --keep-autocheck leaves AutoCheck to the user.

--xcd FILE writes the same lock as a .xcd to copy into <install>/share/registry (Linux/Windows); this is the
preferred form from beta.4 on (docs/UPDATE_ADMIN.md). The .oxt is for installs before beta.4 and for admins who
already deploy it: install with `unopkg add --shared hst-update-policy.oxt`, remove with `unopkg remove --shared
vn.hasontech.hst.update-policy`. It carries the core lock and the old /org.hasontech.hstoffice.UpdateCheck lock.

--reg FILE writes the lock as a Windows .reg file (HKLM policy keys read by the core configuration; it first deletes
the whole HSTUpdate policy key, so importing one template replaces an earlier one). --mobileconfig FILE writes a macOS
configuration profile whose payload is the managed preference domain vn.hasontech.hstoffice (dictionary HSTUpdate,
read by update_config.py); every template shares one PayloadIdentifier, so installing another replaces it.
--templates DIR writes every profile of PROFILES as <DIR>/hst-office-<name>.{xcd,reg,mobileconfig} plus the
removal file hst-office-go-khoa.reg: extensions/hst-vietnamese-tools/help/files/ holds this output
(tests/unit/test_update_policy_templates.py keeps it current; tests/runtime/check-update-policy.py proves it).
"""
import argparse
import os
import plistlib
import uuid
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
DESCRIPTION = """<?xml version="1.0" encoding="UTF-8"?>
<description xmlns="http://openoffice.org/extensions/description/2006" xmlns:d="http://openoffice.org/extensions/description/2006">
  <identifier value="vn.hasontech.hst.update-policy"/>
  <version value="1.0.0"/>
  <display-name>
    <name lang="vi">Chính sách kiểm tra cập nhật HST Office</name>
    <name lang="en">HST Office update check policy</name>
  </display-name>
</description>
"""
MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="http://openoffice.org/2001/manifest">
  <manifest:file-entry manifest:full-path="policy.xcu" manifest:media-type="application/vnd.sun.star.configuration-data"/>
  <manifest:file-entry manifest:full-path="policy-core.xcu" manifest:media-type="application/vnd.sun.star.configuration-data"/>
</manifest:manifest>
"""
POLICY = """<?xml version="1.0" encoding="UTF-8"?>
<oor:component-data xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema"
                    oor:name="UpdateCheck" oor:package="org.hasontech.hstoffice">
%s</oor:component-data>
"""
CORE = """<?xml version="1.0" encoding="UTF-8"?>
<oor:component-data xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema"
                    oor:name="HSTUpdate" oor:package="org.openoffice.Office">
%s</oor:component-data>
"""
XCD = """<?xml version="1.0" encoding="UTF-8"?>
<oor:data xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xmlns:oor="http://openoffice.org/2001/registry">
  <dependency file="main"/>
  <oor:component-data oor:name="HSTUpdate" oor:package="org.openoffice.Office">
%s  </oor:component-data>
</oor:data>
"""
PROP = '  <prop oor:name="%s" oor:finalized="true" oor:op="fuse"><value>%s</value></prop>\n'
# Downloadable templates of the user guide (help/cap-nhat.html): name -> (locks, Vietnamese title).
PROFILES = {
    "tat-kiem-tra": ((("AutoCheck", "false"), ("ManualCheck", "false"), ("AllowInstall", "false")),
                     "tắt mọi kiểm tra cập nhật"),
    "chi-tai-ve": ((("AllowInstall", "false"),), "không có nút Cập nhật ngay"),
    "kenh-chinh-thuc": ((("Channel", "stable"),), "chỉ nhận bản chính thức"),
}
REG_KEY = r"HKEY_LOCAL_MACHINE\SOFTWARE\Policies\LibreOffice\org.openoffice.Office.HSTUpdate"
REG_HEADER = "Windows Registry Editor Version 5.00\r\n\r\n"
REMOVE_REG = "go-khoa"
MAC_DOMAIN, MAC_IDENTIFIER = "vn.hasontech.hstoffice", "vn.hasontech.hstoffice.update-policy"


def typed(name, text):
    """Plist value of one lock (the .xcd/.reg carry text, a configuration profile carries typed values)."""
    if name in ("AutoCheck", "ManualCheck", "AllowInstall"):
        return text == "true"
    return int(text) if name == "CheckIntervalHours" else text


def reg_text(locks):
    """Windows .reg (ASCII, CRLF): delete the HSTUpdate policy key, then one finalized key per lock."""
    out = REG_HEADER + "[-%s]\r\n\r\n" % REG_KEY
    for name, value in locks:
        out += '[%s\\%s]\r\n"Value"="%s"\r\n"Final"=dword:00000001\r\n\r\n' % (REG_KEY, name, value)
    return out


def mobileconfig_bytes(locks, title, seed):
    ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, "https://office.hasontech.vn/update-policy/%s/%d" % (seed, n))) for n in (1, 2)]
    payload = {"PayloadType": MAC_DOMAIN, "PayloadVersion": 1, "PayloadIdentifier": MAC_IDENTIFIER + ".settings",
               "PayloadUUID": ids[1], "PayloadDisplayName": "HST Office: " + title,
               "HSTUpdate": {name: typed(name, value) for name, value in locks}}
    profile = {"PayloadType": "Configuration", "PayloadVersion": 1, "PayloadIdentifier": MAC_IDENTIFIER,
               "PayloadUUID": ids[0], "PayloadDisplayName": "HST Office: " + title, "PayloadOrganization": "HASON TECH",
               "PayloadDescription": "Khóa cài đặt kiểm tra cập nhật của HST Office: " + title + ".",
               "PayloadScope": "System", "PayloadContent": [payload]}
    return plistlib.dumps(profile, sort_keys=True)


def xcd_text(locks):
    return XCD % "".join("  " + PROP % lock for lock in locks)


def write(path, data):
    with open(path, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def write_templates(directory):
    os.makedirs(directory, exist_ok=True)
    for name, (locks, title) in PROFILES.items():
        base = os.path.join(directory, "hst-office-" + name)
        write(base + ".xcd", xcd_text(locks))
        write(base + ".reg", reg_text(locks).encode("ascii"))
        write(base + ".mobileconfig", mobileconfig_bytes(locks, title, name))
    write(os.path.join(directory, "hst-office-%s.reg" % REMOVE_REG), (REG_HEADER + "[-%s]\r\n" % REG_KEY).encode("ascii"))
    print("wrote the templates of %s into %s" % (", ".join(PROFILES), directory))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output", default=os.path.join(ROOT, "dist", "hst-update-policy.oxt"))
    ap.add_argument("--enable", action="store_true", help="lock the automatic check ON instead of OFF")
    ap.add_argument("--no-install", action="store_true", help="lock AllowInstall off: only the manual download is offered")
    ap.add_argument("--keep-autocheck", action="store_true", help="do not set AutoCheck")
    ap.add_argument("--no-manual-check", action="store_true", help="lock ManualCheck off: no menu check either")
    ap.add_argument("--channel", choices=("stable", "beta"), help="lock the release channel")
    ap.add_argument("--xcd", help="also write the lock as a .xcd file for <install>/share/registry")
    ap.add_argument("--reg", help="also write the lock as a Windows .reg file")
    ap.add_argument("--mobileconfig", help="also write the lock as a macOS configuration profile")
    ap.add_argument("--templates", metavar="DIR", help="only write the user-guide templates of every profile into DIR")
    args = ap.parse_args()
    if args.templates:
        write_templates(args.templates)
        return 0
    locks = ([] if args.keep_autocheck else [("AutoCheck", "true" if args.enable else "false")]) \
        + ([("AllowInstall", "false")] if args.no_install else []) \
        + ([("ManualCheck", "false")] if args.no_manual_check else []) \
        + ([("Channel", args.channel)] if args.channel else [])
    if not locks:
        ap.error("nothing to lock: --keep-autocheck needs --no-install, --no-manual-check or --channel")
    core = "".join(PROP % lock for lock in locks)
    legacy = "".join(PROP % lock for lock in locks if lock[0] in ("AutoCheck", "AllowInstall"))  # old schema
    files = {"description.xml": DESCRIPTION, "META-INF/manifest.xml": MANIFEST,
             "policy.xcu": POLICY % legacy, "policy-core.xcu": CORE % core}
    if args.xcd:
        write(args.xcd, xcd_text(locks))
    if args.reg:
        write(args.reg, reg_text(locks).encode("ascii"))
    if args.mobileconfig:
        write(args.mobileconfig, mobileconfig_bytes(locks, ", ".join("%s=%s" % lock for lock in locks), "custom"))
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
            z.writestr(info, files[name].encode("utf-8"))
    extra = [path for path in (args.xcd, args.reg, args.mobileconfig) if path]
    print("built %s%s (%s, finalized)" % (args.output, "".join(" and " + path for path in extra),
                                          ", ".join("%s=%s" % lock for lock in locks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
