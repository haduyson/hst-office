# SPDX-License-Identifier: AGPL-3.0-only
"""Window helpers of the update runtime checks (check-update-notify.py, check-update-install.py and the checks that
load them): waiting, finding and clicking the update dialogs, screenshots, and the ports of a run."""
import os
import re
import subprocess
import threading
import time

import hst_gui

RESULTS = []  # (label, ok) of the checks that record through check()


def check(label, ok):
    RESULTS.append((label, bool(ok)))
    print("%-4s %s" % ("PASS" if ok else "FAIL", label), flush=True)
    return ok


def add_port_options(parser, old_uno, old_http):
    """--uno-port and --http-port; both default to a free port, so runs of other sessions never clash."""
    parser.add_argument("--uno-port", type=int, default=0, help="office UNO socket (default: free; formerly %d)" % old_uno)
    parser.add_argument("--http-port", type=int, default=0, help="local manifest server (default: free; formerly %d)" % old_http)


def ports(args):
    """(UNO port, HTTP port) of the run: the options given, or free ports."""
    return args.uno_port or hst_gui.free_port(), args.http_port or hst_gui.free_port()


def wait(predicate, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.5)
    return False


def dialog_shot(office, shots, name, results, label, pattern):
    """Wait for the result dialog, screenshot it, close it with Escape."""
    found = []
    ok = wait(lambda: found.extend(w for w in hst_gui.toplevels(office.display, office.pid) if w[1] == "Kiểm tra cập nhật") or found, 30)
    time.sleep(1.0)
    office.screenshot(os.path.join(shots, name))
    results.append((label, ok))
    if found:  # click "Đóng" (AppFont box 252..292 x 64..78 of a 300 x 86 dialog); Xvfb has no WM to focus for keys
        wid = found[0][0]
        info = subprocess.run(["xwininfo", "-display", office.display, "-id", wid], capture_output=True, text=True).stdout
        width, height = (int(re.search(r"%s: (\d+)" % k, info).group(1)) for k in ("Width", "Height"))
        env = dict(os.environ, DISPLAY=office.display)
        subprocess.run(["xdotool", "mousemove", "--window", wid, str(int(width * 272 / 300)), str(int(height * 71 / 86)),
                        "click", "1"], env=env, check=False, timeout=10)
        closed = wait(lambda: not [w for w in hst_gui.toplevels(office.display, office.pid) if w[1] == "Kiểm tra cập nhật"], 10)
        results.append((label + ": closes with Đóng", closed))
        ok = ok and closed
    print("%-4s %s (%s)" % ("PASS" if ok else "FAIL", label, pattern), flush=True)


def menu_shot(office, path):
    """Open the Start Center's HST menu (menu bar entry "HST", 4th-from-left label) for a screenshot, then close it."""
    env = dict(os.environ, DISPLAY=office.display)
    windows = [w for w in hst_gui.toplevels(office.display, office.pid) if w[1] == "HST Office"]
    if not windows:
        print("note: Start Center window not found, no menu screenshot", flush=True)
        return
    office.raise_windows()
    subprocess.run(["xdotool", "mousemove", "--window", windows[0][0], "141", "14", "click", "1"], env=env, check=False, timeout=10)
    time.sleep(1.5)
    hst_gui.screenshot(path, office.display)
    subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=10)
    time.sleep(0.5)


def dialogs(office, title):
    return [w for w in hst_gui.toplevels(office.display, office.pid) if w[1] == title]


def click(office, title, fx, fy, timeout=60):
    """Wait for the dialog `title`, click at the fraction (fx, fy) of its window; False when it never shows."""
    found = []
    if not wait(lambda: found.extend(dialogs(office, title)) or found, timeout):
        return False
    time.sleep(1.0)
    wid = found[0][0]
    info = subprocess.run(["xwininfo", "-display", office.display, "-id", wid], capture_output=True, text=True).stdout
    width, height = (int(re.search(r"%s: (\d+)" % k, info).group(1)) for k in ("Width", "Height"))
    env = dict(os.environ, DISPLAY=office.display)
    subprocess.run(["xdotool", "mousemove", "--window", wid, str(int(width * fx)), str(int(height * fy)), "click", "1"],
                   env=env, check=False, timeout=10)
    return True


def dispatch_async(office, frame, command):
    """The Install command runs its modal dialogs inside the dispatch call: dispatch from a helper thread."""
    threading.Thread(target=office.dispatch, args=(frame, command), daemon=True).start()


def shot(office, shots, name):
    time.sleep(0.5)
    office.screenshot(os.path.join(shots, name))


def cache_files(office):
    folder = os.path.join(office.workdir, "cache", "hst-office", "update")
    return folder, sorted(f for f in os.listdir(folder) if f.endswith(".deb") or f.endswith(".part")) if os.path.isdir(folder) else []
