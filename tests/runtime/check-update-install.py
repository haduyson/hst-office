#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of "Cập nhật ngay" in a real HST Office (soffice runs as hstbuild, never as root).

Usage: python3 tests/runtime/check-update-install.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/update-install-runtime] [--shots tests/output/screenshots-update-install] [--display :87]

Test package (build-extensions.py --update-test-mode) in a hard-linked instdir copy, a local HTTP server on 127.0.0.1
serving a schema 2 manifest signed with the real release key plus a dummy .deb; HST_UPDATE_TEST_URL points at it and
HST_UPDATE_DRY_RUN makes the helper log the install and relaunch commands instead of running them. Checks:
  1. HST > Kiểm tra cập nhật shows "Cập nhật ngay"; clicking it downloads (progress dialog), verifies and asks
     "Đã tải xong HST Office X. Đóng HST Office để cập nhật?"; "Để sau" keeps the file and the office running;
  2. the same command again reuses the file (no second download), the question is confirmed: the office closes through
     the normal terminate path and the helper logs the apt-get command line and the relaunch (dry run);
  3. a manifest whose SHA256 does not match: error message with "Tải về", nothing kept in the cache, office stays open;
  4. AllowInstall locked off (hst-update-policy.oxt --no-install): no "Cập nhật ngay" button, Install command only opens the browser path.
