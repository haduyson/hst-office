# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon likeness scorecard of HST Writer, Sheets and Slides.

Usage:
  python3 tests/runtime/ribbon_scorecard.py --instdir DIR [--display :153] [--apps writer,calc,impress]
                                            [--modes light,dark] [--out build/ribbon-scorecard] [--label baseline]
  python3 tests/runtime/ribbon_scorecard.py --instdir DIR --rescore --out build/ribbon-scorecard   (score saved observations)

The X display must already run, at least 1920 px wide. Each app and colour mode runs in its own soffice (as the build user,
under its own dbus-run-session) through ribbon_scorecard_live.py, which saves an observation JSON. This script then scores:
  D1 command parity    present on the Office tab / feasible Office commands (offline, data/ribbon/office-parity.json
                       against the notebookbar.ui files of the instdir, scripts/ribbon/check-office-parity.py);
  D2 structure         Office tabs in order (live tab strip), contextual tabs present, Office groups in order on their tab
                       (longest common subsequence);
  D3 scaling           per tab and width: (a) no "»" while a group still shows its caption, (b) no group grows or
                       comes back while the window narrows, (c) every group reachable in one more click, (d) ribbon
                       height and banner slot kept;
  D4 launchers         launchers present / feasible Office launchers (offline);
  D5 painting          ten pixel probes on Home, light and dark;
  D6 galleries         Writer Styles gallery (>= 2 tiles at 1485, >= 4 at 1920, no growth when narrower, More,
                       keyboard) and a 32 px Paste with label in each app.
Writes OUT/scorecard.json and OUT/scorecard.md. Exit 0; the score is the result, not a gate.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
# the scoring functions are part of this module's interface (tests/unit/test_ribbon_scorecard.py)
from ribbon_scorecard_scoring import (APPS, GALLERY, NAMES, PROBES, dedupe, lcs, parity, ratio,  # noqa: E402,F401
                                      scaling_checks, score, score_galleries, score_probes, score_scaling,
                                      score_structure)


def load_config(path=os.path.join(HERE, "ribbon-scorecard-widths.json")):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)



