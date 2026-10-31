# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of the administrator lock of the update check through a share/registry .xcd (Linux).

Usage: python3 tests/runtime/check-update-lock.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/update-lock] [--shots tests/output/screenshots-update-lock] [--display :97]

Uses the hard-linked instdir copy and the local manifest server of check-update-notify.py and adds
hst-update-policy.xcd (written by scripts/release/build-update-policy-oxt.py --xcd) to the copy's share/registry:
  A. AutoCheck=false + ManualCheck=false finalized, and an old per-user value in the profile:
     the core settings read back locked, a user write is refused, the old SkippedVersion is migrated once,
     the "Kiểm tra cập nhật…" command reports disabled (menu greyed) and does nothing, no request at start-up.
  B. only AutoCheck=false finalized: the menu check works and its dialog shows the AutoCheck box disabled.
The Xvfb display must already run; it is never started or stopped here. Exit 1 when a check fails.
"""
import argparse
import http.server
import importlib.util
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402

_spec = importlib.util.spec_from_file_location("check_update_notify", os.path.join(HERE, "check-update-notify.py"))
notify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(notify)

ROOT = hst_gui.ROOT
UNO_PORT, HTTP_PORT = 22843, 22844
CORE = "/org.openoffice.Office.HSTUpdate"
LEGACY = "/org.hasontech.hstoffice.UpdateCheck"
READONLY = 16


def write_xcd(instdir, out, flags):
    """(Re)write <copy>/share/registry/hst-update-policy.xcd; the registry folder of the copy holds real files."""
    path = os.path.join(instdir, "share", "registry", "hst-update-policy.xcd")
    if os.path.exists(path):
        os.remove(path)  # a new file: never write through a hard link into the original instdir
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "release", "build-update-policy-oxt.py"),
                    "--output", os.path.join(out, "policy.oxt"), "--xcd", path] + flags, check=True)
    os.chmod(path, 0o644)


def node(office, path):
    from com.sun.star.beans import PropertyValue
    arg = PropertyValue()
    arg.Name, arg.Value = "nodepath", path
    return office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))


def command_enabled(office, frame, command):
    """IsEnabled that the HST protocol handler reports for `command` (what the menu shows)."""
    import unohelper
    from com.sun.star.frame import XStatusListener
    from com.sun.star.util import URL
    states = []

    class Listener(unohelper.Base, XStatusListener):
        def statusChanged(self, event):
            states.append(event.IsEnabled)

        def disposing(self, event):
            pass

    url = URL()
    url.Complete = command
    _ok, url = office.service("com.sun.star.util.URLTransformer").parseStrict(url)
    dispatch = frame.queryDispatch(url, "", 0)
    if dispatch is None:
        return None
    listener = Listener()
    dispatch.addStatusListener(listener, url)
    time.sleep(1)
    return states[-1] if states else None


def extension_tab_shot(office, path):
    """Screenshot of the Writer ribbon tab "Phần mở rộng" whose "Kiểm tra cập nhật…" entry must look disabled
    (tab position measured on the 1366x900 test display; best effort, the checks above do not depend on it)."""
    env = dict(os.environ, DISPLAY=office.display)
    windows = [w for w in hst_gui.toplevels(office.display, office.pid) if "HST" in w[1]]
    if windows:
        office.raise_windows()
        subprocess.run(["xdotool", "mousemove", "--window", windows[0][0], "954", "25", "click", "1"], env=env, check=False, timeout=10)
        time.sleep(1.5)
    hst_gui.screenshot(path, office.display)
    if windows:  # the ≡ menu at the right end of the ribbon holds the classic menus, among them HST
        subprocess.run(["xdotool", "mousemove", "--window", windows[0][0], "1223", "22", "click", "1"], env=env, check=False, timeout=10)
        time.sleep(1.5)
        hst_gui.screenshot(path.replace(".png", "-menu.png"), office.display)
        subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=10)


def record(results, label, ok, detail=""):
    results.append((label, bool(ok)))
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", label, (" (%s)" % detail) if detail else ""), flush=True)


def phase_all_off(instdir, args, srv, results):
    write_xcd(instdir, args.out, ["--no-manual-check"])
    notify.REQUESTS.clear()
    notify.serve_manifest(srv, "1.0.0")
    # An existing profile with values of the old extension schema (beta.2/beta.3), written through the
    # configuration API: values seeded into a fresh profile file are dropped by the first-start extension sync.
    seed = hst_gui.Office(instdir, os.path.join(args.out, "gui-off"), UNO_PORT, display=args.display)
    try:
        seed.start()
        old = node(seed, LEGACY)
        old.setPropertyValue("SkippedVersion", "1.0.0-beta.3")
        old.setPropertyValue("LastCheck", 1700000000)
        old.commitChanges()
    finally:
        seed.stop()
    office = hst_gui.Office(instdir, os.path.join(args.out, "gui-off"), UNO_PORT, display=args.display, nodefault=False)
    try:
        office.start(fresh=False)
        doc = office.load("private:factory/swriter")
        time.sleep(8)
        core = node(office, CORE)
        info = core.getPropertySetInfo()
        locked = {n: bool(info.getPropertyByName(n).Attributes & READONLY) for n in ("AutoCheck", "ManualCheck", "AllowInstall")}
        record(results, "xcd: AutoCheck reads false and locked", core.getPropertyValue("AutoCheck") is False and locked["AutoCheck"])
        record(results, "xcd: ManualCheck reads false and locked", core.getPropertyValue("ManualCheck") is False and locked["ManualCheck"])
        record(results, "xcd: AllowInstall not locked", not locked["AllowInstall"])
        try:
            core.setPropertyValue("AutoCheck", True)
            core.commitChanges()
            refused = core.getPropertyValue("AutoCheck") is False
        except Exception as error:  # noqa: BLE001 - configmgr refuses a finalized item
            refused = "finalized" in str(error) or "read-only" in str(error).lower()
        record(results, "xcd: user change refused", refused)
        core = node(office, CORE)
        record(results, "migration: old SkippedVersion copied once",
               core.getPropertyValue("SkippedVersion") == "1.0.0-beta.3" and core.getPropertyValue("LegacyMigrated"),
               "%r" % core.getPropertyValue("SkippedVersion"))
        record(results, "migration: old LastCheck copied", core.getPropertyValue("LastCheck") == 1700000000)
        frame = doc.getCurrentController().getFrame()
        enabled = command_enabled(office, frame, "org.hst.office.update:Check")
        record(results, "xcd: menu command reported disabled", enabled is False, "IsEnabled=%r" % enabled)
        office.dispatch(frame, "org.hst.office.update:Check")
        time.sleep(4)
        dialog = [w for w in hst_gui.toplevels(office.display, office.pid) if w[1] == "Kiểm tra cập nhật"]
        record(results, "xcd: menu command shows no dialog", not dialog)
        extension_tab_shot(office, os.path.join(args.shots, "01-ribbon-check-disabled.png"))
        record(results, "xcd: no request to the update server", not notify.REQUESTS, ", ".join(notify.REQUESTS))
    finally:
        office.stop()


def phase_checkbox(instdir, args, srv, results):
    write_xcd(instdir, args.out, [])  # AutoCheck=false only
    notify.REQUESTS.clear()
    notify.serve_manifest(srv, "1.0.0-beta.2")
    office = hst_gui.Office(instdir, os.path.join(args.out, "gui-box"), UNO_PORT, display=args.display, nodefault=False)
    try:
        office.start()
        doc = office.load("private:factory/swriter")
        time.sleep(6)
        record(results, "AutoCheck locked off: no request at start-up", not notify.REQUESTS, ", ".join(notify.REQUESTS))
        frame = doc.getCurrentController().getFrame()
        record(results, "ManualCheck allowed: menu command enabled", command_enabled(office, frame, "org.hst.office.update:Check") is True)
        office.dispatch(frame, "org.hst.office.update:Check")
        notify.dialog_shot(office, args.shots, "03-menu-check-autocheck-locked.png", results,
                           "menu check works, AutoCheck box disabled (see screenshot)", "phiên bản mới nhất")
        record(results, "menu check contacted the server", bool(notify.REQUESTS))
    finally:
        office.stop()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instdir", default=os.path.join(ROOT, "upstream", "libreoffice", "instdir"))
    ap.add_argument("--out", default=os.path.join(ROOT, "tests", "output", "update-lock"))
    ap.add_argument("--shots", default=os.path.join(ROOT, "tests", "output", "screenshots-update-lock"))
    ap.add_argument("--display", default=":97")
    args = ap.parse_args()
    for d in (args.out, args.shots):
        os.makedirs(d, exist_ok=True)
    srv = os.path.join(args.out, "srv")
    os.makedirs(srv, exist_ok=True)
    notify.args = args  # serve_manifest reads the module-level args of check-update-notify
    instdir = notify.prepare_instdir(args.instdir, args.out)
    registry = os.path.join(instdir, "share", "registry")
    if os.path.islink(registry):
        raise SystemExit("unexpected symlinked share/registry in the copy")
    hst_gui.setup_uno(instdir)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), notify.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ["HST_UPDATE_TEST_URL"] = "http://127.0.0.1:%d/latest.json" % HTTP_PORT
    results = []
    try:
        phase_all_off(instdir, args, srv, results)
        phase_checkbox(instdir, args, srv, results)
    finally:
        server.shutdown()
        server.server_close()
        xcd = os.path.join(registry, "hst-update-policy.xcd")
        if os.path.exists(xcd):
            os.remove(xcd)
    failed = [label for label, ok in results if not ok]
    print("update lock runtime: %d checks, %d failed%s" % (len(results), len(failed), (": " + "; ".join(failed)) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
