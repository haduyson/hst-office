# SPDX-License-Identifier: AGPL-3.0-only
"""Process launch/stop and per-platform trial drivers used by run-context-menu.py."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path

STARTED: list[subprocess.Popen] = []


def stop(proc: subprocess.Popen, term_s: float = 10.0) -> None:
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=term_s)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
    if proc in STARTED:
        STARTED.remove(proc)


def app_binary(platform_name: str, app: Path) -> str:
    if platform_name == "macos" and app.suffix == ".app":
        macos = app / "Contents" / "MacOS"
        for name in ("soffice", "soffice.bin"):
            if (macos / name).is_file():
                return str(macos / name)
        raise FileNotFoundError(f"no soffice executable under {macos}")
    return str(app)


def launch(args, cell: dict, fixture: Path, prof: Path) -> subprocess.Popen:
    env = dict(os.environ)
    env.pop("SAL_SKIA", None)
    if cell["skia"] == "raster":
        env["SAL_SKIA"] = "raster"
    for kv in args.env:
        k, _, v = kv.partition("=")
        env[k] = v
    if args.platform == "linux":
        env["DISPLAY"] = args.display
        if args.vcl:
            env["SAL_USE_VCLPLUGIN"] = args.vcl
    cmd = [app_binary(args.platform, args.app), f"-env:UserInstallation=file://{prof}",
           "--norestore", "--nologo", str(fixture)]
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    STARTED.append(proc)
    return proc


def linux_trials(x11, args, cell, fraction, n, settle_s, warmup) -> tuple[list[dict], dict]:
    """Wait for the document window, settle, then run n right-click trials on it."""
    t_end = time.time() + args.load_timeout_s
    main = None
    while time.time() < t_end and main is None:
        big = {w: g for w, g in x11.viewable_windows().items() if g[2] >= 300 and g[3] >= 300}
        main = max(big.items(), key=lambda kv: kv[1][2] * kv[1][3]) if big else None
        time.sleep(0.25)
    if main is None:
        return [{"i": 1, "ms": None, "timeout": True, "error": "document window not shown"}], {}
    _, (wx, wy, ww, wh) = main
    time.sleep(settle_s)
    px, py = int(wx + ww * fraction[0]), int(wy + wh * fraction[1])
    extra: dict = {"window": [wx, wy, ww, wh], "point": [px, py]}
    trials = []
    for i in range(-warmup + 1, n + 1):
        before = set(x11.viewable_windows())
        res = x11.right_click_and_wait(px, py, args.timeout_ms / 1000.0)
        x11.dismiss_popup(before)
        if i <= 0:
            extra["warmup_ms"] = res["ms"]
            continue
        trials.append({"i": i, **res})
    return trials, extra


def mac_trials(args, cell, fraction, proc, n, settle_s, work: Path, tag: str, interval_ms: int = 700) -> dict:
    out = work / f"{tag}.json"
    cmd = [str(args.swift_tool), "--pid", str(proc.pid), "--trials", str(n), "--timeout-ms", str(args.timeout_ms),
           "--x-frac", str(fraction[0]), "--y-frac", str(fraction[1]), "--wait-window-s", str(args.load_timeout_s),
           "--settle-s", str(settle_s), "--interval-ms", str(interval_ms), "--out", str(out)]
    subprocess.run(cmd, check=True, timeout=args.load_timeout_s + n * (args.timeout_ms / 1000 + 3) + 60)
    return json.loads(out.read_text(encoding="utf-8"))
