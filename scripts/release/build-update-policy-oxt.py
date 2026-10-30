#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build hst-update-policy.oxt: an administrator package that turns the HST Office update check off and locks it.

  build-update-policy-oxt.py [--output dist/hst-update-policy.oxt] [--enable]

Install it for all users of a machine with `unopkg add --shared hst-update-policy.oxt` (as administrator/root,
from the program folder of the installation). It adds a configuration layer that sets
/org.hasontech.hstoffice.UpdateCheck/AutoCheck (false, or true with --enable) with oor:finalized="true", so user
profiles cannot change it. A layer in share/registry (.xcd) or the Windows registry cannot do this: those layers are
read before the bundled extension that defines the setting. Remove with `unopkg remove --shared
vn.hasontech.hst.update-policy`. See docs/UPDATE_CHECK.md.
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
</manifest:manifest>
"""
POLICY = """<?xml version="1.0" encoding="UTF-8"?>
<oor:component-data xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema"
                    oor:name="UpdateCheck" oor:package="org.hasontech.hstoffice">
  <prop oor:name="AutoCheck" oor:finalized="true" oor:op="fuse"><value>%s</value></prop>
</oor:component-data>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output", default=os.path.join(ROOT, "dist", "hst-update-policy.oxt"))
    ap.add_argument("--enable", action="store_true", help="lock the automatic check ON instead of OFF")
    args = ap.parse_args()
    files = {"description.xml": DESCRIPTION, "META-INF/manifest.xml": MANIFEST,
             "policy.xcu": POLICY % ("true" if args.enable else "false")}
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
            z.writestr(info, files[name].encode("utf-8"))
    print("built %s (AutoCheck=%s, finalized)" % (args.output, "true" if args.enable else "false"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
