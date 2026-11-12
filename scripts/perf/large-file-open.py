# SPDX-License-Identifier: AGPL-3.0-only
"""Open-time of large documents in one office installation (HST Office or stock LibreOffice), one office per open.

    python large-file-open.py --soffice <soffice> --python <office python> --files <dir> --out <dir> --label <name>
        [--mode gui|headless] [--repeat N] [--timeout S] [--seed default|toolbar|tabbed|nothreads|norowheight] [--save] [--only a,b]

Per file and repeat: a new office process on the label's profile (seeded once: no first-start dialogs, automatic
spell checking off as in HST), --accept on a private pipe; large_file_open_client.py (the office's Python) loads the
file in a visible window (gui) or hidden (headless) and waits until the office is idle, optionally stores it again
with its own filter (the cost of an autorecovery copy or a save). Peak resident memory of soffice.bin is sampled.
An open that does not finish within --timeout is killed and recorded as "timeout". Writes <label>.jsonl and prints.
--seed toolbar: standard toolbars instead of the tabbed bar in Writer/Calc/Impress; tabbed: the tabbed bar;
nothreads: threaded formula-group calculation off; norowheight: optimal row heights not recalculated on load.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

APPS = ("Writer", "Calc", "Impress", "Draw")


def seed_items(seed):
    items = [("/org.openoffice.Office.Common/Misc", "FirstRun", "false"),
             ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false"),
             ("/org.openoffice.Office.Linguistic/General", "IsSpellAuto", "false"),
             ("/org.openoffice.Office.Recovery/AutoSave", "Enabled", "false"),
             ("/org.hasontech.hstoffice.Welcome", "Shown", "true"),
             ("/org.hasontech.hstoffice.ErrorReport", "AskAfterCrash", "false"),
             ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
             ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false"),
             ("/org.openoffice.Office.Jobs/Jobs/org.openoffice.Office.Jobs:Job['UpdateCheck']/Arguments",
              "AutoCheckEnabled", "false")]
    if seed == "nothreads":
        items.append(("/org.openoffice.Office.Calc/Formula/Calculation", "UseThreadedCalculationForFormulaGroups",
                      "false"))
    if seed == "norowheight":  # Tools - Options - Calc - Formula: recalculation on load of optimal row heights: never
        items.append(("/org.openoffice.Office.Calc/Formula/Load", "RecalcOptimalRowHeightMode", "1"))
    mode = {"toolbar": "Default", "tabbed": "notebookbar.ui"}.get(seed)
    if mode:
        for app in APPS[:3]:
            items.append(("/org.openoffice.Office.UI.ToolbarMode/Applications/"
                          "org.openoffice.Office.UI.ToolbarMode:Application['%s']" % app, "Active", mode))
    body = "".join('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n'
                   % (path, name, value) for path, name, value in items)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
            'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
            + body + "</oor:items>\n")


def profile_dir(url):
    path = url[len("file://"):]
    return path[1:] if sys.platform == "win32" else path


def file_url(path):
    path = os.path.abspath(path).replace("\\", "/")
    return "file:///" + path.lstrip("/")


def office_pids():
    try:
        import psutil
        return [p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith("soffice")]
    except ImportError:
        pids = []
        for d in os.listdir("/proc"):
            if d.isdigit():
                try:
                    with open("/proc/%s/comm" % d) as f:
                        if f.read().strip().startswith("soffice"):
                            pids.append(int(d))
                except OSError:
                    pass
        return pids


def rss_mb(pids):
    total = 0
    for pid in pids:
        try:
            import psutil
            total += psutil.Process(pid).memory_info().rss
        except ImportError:
            try:
                with open("/proc/%d/statm" % pid) as f:
                    total += int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
            except OSError:
                pass
        except Exception:  # noqa: BLE001 - the process ended
            pass
    return total / 1e6


def kill_tree(proc, own):
    try:
        import psutil
        for pid in own:
            try:
                psutil.Process(pid).kill()
            except Exception:  # noqa: BLE001
                pass
    except ImportError:
        for pid in own:
            try:
                os.kill(pid, 9)
            except OSError:
                pass
    try:
        proc.kill()
    except OSError:
        pass


def evidence(a, name, own):
    """A screenshot and the office's window titles when an open does not finish (a dialog, or still working)."""
    shot = os.path.join(a.out, "timeout-%s-%s-%d.png" % (a.label, name, int(time.time())))
    try:
        from PIL import ImageGrab
        ImageGrab.grab().save(shot)
    except Exception:  # noqa: BLE001 - no grabber: X11 import instead
        subprocess.run(["import", "-window", "root", shot], check=False, timeout=60)
    titles = []
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        def cb(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in own and user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buf, 512)
                titles.append(buf.value)
            return True
        user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    with open(os.path.join(a.out, "timeouts.txt"), "a", encoding="utf-8") as f:
        f.write("%s %s windows=%r shot=%s\n" % (a.label, name, titles, os.path.basename(shot)))


