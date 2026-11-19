#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Printer state dots on the Print page (hst-print-printer-status.patch) in a visible office (Linux X display, gen
plugin: the UITest service sees the VCL widgets).

The profile gets generic printers (psprint) and HST_TEST_PRINTER_STATES gives them states, so no print server is
needed: "HST Sẵn sàng" ready (green), "HST Đang in" busy (amber), "HST Ngoại tuyến" offline (red), "HST Hết giấy"
out of paper (red); the generic printer of the profile has no state (grey). Per application the Print page opens,
each printer is selected in turn and the status label must show its text; --shot takes a screenshot of each.
Usage: <office python> check-print-printer-status.py --soffice PATH --out DIR [--shot CMD] [--dark] [--apps ...]
Exit 1 on a failure.
"""
import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location("cancel_back",
                                               os.path.join(HERE, "check-backstage-print-cancel-back.py"))
CB = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(CB)

PRINTERS = {"HST Sẵn sàng": ("ready", "Sẵn sàng"), "HST Đang in": ("busy", "Đang bận"),
            "HST Ngoại tuyến": ("offline", "Ngoại tuyến"), "HST Hết giấy": ("paperout", "Lỗi: hết giấy")}
failures = []


def check(ok, text):
    print(("PASS  " if ok else "FAIL  ") + text, flush=True)
    failures.extend([] if ok else [text])


def write_printers(soffice, out):
    """Generic printers in the profile (they spool into /dev/null: nothing is printed here)."""
    profile = os.path.join(out, "profile")
    subprocess.run([soffice, "--headless", "--terminate_after_init",
                    "-env:UserInstallation=file://" + profile], timeout=300)
    os.makedirs(os.path.join(profile, "user", "psprint"), exist_ok=True)
    with open(os.path.join(profile, "user", "psprint", "psprint.conf"), "w", encoding="utf-8") as handle:
        for name in PRINTERS:
            handle.write(f"[{name}]\nPrinter=SGENPRT/{name}\nDefaultPrinter=0\nLocation=\nComment=\n"
                         "Command=cat > /dev/null\nQueueName=\nFeatures=\n\n")
    os.environ["HST_TEST_PRINTER_STATES"] = ";".join(f"{n}={s}" for n, (s, _) in PRINTERS.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-printer-status-"))  # noqa
    parser.add_argument("--shot", help="screenshot command with {} for the file")
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--apps", default="swriter,scalc")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    tag = "dark" if args.dark else "light"
    shot = lambda name: args.shot and subprocess.run(args.shot.format(os.path.join(out, name)), shell=True)  # noqa
    if args.dark:
        CB.set_dark_appearance(args.soffice, out)
    write_printers(args.soffice, out)
    office = CB.BASE.VisibleOffice(args.soffice, out, None)
    try:
        for app in args.apps.split(","):
            doc = CB.load(office, app)
            office.close_welcome()
            office.ui.executeCommandForProvider(".uno:Print", doc.getCurrentController().getFrame())
            printers = CB.panel_button(office, "printersbox")
            check(printers is not None, f"{app}: the Print page shows its printer list")
            if printers is None:
                continue
            from com.sun.star.beans import PropertyValue
            for index, (name, (_, text)) in enumerate(PRINTERS.items()):
                arg = PropertyValue()
                arg.Name, arg.Value = "TEXT", name
                CB.panel_button(office, "printersbox").executeAction("SELECT", (arg,))
                status = ""
                for _ in range(20):  # the state comes from a thread; grey until then
                    time.sleep(0.5)
                    status = CB.BASE.state(CB.panel_button(office, "status")).get("Text", "")
                    if status.startswith(text):
                        break
                check(status.startswith(text), f"{app}: {name}: status {status!r}")
                shot(f"{app}-printer-{index + 1}-{PRINTERS[name][0]}-{tag}.png")
            office.ui.executeCommandForProvider(".uno:HSTBackstage", doc.getCurrentController().getFrame())
            doc.setModified(False)
    finally:
        office.stop()
    print(f"{len(failures)} failure(s); output in {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
