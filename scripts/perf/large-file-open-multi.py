# SPDX-License-Identifier: AGPL-3.0-only
"""Several workbooks opened at once (as by selecting them in a file manager and pressing Enter), Windows only.

    python large-file-open-multi.py --soffice <soffice.exe> --profile <dir> --out <file.jsonl> --label L
        [--cpus N] [--timeout S] <file>...

Starts one office with all files on its command line, then every second looks at the office's visible top-level
windows: IsHungAppWindow (what Windows shows as "Not responding": no message processed for 5 s) and their titles.
Ends when every file has a window and no window was hung for 15 s, when the office ends, or at --timeout. Writes one
JSON line: hung seconds in total, the longest hung stretch, windows seen, office exit code, elapsed time.
Run with the office's own Python (no extra modules); the profile is seeded like large-file-open.py.
"""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import large_file_open_procs as procs  # noqa: E402
import large_file_open_profile as profiles  # noqa: E402

user32 = ctypes.windll.user32


def windows(pids):
    found = []

    def cb(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            found.append((buf.value, bool(user32.IsHungAppWindow(hwnd))))
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return found


def main():
    ap = argparse.ArgumentParser()
    for name in ("--soffice", "--profile", "--out", "--label"):
        ap.add_argument(name, required=True)
    ap.add_argument("--cpus", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    profiles.create(a.profile, "default")
    url = "file:///" + os.path.abspath(a.profile).replace("\\", "/")
    # a first start registers the extension, outside the measurement
    subprocess.run([a.soffice, "-env:UserInstallation=" + url, "--headless", "--terminate_after_init"], timeout=300)
    for f in a.files:
        profiles.clear_leftovers(a.profile, f)
    profiles.reseed(a.profile, "default")
    before = set(procs.office_pids())
    office = subprocess.Popen(procs.limit_cpus([a.soffice, "-env:UserInstallation=" + url, "--norestore"]
                                               + [os.path.abspath(f) for f in a.files], a.cpus))
    started = time.monotonic()
    hung_total, hung_run, hung_max, quiet, titles, own = 0, 0, 0, 0, set(), set()
    names = [os.path.basename(f) for f in a.files]
    while time.monotonic() - started < a.timeout and office.poll() is None:
        own.update(procs.descendants(office.pid, set(procs.office_pids()) - before))
        seen = windows(own)
        titles.update(t for t, _ in seen)
        hung = any(h for _, h in seen)
        hung_run = hung_run + 1 if hung else 0
        hung_total += hung
        hung_max = max(hung_max, hung_run)
        quiet = 0 if hung else quiet + 1
        if quiet >= 15 and all(any(n.rsplit(".", 1)[0] in t for t in titles) for n in names):
            break
        time.sleep(1)
    res = {"label": a.label, "files": len(a.files), "elapsed": round(time.monotonic() - started, 1),
           "hung_s": hung_total, "hung_longest_s": hung_max, "office_exit": office.poll(),
           "all_open": all(any(n.rsplit(".", 1)[0] in t for t in titles) for n in names), "cpus": a.cpus,
           "titles": sorted(titles)}
    procs.kill(office, own)
    with open(a.out, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    print(json.dumps(res, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