The Xvfb display must already run; it is never started or stopped here. Exit 1 when a check fails.
"""
import argparse
import hashlib
import http.server
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
_spec = importlib.util.spec_from_file_location("notify", os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-update-notify.py"))
notify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(notify)
UNO_PORT, HTTP_PORT = 22094, 22093
DEB = b"!<arch>\ndummy hst office package for the update test\n" * 2000
DEB_NAME = "HSTOffice_9.9.9_Linux_x86-64.deb"
TITLE = "Cập nhật HST Office"
RESULTS = []


def check(label, ok):
    RESULTS.append((label, bool(ok)))
    print("%-4s %s" % ("PASS" if ok else "FAIL", label), flush=True)
    return ok


def serve_manifest(srv, sha=None):
    """Sign (real key) and serve a schema 2 manifest announcing 9.9.9 with the dummy .deb as the Linux installer."""
    entry = {"url": "http://127.0.0.1:%d/files/%s" % (HTTP_PORT, DEB_NAME), "sha256": sha or hashlib.sha256(DEB).hexdigest(), "size": len(DEB)}
    release = {"version": "9.9.9", "date": "2026-10-31", "notes": "https://office.hasontech.vn/#tai-ve", "critical": False,
               "downloads": {p: "https://office.hasontech.vn/tai/" + p for p in ("windows", "macos-arm", "macos-intel", "linux")},
               "installers": {"linux": entry}}
    path = os.path.join(srv, "latest.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"schema": 2, "channels": {"stable": release, "beta": None}}, handle, indent=1)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "release", "sign-update-manifest.py"), "--allow-test-urls", path], check=True, stdout=subprocess.DEVNULL)
    for name in ("latest.json", "latest.json.sig"):
        with open(os.path.join(srv, name), "rb") as handle:
            notify.SERVED["/" + name] = (200, handle.read())
    notify.SERVED["/files/" + DEB_NAME] = (200, DEB)


def dialogs(office, title):
    return [w for w in hst_gui.toplevels(office.display, office.pid) if w[1] == title]


def click(office, title, fx, fy, timeout=60):
    """Wait for the dialog `title`, click at the fraction (fx, fy) of its window; False when it never shows."""
    found = []
    if not notify.wait(lambda: found.extend(dialogs(office, title)) or found, timeout):
        return False
    time.sleep(1.0)
    wid = found[0][0]
    info = subprocess.run(["xwininfo", "-display", office.display, "-id", wid], capture_output=True, text=True).stdout
    width, height = (int(re.search(r"%s: (\d+)" % k, info).group(1)) for k in ("Width", "Height"))
    env = dict(os.environ, DISPLAY=office.display)
    subprocess.run(["xdotool", "mousemove", "--window", wid, str(int(width * fx)), str(int(height * fy)), "click", "1"],
                   env=env, check=False, timeout=10)
    return True


def dispatch_async(office, frame, command):
    """The Install command runs its modal dialogs inside the dispatch call: dispatch from a helper thread."""
    threading.Thread(target=office.dispatch, args=(frame, command), daemon=True).start()


def shot(office, shots, name):
    time.sleep(0.5)
    office.screenshot(os.path.join(shots, name))


def cache_files(office):
    folder = os.path.join(office.workdir, "cache", "hst-office", "update")
    return folder, sorted(f for f in os.listdir(folder) if f.endswith(".deb") or f.endswith(".part")) if os.path.isdir(folder) else []


def deb_requests():
    return len([r for r in notify.REQUESTS if r.endswith(".deb")])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", default=os.path.join(ROOT, "upstream", "libreoffice", "instdir"))
    ap.add_argument("--out", default=os.path.join(ROOT, "tests", "output", "update-install-runtime"))
    ap.add_argument("--shots", default=os.path.join(ROOT, "tests", "output", "screenshots-update-install"))
    ap.add_argument("--display", default=":87")
    args = ap.parse_args()
    os.makedirs(args.shots, exist_ok=True)
    for name in ("gui", "gui-bad", "gui-policy"):  # a cached installer of an earlier run would skip the download
        shutil.rmtree(os.path.join(args.out, name, "cache"), ignore_errors=True)
        os.makedirs(os.path.join(args.out, name), exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, os.path.join(args.out, name)], check=True)
    srv = os.path.join(args.out, "srv")
    os.makedirs(srv, exist_ok=True)
    instdir = notify.prepare_instdir(args.instdir, args.out)
    hst_gui.setup_uno(instdir)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), notify.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {"HST_UPDATE_TEST_URL": "http://127.0.0.1:%d/latest.json" % HTTP_PORT, "HST_UPDATE_DRY_RUN": "1"}
    os.environ.update(env)
    # runuser resets HOME to the build user's real home; the per-user cache goes below the test directory instead
    office = hst_gui.Office(instdir, os.path.join(args.out, "gui"), UNO_PORT, display=args.display, nodefault=False,
                            env=dict(env, XDG_CACHE_HOME=os.path.join(args.out, "gui", "cache")))
    try:
        run_main(office, srv, args)
    finally:
        office.stop()
    try:
        run_bad_hash(instdir, srv, args, env)
        run_policy(instdir, srv, args, env)
    finally:
        server.shutdown()
        server.server_close()
    failed = [label for label, ok in RESULTS if not ok]
    print("update install runtime: %d checks, %d failed%s" % (len(RESULTS), len(failed), (": " + "; ".join(failed)) if failed else ""))
    return 1 if failed else 0


def run_main(office, srv, args):
    serve_manifest(srv)
    office.start()
    doc = office.load("private:factory/swriter")
    frame = doc.getCurrentController().getFrame()
    notify.REQUESTS.clear()
    print("dispatching Check", flush=True)
    office.dispatch(frame, "org.hst.office.update:Check")
    print("dispatched", flush=True)
    # result dialog (300 x 70): first button "Cập nhật ngay" at x 8..68, y 48..62
    check("result dialog offers Cập nhật ngay", click(office, "Kiểm tra cập nhật", 38 / 300.0, 55 / 70.0))
    check("question after download and verification", notify.wait(lambda: dialogs(office, TITLE), 90))
    time.sleep(1.0)
    shot(office, args.shots, "01-ready-question.png")
    folder, files = cache_files(office)
    path = os.path.join(folder, DEB_NAME)
    check("installer cached and identical", files == [DEB_NAME] and open(path, "rb").read() == DEB)
    check("one installer download", deb_requests() == 1)
    # prompt (300 x 64): "Để sau" is the last button, x 248..292, y 44..58
    click(office, TITLE, 270 / 300.0, 51 / 64.0)
    time.sleep(2)
    check("Để sau keeps the file and the office", office.pid is not None and os.path.isfile(path))
    dispatch_async(office, frame, "org.hst.office.update:Install")
    check("second click asks again", notify.wait(lambda: dialogs(office, TITLE), 60))
    check("file reused without a second download", deb_requests() == 1)
    # first button "Cập nhật ngay": x 8..81 -> centre 44.5
    click(office, TITLE, 44.5 / 300.0, 51 / 64.0)
    gone = notify.wait(lambda: office.pid is None, 60)
    check("office closed through the terminate path", gone)
    log = os.path.join(folder, "update.log")
    notify.wait(lambda: os.path.isfile(log) and "DRYRUN relaunch" in open(log, encoding="utf-8").read(), 60)
    text = open(log, encoding="utf-8").read() if os.path.isfile(log) else ""
    print(text, flush=True)
    check("helper logged the install command (dry run)", re.search(r"DRYRUN install:.*(apt-get install -y|pkcon install-local) %s" % re.escape(path), text) is not None)
    check("helper logged the relaunch", "DRYRUN relaunch" in text)
    check("dry run keeps the installer", os.path.isfile(path))


def run_bad_hash(instdir, srv, args, env):
    serve_manifest(srv, sha="0" * 64)
    office = hst_gui.Office(instdir, os.path.join(args.out, "gui-bad"), UNO_PORT, display=args.display, nodefault=False,
                            env=dict(env, XDG_CACHE_HOME=os.path.join(args.out, "gui-bad", "cache")))
    try:
        office.start()
        frame = office.load("private:factory/swriter").getCurrentController().getFrame()
        dispatch_async(office, frame, "org.hst.office.update:Install")
        check("bad SHA256: error message shown", notify.wait(lambda: dialogs(office, TITLE), 90))
        time.sleep(1.0)
        shot(office, args.shots, "02-bad-hash.png")
        click(office, TITLE, 270 / 300.0, 51 / 64.0)  # Đóng
        time.sleep(1.5)
        check("bad SHA256: nothing kept in the cache", cache_files(office)[1] == [])
        check("bad SHA256: office still running", office.pid is not None)
    finally:
        office.stop()


def run_policy(instdir, srv, args, env):
    serve_manifest(srv)
    pkg, home = os.path.join(args.out, "policy", "hst-update-policy.oxt"), os.path.join(args.out, "unopkg-home")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "release", "build-update-policy-oxt.py"), "--output", pkg,
                    "--no-install", "--keep-autocheck"], check=True, stdout=subprocess.DEVNULL)
    os.makedirs(home, exist_ok=True)
    subprocess.run(["chown", "-R", hst_gui.BUILD_USER, os.path.dirname(pkg), home], check=True)
    subprocess.run(["runuser", "-u", hst_gui.BUILD_USER, "--", "env", "HOME=" + home, os.path.join(instdir, "program", "unopkg"),
                    "add", "--shared", "-s", pkg, "-env:UserInstallation=file://" + os.path.join(home, "profile")], check=True, timeout=180)
    notify.REQUESTS.clear()
    office = hst_gui.Office(instdir, os.path.join(args.out, "gui-policy"), UNO_PORT, display=args.display, nodefault=False,
                            env=dict(env, XDG_CACHE_HOME=os.path.join(args.out, "gui-policy", "cache")))
    try:
        office.start()
        frame = office.load("private:factory/swriter").getCurrentController().getFrame()
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", "/org.hasontech.hstoffice.UpdateCheck"
        node = office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
        check("policy: AllowInstall locked false", node.getPropertyValue("AllowInstall") is False)
        notify.REQUESTS.clear()
        office.dispatch(frame, "org.hst.office.update:Check")
        found = notify.wait(lambda: dialogs(office, "Kiểm tra cập nhật"), 60)
        time.sleep(1.0)
        shot(office, args.shots, "03-policy-no-install-button.png")
        check("policy: result dialog shown", found)
        # without Cập nhật ngay the first button is "Tải về" and Đóng stays at x 252..292 of 300; click Đóng
        click(office, "Kiểm tra cập nhật", 272 / 300.0, 55 / 70.0)
        dispatch_async(office, frame, "org.hst.office.update:Install")
        time.sleep(4)
        check("policy: Install downloads nothing", deb_requests() == 0 and not dialogs(office, TITLE))
    finally:
        office.stop()


if __name__ == "__main__":
    sys.exit(main())
