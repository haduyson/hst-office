#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build the KeyTip parity table: the familiar suite's letter for every HST ribbon command that has a counterpart.

Usage: python3 scripts/ribbon/build-keytips-parity.py --tree PATCHED_TREE [--out data/ribbon/keytips-office-parity.json]

Joins data/ribbon/office-keytips-reference.json (KeyTips captured from the installed suite), data/ribbon/office-parity.json
(which HST UNO commands stand for which of its commands, per tab) and the patched notebookbar.ui files (which commands
each HST tab shows). Per app, HST tab and command the table keeps the letter of the suite's control on the matching tab.
When a command stands for several controls (Find & Replace for Find FD and Replace R) and the general table already
gives it one of their letters, that letter is kept. The table is the source of HstKeyTipOffice.hxx
(scripts/patches/generate-keytips-office-parity.py) and of the CI check (scripts/check-keytips-parity.py).
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from keytips_model import MODULES, ROOT, TABLE_HEADER, parse_table, tab_pages  # noqa: E402

REFERENCE = os.path.join(ROOT, "data", "ribbon", "office-keytips-reference.json")
SPEC = os.path.join(ROOT, "data", "ribbon", "office-parity.json")
OUT = os.path.join(ROOT, "data", "ribbon", "keytips-office-parity.json")
# HST app -> reference app; HST Draw (the PDF editor) has no counterpart, its shared tabs follow the presentation app
REFERENCE_APP = {"writer": "word", "calc": "excel", "impress": "powerpoint", "draw": "powerpoint"}
SPEC_APP = {"writer": "writer", "calc": "calc", "impress": "impress", "draw": "impress"}
# office tab name -> HST tab label id
TAB_IDS = {"Home": "HomeLabel", "Insert": "InsertLabel", "Design": "DesignLabel", "Layout": "LayoutLabel",
           "Page Layout": "LayoutLabel", "References": "ReferencesLabel", "Mailings": "MailingsLabel",
           "Formulas": "FunctionsLabel1", "Data": "DataLabel", "Transitions": "TransitionsLabel",
           "Animations": "AnimationsLabel", "Slide Show": "SlideShowLabel", "Review": "ReviewLabel", "View": "ViewLabel",
           "Help": "HelpLabel", "Table Design": "TableDesignLabel", "Table Layout": "TableLabel",
           "Picture Format": "ImageLabel", "Chart Design": "ChartDesignLabel", "Chart Format": "ChartFormatLabel"}
# HST Draw tabs that follow the presentation app's tab of the same id (its own tabs Arrange, Page, PDF do not)
DRAW_TABS = {"HomeLabel", "InsertLabel", "ReviewLabel", "ViewLabel", "HelpLabel", "TableDesignLabel", "TableLabel",
             "ImageLabel", "ChartDesignLabel", "ChartFormatLabel"}
# spec names that the suite's controls call differently: spec name -> control name
ALIASES = {"Show/Hide": "Show All", "Online Videos": "Online Videos...", "Footnote": "Insert Footnote",
           "Chart types (Column/Line/Pie/Bar/Area/Scatter...)": "Insert Column or Bar Chart"}
# controls the spec does not list (group launchers): (reference app, tab) -> {control name: [HST commands]}
EXTRA = {("excel", "Page Layout"): {"Page Setup": ["PageFormatDialog"]}}


def norm(text):
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text.split("\n")[0]).lower()
    text = text.replace("…", "").replace("...", "").replace("&", "and")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def letters_of(controls, name):
    """Letters of the controls on one tab whose name or tooltip is `name` (exact, normalised)."""
    wanted = norm(ALIASES.get(name, name))
    by_name = [tip for control, tip, _tip in controls if norm(control) == wanted]
    return by_name or [tip for _control, tip, tooltip in controls if norm(tooltip) == wanted]


