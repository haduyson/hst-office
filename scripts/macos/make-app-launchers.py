#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build HST Writer.app, HST Sheets.app and HST Slides.app into "HST Office.app/Contents/Helpers/".

Usage (macOS, Xcode tools): python3 -I scripts/macos/make-app-launchers.py "<path>/HST Office.app" --arch arm64|x86_64

Each launcher is a small native app (scripts/macos/hst-app-launcher.m, compiled once for the bundle's architecture)
with the HST module icon (assets/brand/icons/hst-<family>-<px>.png) and an Info.plist that names its module and the
host's bundle id. They live inside the host bundle, so the dmg, notarization, the move to /Applications and in-place
updates carry them along. Run before the bundle is signed: adhoc-sign.sh signs them as nested apps, and
sign-notarize.sh re-signs them without upstream's parent-process launch constraint (they are started by the Dock).
"""
import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve().parent / "hst-app-launcher.m"
ICONS = ROOT / "assets" / "brand" / "icons"
HELPERS = ("Contents", "Helpers")
EXECUTABLE = "hst-app-launcher"
# module (soffice --<module>) -> (app name, icon family, bundle id suffix)
LAUNCHERS = (("writer", "HST Writer", "hst-writer", "writer"), ("calc", "HST Sheets", "hst-sheets", "sheets"),
             ("impress", "HST Slides", "hst-slides", "slides"))
# iconset member -> pixel size (Apple iconset naming)
MEMBERS = {
    "icon_16x16.png": 16, "icon_16x16@2x.png": 32, "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128, "icon_128x128@2x.png": 256, "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512, "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
}
HOST_KEYS = ("CFBundleIdentifier", "CFBundleShortVersionString", "CFBundleVersion", "LSMinimumSystemVersion")


def launcher_info(host, module, name, suffix):
    """Info.plist of one launcher, from the host's Info.plist dict (pure). Raises ValueError on a missing key."""
    missing = [key for key in HOST_KEYS if not str(host.get(key) or "").strip()]
    if missing:
        raise ValueError("host Info.plist lacks %s" % ", ".join(missing))
    info = {
        "CFBundleDevelopmentRegion": "vi",
        "CFBundleDisplayName": name,
        "CFBundleExecutable": EXECUTABLE,
        "CFBundleIconFile": "app.icns",
        "CFBundleIdentifier": "%s.launcher.%s" % (host["CFBundleIdentifier"], suffix),
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": name,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": host["CFBundleShortVersionString"],
        "CFBundleVersion": host["CFBundleVersion"],
        "LSApplicationCategoryType": "public.app-category.productivity",
        "LSMinimumSystemVersion": host["LSMinimumSystemVersion"],
        "LSUIElement": True,  # no menu bar or Dock icon of its own: it only hands the request to HST Office
        "NSHighResolutionCapable": True,
        "HSTOfficeModule": module,
        "HSTOfficeHostIdentifier": host["CFBundleIdentifier"],
    }
    if host.get("NSHumanReadableCopyright"):
        info["NSHumanReadableCopyright"] = host["NSHumanReadableCopyright"]
    return info


def iconset_sources(family, icons=ICONS):
    """{iconset member: HST PNG of exactly that size} (pure apart from the file checks). Raises FileNotFoundError."""
    plan = {}
    for member, size in MEMBERS.items():
        path = Path(icons) / ("%s-%d.png" % (family, size))
        if not path.is_file():
            raise FileNotFoundError("missing icon %s" % path)
        plan[member] = path
    return plan


def bundle_path(app, name):
    return Path(app).joinpath(*HELPERS, name + ".app")


def run(argv):
    print("+ " + " ".join(str(a) for a in argv), flush=True)
    subprocess.run([str(a) for a in argv], check=True)


def compile_stub(out, arch, minimum):
    run(["xcrun", "clang", "-fobjc-arc", "-O2", "-Wall", "-Wextra", "-arch", arch, "-mmacosx-version-min=" + minimum,
         "-framework", "AppKit", "-o", out, SOURCE])


def build(app, arch, icons=ICONS):
    app = Path(app)
    with open(app / "Contents" / "Info.plist", "rb") as handle:
        host = plistlib.load(handle)
    infos = [(name, family, launcher_info(host, module, name, suffix)) for module, name, family, suffix in LAUNCHERS]
    plans = {family: iconset_sources(family, icons) for _name, family, _info in infos}
    with tempfile.TemporaryDirectory() as tmp:
        stub = Path(tmp) / EXECUTABLE
        compile_stub(stub, arch, host["LSMinimumSystemVersion"])
        for name, family, info in infos:
            bundle = bundle_path(app, name)
            if bundle.exists():
                shutil.rmtree(bundle)
            (bundle / "Contents" / "MacOS").mkdir(parents=True)
            (bundle / "Contents" / "Resources").mkdir()
            shutil.copyfile(stub, bundle / "Contents" / "MacOS" / EXECUTABLE)
            os.chmod(bundle / "Contents" / "MacOS" / EXECUTABLE, 0o755)
            with open(bundle / "Contents" / "Info.plist", "wb") as handle:
                plistlib.dump(info, handle, fmt=plistlib.FMT_XML)  # upstream's signing script reads it as XML
            (bundle / "Contents" / "PkgInfo").write_text("APPL????", encoding="ascii")
            iconset = Path(tmp) / (family + ".iconset")
            iconset.mkdir()
            for member, source in plans[family].items():
                shutil.copyfile(source, iconset / member)
            run(["iconutil", "-c", "icns", "-o", bundle / "Contents" / "Resources" / "app.icns", iconset])
            run(["plutil", "-lint", bundle / "Contents" / "Info.plist"])
            print("built %s (%s, --%s)" % (bundle, info["CFBundleIdentifier"], info["HSTOfficeModule"]), flush=True)
    run(["lipo", bundle_path(app, LAUNCHERS[0][1]) / "Contents" / "MacOS" / EXECUTABLE, "-verify_arch", arch])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("app")
    parser.add_argument("--arch", required=True, choices=("arm64", "x86_64"))
    args = parser.parse_args(argv)
    if not (Path(args.app) / "Contents" / "Info.plist").is_file():
        parser.error("not an app bundle: %s" % args.app)
    try:
        build(args.app, args.arch)
    except (OSError, ValueError, subprocess.CalledProcessError, plistlib.InvalidFileException) as exc:
        print("make-app-launchers: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
