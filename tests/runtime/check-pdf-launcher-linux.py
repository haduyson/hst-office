#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""HST PDF's Linux launcher arguments (hst-pdf-launchers.patch, hst_office/pdf_open.py) on a real office.

Usage: python3 tests/runtime/check-pdf-launcher-linux.py --instdir <dir with program/soffice> [--display :93]
The X display must already run (Xvfb is fine); needs xdotool. Each case uses a fresh profile:
  - bare launcher: the "HST PDF" PDF dialog shows, no Start Center; closing it makes the office quit;
  - launcher with a PDF (file manager "Open with"): the viewer shows the file and no dialog comes;
  - service missing (the HST extension disabled or broken; simulated by a service name nothing provides, same
    arguments otherwise): the office quits on its own instead of running without a window.
Exit 1 when a check fails.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

SERVICE = "service:org.hst.office.vi.PdfOpen"
MISSING = "service:org.hst.office.vi.PdfOpenNotInstalled"
DIALOG = "HST PDF"
PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
failures = []


def check(ok, what):
    print(("PASS " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def titles():
    found = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "."], capture_output=True, text=True)
    names = set()
    for window in found.stdout.split():
        name = subprocess.run(["xdotool", "getwindowname", window], capture_output=True, text=True).stdout.strip()
        if name:
            names.add(name)
    return names


def wait(predicate, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.5)
    return False


def launch(soffice, profile, *args):
    return subprocess.Popen([soffice, "-env:UserInstallation=file://" + profile, *args],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def profile_dir(work, name, soffice):
    """A fresh profile, first-start work (bundled extension registration) done headless beforehand."""
    path = os.path.join(work, name)
    subprocess.run([soffice, "-env:UserInstallation=file://" + path, "--headless", "--terminate_after_init"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300, check=False)
    return path


def dialog_shown():
    return any(DIALOG in title and ".pdf" not in title for title in titles())


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=os.environ.get("DISPLAY", ":93"))
    args = parser.parse_args()
    os.environ["DISPLAY"] = args.display
    soffice = os.path.join(args.instdir, "program", "soffice")
    work = tempfile.mkdtemp(prefix="hst-pdf-launcher-")
    try:
        pdf = os.path.join(work, "launcher-test.pdf")
        with open(pdf, "wb") as handle:
            handle.write(PDF)

        proc = launch(soffice, profile_dir(work, "bare", soffice), "--nodefault", SERVICE + "?begin", SERVICE)
        check(wait(dialog_shown, 90), "bare launcher shows the PDF dialog")
        check(not any("HST Office" == t or "Trung tâm" in t for t in titles()), "bare launcher shows no Start Center")
        window = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", DIALOG], capture_output=True,
                                text=True).stdout.split()
        if window:
            subprocess.run(["xdotool", "windowfocus", "--sync", window[0]], check=False)
            subprocess.run(["xdotool", "key", "Escape"], check=False)
            if not wait(lambda: proc.poll() is not None, 5):
                subprocess.run(["xdotool", "windowfocus", "--sync", window[0]], check=False)
                subprocess.run(["xdotool", "key", "alt+F4"], check=False)
        check(wait(lambda: proc.poll() is not None, 30), "closing the dialog quits the office")
        stop(proc)

        proc = launch(soffice, profile_dir(work, "file", soffice), "--nodefault", SERVICE + "?begin", pdf, SERVICE)
        check(wait(lambda: any("launcher-test.pdf" in t for t in titles()), 90), "a passed PDF opens in the viewer")
        time.sleep(8)
        check(not dialog_shown(), "a passed PDF raises no dialog")
        stop(proc)

        proc = launch(soffice, profile_dir(work, "missing", soffice), "--nodefault", MISSING + "?begin", MISSING)
        check(wait(lambda: proc.poll() is not None, 60), "without the service the office quits, no windowless office")
        stop(proc)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("pdf launcher: %d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
