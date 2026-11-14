# SPDX-License-Identifier: AGPL-3.0-only
"""Shared scenario and verdict of check-ui-mode-cycle-stress.py (Linux) and check-windows-ui-mode-cycle-stress.py.

Each round opens two Writer and two Sheets documents (tabs of one window), applies every user interface mode to each
of them in turn (.uno:ToolbarMode over UNO, as the dialog's "Apply to <module>"), then "Apply to All" for the three
toolbar modes with four tab switches each, returns to the ribbon and closes all documents but one.

Verdict: PASS when all rounds ran; FAIL only when the office crashed (the defect this check is for); INCONCLUSIVE when
the office hung (stacks saved where the platform can) or the harness failed otherwise. Exit 1 on FAIL only, so CI can
run it although the known gtk clipboard hang of UNO-driven offices (see check-ui-mode-cycle-stress.py) may stop a run.
"""
import json
import os
import threading
import time

import ui_mode_tabs_scenario as scenario

HANG_SECONDS = 300
MODES = ("Single", "Sidebar", "notebookbar_compact.ui", "notebookbar_groupedbar_compact.ui", "notebookbar_single.ui",
         "Default", "notebookbar.ui")
DOCS = (("Writer", "swriter", "docx", "MS Word 2007 XML"), ("Calc", "scalc", "xlsx", "Calc MS Excel 2007 XML"))


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


def load(office, url):
    """Open the document as a new tab. Type detection of a just-written file failed once in about 130 loads (the file was
    complete and valid): retry that once, it is not what this check is about."""
    try:
        office.desktop.loadComponentFromURL(url, "_blank", 0, ())
    except Exception as error:  # noqa: BLE001 - only the type detection error is retried
        if "type detection failed" not in str(error):
            raise
        print("retry load after: %s" % error, flush=True)
        time.sleep(3)
        office.desktop.loadComponentFromURL(url, "_blank", 0, ())


def run_round(office, folder, number, progress):
    for app, factory, ext, filter_name in DOCS * 2:
        path = os.path.join(folder, "%s%d-%d.%s" % (app, number, int(time.time() * 1000) % 100000, ext))
        url = scenario.make_document(office, factory, path, filter_name)
        progress("load %s round %d" % (app, number))
        load(office, url)
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
    # Back to the default ribbon (no menubar) before the next round's documents load: on gtk a document loaded over UNO
    # into a window with a menubar builds the menubar on the request thread, whose Paste state can then wait for the
    # clipboard for good (the known hang). It keeps that out of the loads; mode switches can still meet it.
    progress("all notebookbar.ui round %d" % number)
    scenario.apply_mode(office, "Writer", "notebookbar.ui", to_all=True)
    close_all_but_one(office)


def run(adapter, rounds, out, on_hang, is_crash, crash_detail=lambda: ""):
    """Run `rounds` rounds on `adapter` (the scenario's office interface) and write <out>/results.json.

    on_hang(): save what the platform can (stacks), then kill the hung office. is_crash(error) -> bool: the office died.
    crash_detail() -> str: the platform's crash record (e.g. the faulting module). Returns the exit code."""
    folder = os.path.join(out, "docs")
    os.makedirs(folder, exist_ok=True)
    name = "UI mode cycling, %d rounds" % rounds
    state = {"step": "start", "last": time.time()}

    def progress(step):
        state["step"], state["last"] = step, time.time()

    def finish(status, detail):
        print("%s  %s  %s" % (status, name, detail), flush=True)
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as handle:
            json.dump([{"check": name, "status": status, "detail": detail}], handle, ensure_ascii=False, indent=1)
        return 1 if status == "FAIL" else 0

    def watchdog():
        while True:
            time.sleep(20)
            if time.time() - state["last"] > HANG_SECONDS:
                step = state["step"]
                try:
                    on_hang()
                finally:
                    os._exit(finish("INCONCLUSIVE", "office hung at %s (no crash; see hang-stacks.txt)" % step))

    threading.Thread(target=watchdog, daemon=True).start()
    try:
        for number in range(rounds):
            run_round(adapter, folder, number, progress)
            print("round %d ok" % number, flush=True)
    except Exception as error:  # noqa: BLE001 - a dead bridge is the crash this check is for
        time.sleep(5)  # the crash handler of a dying office still runs for a moment
        state["last"] = time.time() + 3600  # the verdict is being written: no hang verdict any more
        if is_crash(error):
            return finish("FAIL", "office crashed at %s: %r %s" % (state["step"], error, crash_detail()))
        return finish("INCONCLUSIVE", "harness error at %s (no crash): %r" % (state["step"], error))
    state["last"] = time.time() + 3600
    return finish("PASS", "")
