# SPDX-License-Identifier: AGPL-3.0-only
"""Sheets' pivot table contextual tab (hst-ribbon-pivot-context.patch), read from the patch itself.

The tab is shown in the "Pivot" context, holds the commands the parity spec lists for Office's PivotTable Analyze,
has a key tip, a Vietnamese caption for every new string and a sanitizer line for every new unlabelled icon button.
"""
import json
import os
import re
import unittest

from _paths import ROOT

PATCH = os.path.join(ROOT, "patches", "libreoffice", "hst-ribbon-pivot-context.patch")
SPEC = os.path.join(ROOT, "data", "ribbon", "office-parity.json")
UI = "sc/uiconfig/scalc/ui/notebookbar.ui"


def added(path):
    lines, current = [], None
    with open(PATCH, encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            match = re.match(r"^\+\+\+ b/(\S+)", line)
            if match:
                current = match.group(1)
            elif current == path and line.startswith("+"):
                lines.append(line[1:])
    return "\n".join(lines)


def spec_tab(name):
    def walk(node):
        if isinstance(node, dict):
            if node.get("office") == name and "groups" in node:
                yield node
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for value in node:
                yield from walk(value)
    with open(SPEC, encoding="utf-8") as handle:
        return next(walk(json.load(handle)))


class PivotContextTest(unittest.TestCase):
    def test_tab_is_contextual_and_translated(self):
        ui = added(UI)
        self.assertRegex(ui, r'id="PivotLabel"[\s\S]*?<class name="context-Pivot"/>')
        po = added("translations/source/vi/sc/messages.po")
        for ctx in re.findall(r'context="(TabbedCalc\|[^"]+)"', ui):
            self.assertIn(f'msgctxt "{ctx}"', po, ctx)
        self.assertIn('msgstr "Phân tích Bảng tổng ~hợp"', po)

    def test_commands_cover_the_spec(self):
        ui = added(UI)
        actions = set(re.findall(r'name="action-name">\.uno:([^<]+)<', ui))
        tab = spec_tab("PivotTable Analyze")
        self.assertEqual(tab["hst_tab"], "Phân tích Bảng tổng hợp")
        wanted = {uno for group in tab["groups"] for command in group["commands"] if command["feasible"]
                  for uno in command["uno"]}
        self.assertLessEqual(wanted, actions)

    def test_key_tip_and_sanitizer_lines(self):
        self.assertIn('{ "PivotLabel", "JT" }', added("sfx2/source/notebookbar/HstKeyTipTable.hxx"))
        ui = added(UI)
        suppr = added("solenv/sanitizers/ui/modules/scalc.suppr")
        for ident in re.findall(r'<object class="GtkToolButton" id="([^"]+)">', ui):
            self.assertIn(f"{UI}://GtkToolButton[@id='{ident}'] button-no-label", suppr)


if __name__ == "__main__":
    unittest.main()
