#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build hst-update-policy.oxt (or a share/registry .xcd): an administrator lock of the HST Office update check.

  build-update-policy-oxt.py [--output dist/hst-update-policy.oxt] [--xcd FILE] [--enable] [--no-install]
                             [--keep-autocheck] [--no-manual-check]

The settings live in the core schema /org.openoffice.Office.HSTUpdate (hst-update-config.patch). The lock sets
AutoCheck (false, or true with --enable) with oor:finalized="true", so user profiles cannot change it. --no-install
also locks AllowInstall=false ("Cập nhật ngay" disappears, only "Tải về" remains); --no-manual-check locks
ManualCheck=false (the "Kiểm tra cập nhật…" menu entries are disabled); --keep-autocheck leaves AutoCheck to the user.

--xcd FILE writes the same lock as a .xcd to copy into <install>/share/registry (Linux/Windows); this is the
preferred form from beta.4 on (docs/UPDATE_ADMIN.md). The .oxt is for installs before beta.4 and for admins who
already deploy it: install with `unopkg add --shared hst-update-policy.oxt`, remove with `unopkg remove --shared
vn.hasontech.hst.update-policy`. It carries the core lock and the old /org.hasontech.hstoffice.UpdateCheck lock.
"""
import argparse
import os
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output", default=os.path.join(ROOT, "dist", "hst-update-policy.oxt"))
    ap.add_argument("--enable", action="store_true", help="lock the automatic check ON instead of OFF")
    ap.add_argument("--no-install", action="store_true", help="lock AllowInstall off: only the manual download is offered")
    ap.add_argument("--keep-autocheck", action="store_true", help="do not set AutoCheck")
    ap.add_argument("--no-manual-check", action="store_true", help="lock ManualCheck off: no menu check either")
    ap.add_argument("--xcd", help="also write the lock as a .xcd file for <install>/share/registry")
    args = ap.parse_args()
    locks = ([] if args.keep_autocheck else [("AutoCheck", "true" if args.enable else "false")]) \
        + ([("AllowInstall", "false")] if args.no_install else []) \
        + ([("ManualCheck", "false")] if args.no_manual_check else [])
    if not locks:
        ap.error("nothing to lock: --keep-autocheck needs --no-install or --no-manual-check")
    core = "".join(PROP % lock for lock in locks)
    legacy = "".join(PROP % lock for lock in locks if lock[0] in ("AutoCheck", "AllowInstall"))  # old schema
    files = {"description.xml": DESCRIPTION, "META-INF/manifest.xml": MANIFEST,
             "policy.xcu": POLICY % legacy, "policy-core.xcu": CORE % core}
    if args.xcd:
        with open(args.xcd, "w", encoding="utf-8") as fh:
            fh.write(XCD % "".join("  " + line + "\n" for line in core.splitlines()))
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
            z.writestr(info, files[name].encode("utf-8"))
    print("built %s%s (%s, finalized)" % (args.output, " and " + args.xcd if args.xcd else "",
                                          ", ".join("%s=%s" % lock for lock in locks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
