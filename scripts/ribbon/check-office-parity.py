# SPDX-License-Identifier: AGPL-3.0-only
"""Offline ribbon parity check: data/ribbon/office-parity.json against the patched notebookbar.ui files.

Usage:
  python3 scripts/ribbon/check-office-parity.py --instdir DIR [--apps writer,calc,impress] [--json OUT] [--strict]
  python3 scripts/ribbon/check-office-parity.py --src upstream/libreoffice [...]   (patched source tree; vi .po)

For each Office command of the spec the status is:
  present     one of its UNO commands is a visible ribbon item on the HST tab that matches the Office tab;
  elsewhere   it is on another tab, or only in a tab menu (the "≡" button of a tab);
  missing     feasible, but nowhere on the ribbon;
  infeasible  no UNO command (listed in the spec, never counted against parity).
Group launchers (↘) are ToolBox items with an id starting with `btnHstLaunch` inside a captioned group.
D1 = present / feasible; D4 = launchers present / feasible launchers. Exit 1 only with --strict when a feasible command
is not present on its Office tab or a feasible launcher is missing.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# the reading functions are part of this script's interface (tests/unit/test_check_office_parity.py, the scorecard)
from office_parity_ui import (ITEM_CLASSES, LAUNCHER_PREFIX, Translator, clean_label, command_name,  # noqa: E402,F401
                              page_by_label, parse_notebookbar, read_po)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPEC = os.path.join(ROOT, "data", "ribbon", "office-parity.json")
MODULES = {"writer": ("swriter", "sw"), "calc": ("scalc", "sc"), "impress": ("simpress", "sd")}


def command_status(entry, target, pages):
    """(status, where) of one spec command against the parsed pages."""
    if not entry.get("feasible"):
        return "infeasible", []
    wanted = set(entry.get("uno") or [])
    if target is not None and wanted & target["commands"]:
        return "present", [target["label"]]
    where = [p["label"] for p in pages if wanted & p["commands"]]
    where += [f"≡ {p['label']}" for p in pages if wanted & p["menu_commands"]]
    return ("elsewhere" if where else "missing"), where


def app_report(spec_app, pages):
    """Rows, counts, D1, D4 and the offline group order of one app."""
    by_label = page_by_label(pages)
    rows, launchers = [], []
    for tab in spec_app["tabs"]:
        target = by_label.get(tab.get("hst_tab") or "")
        for group in tab["groups"]:
            for entry in group["commands"]:
                status, where = command_status(entry, target, pages)
                rows.append({"tab": tab["office"], "group": group["office"], "command": entry["office"],
                             "uno": entry.get("uno") or [], "status": status, "where": where})
            launcher = group.get("launcher")
            if launcher and launcher.get("feasible"):
                found = target is not None and any(
                    item["command"] == launcher["command"] and item["group"] == group.get("hst_group")
                    for item in target["launchers"])
                launchers.append({"tab": tab["office"], "group": group["office"], "command": launcher["command"],
                                  "present": found})
    counts = {s: sum(r["status"] == s for r in rows) for s in ("present", "elsewhere", "missing", "infeasible")}
    feasible = counts["present"] + counts["elsewhere"] + counts["missing"]
    return {"rows": rows, "launchers": launchers, "counts": counts, "listed": len(rows), "feasible": feasible,
            "d1": round(counts["present"] / feasible, 4) if feasible else 0.0,
            "raw_coverage": round(counts["present"] / len(rows), 4) if rows else 0.0,
            "d4": round(sum(l["present"] for l in launchers) / len(launchers), 4) if launchers else 0.0,
            "launchers_present": sum(l["present"] for l in launchers), "launchers_feasible": len(launchers)}


def ui_paths(app, instdir=None, src=None):
    """(notebookbar.ui, translator) for an app from an instdir or a patched source tree."""
    module, catalog = MODULES[app]
    if instdir:
        ui = os.path.join(instdir, "share", "config", "soffice.cfg", "modules", module, "ui", "notebookbar.ui")
        translate = Translator(mo_path=os.path.join(instdir, "program", "resource", "vi", "LC_MESSAGES", f"{catalog}.mo"))
    else:
        folder = {"swriter": "sw/uiconfig/swriter", "scalc": "sc/uiconfig/scalc", "simpress": "sd/uiconfig/simpress"}[module]
        ui = os.path.join(src, folder, "ui", "notebookbar.ui")
        translate = Translator(po_path=os.path.join(src, "translations", "source", "vi", catalog, "messages.po"))
    return ui, translate


def load_spec(path=SPEC):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def report(spec, apps, instdir=None, src=None):
    result = {}
    for app in apps:
        ui, translate = ui_paths(app, instdir, src)
        result[app] = app_report(spec["apps"][app], parse_notebookbar(ui, translate))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--instdir")
    where.add_argument("--src")
    parser.add_argument("--spec", default=SPEC)
    parser.add_argument("--apps", default="writer,calc,impress")
    parser.add_argument("--json")
    parser.add_argument("--verbose", action="store_true", help="list every row that is not present")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    result = report(load_spec(args.spec), args.apps.split(","), args.instdir, args.src)
    failed = False
    for app, data in result.items():
        c = data["counts"]
        print(f"{app}: listed {data['listed']}, present {c['present']}, elsewhere {c['elsewhere']}, missing {c['missing']}, "
              f"infeasible {c['infeasible']}; D1 {data['d1']:.4f}; launchers {data['launchers_present']}/"
              f"{data['launchers_feasible']} (D4 {data['d4']:.4f})")
        if args.verbose:
            for row in data["rows"]:
                if row["status"] in ("elsewhere", "missing"):
                    print(f"  {row['status']:9} {row['tab']} / {row['group']} / {row['command']} {row['uno']} {row['where']}")
        failed |= c["elsewhere"] + c["missing"] > 0 or data["launchers_present"] < data["launchers_feasible"]
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=1)
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    sys.exit(main())