def markdown(card, meta):
    lines = [f"# Ribbon scorecard: {meta.get('label', '')}", "",
             f"Build: `{meta.get('instdir', '')}`; measured {meta.get('when', '')}; gtk3, vi_VN, scale 1, Xvfb.", "",
             f"**Total: {card['total'] * 100:.1f} %**", "",
             "| Dim | Name | Weight | Writer | Sheets | Slides | Score | Floor |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for dim in ("D1", "D2", "D3", "D4", "D5", "D6"):
        per = card["per_app"].get(dim, {})
        cells = [f"{per[a]:.3f}" if a in per else "–" for a in APPS]
        mark = " ✗" if dim in card["below_floor"] else ""
        lines.append(f"| {dim} | {NAMES[dim]} | {card['weights'][dim]:.2f} | {' | '.join(cells)} | "
                     f"{card['dimensions'][dim]:.3f}{mark} | {card['floors'][dim]:.2f} |")
    lines += ["", "## Detail", ""]
    for app, detail in card["details"].items():
        c = detail["parity_counts"]
        lines += [f"### {app}", "",
                  f"- D1: present {c['present']}, elsewhere {c['elsewhere']}, missing {c['missing']}, infeasible "
                  f"{c['infeasible']}; raw Office coverage {detail['raw_coverage']:.3f}.",
                  f"- D2: tabs {detail['D2']['tabs']}, contextual {detail['D2']['contextual']}, groups "
                  f"{detail['D2']['groups']}; missing tabs: {', '.join(detail['D2']['missing_tabs']) or 'none'}.",
                  f"- D3: {detail['D3_checks'] - len(detail['D3_failed'])}/{detail['D3_checks']} checks pass. Failed by "
                  f"check: " + ", ".join(f"{k} {sum(1 for r in detail['D3_failed'] if r[2] == k)}" for k in "abcd") + ".",
                  f"- D4: launchers {detail['launchers'][0]}/{detail['launchers'][1]}.",
                  "- D5: " + ", ".join(f"{m}/{n} {'pass' if ok else 'fail'}" for m, n, ok, _d in detail["D5"]) + "."]
        if detail["errors"]:
            lines.append(f"- Errors: {detail['errors']}")
        lines.append("")
    lines += ["### D6", ""] + [f"- {name}: {'pass' if ok else 'fail'} ({d})" for name, ok, d in card["D6"]]
    return "\n".join(lines) + "\n"


def run_live(args, apps, modes):
    """Run ribbon_scorecard_live.py once per app and mode; returns {app: {mode: observation}}."""
    obs_dir = os.path.join(args.out, "observations")
    os.makedirs(obs_dir, exist_ok=True)
    as_user = os.geteuid() == 0
    if as_user:
        subprocess.run(["chown", "-R", os.environ.get("HST_BUILD_USER", "hstbuild"), args.out], check=False)
    for index, (app, mode) in enumerate((a, m) for a in apps for m in modes):
        out = os.path.join(obs_dir, f"{app}-{mode}.json")
        work = os.path.join(args.out, "work", f"{app}-{mode}")
        command = [sys.executable, os.path.join(HERE, "ribbon_scorecard_live.py"), "--app", app, "--mode", mode,
                   "--instdir", args.instdir, "--display", args.display, "--work", work, "--out", out,
                   "--port", str(args.port + 2 * index)]
        prefix = ["runuser", "-u", os.environ.get("HST_BUILD_USER", "hstbuild"), "--"] if as_user else []
        with open(os.path.join(obs_dir, f"{app}-{mode}.log"), "w", encoding="utf-8") as log:
            print(f"measuring {app} {mode}", flush=True)
            done = subprocess.run(prefix + ["dbus-run-session", "--"] + command, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=3600, check=False)
        if done.returncode != 0 or not os.path.exists(out):
            with open(out, "w", encoding="utf-8") as handle:
                json.dump({"app": app, "mode": mode, "errors": [f"live run exited {done.returncode}"]}, handle)
    return read_observations(obs_dir, apps, modes)


def read_observations(obs_dir, apps, modes):
    result = {}
    for app in apps:
        for mode in modes:
            path = os.path.join(obs_dir, f"{app}-{mode}.json")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    result.setdefault(app, {})[mode] = json.load(handle)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", default=":153")
    parser.add_argument("--apps", default=",".join(APPS))
    parser.add_argument("--modes", default="light,dark")
    parser.add_argument("--out", default=os.path.join(ROOT, "build", "ribbon-scorecard"))
    parser.add_argument("--label", default="")
    parser.add_argument("--port", type=int, default=7650)
    parser.add_argument("--rescore", action="store_true", help="score the saved observations; start nothing")
    args = parser.parse_args(argv)
    args.instdir, args.out = os.path.abspath(args.instdir), os.path.abspath(args.out)
    apps, modes = args.apps.split(","), args.modes.split(",")
    config, spec = load_config(), parity.load_spec()
    os.makedirs(args.out, exist_ok=True)
    if args.rescore:
        per_app = read_observations(os.path.join(args.out, "observations"), apps, modes)
    else:
        per_app = run_live(args, apps, modes)
    pages = {}
    for app in apps:
        ui, translate = parity.ui_paths(app, instdir=args.instdir)
        pages[app] = parity.parse_notebookbar(ui, translate)
    report = {app: parity.app_report(spec["apps"][app], pages[app]) for app in apps}
    card = score(per_app, report, pages, spec, config, apps)
    meta = {"label": args.label, "instdir": args.instdir,
            "when": datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")}
    with open(os.path.join(args.out, "scorecard.json"), "w", encoding="utf-8") as handle:
        json.dump(dict(card, meta=meta), handle, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, "scorecard.md"), "w", encoding="utf-8") as handle:
        handle.write(markdown(card, meta))
    print(f"total {card['total'] * 100:.1f} % " + " ".join(f"{d} {v:.3f}" for d, v in card["dimensions"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
