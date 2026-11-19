# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of the new-version pop-up after the automatic check, in a real HST Office (Linux, Xvfb).

Usage: python3 tests/runtime/check-update-popup.py --instdir <instdir> [--out DIR] [--display :143]
           [--uno-port N] [--http-port N]

The test package of the extension (scripts/build-extensions.py --update-test-mode) goes into a hard-linked copy of
the instdir (check-update-notify.prepare_instdir); a local plain-HTTP server on 127.0.0.1 serves manifests signed
with the release key (HST_UPDATE_TEST_URL, honoured only by test packages). No published feed is read or changed.
  1. the pop-up shows over the document once the window is ready; it is modeless: the document window stays
     enabled and real key presses (XTEST) land in the document while the pop-up is open;
  2. "Để sau" closes it and remembers the version for the day: the next start's check shows the infobar instead;
  3. a newer version is announced at once; "Bỏ qua bản này" saves SkippedVersion: the next start shows nothing;
  4. AutoCheck off ("no update check"): no request, no pop-up; then the administrator policy (no request).
The Xvfb display must already run. Exit 1 when a check fails.
"""
import argparse
import http.server
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
from hst_gui_profile import seed_profile  # noqa: E402
from update_test_gui import RESULTS, add_port_options, check, click, dialogs, ports, wait  # noqa: E402

TITLE = "Cập nhật HST Office"
NODE = "/org.openoffice.Office.HSTUpdate"
LABELS = ("Tải về", "Để sau", "Bỏ qua phiên bản này")  # Linux test manifest: no installer, so "Tải về" first
_spec = importlib.util.spec_from_file_location("check_update_notify", os.path.join(os.path.dirname(__file__), "check-update-notify.py"))
notify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(notify)


def serve(srv, version):
    """Sign (real key, read by the signing script from its own config) and serve a manifest announcing `version`."""
    entry = {"version": version, "date": "2026-11-19", "notes": "https://office.hasontech.vn/#tai-ve", "critical": False,
             "downloads": {p: "https://office.hasontech.vn/tai/" + p for p in ("windows", "macos-arm", "macos-intel", "linux")}}
    path = os.path.join(srv, "latest.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"schema": 1, "channels": {"stable": entry, "beta": entry}}, handle, indent=1)
    subprocess.run([sys.executable, os.path.join(hst_gui.ROOT, "scripts", "release", "sign-update-manifest.py"), path],
                   check=True, stdout=subprocess.DEVNULL)
    for name in ("latest.json", "latest.json.sig"):
        with open(os.path.join(srv, name), "rb") as handle:
            notify.SERVED["/" + name] = (200, handle.read())


def button_x(index):
    """Centre of the pop-up's button `index` as a fraction of its 280 AppFont width (update_popup.show)."""
    x = 8
    for label in LABELS[:index]:
        x += max(48, 8 + 5 * len(label)) + 4
    return (x + max(48, 8 + 5 * len(LABELS[index])) / 2) / 280


def load(office, url):
    from com.sun.star.beans import PropertyValue
    prop = PropertyValue()
    prop.Name, prop.Value = "OnMainThread", True
    return office.desktop().loadComponentFromURL(url, "_blank", 0, (prop,))


def start(office, fresh, config=()):
    """Start (a kept profile gets LastCheck 0 and `config` first, so its start-up check runs) and open Writer."""
    if not fresh:
        seed_profile(os.path.join(office.workdir, "profile"), [(NODE, "LastCheck", "0")] + list(config))
    notify.REQUESTS.clear()
    office.start(fresh=fresh)
    return load(office, "private:factory/swriter")


