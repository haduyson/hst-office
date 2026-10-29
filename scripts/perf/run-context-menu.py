#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Orchestrate context-menu latency runs on Linux (X11 + XTest) or macOS (Swift CGEvent tool).

Writes one JSON per matrix cell plus env.json into --output; analyse with analyze-context-menu.py.
Only processes started here are tracked and terminated (own session / process group).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import context_menu_drivers as drv  # noqa: E402
import context_menu_env as cenv  # noqa: E402
import context_menu_fixtures as cfix  # noqa: E402

def run_cell(args, cell, matrix, fixtures, x11, out_dir: Path, work: Path) -> dict:
    mod, start = cell["module"], cell["start"]
    d = matrix["defaults"]
    n = args.cold if start == "cold" else args.warm
    n = d["cold" if start == "cold" else "warm"] if n is None else n
    settle = args.settle_s if args.settle_s is not None else d["cold_settle_s" if start == "cold" else "settle_s"]
    fraction = matrix["right_click_fraction"][mod]
    fixture = fixtures / cfix.write_fixtures(fixtures)[mod]["file"]
    trials, extra, sample_file = [], {}, None
    launches = n if start == "cold" else 1
    for k in range(launches):
        prof = cenv.prepare_profile(cell, work, args.user_profile)
        proc = drv.launch(args, cell, fixture, prof)
        try:
            if args.platform == "linux":
                t, extra = drv.linux_trials(x11, args, cell, fraction, 1 if start == "cold" else n, settle,
                                        0 if start == "cold" else 1)
            else:
                res = drv.mac_trials(args, cell, fraction, proc, 1 if start == "cold" else n, settle, work, "trial")
                t, extra = res["trials"], {k2: v for k2, v in res.items() if k2 != "trials"}
                if args.sample and start == "warm":
                    sample_file = str(out_dir / f"{cell['id']}.sample.txt")
                    sp = subprocess.Popen(["sample", str(proc.pid), "5", "1", "-file", sample_file],
                                          stdout=subprocess.DEVNULL, start_new_session=True)
                    drv.STARTED.append(sp)
                    drv.mac_trials(args, cell, fraction, proc, 3, 1, work, "sample-trial", 900)
                    sp.wait(timeout=30)
                    drv.STARTED.remove(sp)
        finally:
            drv.stop(proc)
            time.sleep(1.0)
        for tr in t:
            trials.append({**tr, "i": len(trials) + 1})
    return {"schema": 1, "cell": cell, "platform": args.platform, "app": str(args.app), "params": {
            "timeout_ms": args.timeout_ms, "settle_s": settle, "vcl": args.vcl, "display": args.display},
            "extra": extra, "trials": trials, "sample_file": sample_file}


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--platform", choices=["linux", "macos"], required=True)
    ap.add_argument("--app", type=Path, required=True, help="soffice binary (linux) or .app bundle (macos)")
    ap.add_argument("--matrix", type=Path, default=here / "context-menu-matrix.json")
    ap.add_argument("--preset", default="owner-quick")
    ap.add_argument("--only", default="", help="substring filter on cell ids")
    ap.add_argument("--cold", type=int, help="cold trials per cell (fresh process each)")
    ap.add_argument("--warm", type=int, help="warm trials per cell")
    ap.add_argument("--timeout-ms", type=int, default=5000)
    ap.add_argument("--settle-s", type=float, help="seconds to idle after the window appears")
    ap.add_argument("--load-timeout-s", type=int, default=90)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--user-profile", type=Path, help="existing LibreOffice profile dir to COPY for profile=user cells")
    ap.add_argument("--display", default=":98", help="linux: X display (must already exist or use --start-xvfb)")
    ap.add_argument("--start-xvfb", action="store_true", help="linux: start Xvfb on --display (fails if in use)")
    ap.add_argument("--vcl", default="", help="linux: SAL_USE_VCLPLUGIN value (e.g. gtk3); empty = LibreOffice default")
    ap.add_argument("--swift-tool", type=Path, default=Path("build/tools/macos-context-menu"))
    ap.add_argument("--sample", action="store_true", help="macos: run `sample` during 3 extra warm trials")
    ap.add_argument("--env", action="append", default=[], help="extra KEY=VALUE for the app (repeatable)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    args.output, args.app, args.swift_tool = args.output.resolve(), args.app.resolve(), args.swift_tool.resolve()
    if args.user_profile:
        args.user_profile = args.user_profile.resolve()

    matrix = cenv.load_matrix(args.matrix)
    cells = [c for c in cenv.expand_preset(matrix, args.preset) if args.only in c["id"]]
    if args.user_profile is None:
        mac_default = Path.home() / "Library/Application Support/LibreOffice/4"
        if args.platform == "macos" and mac_default.is_dir():
            args.user_profile = mac_default
    if args.user_profile is None:
        skipped = [c["id"] for c in cells if c["profile"] == "user"]
        cells = [c for c in cells if c["profile"] != "user"]
        if skipped:
            print(f"skipping profile=user cells (no --user-profile): {skipped}", file=sys.stderr)
    if args.dry_run:
        print("\n".join(c["id"] for c in cells))
        return 0

    args.output.mkdir(parents=True, exist_ok=True)
    work = args.output / "work"
    fixtures = work / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    x11, xvfb = None, None
    try:
        if args.platform == "linux":
            sock = Path("/tmp/.X11-unix") / f"X{args.display.lstrip(':').split('.')[0]}"
            if args.start_xvfb:
                if sock.exists():
                    print(f"ERROR: display {args.display} already in use ({sock}); stop its owner, not auto-incrementing", file=sys.stderr)
                    return 2
                xvfb = subprocess.Popen(["Xvfb", args.display, "-screen", "0", "1600x1000x24", "-nolisten", "tcp"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                drv.STARTED.append(xvfb)
                time.sleep(2)
            elif not sock.exists():
                print(f"ERROR: display {args.display} not found ({sock}); pass --start-xvfb or create it", file=sys.stderr)
                return 2
            import context_menu_x11 as cx  # noqa: E402
            x11 = cx.X11Driver(args.display)
        elif not args.swift_tool.is_file():
            print(f"ERROR: Swift tool {args.swift_tool} missing; build it first (see docs/CONTEXT_MENU_PERFORMANCE.md)", file=sys.stderr)
            return 2
        env = cenv.collect(args.platform, args.app)
        (args.output / "env.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
        for cell in cells:
            print(f"[{time.strftime('%H:%M:%S')}] {cell['id']}", flush=True)
            doc = run_cell(args, cell, matrix, fixtures, x11, args.output, work)
            doc["env"] = env
            (args.output / f"{cell['id']}.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    finally:
        if x11:
            x11.close()
        for proc in list(drv.STARTED):
            drv.stop(proc)
        shutil.rmtree(work / "profile", ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
