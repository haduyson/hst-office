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
import gettext
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPEC = os.path.join(ROOT, "data", "ribbon", "office-parity.json")
MODULES = {"writer": ("swriter", "sw"), "calc": ("scalc", "sc"), "impress": ("simpress", "sd")}
ITEM_CLASSES = ("GtkToolButton", "GtkMenuToolButton", "GtkToggleToolButton", "GtkRadioToolButton")
LAUNCHER_PREFIX = "btnHstLaunch"


def command_name(action):
    """'.uno:Bold' -> 'Bold', without arguments ('.uno:StyleApply?Style:string=Good' -> 'StyleApply');
    other protocols ('org.hst.office.vi:ReportError') stay whole."""
    return action[len(".uno:"):].split("?", 1)[0] if action.startswith(".uno:") else action


def read_po(path):
    """{(msgctxt, msgid): msgstr} of a gettext .po file (enough of the format for LibreOffice's ui strings)."""
    entries, current, key = {}, {}, None

    def unquote(text):
        return json.loads(text) if text.startswith('"') else text

    def flush():
        if current.get("msgstr"):
            entries[(current.get("msgctxt", ""), current.get("msgid", ""))] = current["msgstr"]

    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                if not line and current:
                    flush()
                    current, key = {}, None
                continue
            match = re.match(r'^(msgctxt|msgid|msgstr)\s+(".*")$', line)
            if match:
                key = match.group(1)
                current[key] = unquote(match.group(2))
            elif line.startswith('"') and key:
                current[key] += unquote(line)
    flush()
    return entries


class Translator:
    """Translate ui strings with a compiled .mo (instdir) or a .po (source tree); identity without either."""

    def __init__(self, mo_path=None, po_path=None):
        self.mo = None
        self.po = {}
        if mo_path and os.path.exists(mo_path):
            with open(mo_path, "rb") as handle:
                self.mo = gettext.GNUTranslations(handle)
        elif po_path and os.path.exists(po_path):
            self.po = read_po(po_path)

    def __call__(self, context, text):
        if self.mo is not None:
            return self.mo.pgettext(context, text)
        return self.po.get((context, text), text)


def clean_label(text):
    return (text or "").replace("~", "").replace("_", "").strip()


def _props(obj):
    return {p.get("name").replace("_", "-"): p for p in obj.findall("property")}


def _text(prop, translate):
    if prop is None:
        return ""
    if prop.get("translatable") == "yes":
        return clean_label(translate(prop.get("context", ""), prop.text or ""))
    return clean_label(prop.text)


def parse_notebookbar(path, translate=lambda _c, t: t):
    """Pages of the Tabbed notebookbar, in order: [{label, id, contexts, groups, commands, menu_commands, launchers}].

    groups: [{id, caption, commands}] in document order (captioned grids only); commands: set of visible ribbon items
    on the page; menu_commands: commands of the page's tab menu; launchers: [{id, command, group}].
    """
    root = ET.parse(path).getroot()
    menus = {o.get("id"): o for o in root.findall("object") if o.get("class") == "GtkMenu"}
    captions = {}
    for label in root.iter("object"):
        if label.get("class") != "GtkLabel":
            continue
        for relation in label.iter("relation"):
            if relation.get("type") == "label-for":
                captions[relation.get("target")] = _text(_props(label).get("label"), translate)
    for grid in root.iter("object"):  # groups whose caption has no relation (Sheets): the label of the bottom row
        if grid.get("class") != "GtkGrid" or grid.get("id") in captions or not grid.get("id"):
            continue
        bottom = None
        for child in grid.findall("child"):
            obj, packing = child.find("object"), child.find("packing")
            if obj is None or packing is None:
                continue
            top = next((int(p.text) for p in packing.findall("property") if p.get("name") == "top-attach"), 0)
            labels = [obj] if obj.get("class") == "GtkLabel" else obj.findall("child/object[@class='GtkLabel']")
            for label in labels:
                prop = _props(label).get("label")
                if prop is not None and prop.get("translatable") == "yes" and top > 0 and (bottom is None or top > bottom[0]):
                    bottom = (top, _text(prop, translate))
        if bottom:
            captions[grid.get("id")] = bottom[1]
    control = next(o for o in root.iter("object") if o.get("class") == "sfxlo-NotebookbarTabControl")
    pages, pending = [], None
    for child in control.findall("child"):
        obj = child.find("object")
        if obj is None:
            continue
        if child.get("type") != "tab":
            pending = obj
            continue
        if pending is None:
            continue
        contexts = [c.get("name").replace("context-", "") for c in obj.findall("style/class") + pending.findall("style/class")
                    if c.get("name", "").startswith("context-")]
        page = {"label": _text(_props(obj).get("label"), translate), "id": obj.get("id"), "contexts": contexts,
                "groups": [], "commands": set(), "menu_commands": set(), "launchers": []}
        _walk_page(pending, page, menus, captions, None, False)
        pages.append(page)
        pending = None
    return pages


def _menu_commands(menu):
    found = set()
    for item in menu.iter("object"):
        action = _props(item).get("action-name")
        if action is not None and action.text:
            found.add(command_name(action.text))
    return found


def _walk_page(obj, page, menus, captions, group, hidden):
    props = _props(obj)
    hidden = hidden or (props.get("visible") is not None and props["visible"].text == "False")
    klass, ident = obj.get("class"), obj.get("id") or ""
    if ident in captions and not hidden:
        group = {"id": ident, "caption": captions[ident], "commands": []}
        page["groups"].append(group)
    if klass in ITEM_CLASSES and not hidden:
        action = props.get("action-name")
        if action is not None and action.text:
            command = command_name(action.text)
            if ident.startswith(LAUNCHER_PREFIX):
                page["launchers"].append({"id": ident, "command": command, "group": group["caption"] if group else None})
            else:
                page["commands"].add(command)
                if group is not None:
                    group["commands"].append(command)
    elif klass == "svtlo-ManagedMenuButton" and not hidden and ":" in ident:
        menu = menus.get(ident.split(":", 1)[1])
        if menu is not None:
            # "btn…" menu buttons are ribbon drop-downs; the others are the tab menu ("≡") of the page
            target = page["commands"] if ident.startswith("btn") else page["menu_commands"]
            target.update(_menu_commands(menu))
    for child in obj.findall("child"):
        for sub in child.findall("object"):
            _walk_page(sub, page, menus, captions, group, hidden)


def page_by_label(pages):
    return {p["label"]: p for p in pages}


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
