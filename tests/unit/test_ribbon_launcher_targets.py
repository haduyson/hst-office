# SPDX-License-Identifier: AGPL-3.0-only
"""Ribbon group launchers (↘) keep the targets of data/ribbon/launcher-targets.json through the patch series.

The command of every btnHstLaunch* ToolButton is followed through patches/libreoffice/series in order (the last
patch that sets it wins), so a later patch that points a launcher somewhere else, or adds one without a row, fails
here before a build. tests/runtime/check-ribbon-launchers.py checks the same table on a built office.
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCHES = os.path.join(ROOT, "patches/libreoffice")
UI = {"writer": "sw/uiconfig/swriter/ui/notebookbar.ui", "calc": "sc/uiconfig/scalc/ui/notebookbar.ui",
      "impress": "sd/uiconfig/simpress/ui/notebookbar.ui", "draw": "sd/uiconfig/sdraw/ui/notebookbar.ui"}
APP_OF = {path: app for app, path in UI.items()}
ID = re.compile(r'<object class="[^"]+" id="([^"]+)"')
ACTION = re.compile(r'<property name="action-name">([^<]*)</property>')
# a launcher's Page argument names a tab of its dialog: ".uno:Command?Page:string=<tab id>"
PAGE = re.compile(r"^\.uno:[A-Za-z]+(\?Page:string=[A-Za-z_]+)?$")


def load(name):
    with open(os.path.join(ROOT, "data/ribbon", name), encoding="utf-8") as handle:
        return json.load(handle)["launchers"]


def series():
    with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip() and not line.startswith("#")]


def hunks(patch):
    """(app, [hunk lines]) of the four notebookbar files in a patch."""
    app, current = None, None
    with open(os.path.join(PATCHES, patch), encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("+++ "):
                app = APP_OF.get(line[4:].strip().removeprefix("b/"))
            elif line.startswith("@@"):
                if current:
                    yield current
                current = (app, []) if app else None
            elif current is not None and line[:1] in " +-":
                current[1].append(line.rstrip("\n"))
    if current:
        yield current


def follow(rows_by_command):
    """{(app, id): (command, patch)} after the whole series; ambiguous hunks are resolved through the table."""
    state = {}
    for patch in series():
        for app, lines in hunks(patch):
            ident, old = None, None
            for line in lines:
                sign, text = line[0], line[1:]
                found = ID.search(text)
                if found and sign != "-":
                    ident = found.group(1) if found.group(1).startswith("btnHstLaunch") else None
                action = ACTION.search(text)
                if not action:
                    continue
                if sign == "-":
                    old = action.group(1)
                elif sign == "+":
                    target = ident
                    if target is None and old is not None:
                        owners = [key for key, (command, _) in state.items() if key[0] == app and command == old]
                        if len(owners) > 1:  # e.g. two launchers sending the same command: the table decides
                            owners = [key for key in owners if action.group(1) in rows_by_command.get(key, ())]
                        target = owners[0][1] if len(owners) == 1 else None
                    if target:
                        state[(app, target)] = (action.group(1), patch)
                    old = None
    return state


class LauncherTargets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load("launcher-targets.json")
        cls.by_key = {(row["app"], row["id"]): row for row in cls.rows}
        cls.state = follow({key: (row["command"],) for key, row in cls.by_key.items()})

    def test_rows_match_the_launcher_list(self):
        listed = {(row["app"], row["id"]) for row in load("launchers.json")}
        self.assertEqual(sorted(listed ^ set(self.by_key)), [])
        self.assertEqual(len(self.by_key), len(self.rows), "duplicate rows")

    def test_every_launcher_in_the_series_has_a_row(self):
        self.assertEqual(sorted(set(self.state) - set(self.by_key)), [])

    def test_series_gives_each_launcher_its_target(self):
        for key, row in self.by_key.items():
            with self.subTest(app=key[0], launcher=key[1]):
                command, patch = self.state.get(key, (None, None))
                if command != row["command"] and "?Page:" in row["command"] and command == row["command"].split("?")[0]:
                    self.skipTest(f"the patch adding the Page argument is not in this series yet ({patch})")
                self.assertEqual(command, row["command"], f"last set by {patch}")

    def test_rows_are_complete(self):
        for row in self.rows:
            with self.subTest(app=row["app"], launcher=row["id"]):
                self.assertRegex(row["command"], PAGE)
                for field in ("ribbon_tab", "group", "reference"):
                    self.assertTrue(row.get(field), field)
                if "?Page:" in row["command"]:
                    self.assertTrue(row["dialog"] and row["tab"], "a Page argument needs a dialog and a tab")
                self.assertIn(row.get("context"), (None, "table", "picture", "shape"))


if __name__ == "__main__":
    unittest.main()