def tiny_xlsx(path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import large_file_fixtures as fx
    fx.write_xlsx(path, 20, True, "Microsoft Excel")


def one_open(a, path, profile_url, pipe):
    lock = os.path.join(os.path.dirname(path), ".~lock.%s#" % os.path.basename(path))
    if os.path.exists(lock):  # left by an office killed after a timeout: it would ask "document in use"
        os.remove(lock)
    # HST's crash question after an office this harness had to kill (its session marker stays): not part of an open
    marker = os.path.join(profile_dir(profile_url), "user", "hst-office", "session.json")
    if os.path.exists(marker):
        os.remove(marker)
    before = set(office_pids())
    args = [a.soffice, "-env:UserInstallation=" + profile_url, "--accept=pipe,name=%s;urp;" % pipe,
            "--norestore", "--nologo", "--nodefault"]
    if a.mode == "headless":
        args.append("--headless")
    office = subprocess.Popen(args)
    save_to = "-"
    if a.save:
        save_to = os.path.join(tempfile.gettempdir(), "lfo-save-" + os.path.basename(path))
    client = subprocess.Popen([a.python, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                      "large_file_open_client.py"),
                               pipe, os.path.abspath(path), "1" if a.mode == "headless" else "0", save_to],
                              stdout=subprocess.PIPE, text=True)
    peak, own, stop = [0.0], set(), threading.Event()

    def sample():
        while not stop.is_set():
            own.update(set(office_pids()) - before)
            peak[0] = max(peak[0], rss_mb(own))
            time.sleep(0.25)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    started = time.monotonic()
    try:
        out, _ = client.communicate(timeout=a.timeout)
        line = (out.strip().splitlines() or ["{}"])[-1]
        res = json.loads(line) if line.startswith("{") else {"error": "client: " + line[:200]}
    except subprocess.TimeoutExpired:
        evidence(a, os.path.basename(path), own)
        client.kill()
        out, _ = client.communicate()
        lines = [x for x in out.strip().splitlines() if x.startswith("{")]
        res = json.loads(lines[-1]) if lines else {}
        res.update({"error": "timeout", "after": round(time.monotonic() - started, 1)})
    try:
        office.wait(timeout=120)
    except subprocess.TimeoutExpired:
        res.setdefault("note", "office killed after close")
    stop.set()
    sampler.join()
    kill_tree(office, own)
    res["peak_mb"] = round(peak[0])
    if save_to != "-" and os.path.exists(save_to):
        res["saved_mb"] = round(os.path.getsize(save_to) / 1e6, 1)
        os.remove(save_to)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--soffice", required=True)
    ap.add_argument("--python", required=True)
    ap.add_argument("--files", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--mode", default="gui", choices=("gui", "headless"))
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--seed", default="default", choices=("default", "toolbar", "tabbed", "nothreads", "norowheight"))
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--profile", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    profile = a.profile or os.path.join(a.out, "profile-" + a.label)
    shutil.rmtree(profile, ignore_errors=True)
    os.makedirs(os.path.join(profile, "user"))
    with open(os.path.join(profile, "user", "registrymodifications.xcu"), "w", encoding="utf-8") as f:
        f.write(seed_items(a.seed))
    only = set(filter(None, a.only.split(",")))
    files = sorted(n for n in os.listdir(a.files) if not only or n in only)
    pipe = "lfo%d" % os.getpid()
    # a first start creates the profile (extension registration, configuration) outside the measurements
    small = os.path.join(a.out, "warm-up.xlsx")
    tiny_xlsx(small)
    for _ in range(2):  # registration on the first start, the second as every later one
        warm = one_open(argparse.Namespace(**{**vars(a), "save": False, "timeout": 300}), small, file_url(profile), pipe)
        print("warm-up: %s" % warm, flush=True)
    with open(os.path.join(a.out, a.label + ".jsonl"), "a", encoding="utf-8") as log:
        for name in files:
            for i in range(a.repeat):
                res = one_open(a, os.path.join(a.files, name), file_url(profile), pipe)
                res.update({"label": a.label, "file": name, "run": i + 1, "mode": a.mode, "seed": a.seed,
                            "size_mb": round(os.path.getsize(os.path.join(a.files, name)) / 1e6, 1)})
                log.write(json.dumps(res, ensure_ascii=False) + "\n")
                log.flush()
                print(json.dumps(res, ensure_ascii=False), flush=True)
                if res.get("error") == "timeout":
                    break  # a second run would only time out again
    return 0


if __name__ == "__main__":
    sys.exit(main())
