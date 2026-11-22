# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Open time of large documents in one office installation (HST Office or stock LibreOffice), one office per open.

    python large-file-open.py --soffice <soffice> --python <office python> --files <dir> --out <dir> --label <name>
        [--mode gui|headless|cli] [--repeat N] [--timeout S] [--seed default|spell|...] [--cpus N] [--save] [--full-layout] [--probe S] [--only a,b]
        [--freeze] [--interact] [--autosave]

Per file and repeat: a new office process on the label's profile (large_file_open_profile.py), --accept on a private
pipe; large_file_open_client.py (run by the office's Python) loads the file in a visible window (gui), hidden
(headless) or finds it opened from the command line as by a double-click (cli), waits until the office is idle,
optionally stores it again with its own filter and as ODF (the cost of a save / an AutoRecovery copy). Peak memory of
the office processes is sampled. An open that does not finish within --timeout is killed and recorded as "timeout";
an office that ends with a non-zero code is recorded as "office_exit" (crash). --cpus N runs the office on N logical
processors only (a 4-core PC on a big build machine). --freeze records the longest frozen user interface (main-loop
stall) during and after the load, --interact scroll/typing latencies, --autosave the AutoRecovery timer's save (seed
"autosave": every minute); on Windows hung_s/hung_longest_s count what Windows shows as "Not responding" (needs a desktop
session). Writes <label>.jsonl and prints one JSON line per open.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import large_file_open_procs as procs  # noqa: E402
import large_file_open_profile as profiles  # noqa: E402

CLIENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "large_file_open_client.py")


def file_url(path):
    return "file:///" + os.path.abspath(path).replace("\\", "/").lstrip("/")


def evidence(a, name, own):
    """The office's window titles (Windows) when an open does not finish: a dialog, or still working."""
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
        f.write("%s %s windows=%r\n" % (a.label, name, titles))


def one_open(a, path, profile, pipe):
    profiles.clear_leftovers(profile, path)
    profiles.reseed(profile, a.seed)
    before = set(procs.office_pids())
    args = [a.soffice, "-env:UserInstallation=" + file_url(profile), "--accept=pipe,name=%s;urp;" % pipe,
            "--nologo", "--nodefault"] + ([] if a.seed == "autosave" else ["--norestore"])  # it disables AutoRecovery
    if a.mode == "headless":
        args.append("--headless")
    if a.mode == "cli":  # as a double-click: the file on the command line
        args.append(os.path.abspath(path))
    office = subprocess.Popen(procs.limit_cpus(args, a.cpus))
    # in this run's own output directory: two runs that save the same file must not share (and lock) one copy
    save_to = os.path.join(os.path.abspath(a.out), "lfo-save-" + os.path.basename(path)) if a.save else "-"
    client = subprocess.Popen([a.python, CLIENT, pipe, os.path.abspath(path),
                               {"headless": "1", "gui": "0"}.get(a.mode, "cli"), save_to],
                              stdout=subprocess.PIPE, text=True)
    peak, own, stop, hung = [0.0], set(), threading.Event(), [0.0, 0.0, 0.0]  # total, current, longest

    def sample():
        last = time.monotonic()
        while not stop.is_set():
            own.update(procs.descendants(office.pid, set(procs.office_pids()) - before))
            peak[0] = max(peak[0], procs.rss_mb(own))
            now = time.monotonic()
            if procs.WINDOWS and procs.any_hung_window(own):
                hung[0] += now - last
                hung[1] += now - last
                hung[2] = max(hung[2], hung[1])
            else:
                hung[1] = 0.0
            last = now
            time.sleep(0.5 if sys.platform == "win32" else 0.25)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    started = time.monotonic()
    try:
        out, _ = client.communicate(timeout=a.timeout)
        line = (out.strip().splitlines() or ["{}"])[-1]
        res = json.loads(line) if line.startswith("{") else {"error": "client: " + line[:200]}
        res["after"] = round(time.monotonic() - started, 1)
    except subprocess.TimeoutExpired:
        evidence(a, os.path.basename(path), own)
        procs.kill(client, [client.pid])  # its tree: on Windows the office's python.exe is a launcher
        try:
            out, _ = client.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            out = ""
        lines = [x for x in out.strip().splitlines() if x.startswith("{")]
        res = json.loads(lines[-1]) if lines else {}
        res.update({"error": "timeout", "after": round(time.monotonic() - started, 1)})
    try:
        office.wait(timeout=120)
    except subprocess.TimeoutExpired:
        res.setdefault("note", "office killed after close")
    stop.set()
    sampler.join()
    if office.returncode not in (None, 0):  # 3221226505 = 0xC0000409 (abort), 3221225725 = 0xC00000FD, ...
        res["office_exit"] = office.returncode
    procs.kill(office, own)
    res["peak_mb"] = round(peak[0])
    if procs.WINDOWS:
        res["hung_s"], res["hung_longest_s"] = round(hung[0], 1), round(hung[2], 1)
    for leftover, key in ((save_to, "saved_mb"), (save_to + ".odf", "")):
        if save_to != "-" and os.path.exists(leftover):
            if key:
                res[key] = round(os.path.getsize(leftover) / 1e6, 1)
            os.remove(leftover)
    return res


