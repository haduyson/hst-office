# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of the update check in a real HST Office (soffice runs as hstbuild, never as root).

Usage: python3 tests/runtime/check-update-notify.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/update-runtime] [--shots tests/output/screenshots-update] [--display :97]

Builds a test package (scripts/build-extensions.py --update-test-mode), puts it as the bundled extension into
a hard-linked copy of the instdir (the original is not modified), serves manifests from a local plain-HTTP
server on 127.0.0.1 (HST_UPDATE_TEST_URL; honoured only by test packages) signed with the real release key
(scripts/release/sign-update-manifest.py, key outside the repository), then:
  1. start-up with the Start Center: the automatic check finds 1.0.0, the notice waits for the first document
     view and appears there as an infobar ("Đã có HST Office 1.0.0 — bản mới.") -> screenshot;
  2. menu command org.hst.office.update:Check with an up-to-date manifest -> "phiên bản mới nhất" dialog;
  3. the same with the server answering 500 -> "Không kiểm tra được cập nhật" dialog; a new version -> dialog
     with the three actions; "Bỏ qua phiên bản này" removes the infobar;
  4. administrator lock (hst-update-policy.oxt, unopkg add --shared): AutoCheck off and finalized, no request.
The Xvfb display must already run; it is never started or stopped here. Exit 1 when a check fails.
"""
import argparse
import http.server
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
UNO_PORT, HTTP_PORT = 22091, 22092
EXT = "hst-vietnamese-tools"
SERVED = {}
REQUESTS = []


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        status, body = SERVED.get(self.path, (404, b""))
        REQUESTS.append(self.path)
        print("server: %s %s -> %d (%s)" % (self.command, self.path, status, self.headers.get("User-Agent")), flush=True)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def serve_manifest(srv, version, status=200):
    """Write, sign (real key) and serve a manifest whose beta channel announces `version`."""
    entry = {"version": version, "date": "2026-10-30", "notes": "https://office.hasontech.vn/#tai-ve", "critical": False,
             "downloads": {p: "https://office.hasontech.vn/tai/" + p for p in ("windows", "macos-arm", "macos-intel", "linux")}}
    path = os.path.join(srv, "latest.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"schema": 1, "channels": {"stable": None, "beta": entry}}, handle, indent=1)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "release", "sign-update-manifest.py"), path], check=True)
    for name in ("latest.json", "latest.json.sig"):
        with open(os.path.join(srv, name), "rb") as handle:
            SERVED["/" + name] = (status, handle.read() if status == 200 else b"")


def prepare_instdir(instdir, out):
    """Hard-linked instdir copy whose bundled HST extension is the freshly built test package."""
    copy = os.path.join(out, "instdir")
    if not os.path.isdir(copy):
        subprocess.run(["cp", "-al", os.path.abspath(instdir), copy], check=True)
    pkg = os.path.join(out, "ext")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build-extensions.py"), "--output", pkg, "--update-test-mode"], check=True)
    target = os.path.join(copy, "share", "extensions", EXT)
    shutil.rmtree(target, ignore_errors=True)  # removes only this copy's links, never the original files
    subprocess.run(["unzip", "-q", os.path.join(pkg, EXT + ".oxt"), "-d", target], check=True)
    shared = os.path.join(copy, "share", "uno_packages")  # real copy: unopkg --shared must not write through links
    shutil.rmtree(shared, ignore_errors=True)
    subprocess.run(["cp", "-a", os.path.join(os.path.abspath(instdir), "share", "uno_packages"), shared], check=True)
    subprocess.run(["chown", "-R", hst_gui.BUILD_USER, shared], check=True)
    return copy


def install_policy(instdir, out):
    """Administrator lock: scripts/release/build-update-policy-oxt.py, installed with unopkg add --shared."""
    pkg, home = os.path.join(out, "policy", "hst-update-policy.oxt"), os.path.join(out, "unopkg-home")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "release", "build-update-policy-oxt.py"), "--output", pkg], check=True)
    os.makedirs(home, exist_ok=True)
    subprocess.run(["chown", "-R", hst_gui.BUILD_USER, os.path.dirname(pkg), home], check=True)
    subprocess.run(["runuser", "-u", hst_gui.BUILD_USER, "--", "env", "HOME=" + home, os.path.join(instdir, "program", "unopkg"),
                    "add", "--shared", "-s", pkg, "-env:UserInstallation=file://" + os.path.join(home, "profile")],
                   check=True, timeout=180)


def policy_phase(instdir, out, results, display=":97"):
    """With the policy installed: AutoCheck reads false, user writes are refused, no request reaches the server."""
    install_policy(instdir, out)
    SERVED.clear()
    REQUESTS.clear()
    office = hst_gui.Office(instdir, os.path.join(out, "gui-policy"), UNO_PORT, display=display, nodefault=False)
    try:
        office.start()
        office.load("private:factory/swriter")
        time.sleep(8)
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", "/org.hasontech.hstoffice.UpdateCheck"
        node = office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
        locked_off = node.getPropertyValue("AutoCheck") is False
        try:
            node.setPropertyValue("AutoCheck", True)
            node.commitChanges()
            refused = node.getPropertyValue("AutoCheck") is False
        except Exception as error:  # noqa: BLE001 - configmgr: modification of finalized item
            refused = "finalized" in str(error)
    finally:
        office.stop()
    for label, ok in (("policy: AutoCheck locked off", locked_off), ("policy: user change refused", refused),
                      ("policy: no automatic request", not REQUESTS)):
        results.append((label, ok))
        print("%-4s %s" % ("PASS" if ok else "FAIL", label), flush=True)


def wait(predicate, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.5)
    return False


def dialog_shot(office, shots, name, results, label, pattern):
    """Wait for the result dialog, screenshot it, close it with Escape."""
    found = []
    ok = wait(lambda: found.extend(w for w in hst_gui.toplevels(office.display, office.pid) if w[1] == "Kiểm tra cập nhật") or found, 30)
    time.sleep(1.0)
    office.screenshot(os.path.join(shots, name))
    results.append((label, ok))
    if found:  # click "Đóng" (AppFont box 202..242 x 48..62 of a 250 x 70 dialog); Xvfb has no WM to focus for keys
        wid = found[0][0]
        info = subprocess.run(["xwininfo", "-display", office.display, "-id", wid], capture_output=True, text=True).stdout
        width, height = (int(re.search(r"%s: (\d+)" % k, info).group(1)) for k in ("Width", "Height"))
        env = dict(os.environ, DISPLAY=office.display)
        subprocess.run(["xdotool", "mousemove", "--window", wid, str(int(width * 222 / 250)), str(int(height * 55 / 70)),
                        "click", "1"], env=env, check=False, timeout=10)
        closed = wait(lambda: not [w for w in hst_gui.toplevels(office.display, office.pid) if w[1] == "Kiểm tra cập nhật"], 10)
        results.append((label + ": closes with Đóng", closed))
        ok = ok and closed
    print("%-4s %s (%s)" % ("PASS" if ok else "FAIL", label, pattern), flush=True)


def menu_shot(office, path):
    """Open the Start Center's HST menu (menu bar entry "HST", 4th-from-left label) for a screenshot, then close it."""
    env = dict(os.environ, DISPLAY=office.display)
    windows = [w for w in hst_gui.toplevels(office.display, office.pid) if w[1] == "HST Office"]
    if not windows:
        print("note: Start Center window not found, no menu screenshot", flush=True)
        return
    office.raise_windows()
    subprocess.run(["xdotool", "mousemove", "--window", windows[0][0], "141", "14", "click", "1"], env=env, check=False, timeout=10)
    time.sleep(1.5)
    hst_gui.screenshot(path, office.display)
    subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=10)
    time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", default=os.path.join(ROOT, "upstream", "libreoffice", "instdir"))
    ap.add_argument("--out", default=os.path.join(ROOT, "tests", "output", "update-runtime"))
    ap.add_argument("--shots", default=os.path.join(ROOT, "tests", "output", "screenshots-update"))
    ap.add_argument("--display", default=":97")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.shots, exist_ok=True)
    srv = os.path.join(args.out, "srv")
    os.makedirs(srv, exist_ok=True)
    instdir = prepare_instdir(args.instdir, args.out)
    hst_gui.setup_uno(instdir)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ["HST_UPDATE_TEST_URL"] = "http://127.0.0.1:%d/latest.json" % HTTP_PORT
    results = []
    office = hst_gui.Office(instdir, os.path.join(args.out, "gui"), UNO_PORT, display=args.display, nodefault=False)
    try:
        serve_manifest(srv, "1.0.0")
        office.start()
        time.sleep(4)
        office.screenshot(os.path.join(args.shots, "01-start-center.png"))
        menu_shot(office, os.path.join(args.shots, "01b-start-center-hst-menu.png"))
        doc = office.load("private:factory/swriter")
        controller = doc.getCurrentController()
        ok = wait(lambda: controller.hasInfobar("hst-update-available"), 30)
        time.sleep(1.5)
        office.screenshot(os.path.join(args.shots, "02-writer-infobar-new-version.png"))
        results.append(("automatic check shows the infobar on the first document", ok))
        print("%-4s infobar after Start Center start" % ("PASS" if ok else "FAIL"), flush=True)
        frame = controller.getFrame()
        serve_manifest(srv, "1.0.0-beta.2")
        office.dispatch(frame, "org.hst.office.update:Check")
        dialog_shot(office, args.shots, "03-menu-up-to-date.png", results, "menu check: up to date", "phiên bản mới nhất")
        SERVED.clear()
        SERVED["/latest.json"] = (500, b"")
        office.dispatch(frame, "org.hst.office.update:Check")
        dialog_shot(office, args.shots, "04-menu-could-not-check.png", results, "menu check: could not check", "Không kiểm tra được")
        serve_manifest(srv, "1.0.0")
        office.dispatch(frame, "org.hst.office.update:Check")
        dialog_shot(office, args.shots, "05-menu-new-version.png", results, "menu check: new version", "Đã có HST Office 1.0.0")
        office.dispatch(frame, "org.hst.office.update:Skip")
        ok = wait(lambda: not controller.hasInfobar("hst-update-available"), 10)
        results.append(("skip removes the infobar", ok))
        print("%-4s skip removes the infobar" % ("PASS" if ok else "FAIL"), flush=True)
        office.screenshot(os.path.join(args.shots, "06-writer-after-skip.png"))
    finally:
        office.stop()
    try:
        policy_phase(instdir, args.out, results, display=args.display)
    finally:
        server.shutdown()
        server.server_close()
    failed = [label for label, ok in results if not ok]
    print("update runtime: %d checks, %d failed%s" % (len(results), len(failed), (": " + "; ".join(failed)) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
