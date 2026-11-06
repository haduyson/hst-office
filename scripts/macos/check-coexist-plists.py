#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Fail when the HST Office macOS bundle declares something that clashes with LibreOffice.

  check-coexist-plists.py --hst "HST Office.app" [--lo LibreOffice.app]
Rules for HST alone (every build, scripts/macos/trial-build.sh --verify):
  - its bundle id and CFBundleSignature are not LibreOffice's;
  - it exports no uniform type identifier (UTI) outside its own bundle id: types it does not own (ODF,
    OpenOffice.org, .oxt) are imported, so the system keeps the owner's single declaration;
  - LSHandlerRank is not checked: HST claims the ODF types as Owner so a Mac with only HST opens them
    (owner decision 2026-11-06); with LibreOffice installed too, LaunchServices picks one of them;
  - no URL scheme in LibreOffice's vnd.libreoffice.* / vnd.sun.star.* namespaces;
  - every Spotlight importer and app extension inside it has a bundle id under HST's bundle id;
  - its profile (bootstraprc UserInstallation) is not LibreOffice's.
With --lo (the coexistence probe, scripts/macos/coexist-probe.sh) also, against that bundle:
  distinct bundle id, name and profile; no UTI exported by both; shared URL schemes only from the
  Microsoft Office URI set; disjoint plug-in bundle ids and CFPlugIn factory UUIDs.
Exit 0 = clean, 1 = a rule failed, 2 = unreadable bundle or bad arguments.
"""
import argparse
import plistlib
import re
import sys
from pathlib import Path

LIBREOFFICE_ID = "org.libreoffice.script"
# Microsoft's Office URI schemes: every office suite may register them; the user picks the handler.
SHARED_SCHEMES = {"ms-word", "ms-excel", "ms-powerpoint", "ms-visio", "ms-access"}
UPSTREAM_SCHEME = re.compile(r"^vnd\.(libreoffice|sun\.star)\.", re.IGNORECASE)


class Bundle:
    """The parts of an .app that LaunchServices, Spotlight and Quick Look read."""

    def __init__(self, app):
        self.app = Path(app)
        try:
            with open(self.app / "Contents/Info.plist", "rb") as handle:
                self.info = plistlib.load(handle)
        except (OSError, plistlib.InvalidFileException, ValueError) as error:
            raise SystemExit(f"cannot read {self.app}/Contents/Info.plist: {error}") from error
        self.id = self.info.get("CFBundleIdentifier", "")

    def exported(self):
        return {t.get("UTTypeIdentifier", "") for t in self.info.get("UTExportedTypeDeclarations", [])}

    def schemes(self):
        return {s.lower() for url in self.info.get("CFBundleURLTypes", []) for s in url.get("CFBundleURLSchemes", [])}

    def plugins(self):
        """(relative path, Info.plist dict) of every Spotlight importer and app extension."""
        found = []
        for pattern in ("Contents/Library/Spotlight/*/Contents/Info.plist", "Contents/PlugIns/*/Contents/Info.plist"):
            for path in sorted(self.app.glob(pattern)):
                try:
                    with open(path, "rb") as handle:
                        found.append((str(path.relative_to(self.app)), plistlib.load(handle)))
                except (OSError, plistlib.InvalidFileException, ValueError) as error:
                    raise SystemExit(f"cannot read {path}: {error}") from error
        return found

    def factories(self):
        return {uuid.upper() for _, info in self.plugins() for uuid in info.get("CFPlugInFactories", {})}

    def profile(self):
        """UserInstallation from Contents/Resources/bootstraprc, as written (with $SYSUSERCONFIG)."""
        try:
            text = (self.app / "Contents/Resources/bootstraprc").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        match = re.search(r"^UserInstallation=(.*)$", text, re.MULTILINE)
        return match.group(1).strip() if match else ""


def own(identifier, bundle_id):
    return identifier == bundle_id or identifier.startswith(bundle_id + ".")


def check(hst, lo=None):
    """List of (ok, message)."""
    results = []

    def rule(ok, message):
        results.append((bool(ok), message))

    rule(hst.id and not hst.id.lower().startswith("org.libreoffice"), f"bundle id {hst.id!r} is HST's own")
    rule(hst.info.get("CFBundleSignature") != "LibO", f"CFBundleSignature {hst.info.get('CFBundleSignature')!r} is not LibreOffice's")
    foreign = sorted(t for t in hst.exported() if not own(t, hst.id))
    rule(not foreign, "exports no UTI it does not own" + (f": exports {', '.join(foreign)}" if foreign else ""))
    upstream = sorted(s for s in hst.schemes() if UPSTREAM_SCHEME.match(s))
    rule(not upstream, "no LibreOffice URL scheme" + (f": {', '.join(upstream)}" if upstream else ""))
    plugins = hst.plugins()
    alien = [f"{path} ({info.get('CFBundleIdentifier')})" for path, info in plugins if not own(info.get("CFBundleIdentifier", ""), hst.id)]
    rule(not alien, f"{len(plugins)} plug-ins carry ids under {hst.id}" + (f": {', '.join(alien)}" if alien else ""))
    profile = hst.profile()
    rule(profile and "libreoffice" not in profile.lower(), f"profile {profile!r} is not LibreOffice's")
    if lo is None:
        return results
    rule(hst.id != lo.id, f"bundle ids differ: {hst.id} / {lo.id}")
    rule(hst.info.get("CFBundleName") != lo.info.get("CFBundleName"),
         f"bundle names differ: {hst.info.get('CFBundleName')!r} / {lo.info.get('CFBundleName')!r}")
    both = sorted(hst.exported() & lo.exported())
    rule(not both, "no UTI exported by both" + (f": {', '.join(both)}" if both else ""))
    shared = hst.schemes() & lo.schemes()
    rule(shared <= SHARED_SCHEMES, f"shared URL schemes only from the Office URI set: {', '.join(sorted(shared)) or 'none'}")
    lo_plugin_ids = {info.get("CFBundleIdentifier") for _, info in lo.plugins()}
    clash = sorted({info.get("CFBundleIdentifier") for _, info in plugins} & lo_plugin_ids)
    rule(not clash, "no plug-in bundle id in both" + (f": {', '.join(clash)}" if clash else ""))
    uuids = sorted(hst.factories() & lo.factories())
    rule(not uuids, "no CFPlugIn factory UUID in both" + (f": {', '.join(uuids)}" if uuids else ""))
    rule(profile != lo.profile(), f"profiles differ: {profile!r} / {lo.profile()!r}")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hst", required=True, help="HST Office.app")
    parser.add_argument("--lo", help="LibreOffice.app to compare with")
    args = parser.parse_args(argv)
    try:
        hst = Bundle(args.hst)
        lo = Bundle(args.lo) if args.lo else None
    except SystemExit as error:
        print(error, file=sys.stderr)
        return 2
    results = check(hst, lo)
    for ok, message in results:
        print(f"{'PASS' if ok else 'FAIL'} {message}")
    return 0 if all(ok for ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
