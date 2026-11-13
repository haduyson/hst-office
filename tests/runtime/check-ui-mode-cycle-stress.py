# SPDX-License-Identifier: AGPL-3.0-only
"""Stress: cycling the user interface modes with two documents of each module open never crashes the office
(Linux, GUI build, existing X display).

Each round opens two Writer and two Sheets documents (tabs of one window), applies every user interface mode to each
of them in turn (.uno:ToolbarMode over UNO, as the dialog's "Apply to <module>"), then "Apply to All" for the three
toolbar modes with four tab switches each, and closes all documents but one. Before
hst-toolbox-control-disposed-state.patch the office died with SIGSEGV within a few rounds: a toolbar's delayed
controller update (ToolBarManager::AsyncUpdateControllersHdl) bound the paste control, whose first state asks the
system clipboard and so runs a nested main loop with the SolarMutex released; the mode switch on the UNO request
thread destroyed that toolbar meanwhile, and the paste control then laid out its disposed ToolBox
(ToolBox::GetItemRect -> ImplFormat); with that fixed alone, the update loop then read the controller map the
dispose had cleared (ToolBarManager::UpdateControllers). Usage: python3 tests/runtime/check-ui-mode-cycle-stress.py
[--instdir upstream/libreoffice/instdir] [--out tests/output/ui-mode-cycle-stress] [--display :97] [--rounds 20] [--port 21994].
Exit 1 when the office crashed, hung or a round failed.
"""
import argparse
import importlib.util
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hst_gui  # noqa: E402
import ui_mode_tabs_scenario as scenario  # noqa: E402

PORT = 21994  # deterministic per check (see hst_gui)
HANG_SECONDS = 300
MODES = ("Single", "Sidebar", "notebookbar_compact.ui", "notebookbar_groupedbar_compact.ui", "notebookbar_single.ui",
         "Default", "notebookbar.ui")
DOCS = (("Writer", "swriter", "docx", "MS Word 2007 XML"), ("Calc", "scalc", "xlsx", "Calc MS Excel 2007 XML"))


def load_adapter():
    """The Adapter of check-ui-mode-tabs.py (hst_gui.Office with the interface the scenario helpers expect)."""
    spec = importlib.util.spec_from_file_location("check_ui_mode_tabs", os.path.join(HERE, "check-ui-mode-tabs.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Adapter


def close_all_but_one(office):
    components = office.desktop.getComponents().createEnumeration()
    docs = []
    while components.hasMoreElements():
        docs.append(components.nextElement())
    for doc in docs[1:]:  # keep one document: the office stays up
        try:
            doc.setModified(False)
            doc.close(True)
        except Exception:  # noqa: BLE001 - a document that refuses to close does not change the verdict
            pass
    time.sleep(3)


def run_round(office, folder, number, progress):
    for app, factory, ext, filter_name in DOCS * 2:
        path = os.path.join(folder, "%s%d-%d.%s" % (app, number, int(time.time() * 1000) % 100000, ext))
        url = scenario.make_document(office, factory, path, filter_name)
        progress("load %s round %d" % (app, number))
        office.desktop.loadComponentFromURL(url, "_blank", 0, ())
        time.sleep(3)
        for mode in MODES:
            progress("%s %s round %d" % (app, mode, number))
            scenario.apply_mode(office, app, mode)
    for mode in ("Single", "Default", "Sidebar"):
        progress("all %s round %d" % (mode, number))
        scenario.apply_mode(office, "Writer", mode, to_all=True)
        for switch in range(4):
            progress("switch %s round %d #%d" % (mode, number, switch))
            office.dispatch(scenario.shown(office.desktop), ".uno:NextDocumentTab")
            time.sleep(2)
    close_all_but_one(office)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ui-mode-cycle-stress"))
    parser.add_argument("--display", default=":97")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--port", type=int, default=PORT, help="UNO port (another one to run two builds side by side)")
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    folder = os.path.join(args.out, "docs")
    os.makedirs(folder, exist_ok=True)
    if os.geteuid() == 0:
        os.chmod(folder, 0o777)

    state = {"step": "start", "last": time.time()}

    def progress(step):
        state["step"], state["last"] = step, time.time()

    def watchdog():  # a hang is a failure too: report it instead of waiting for the CI timeout
        while True:
            time.sleep(20)
            if time.time() - state["last"] > HANG_SECONDS:
                hst_gui.screenshot(os.path.join(args.out, "hang.png"), args.display)
                print("FAIL  office hung at %s" % state["step"], flush=True)
                os._exit(1)

    threading.Thread(target=watchdog, daemon=True).start()
    office = hst_gui.Office(args.instdir, args.out, args.port, display=args.display, nodefault=True)
    office.start()
    result = {"check": "UI mode cycling, %d rounds" % args.rounds, "status": "PASS", "detail": ""}
    try:
        adapter = load_adapter()(office)
        for number in range(args.rounds):
            run_round(adapter, folder, number, progress)
            print("round %d ok" % number, flush=True)
    except Exception as error:  # noqa: BLE001 - a dead bridge is the crash this check is for
        alive = office.pid is not None
        result.update(status="FAIL", detail="%s at %s: %r" % ("error" if alive else "office crashed",
                                                             state["step"], error))
    finally:
        office.stop()
    print("%s  %s  %s" % (result["status"], result["check"], result["detail"]), flush=True)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump([result], handle, ensure_ascii=False, indent=1)
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