def candidates(reference, spec_app, app):
    """{(tab id, uno): [(letter, control name), ...]} from the spec commands that the reference shows."""
    found = {}
    for tab in spec_app["tabs"]:
        tab_id = TAB_IDS.get(tab["office"])
        controls = reference["controls"].get(tab["office"])
        if not tab_id or controls is None or (app == "draw" and tab_id not in DRAW_TABS):
            continue
        for group in tab["groups"]:
            for command in group["commands"]:
                for letter in letters_of(controls, command["office"]):
                    for uno in command.get("uno") or []:
                        found.setdefault((tab_id, uno), []).append((letter, command["office"]))
        for name, unos in EXTRA.get((REFERENCE_APP[app], tab["office"]), {}).items():
            for letter in letters_of(controls, name):
                for uno in unos:
                    found.setdefault((tab_id, uno), []).append((letter, name))
    return found


def pick(tab, items, found, general):
    """{ident: [letter, control]} of one tab. One control's letter goes to one command only (a split button of the
    suite can stand for several HST commands): first to a command whose general letter it already is, then in ribbon
    order; a letter that clashes with one already given (prefix) is skipped. The menu buttons of the tab ("Lề ▾") keep
    the letters the general table gives them by widget id: those were chosen from the suite's tabs."""
    given = {}
    used = [general[i] for i in items if i.startswith("btn") and general.get(i)]

    def take(ident, letter, control):
        if not any(letter.startswith(u) or u.startswith(letter) for u in used):
            given[ident] = [letter, control]
            used.append(letter)

    for ident in items:
        for letter, control in found.get((tab, ident), []):
            if letter == general.get(ident):
                take(ident, letter, control)
                break
    for ident in items:
        for letter, control in found.get((tab, ident), []):
            if ident in given:
                break
            take(ident, letter, control)
    return {ident: given[ident] for ident in items if ident in given}


def build(tree):
    with open(REFERENCE, encoding="utf-8") as handle:
        reference = json.load(handle)
    with open(SPEC, encoding="utf-8") as handle:
        spec = json.load(handle)
    with open(os.path.join(tree, TABLE_HEADER), encoding="utf-8") as handle:
        header = handle.read()
    general, tab_keys = parse_table(header, "COMMAND_KEYS"), parse_table(header, "TAB_KEYS")
    table = {"version": 1,
             "about": "Generated by scripts/ribbon/build-keytips-parity.py. tabs: the suite's tab letters by HST tab "
                      "label id; commands: module -> HST tab id -> command or widget id -> [letter, the suite's control]. "
                      "Source of HstKeyTipOffice.hxx; checked by scripts/check-keytips-parity.py.",
             "reference": "data/ribbon/office-keytips-reference.json", "tabs": {}, "commands": {}}
    for app, (module, ui) in MODULES.items():
        ref = reference["apps"][REFERENCE_APP[app]]
        found = candidates(ref, spec["apps"][SPEC_APP[app]], app)
        pages = tab_pages(os.path.join(tree, ui))
        office_tabs = {TAB_IDS[name]: tip for name, tip in ref["tabs"].items() if name in TAB_IDS}
        table["tabs"][app] = {tab: office_tabs[tab] for tab, _items in pages
                              if tab in office_tabs and (app != "draw" or tab in DRAW_TABS)}
        table["tabs"][app]["FileLabel"] = "F"
        for extra in ("ExtensionLabel",):  # the suite's Add-ins tab is X; HST merges Developer and Add-ins there
            if extra in tab_keys and any(tab == extra for tab, _items in pages):
                table["tabs"][app][extra] = tab_keys[extra]
        table["commands"][module] = {tab: picked for tab, items in pages
                                     if (picked := pick(tab, list(dict.fromkeys(items)), found, general))}
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tree", required=True, help="patched source tree (fresh-apply of the series)")
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args(argv)
    table = build(args.tree)
    text = json.dumps(table, ensure_ascii=False, indent=1, sort_keys=False)
    text = re.sub(r'\[\n\s+("[^"\n]*"),\n\s+("[^"\n]*")\n\s+\]', r"[\1, \2]", text)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    count = sum(len(c) for tabs in table["commands"].values() for c in tabs.values())
    print(f"wrote {os.path.relpath(args.out, ROOT)}: {count} commands")
    return 0


if __name__ == "__main__":
    sys.exit(main())
