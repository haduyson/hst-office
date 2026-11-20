#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Runtime check of Alt+\\ (Chuyển TeX ⇄ công thức) in a visible HST Writer on X11 (Linux, xdotool).

Usage (as hstbuild inside tests/runtime/no-hst-telemetry.sh, on a display of your own):
    DISPLAY=:87 python3 tests/runtime/check-tex-toggle-key.py --soffice PATH [--out DIR] [--port 2398]

A new Writer document holds "Thử $x^2+1$ và $\\frac{1}{2}$ nhé". Alt+\\ is typed into its window: both spans become
formulas, no backslash is typed, and the end-of-run message is closed with Enter. The office quits on its main thread.
Exit 1 when a check fails.
"""
import argparse
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import headless_office  # noqa: E402
import tex_toggle_check_helpers as base  # noqa: E402
TEXT = "Thử $x^2+1$ và $\\frac{1}{2}$ nhé"


class VisibleOffice:
    """An office with a window (not headless), own profile, fixed port."""

    def __init__(self, soffice, workdir, port):
        uno = headless_office.import_uno(soffice)
        profile = uno.systemPathToFileUrl(os.path.join(workdir, "profile"))
        self.proc = subprocess.Popen([soffice, "--norestore", "--nologo", "--writer", "-env:UserInstallation=" + profile,
                                      f"--accept=socket,host=127.0.0.1,port={port};urp;"])
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(240):
            try:
                self.ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001 - the office is still starting
                time.sleep(0.5)
        else:
            raise SystemExit("office did not start")
        self.desktop = self.service("com.sun.star.frame.Desktop")

    def service(self, name):
        return self.ctx.ServiceManager.createInstanceWithContext(name, self.ctx)


def xdotool(*args):
    return subprocess.run(("xdotool",) + args, capture_output=True, text=True).stdout.strip()


def objects(doc, timeout=20):
    """Number of embedded objects, read off the main thread (the end-of-run message may be up); None on timeout."""
    box = {}
    thread = threading.Thread(target=lambda: box.update(n=len(doc.getEmbeddedObjects().getElementNames())),
                              daemon=True)
    thread.start()
    thread.join(timeout)
    return box.get("n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=os.path.join("tests", "output", "tex-toggle-key"))
    parser.add_argument("--port", type=int, default=2398)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    office = VisibleOffice(args.soffice, out, args.port)
    try:
        doc = None
        for _ in range(60):
            doc = office.desktop.getCurrentComponent()
            if doc is not None and doc.supportsService("com.sun.star.text.TextDocument"):
                break
            time.sleep(1)
        time.sleep(5)  # the view and its key handler are set up after the document
        base.on_main(office, lambda: doc.getText().setString(TEXT))
        windows = xdotool("search", "--onlyvisible", "--name", "Writer").split()
        base.record("Writer window found", bool(windows), windows)
        if windows:
            xdotool("windowactivate", "--sync", windows[-1])
        time.sleep(1)
        xdotool("key", "--clearmodifiers", "alt+backslash")
        time.sleep(4)
        count = objects(doc)
        xdotool("key", "Return")  # the end-of-run message
        time.sleep(1)
        if count is None:
            count = objects(doc)
        base.record("Alt+\\ turned both spans into formulas", count == 2, count)
        text = base.on_main(office, lambda: doc.getText().getString())
        base.record("no backslash typed", "\\" not in text and "$" not in text, repr(text))
        base.on_main(office, lambda: doc.setModified(False))
    finally:
        base.quit_office(office)
    failed = [name for name, ok in base.ROWS if not ok]
    print("%d checks, %d failed" % (len(base.ROWS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
