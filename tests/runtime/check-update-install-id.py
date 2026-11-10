# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of the anonymous install ID of the update check in a real HST Office (Linux).

Usage: python3 tests/runtime/check-update-install-id.py --display :157 [--instdir upstream/libreoffice/instdir]
           [--out tests/output/update-install-id] [--uno-port N] [--http-port N]

Uses the hard-linked instdir copy, the test package and the local signed-manifest server of check-update-notify.py:
  1. fresh profile: the automatic check sends GET /latest.json?i=<uuid4>, the .sig request carries no ID, the ID is
     stored in the profile; Tùy chọn ▸ HST Office ▸ Cập nhật shows the box ticked and editable;
  2. "Kiểm tra cập nhật" sends the same ID; unticking the box (OK) stores SendInstallId=false and the next check
     sends /latest.json without a query; ticking it again sends the same ID again; a restart keeps the ID;
  3. administrator lock (shared policy extension, build-update-policy-oxt.py --keep-autocheck --no-install-id): the
     box is unticked and greyed out with the lock note, and a check sends no ID.
Screenshot: options-update-page.png (the Options dialog opened at the page). The Xvfb display must already run; it is
never started or stopped here. Exit 1 when a check fails.
"""
import argparse
import http.server
import importlib.util
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
from update_test_gui import add_port_options, dialog_shot, ports, wait  # noqa: E402

_spec = importlib.util.spec_from_file_location("check_update_notify", os.path.join(HERE, "check-update-notify.py"))
notify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(notify)

PAGE = "vnd.sun.star.expand:$BUNDLED_EXTENSIONS/hst-vietnamese-tools/dialogs/Update.xdl"
LEGACY = "/org.hasontech.hstoffice.UpdateCheck"
WITH_ID = re.compile(r"^/latest\.json\?i=([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$")
RESULTS = []


def check(label, ok, detail=""):
    RESULTS.append((label, bool(ok)))
    print("%-4s %s  %s" % ("PASS" if ok else "FAIL", label, str(detail)[:200]), flush=True)
    return ok


def setting(office, name):
    from com.sun.star.beans import PropertyValue
    arg = PropertyValue()
    arg.Name, arg.Value = "nodepath", LEGACY
    node = office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationAccess", (arg,))
    return node.getPropertyValue(name)


def manifest_requests(since):
    return [path for path in notify.REQUESTS[since:] if not path.endswith(".sig")]


def menu_check(office, frame, label):
    """Run "Kiểm tra cập nhật", close its result dialog; the manifest request it made (or None)."""
    since = len(notify.REQUESTS)
    office.dispatch(frame, "org.hst.office.update:Check")
    dialog_shot(office, office.workdir, "check.png", RESULTS, label + ": result dialog", "Kiểm tra cập nhật")
    requests = manifest_requests(since)
    return requests[-1] if requests else None


class Page:
    """Tùy chọn ▸ HST Office ▸ Cập nhật built from the installed extension with its handler service."""

    def __init__(self, office, parent):
        self.handler = office.service("org.hst.office.vi.OptionsUpdate")
        check("the Cập nhật handler service exists", self.handler is not None)
        provider = office.service("com.sun.star.awt.ContainerWindowProvider")
        self.window = provider.createContainerWindow(PAGE, "", parent, self.handler)
        self.handler.callHandlerMethod(self.window, "initialize", "external_event")
        self.box = self.window.getControl("sendInstallId")

    def state(self):
        return self.box.getState(), self.box.isEnabled(), self.window.getControl("locked").isVisible()

    def set_and_ok(self, ticked):
        self.box.setState(1 if ticked else 0)
        self.handler.callHandlerMethod(self.window, "ok", "external_event")

    def close(self):
        self.window.dispose()


def options_screenshot(office, frame, path):
    """Open Công cụ ▸ Tùy chọn at the Cập nhật page for a screenshot, then close it."""
    from com.sun.star.beans import PropertyValue
    arg = PropertyValue()
    arg.Name, arg.Value = "OptionsPageURL", PAGE
    runner = threading.Thread(target=lambda: office.dispatch(frame, ".uno:OptionsTreeDialog", (arg,)), daemon=True)
    runner.start()
    found = wait(lambda: any(name.startswith("Tùy chọn") for _w, name in hst_gui.toplevels(office.display, office.pid)), 30)
    time.sleep(2)
    hst_gui.screenshot(path, office.display)
    subprocess.run(["xdotool", "key", "Escape"], env=dict(os.environ, DISPLAY=office.display), check=False, timeout=10)
    runner.join(15)
    check("Công cụ ▸ Tùy chọn opens at the Cập nhật page (screenshot)", found, path)


def phase_user(instdir, out, uno_port):
    office = hst_gui.Office(instdir, os.path.join(out, "gui"), uno_port, display=DISPLAY, nodefault=False)
    try:
        office.start()
        check("automatic check reached the server", wait(lambda: manifest_requests(0), 40), notify.REQUESTS)
        first = manifest_requests(0)[0] if manifest_requests(0) else ""
        match = WITH_ID.match(first)
        check("automatic check sends /latest.json?i=<uuid4>", match, first)
        install_id = match.group(1) if match else None
        check("the .sig request carries no ID", all(p == "/latest.json.sig" for p in notify.REQUESTS if ".sig" in p))
        check("the ID is stored in the profile", setting(office, "InstallId") == install_id, setting(office, "InstallId"))
        doc = office.load("private:factory/swriter")
        frame = doc.getCurrentController().getFrame()
        page = Page(office, frame.getContainerWindow())
        check("page: ticked by default, editable, no lock note", page.state() == (1, True, False), page.state())
        check("menu check sends the same ID", menu_check(office, frame, "with ID") == first)
        page.set_and_ok(False)
        check("unticked + OK stores SendInstallId=false", setting(office, "SendInstallId") is False)
        check("unticked: the check sends no ID", menu_check(office, frame, "without ID") == "/latest.json")
        options_screenshot(office, frame, os.path.join(out, "options-update-page.png"))
        page.set_and_ok(True)
        check("ticked again: the same ID again", menu_check(office, frame, "ticked again") == first)
        page.close()
        doc.close(True)
    finally:
        office.stop()
    office.start(fresh=False)
    try:
        frame = office.load("private:factory/swriter").getCurrentController().getFrame()
        check("after a restart: the same ID", menu_check(office, frame, "after restart") == first)
    finally:
        office.stop()


def phase_locked(instdir, out, uno_port):
    notify.install_policy(instdir, out, ["--keep-autocheck", "--no-install-id"])
    office = hst_gui.Office(instdir, os.path.join(out, "gui"), uno_port, display=DISPLAY, nodefault=False)
    office.start(fresh=False)  # the user's own value says true; the administrator's lock wins
    try:
        frame = office.load("private:factory/swriter").getCurrentController().getFrame()
        page = Page(office, frame.getContainerWindow())
        check("locked: unticked, greyed out, lock note shown", page.state() == (0, False, True), page.state())
        page.set_and_ok(True)
        check("locked: OK writes nothing", setting(office, "SendInstallId") is False)
        check("locked: the check sends no ID", menu_check(office, frame, "locked") == "/latest.json")
        page.close()
    finally:
        office.stop()


def main():
    global DISPLAY
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream", "libreoffice", "instdir"))
    ap.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests", "output", "update-install-id"))
    ap.add_argument("--display", required=True)
    add_port_options(ap, 22191, 22192)
    args = ap.parse_args()
    DISPLAY = args.display
    uno_port, http_port = ports(args)
    out = os.path.abspath(args.out)
    srv = os.path.join(out, "srv")
    os.makedirs(srv, exist_ok=True)
    instdir = notify.prepare_instdir(args.instdir, out)
    hst_gui.setup_uno(instdir)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", http_port), notify.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ["HST_UPDATE_TEST_URL"] = "http://127.0.0.1:%d/latest.json" % http_port
    try:
        notify.serve_manifest(srv, "1.0.0-beta.2")  # older than the package: "up to date", so no retries
        phase_user(instdir, out, uno_port)
        phase_locked(instdir, out, uno_port)
    finally:
        server.shutdown()
        server.server_close()
    failed = [label for label, ok in RESULTS if not ok]
    print("install-id runtime: %d checks, %d failed%s" % (len(RESULTS), len(failed), (": " + "; ".join(failed)) if failed else ""))
    return 1 if failed else 0


DISPLAY = ":97"

if __name__ == "__main__":
    sys.exit(main())
