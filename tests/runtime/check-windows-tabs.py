#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Document tabs in an INSTALLED HST Office on Windows (CI): the app starts, three documents form one
tab group with exactly one shown window, the tab commands switch, and closing a tab shows the neighbour.

    "<install>\\program\\python.exe" tests/runtime/check-windows-tabs.py --install "<install>" --out <dir>
Reuses the helpers of check-windows-smoke.py. Results: <out>/tabs-results.json. Exit status 1 on any FAIL.
"""
import argparse
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("smoke", os.path.join(HERE, "check-windows-smoke.py"))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def frames(desktop):
    access = desktop.getFrames()
    return [access.getByIndex(i) for i in range(access.getCount())]


def shown(desktop):
    return [f for f in frames(desktop) if f.getContainerWindow().isVisible()]


def wait(predicate, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if predicate():
                return True
        except Exception:  # noqa: BLE001 - UNO objects change while windows open and close
            pass
        time.sleep(0.3)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=2107)
    args = ap.parse_args()
    install, out = os.path.abspath(args.install), os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    smoke.OUT = out
    smoke.SHOT_DIR = None
    import uno  # noqa: F401  (the office's own Python)
    print("starting office", flush=True)
    profile = "file:///" + os.path.join(out, "profile").replace("\\", "/")
    proc, ctx = smoke.start_office(os.path.join(install, "program"), profile, args.port,
                                   os.path.join(out, "soffice.err"), dict(os.environ))
    print("office socket open", flush=True)
    code = 1
    try:
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
        smoke.record("office started", True)
        docs = [smoke.open_document(ctx, desktop, kind) for kind in ("swriter", "scalc", "simpress")]
        smoke.record("three documents open", all(docs) and len(frames(desktop)) == 3, len(frames(desktop)))
        smoke.record("one shown window (others parked)", wait(lambda: len(shown(desktop)) == 1), len(shown(desktop)))
        before = shown(desktop)[0].getTitle()
        helper.executeDispatch(shown(desktop)[0], ".uno:NextDocumentTab", "_self", 0, ())
        smoke.record("NextDocumentTab shows another tab",
                     wait(lambda: len(shown(desktop)) == 1 and shown(desktop)[0].getTitle() != before),
                     shown(desktop)[0].getTitle() if shown(desktop) else "-")
        started = time.time()
        helper.executeDispatch(shown(desktop)[0], ".uno:NextDocumentTab", "_self", 0, ())
        smoke.record("tab switch time", wait(lambda: len(shown(desktop)) == 1), "%.2f s" % (time.time() - started))
        for doc in docs:
            doc.setModified(False)
        helper.executeDispatch(shown(desktop)[0], ".uno:CloseWin", "_self", 0, ())
        smoke.record("closing a tab shows the neighbour",
                     wait(lambda: len(frames(desktop)) == 2 and len(shown(desktop)) == 1
                          and shown(desktop)[0].isActive()), "frames=%d shown=%d" % (len(frames(desktop)), len(shown(desktop))))
        code = 0
    except Exception as error:  # noqa: BLE001
        smoke.record("tab check ran", False, repr(error))
    finally:
        try:
            for doc in desktop.getComponents():
                doc.setModified(False)
            desktop.terminate()
        except Exception:  # noqa: BLE001
            pass
        try:
            proc.wait(20)
        except Exception:  # noqa: BLE001
            proc.kill()
    failed = [r for r in smoke.ROWS if r["status"] == "FAIL"]
    with open(os.path.join(out, "tabs-results.json"), "w", encoding="utf-8") as handle:
        json.dump({"results": smoke.ROWS, "failed": len(failed)}, handle, ensure_ascii=False, indent=1)
    return 1 if failed or code else 0


if __name__ == "__main__":
    sys.exit(main())
