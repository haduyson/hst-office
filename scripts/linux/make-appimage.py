#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Repack the single HST Office .deb as an AppImage that runs on any x86-64 Linux with glibc >= the .deb's baseline.

No second build: the AppDir is the .deb payload (/opt/hst-office1.0 plus launchers, icons, MIME types) with
  AppRun                              scripts/linux/appimage/AppRun (integration on first start, then soffice)
  appimage_desktop_integration.py     per-user menu/MIME integration, run by AppRun with the bundled python
  vn.hasontech.hstoffice-startcenter.desktop / .png / .DirIcon   what appimagetool and file managers show
and is packed by appimagetool with the static type-2 runtime (squashfs + FUSE 3 built in: no libfuse2 needed; without
FUSE at all the AppImage still runs with --appimage-extract-and-run). Both tools are pinned by SHA-256 here.

  make-appimage.py <HSTOffice_<release>_Linux_x86-64.deb> <out-dir> --tools <dir>
<dir> holds (or receives, when --download is given) appimagetool-x86_64.AppImage and runtime-x86_64. Needs dpkg-deb and
`file` (appimagetool calls it).
Writes <out-dir>/HSTOffice_<release>_Linux_x86-64.AppImage and adds its line to <out-dir>/SHA256SUMS.
Unsigned, no update information: signing/zsync are release steps (docs/LINUX_PACKAGES.md).
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # sibling modules (also under python3 -I)
from importlib import util as _util  # noqa: E402

_spec = _util.spec_from_file_location("make_rpm", HERE / "make-rpm.py")
make_rpm = _util.module_from_spec(_spec)
_spec.loader.exec_module(make_rpm)

# appimagetool 1.9.1 (2025-11-18) and type2-runtime 20251108: https://github.com/AppImage/{appimagetool,type2-runtime}
TOOLS = {
    "appimagetool-x86_64.AppImage": ("https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage",
                                     "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"),
    "runtime-x86_64": ("https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64",
                       "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"),
}
MAIN_ID = "vn.hasontech.hstoffice-startcenter"
DEBIAN_ONLY = make_rpm.DEBIAN_ONLY
run = make_rpm.run


def die(msg):
    sys.exit("make-appimage: %s" % msg)


def fetch_tools(tools, download):
    """Pinned tools in `tools`, downloaded first when allowed; any SHA-256 mismatch is fatal."""
    tools.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in TOOLS.items():
        path = tools / name
        if not path.exists():
            if not download:
                die("%s missing (pass --download, or place it in %s)" % (name, tools))
            with urllib.request.urlopen(url, timeout=120) as response, open(str(path) + ".part", "wb") as out:
                shutil.copyfileobj(response, out)
            os.replace(str(path) + ".part", path)
        if make_rpm.sha256(path) != digest:
            path.unlink()
            die("%s: SHA-256 differs from the pinned %s" % (name, digest))
        path.chmod(0o755)
    return tools / "appimagetool-x86_64.AppImage", tools / "runtime-x86_64"


def make_appdir(deb, appdir):
    run("dpkg-deb", "-x", deb, appdir)
    for rel in DEBIAN_ONLY + ("usr/bin",):  # usr/bin: absolute links to /opt, meaningless inside the AppImage
        target = appdir / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    xdg = appdir / "opt/hst-office1.0/share/xdg/startcenter.desktop"
    icon = appdir / "usr/share/icons/hicolor/256x256/apps" / (MAIN_ID + ".png")
    if not xdg.is_file() or not icon.is_file():
        die("the .deb has no Start Center launcher or 256x256 icon")
    # appimagetool needs one launcher at the top with a plain Exec (the real ones are written per user).
    text = re.sub(r"(?m)^Exec=hst-office1\.0\b", "Exec=AppRun", xdg.read_text(encoding="utf-8"))
    (appdir / (MAIN_ID + ".desktop")).write_text(text, encoding="utf-8")
    shutil.copy2(icon, appdir / (MAIN_ID + ".png"))
    os.symlink(MAIN_ID + ".png", appdir / ".DirIcon")
    for name in ("AppRun", "appimage_desktop_integration.py"):
        shutil.copy2(HERE / "appimage" / name, appdir / name)
    (appdir / "AppRun").chmod(0o755)
    (appdir / "appimage_desktop_integration.py").chmod(0o644)
    appdir.chmod(0o755)


def build(deb, out_dir, tools, work):
    match = make_rpm.DEB_NAME.fullmatch(deb.name)
    if not match:
        die("not a single HST Office .deb name: %s" % deb.name)
    tool, runtime = tools
    appdir = work / "HSTOffice.AppDir"
    make_appdir(deb, appdir)
    out = out_dir / ("HSTOffice_%s_Linux_x86-64.AppImage" % match.group("release"))
    out.unlink(missing_ok=True)
    # The tool is itself an AppImage: extract-and-run works in containers without FUSE.
    env = dict(os.environ, ARCH="x86_64", APPIMAGE_EXTRACT_AND_RUN="1", NO_CLEANUP="", TMPDIR=str(work))
    run(tool, "--runtime-file", runtime, "--no-appstream", "--comp", "zstd", appdir, out, env=env,
        stdout=subprocess.DEVNULL)
    if not out.is_file():
        die("appimagetool wrote nothing")
    out.chmod(0o755)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("deb", type=pathlib.Path)
    ap.add_argument("out_dir", type=pathlib.Path)
    ap.add_argument("--tools", type=pathlib.Path, required=True, help="directory of the pinned appimagetool and runtime")
    ap.add_argument("--download", action="store_true", help="download missing pinned tools (SHA-256 checked)")
    args = ap.parse_args()
    if not args.deb.is_file():
        die("no such file: %s" % args.deb)
    if not shutil.which("file"):
        die("the `file` command is missing (appimagetool needs it): apt-get install file")
    tools = fetch_tools(args.tools.resolve(), args.download)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hst-appimage-") as tmp:
        out = build(args.deb.resolve(), args.out_dir.resolve(), tools, pathlib.Path(tmp))
    digest = make_rpm.sha256(out)
    make_rpm.add_sum(args.out_dir, out.name, digest)
    print("appimage: %s (%d MiB)" % (out, out.stat().st_size // 2**20))
    print("%s  %s" % (digest, out.name))


if __name__ == "__main__":
    main()