def reminder(office):
    try:
        with open(os.path.join(office.workdir, "home", ".cache", "hst-office", "update", "update-reminder.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def setting(office, name):
    from com.sun.star.beans import PropertyValue
    arg = PropertyValue()
    arg.Name, arg.Value = "nodepath", NODE
    access = office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationAccess", (arg,))
    return access.getPropertyValue(name)


def typing_goes_through(office, doc):
    """Real key presses (XTEST) into the document window while the pop-up is open."""
    env = dict(os.environ, DISPLAY=office.display)
    window = [w for w in hst_gui.toplevels(office.display, office.pid) if " — HST " in w[1] or "Writer" in w[1]]
    if not window:
        return False
    subprocess.run(["xdotool", "windowfocus", "--sync", window[0][0]], env=env, check=False, timeout=10)
    subprocess.run(["xdotool", "type", "--delay", "60", "hstpopup"], env=env, check=False, timeout=30)
    return wait(lambda: "hstpopup" in doc.getText().getString(), 10)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", required=True)
    ap.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests", "output", "update-popup"))
    ap.add_argument("--display", default=":143")
    add_port_options(ap, 22093, 22094)
    args = ap.parse_args()
    notify.UNO_PORT, http_port = ports(args)
    shots = os.path.join(args.out, "shots")
    os.makedirs(shots, exist_ok=True)
    srv = os.path.join(args.out, "srv")
    os.makedirs(srv, exist_ok=True)
    instdir = notify.prepare_instdir(args.instdir, args.out)
    hst_gui.setup_uno(instdir)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", http_port), notify.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ["HST_UPDATE_TEST_URL"] = "http://127.0.0.1:%d/latest.json" % http_port
    work = os.path.join(args.out, "gui")
    # runuser resets HOME to the build user's own (not writable here): the reminder file needs a writable cache
    home = {"HOME": os.path.join(work, "home"), "XDG_CACHE_HOME": os.path.join(work, "home", ".cache")}
    office = hst_gui.Office(instdir, work, notify.UNO_PORT, display=args.display, nodefault=False, env=home)
    popup = lambda: dialogs(office, TITLE)  # noqa: E731
    try:
        serve(srv, "1.0.8")
        doc = start(office, fresh=True)
        controller = doc.getCurrentController()
        check("1: the pop-up shows after the start-up check", wait(popup, 90))
        time.sleep(1.5)
        office.screenshot(os.path.join(shots, "1-popup.png"))
        check("1: the document window stays enabled (modeless)", controller.getFrame().getContainerWindow().isEnabled())
        check("1: typing reaches the document while the pop-up is open", typing_goes_through(office, doc) and popup())
        check("1: no infobar while the pop-up shows it", not controller.hasInfobar("hst-update-available"))
        office.screenshot(os.path.join(shots, "1-typed.png"))
        click(office, TITLE, button_x(1), 41 / 54)
        check("2: Để sau closes the pop-up", wait(lambda: not popup(), 10))
        check("2: the version is remembered for the day", (reminder(office) or {}).get("version") == "1.0.8")
        office.stop()
        doc = start(office, fresh=False)
        controller = doc.getCurrentController()
        check("2: next start: infobar, no second pop-up the same day",
              wait(lambda: controller.hasInfobar("hst-update-available"), 60) and not popup())
        check("2: the check did run", any(r.startswith("/latest.json") for r in notify.REQUESTS))
        office.screenshot(os.path.join(shots, "2-later-infobar.png"))
        office.stop()
        serve(srv, "1.0.9")
        doc = start(office, fresh=False)
        check("3: a newer version is announced at once", wait(popup, 90))
        time.sleep(1.5)
        office.screenshot(os.path.join(shots, "3-newer-popup.png"))
        click(office, TITLE, button_x(2), 41 / 54)
        check("3: Bỏ qua bản này closes the pop-up", wait(lambda: not popup(), 10))
        check("3: SkippedVersion saved", wait(lambda: setting(office, "SkippedVersion") == "1.0.9", 10))
        office.stop()
        doc = start(office, fresh=False)
        controller = doc.getCurrentController()
        time.sleep(20)
        check("3: next start: the skipped version shows nothing", not popup() and not controller.hasInfobar("hst-update-available"))
        check("3: the check did run", any(r.startswith("/latest.json") for r in notify.REQUESTS))
        office.stop()
        serve(srv, "1.0.10")
        doc = start(office, fresh=False, config=[(NODE, "AutoCheck", "false")])
        time.sleep(25)
        check("4: AutoCheck off: no request, no pop-up", not notify.REQUESTS and not popup())
    finally:
        office.stop()
    try:
        notify.policy_phase(instdir, args.out, RESULTS, display=args.display)
    finally:
        server.shutdown()
        server.server_close()
    failed = [label for label, ok in RESULTS if not ok]
    print("update pop-up: %d checks, %d failed%s" % (len(RESULTS), len(failed), (": " + "; ".join(failed)) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