def main():
    ap = argparse.ArgumentParser()
    for name in ("--soffice", "--python", "--files", "--out", "--label"):
        ap.add_argument(name, required=True)
    ap.add_argument("--mode", default="gui", choices=("gui", "headless", "cli"))
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--seed", default="default", choices=profiles.SEEDS)
    ap.add_argument("--cpus", type=int, default=0)
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--full-layout", action="store_true", help="Writer: also time the layout of the whole document")
    ap.add_argument("--probe", type=float, default=0, help="seconds of responsiveness probes after the load")
    ap.add_argument("--only", default="")
    ap.add_argument("--profile", default="")
    for flag in ("freeze", "interact", "autosave"):  # read by the client (large_file_open_interact.py)
        ap.add_argument("--" + flag, action="store_true")
    a = ap.parse_args()
    for flag in ("freeze", "interact", "autosave"):
        if getattr(a, flag):
            os.environ["LFO_" + flag.upper()] = "1"
    if a.autosave:
        os.environ["LFO_FREEZE"] = "1"
    if a.full_layout:
        os.environ["LFO_FULL_LAYOUT"] = "1"  # read by the client (large_file_open_client.py)
    if a.probe:
        os.environ["LFO_PROBE"] = str(a.probe)
    os.makedirs(a.out, exist_ok=True)
    profile = a.profile or os.path.join(a.out, "profile-" + a.label)
    os.environ["LFO_PROFILE"] = os.path.abspath(profile)
    shutil.rmtree(profile, ignore_errors=True)
    profiles.create(profile, a.seed)
    only = list(filter(None, a.only.split(",")))  # opened in this order (the most important first)
    present = set(os.listdir(a.files))
    files = [n for n in only if n in present] if only else sorted(n for n in present if not n.startswith("."))
    pipe = "lfo%d" % os.getpid()
    # the first start creates the profile (extension registration, configuration) outside the measurements
    from large_file_fixtures_xlsx import write_xlsx
    small = os.path.join(a.out, "warm-up.xlsx")
    write_xlsx(small, 20, True, "Microsoft Excel")
    for _ in range(2):  # registration on the first start, the second as every later one
        warm = one_open(argparse.Namespace(**{**vars(a), "save": False, "timeout": 300}), small, profile, pipe)
        print("warm-up: %s" % json.dumps(warm), flush=True)
    with open(os.path.join(a.out, a.label + ".jsonl"), "a", encoding="utf-8") as log:
        for name in files:
            for i in range(a.repeat):
                for _ in range(3):
                    res = one_open(a, os.path.join(a.files, name), profile, pipe)
                    # SIGKILL from outside (another tool's cleanup on a shared machine), not a crash: again
                    if res.get("office_exit") not in (137, -9) or res.get("error") == "timeout":
                        break
                    print("killed from outside, again: %s" % json.dumps(res), flush=True)
                res.update({"label": a.label, "file": name, "run": i + 1, "mode": a.mode, "seed": a.seed,
                            "cpus": a.cpus, "size_mb": round(os.path.getsize(os.path.join(a.files, name)) / 1e6, 1)})
                log.write(json.dumps(res, ensure_ascii=False) + "\n")
                log.flush()
                print(json.dumps(res, ensure_ascii=False), flush=True)
                if res.get("error") == "timeout" or "office_exit" in res:
                    break  # a second run would only time out or crash again
    return 0


if __name__ == "__main__":
    sys.exit(main())
