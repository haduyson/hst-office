# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""An AT-SPI client walking the office's accessibility tree while the office is terminated over UNO (gtk3, vi_VN).

Usage: python3 tests/runtime/check-draw-a11y-walk-terminate.py --instdir DIR --work DIR [--display :NNN]
                                                                [--apps draw,impress,writer,calc] [--rounds 4]
The X display must already run (this script never starts or stops it). Per app and round, on a private AT-SPI bus
(at-spi2-registryd) and a fresh profile:
  1. the whole tree is walked like accerciser (name, role, states, attributes, relations, extents, text);
  2. while another thread keeps asking every walked node for its name, states and index in parent, the window is
     resized (the slide sorter rebuilds its page objects) and Desktop.terminate() is called over UNO, so the office
     closes on a UNO bridge thread while the gtk3 accessibility bridge is serving AT-SPI on the main thread;
  3. the round fails when the office did not quit cleanly: a non-zero exit (a crash ends with 134, the crash
     handler's abort), a "Fatal exception" in <profile>/user/hst-office/last-session.err, or the session marker
     session.json left behind.
Writes <work>/evidence.json; exit 1 on any failure.
"""
import argparse
import importlib.util
import json
import os
import signal
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402

PORTS = {"writer": 7651, "calc": 7652, "impress": 7653, "draw": 7654}
ROWS = []


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
    return ok


def full_walk(node, found, depth=0):
    """Every node with everything an inspector shows; widgets that vanish meanwhile are skipped."""
    import pyatspi
    if node is None or depth > 40 or len(found) > 5000:
        return
    try:
        node.name, node.getRoleName(), node.description, node.getState().getStates()
        node.getRelationSet(), node.getAttributes(), node.getIndexInParent()
        try:
            node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
        except NotImplementedError:
            pass
        try:
            text = node.queryText()
            text.getText(0, min(text.characterCount, 200))
        except NotImplementedError:
            pass
        count = min(node.childCount, 2000)
    except Exception:  # noqa: BLE001 - the node went away while we looked at it
        return
    found.append(node)
    for index in range(count):
        try:
            child = node.getChildAtIndex(index)
        except Exception:  # noqa: BLE001
            continue
        full_walk(child, found, depth + 1)


def hammer(nodes, stop):
    """Keeps the office's accessibility bridge busy: uncached name, state and index requests."""
    while not stop.is_set():
        for node in nodes:
            if stop.is_set():
                return
            try:
                node.clearCache()
                node.name, node.getState().getStates(), node.getIndexInParent()
            except Exception:  # noqa: BLE001 - disposed or gone: that is what the office must survive
                pass


def crashed(work):
    err = os.path.join(work, "profile", "user", "hst-office", "last-session.err")
    try:
        with open(err, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return ""
    return text[:300] if "Fatal exception" in text else ""


def run_round(args, app, round_no):
    work = os.path.join(args.work, f"{app}-{round_no}")
    office = hst_gui.Office(args.instdir, work, PORTS[app], display=args.display, extra_args=[f"--{app}"],
                            nodefault=False,
                            config=[("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false")])
    office.start(fresh=True)
    time.sleep(8)
    nodes = []
    full_walk(gui.office_app(), nodes)
    windows = [w for w, n in hst_gui.toplevels(args.display, office.pid) if gui.NAMES[app] in n]
    stop = threading.Event()
    worker = threading.Thread(target=hammer, args=(nodes, stop), daemon=True)
    worker.start()
    time.sleep(1)
    for size in ("1200 800", "1485 900"):
        if windows:
            gui.xdo(args.display, "windowsize", windows[0], *size.split())
        time.sleep(0.3)
    try:
        office.desktop().getCurrentComponent().setModified(False)
    except Exception:  # noqa: BLE001 - no document
        pass
    office.stop()  # Desktop.terminate() over UNO: runs on a UNO bridge thread
    stop.set()
    worker.join(10)
    code = office.proc.returncode if office.proc is not None else None
    marker = os.path.isfile(os.path.join(work, "profile", "user", "hst-office", "session.json"))
    crash = crashed(work)
    record(f"[{app}] round {round_no}: walked {len(nodes)} nodes, terminated without a crash",
           code == 0 and not marker and not crash,
           f"exit {code}{' (crash)' if code == 134 else ''}, session marker {'left' if marker else 'removed'}"
           + (f", {crash}" if crash else ""))


def private_atspi_bus():
    """This run's own AT-SPI bus, as check-banner-everywhere.py sets it up (that file's name is not importable)."""
    spec = importlib.util.spec_from_file_location("banner_everywhere", os.path.join(HERE, "check-banner-everywhere.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.private_atspi_bus()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--display", default=":247")
    parser.add_argument("--apps", default="draw,impress,writer,calc")
    parser.add_argument("--rounds", type=int, default=4)
    args = parser.parse_args()
    if os.geteuid() == 0:  # as the build user under a session bus of its own (AT-SPI needs one)
        os.makedirs(args.work, exist_ok=True)
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, args.work], check=False)
        os.execvp("runuser", ["runuser", "-u", hst_gui.BUILD_USER, "--", "dbus-run-session", "--", sys.executable]
                  + sys.argv)
    args.instdir, args.work = os.path.abspath(args.instdir), os.path.abspath(args.work)
    address, launcher = private_atspi_bus()
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge", AT_SPI_BUS_ADDRESS=address)
    try:
        hst_gui.setup_uno(args.instdir)
        for app in args.apps.split(","):
            for round_no in range(1, args.rounds + 1):
                try:
                    run_round(args, app, round_no)
                except Exception as error:  # noqa: BLE001 - the next round still runs
                    record(f"[{app}] round {round_no}", False, repr(error))
    finally:
        try:
            os.kill(launcher, signal.SIGTERM)
        except ProcessLookupError:
            pass
    with open(os.path.join(args.work, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(ROWS, handle, ensure_ascii=False, indent=1)
    failed = [r for r in ROWS if r["status"] != "PASS"]
    print(f"{len(ROWS) - len(failed)} pass, {len(failed)} fail")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
