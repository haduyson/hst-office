#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Every ribbon group launcher (↘) opens its own group's dialog on the group's tab (owner rule, 2026-11-14).

For each row of data/ribbon/launcher-targets.json: the installed notebookbar.ui gives the launcher exactly that
command, and dispatching it (with the document context the contextual tab needs) opens that dialog on that tab,
also after the dialog was last left on another tab (a tab dialog reopens on its last tab unless told otherwise).
Rows without a dialog (the Styles pane) are checked in the .ui only.

Usage: check-ribbon-launchers.py [--instdir DIR] [--work DIR] [app ...]   (apps: writer calc impress draw)
Needs a built instdir with the vi language pack. Runs on a private Xvfb with a fresh profile.
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hst_dialog_uitest import Checks, DialogHarness, click, select_tab, state  # noqa: E402
from dialogs_writer_picture_cases import new_picture  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABLE = os.path.join(ROOT, "data/ribbon/launcher-targets.json")
MODULES = {"writer": "swriter", "calc": "scalc", "impress": "simpress", "draw": "sdraw"}


def ui_commands(instdir, app):
    """{launcher id: action-name} of the installed Tabbed notebookbar of an app."""
    path = os.path.join(instdir, "share/config/soffice.cfg/modules", MODULES[app], "ui/notebookbar.ui")
    found = {}
    for obj in ET.parse(path).getroot().iter("object"):
        ident = obj.get("id") or ""
        if ident.startswith("btnHstLaunch"):
            found[ident] = next((p.text for p in obj.findall("property") if p.get("name") == "action-name"), None)
    return found


def add_shape(doc, text=""):
    shape = doc.createInstance("com.sun.star.drawing.RectangleShape")
    page = doc.getDrawPage() if hasattr(doc, "getDrawPage") else doc.getDrawPages().getByIndex(0)
    page.add(shape)
    from com.sun.star.awt import Point, Size
    shape.setPosition(Point(2000, 2000))
    shape.setSize(Size(6000, 3000))
    if text:
        shape.setString(text)
    doc.getCurrentController().select(shape)
    return shape


def open_context(h, app, context):
    """A new document of the app with what the row's tab needs selected."""
    doc = h.new_document(MODULES[app])
    if context == "table":
        table = doc.createInstance("com.sun.star.text.TextTable")
        table.initialize(2, 2)
        doc.getText().insertTextContent(doc.getText().getEnd(), table, False)
        doc.getCurrentController().select(table.getCellByName("A1").createTextCursor())
    elif context == "picture":
        new_picture(h, doc)
    elif context == "shape":
        add_shape(doc, "Hình" if app in ("impress", "draw") else "")
    elif app == "writer":
        doc.getText().setString("Đoạn văn mẫu.")
    elif app == "calc":
        doc.getCurrentController().select(doc.Sheets.getByIndex(0).getCellRangeByName("A1"))
    h.wait_idle()
    return doc


def current_tab(dialog):
    if "tabcontrol" not in dialog.getChildren():
        return None
    return state(dialog.getChild("tabcontrol")).get("CurrPageTitle")


def leave_on_other_tab(h, row):
    """Open the dialog the plain way (no Page) and leave it on another tab, so the launcher must pick the tab."""
    plain = row["command"].split("?", 1)[0]
    dialog = h.open_dialog(plain, row["dialog"])
    tabs = dialog.getChild("tabcontrol")
    count = int(state(tabs)["PageCount"])
    for pos in range(count):
        select_tab(dialog, pos)
        if state(tabs).get("CurrPageTitle") != row["tab"]:
            break
    click(dialog, row.get("cancel", "cancel"))
    h.wait_idle()


def check_row(h, c, row):
    what = f"{row['app']} {row['ribbon_tab']} > {row['group']}"
    doc = open_context(h, row["app"], row.get("context"))
    try:
        if row.get("tab"):
            leave_on_other_tab(h, row)
        dialog = h.open_dialog(row["command"], row["dialog"])
        c.equal(f"{what}: opens {row['dialog']}", state(dialog).get("ID"), row["dialog"])
        if row.get("tab"):
            c.equal(f"{what}: on tab", current_tab(dialog), row["tab"])
        click(dialog, row.get("cancel", "cancel"))
        h.wait_idle()
    except Exception as error:  # noqa: BLE001 - one broken launcher must not hide the others
        c.error(what, error)
    finally:
        h.close_document(doc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--work", default=os.path.join(ROOT, "tests/output/ribbon-launchers"))
    parser.add_argument("apps", nargs="*", choices=[[], *MODULES], default=[])
    args = parser.parse_args()
    apps = args.apps or list(MODULES)
    with open(TABLE, encoding="utf-8") as handle:
        rows = [row for row in json.load(handle)["launchers"] if row["app"] in apps]
    checks = Checks()
    for app in apps:
        found = ui_commands(args.instdir, app)
        listed = {row["id"] for row in rows if row["app"] == app}
        checks.equal(f"{app}: every launcher has a row", sorted(set(found) - listed), [])
        for row in (r for r in rows if r["app"] == app):
            checks.equal(f"{app} {row['id']}: command", found.get(row["id"]), row["command"])
    harness = DialogHarness(args.instdir, args.work, 22983, ":83")
    try:
        for row in rows:
            if row.get("dialog"):
                check_row(harness, checks, row)
    finally:
        harness.close()
    return checks.finish()


if __name__ == "__main__":
    sys.exit(main())
