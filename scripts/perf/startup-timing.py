#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Time office start-ups on this machine: launch to splash, splash gone, first Start Center or document window.

Runs with any Python 3.9+ (the runner's); quits each start through scripts/perf/startup-quit-office.py run with the
office's own Python. Starts are given in order with --starts, each one of:
  fresh  delete the profile first: the very first start of a new user
  warm   the profile the previous start left
  cold   like warm, after --cold-command (emptying the OS file cache: a start after a reboot)
--trace loads scripts/perf/startup_trace/sitecustomize.py into the office's Python (module import, compile and HST
job timings, network calls with their thread). --env NAME=VALUE (repeatable) sets an environment variable of the
office. Writes <out>/<label>.json and prints one line per start. Evidence only: exit 0 unless the office never showed
a window.

Usage: startup-timing.py --soffice PATH --python PATH --intro intro.png --profile DIR --out DIR --label NAME
           [--starts fresh,warm,warm,cold] [--trace] [--env NAME=VALUE] [--cold-command CMD] [--settle 8]
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import startup_phases  # noqa: E402
import startup_window_samplers  # noqa: E402
from startup_evidence import png_size, profile_facts, screenshot  # noqa: E402

PORT = 2117  # the UNO socket of the office this harness starts


def profile_url(path):
    return urllib.parse.urljoin("file:", urllib.request.pathname2url(os.path.abspath(path)))


def kill_own(proc, profile):
    """Stop the office of our profile when it did not quit: the launcher's process tree on Windows, the processes
    started with our profile elsewhere (never another office)."""
    url = profile_url(profile)
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False)
        return [proc.pid]
    proc.terminate()  # the office quits cleanly on SIGTERM unless a modal dialog holds it
    try:
        proc.wait(15)
    except subprocess.TimeoutExpired:
        proc.kill()
    listing = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, check=False).stdout
    killed = []
    for line in listing.splitlines():
        pid, _, command = line.strip().partition(" ")
        if "soffice" in command and "UserInstallation=" + url in command and int(pid) != os.getpid():
            subprocess.run(["kill", "-9", pid], check=False)
            killed.append(int(pid))
    return killed


def wait_gone(sample, seconds=20):
    """Wait until no office window is left on screen (the previous start's process may still be ending)."""
    deadline = time.time() + seconds
    while sample() and time.time() < deadline:
        time.sleep(0.2)


def one_start(args, index, kind, sample, bitmap):
    if kind == "fresh" and os.path.isdir(args.profile):
        import shutil
        shutil.rmtree(args.profile, ignore_errors=True)
    if kind == "cold" and args.cold_command:
        cold = subprocess.run(args.cold_command, shell=True, capture_output=True, text=True, check=False)
        print("cold command exit %d %s" % (cold.returncode, (cold.stdout + cold.stderr).strip()[-300:]), flush=True)
    env = dict(os.environ)
    trace = os.path.join(args.out, "%s-%d-trace.jsonl" % (args.label, index))
    if args.trace:
        env["PYTHONPATH"] = os.path.join(HERE, "startup_trace") + os.pathsep + env.get("PYTHONPATH", "")
        env["HST_STARTUP_TRACE"] = trace
        if os.path.exists(trace):
            os.remove(trace)
    for item in args.env:
        name, _, value = item.partition("=")
        env[name] = value
    cmd = [args.soffice, "--norestore", "-env:UserInstallation=" + profile_url(args.profile),
           "--accept=socket,host=127.0.0.1,port=%d;urp;" % PORT] + args.extra
    wait_gone(sample)
    log = open(os.path.join(args.out, "%s-%d-soffice.log" % (args.label, index)), "w", encoding="utf-8")
    samples, shot = [], None
    launched = time.time()
    proc = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    frame_at = splash_at = None
    while True:
        now = time.time() - launched
        windows = sample()
        samples.append((round(now, 3), windows))
        kinds = [startup_phases.kind_of(w, bitmap) for w in windows]
        if "splash" in kinds and splash_at is None:
            splash_at = now
        if shot is None and args.shots and "splash" in kinds and now > splash_at + 0.4:  # painted, progress drawn
            splash = windows[kinds.index("splash")]
            shot = screenshot(os.path.join(args.out, "%s-%d-splash.png" % (args.label, index)),
                              (splash[5], splash[6], splash[5] + splash[1], splash[6] + splash[2]) if len(splash) > 6 else None)
        if frame_at is None and "frame" in kinds:
            frame_at = now
        if frame_at is not None and now > frame_at + args.settle:
            break
        if now > args.timeout or (proc.poll() is not None and frame_at is None and now > 30):
            break
        time.sleep(0.02)
    if args.shots:
        screenshot(os.path.join(args.out, "%s-%d-ready.png" % (args.label, index)))
    quit_out = subprocess.run([args.python, os.path.join(HERE, "startup-quit-office.py"), str(PORT)], capture_output=True,
                              text=True, check=False, timeout=120)
    try:
        code = proc.wait(30)
    except subprocess.TimeoutExpired:
        code = "killed %s" % kill_own(proc, args.profile)
        proc.wait(30)
    wait_gone(sample)
    log.close()
    events = []
    if args.trace and os.path.exists(trace):
        with open(trace, encoding="utf-8") as handle:
            events = [json.loads(line) for line in handle if line.strip()]
    result = {"start": index, "kind": kind, "phases": startup_phases.phases(samples, bitmap), "exit": code,
              "quit": quit_out.stdout.strip()[-800:] or quit_out.stderr.strip()[-800:], "profile": profile_facts(args.profile),
              "windows_seen": sorted({(w[1], w[2], w[3], startup_phases.kind_of(w, bitmap)) for _t, ws in samples for w in ws}),
              "splash_shot": shot}
    if events:
        result["python"] = startup_phases.python_breakdown(events, launched, result["phases"]["frame_shown"])
    with open(os.path.join(args.out, "%s-%d-samples.json" % (args.label, index)), "w", encoding="utf-8") as handle:
        json.dump(samples, handle)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--intro")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--starts", default="fresh,warm,warm")
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--shots", action="store_true")
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--extra", default="", help="more office arguments, shell-quoted")
    parser.add_argument("--cold-command", default="")
    parser.add_argument("--settle", type=float, default=8)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    args.extra = shlex.split(args.extra)
    os.makedirs(args.out, exist_ok=True)
    bitmap = png_size(args.intro) if args.intro and os.path.exists(args.intro) else (644, 199)
    sample = startup_window_samplers.sampler()
    results = []
    for index, kind in enumerate(args.starts.split(","), 1):
        result = one_start(args, index, kind.strip(), sample, bitmap)
        results.append(result)
        p = result["phases"]
        py = result.get("python", {})
        print("%-24s start %d %-5s frame %6s s  splash %5s s visible  pids %s  exit %s%s" % (
            args.label, index, kind, p["launch_to_frame_s"], p["splash_visible_s"], len(p["pids"]), result["exit"],
            ("  python up %s s; before the window: imports %s s, %s modules, %s compiled in %s s" % (
                py.get("python_init_s"), *[py.get("before_frame", {}).get(k) for k in (
                    "imports_s", "modules", "compiled", "compile_s")]) if py else "")), flush=True)
    with open(os.path.join(args.out, args.label + ".json"), "w", encoding="utf-8") as handle:
        json.dump({"label": args.label, "splash_bitmap": bitmap, "starts": results}, handle, ensure_ascii=False,
                  indent=1)
    return 0 if any(r["phases"]["frame_shown"] is not None for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
