# SPDX-License-Identifier: AGPL-3.0-only
"""Contextual ribbon tabs added for 1.0.0, read from their patches: Sheets' pivot table tab
(hst-ribbon-pivot-context.patch) and Writer's header and footer tab (hst-ribbon-header-footer-tab.patch).

Each tab is shown in its context, holds the feasible commands the parity spec lists for the Office tab, has its key
tip, a Vietnamese text for every new string and a sanitizer line for every new unlabelled icon button.
"""
import json
import os
import re
import unittest

from _paths import ROOT

PATCHES = os.path.join(ROOT, "patches", "libreoffice")
SPEC = os.path.join(ROOT, "data", "ribbon", "office-parity.json")
# patch: (ui, po, suppr, tab label id, context, key tip, Office tab, HST tab, vi tab label of the patch; the
# shown label is in sentence case from l10n/vi-overrides.jsonl)
TABS = {
    "hst-ribbon-pivot-context.patch": (
        "sc/uiconfig/scalc/ui/notebookbar.ui", "translations/source/vi/sc/messages.po",
        "solenv/sanitizers/ui/modules/scalc.suppr", "PivotLabel", "Pivot", "JT", "PivotTable Analyze",
        "Phân tích bảng tổng hợp", "Phân tích Bảng tổng ~hợp"),
    "hst-ribbon-header-footer-tab.patch": (
        "sw/uiconfig/swriter/ui/notebookbar.ui", "translations/source/vi/sw/messages.po",
        "solenv/sanitizers/ui/modules/swriter.suppr", "HeaderFooterLabel", "HeaderFooter", "JH", "Header & Footer",
        "Đầu trang & chân trang", "Đầu trang & C~hân trang"),
}


def added(patch, path):
    lines, current = [], None
    with open(os.path.join(PATCHES, patch), encoding="utf-8") as handle:
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
            if node.get("office") == name and node.get("contextual") and "groups" in node:
                yield node
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for value in node:
                yield from walk(value)
    with open(SPEC, encoding="utf-8") as handle:
        return next(walk(json.load(handle)))


class ContextTabsTest(unittest.TestCase):
    def test_tab_is_contextual_and_translated(self):
        for patch, (ui, po, _suppr, label, context, _tip, _office, _hst, vi) in TABS.items():
            with self.subTest(patch=patch):
                new_ui = added(patch, ui)
                self.assertRegex(new_ui, rf'id="{label}"[\s\S]*?<class name="context-{context}"/>')
                new_po = added(patch, po)
                for ctx in re.findall(r'context="(Tabbed\w+\|[^"]+)"', new_ui):
                    self.assertIn(f'msgctxt "{ctx}"', new_po, ctx)
                self.assertIn(f'msgstr "{vi}"', new_po)

    def test_commands_cover_the_spec(self):
        for patch, (ui, _po, _suppr, _label, _context, _tip, office, hst, _vi) in TABS.items():
            with self.subTest(patch=patch):
                actions = set(re.findall(r'name="action-name">\.uno:([^<]+)<', added(patch, ui)))
                tab = spec_tab(office)
                self.assertEqual(tab["hst_tab"], hst)
                wanted = {uno for group in tab["groups"] for command in group["commands"] if command["feasible"]
                          for uno in command["uno"]}
                self.assertLessEqual(wanted, actions)

    def test_key_tip_and_sanitizer_lines(self):
        for patch, (ui, _po, suppr, label, _context, tip, _office, _hst, _vi) in TABS.items():
            with self.subTest(patch=patch):
                self.assertIn(f'{{ "{label}", "{tip}" }}', added(patch, "sfx2/source/notebookbar/HstKeyTipTable.hxx"))
                new_suppr = added(patch, suppr)
                for ident in re.findall(r'<object class="GtkToolButton" id="([^"]+)">', added(patch, ui)):
                    self.assertIn(f"{ui}://GtkToolButton[@id='{ident}'] button-no-label", new_suppr)


if __name__ == "__main__":
    unittest.main()
