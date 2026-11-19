# SPDX-License-Identifier: AGPL-3.0-only
"""Trợ lý AI "Hỏi cách dùng": the ribbon command map read from the notebookbar.ui files.

Offline: the parser rules on a small .ui (tabs, contextual tabs, captions with a launcher, the HST ribbon label, a
placeholder label, command labels, dropdown menus, hidden items) and the system text built from the map.

With HST_LO_SRC set to a patched tree whose Vietnamese .po files are merged (scripts/l10n/merge-vi.py --apply and
apply-overrides.py), the four real ribbons are read the way the office reads them (the module catalogue for the .ui
texts, the officecfg catalogue for command labels): every app has a map with the Vietnamese tab names, and when the
v3 ribbon data is present (data/ribbon/ribbon-v3.json, or HST_RIBBON_DATA) every tab, group caption and command of
the design is in the map under the same tab and group.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from pathlib import Path

import _paths  # noqa: F401


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.lang", "com.sun.star.frame",
              "com.sun.star.awt"):
    sys.modules.setdefault(_name, _StubModule(_name))

from hst_office import ai_ribbon_map as ribbon_map, ai_ribbon_map_uno  # noqa: E402
from hst_office.ai_texts import HELP, help_system  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "l10n"))
from catalog_paths import vi_po_dir  # noqa: E402

UI = """<?xml version="1.0" encoding="UTF-8"?>
<interface domain="sw">
  <object class="GtkMenu" id="Menu Effects">
    <child><object class="GtkMenuItem" id="m1"><property name="action-name">.uno:Shadowed</property></object></child>
    <child><object class="GtkMenuItem" id="m2"><property name="label" translatable="yes" context="T|outline">Outline</property></object></child>
    <child><object class="GtkSeparatorMenuItem" id="m3"/></child>
    <child><object class="GtkMenuItem" id="m4"><property name="visible">False</property><property name="label">Hidden</property></object></child>
  </object>
  <object class="sfxlo-NotebookbarTabControl" id="tabs">
    <child><object class="GtkBox" id="filepage"><child><object class="GtkGrid" id="gdFile">
      <child><object class="GtkLabel" id="lbFile"><property name="label">File group</property></object></child>
      <child><object class="sfxlo-NotebookbarToolBox" id="bxSave"><child><object class="GtkToolButton" id="s"><property name="action-name">.uno:Save</property></object></child></object></child>
    </object></child></object></child>
    <child type="tab"><object class="GtkLabel" id="FileLabel"><property name="label" translatable="yes" context="T|File">~File</property></object></child>
    <child><object class="GtkBox" id="homepage">
      <child><object class="GtkGrid" id="gdFont">
        <child><object class="sfxlo-NotebookbarToolBox" id="bxBold"><child><object class="GtkToolButton" id="b"><property name="action-name">.uno:Bold</property></object></child></object></child>
        <child><object class="sfxlo-NotebookbarToolBox" id="bxFind"><child><object class="GtkToolButton" id="f">
          <property name="action-name">vnd.sun.star.findbar:FocusToFindbar</property>
          <property name="hst-ribbon-label" translatable="yes" context="T|hstUxLabel">Find</property></object></child></object></child>
        <child><object class="sfxlo-NotebookbarToolBox" id="bxPlace"><child><object class="GtkToolButton" id="p">
          <property name="label">InsertAnnotation</property><property name="action-name">.uno:InsertAnnotation</property></object></child></object></child>
        <child><object class="sfxlo-NotebookbarToolBox" id="bxHidden"><child><object class="GtkToolButton" id="h">
          <property name="visible">False</property><property name="action-name">.uno:Italic</property></object></child></object></child>
        <child><object class="svtlo-ManagedMenuButton" id="btnEffects:Menu Effects">
          <property name="tooltip-text" translatable="yes" context="T|hstUxLabel">Text Effects</property></object></child>
        <child><object class="sfxlo-NotebookbarToolBox" id="bxAi"><child><object class="GtkToolButton" id="ai">
          <property name="label">Hỏi cách dùng</property><property name="action-name">org.hst.office.ai:Help</property></object></child></object></child>
        <child><object class="GtkBox" id="capbox">
          <child><object class="GtkLabel" id="lbFont"><property name="label" translatable="yes" context="T|font">Font</property></object></child>
          <child><object class="sfxlo-NotebookbarToolBox" id="bxLaunch"><child><object class="GtkToolButton" id="l"><property name="action-name">.uno:FontDialog</property></object></child></object></child>
        </object></child>
      </object></child>
      <child><object class="GtkGrid" id="gdNoCaption">
        <child><object class="sfxlo-NotebookbarToolBox" id="bxUnknown"><child><object class="GtkToolButton" id="u"><property name="action-name">.uno:HstUnknown</property></object></child></object></child>
        <child><object class="GtkLabel" id="lbEmpty"/></child>
      </object></child>
    </object></child>
    <child type="tab"><object class="GtkLabel" id="HomeLabel"><property name="label" translatable="yes" context="T|Home">~Home</property>
      <style><class name="context-default"/><class name="context-any"/></style></object></child>
    <child><object class="GtkBox" id="tablepage"><child><object class="GtkGrid" id="gdRows">
      <child><object class="GtkLabel" id="lbRows"><property name="label" translatable="yes" context="T|rows">Rows</property></object></child>
      <child><object class="sfxlo-NotebookbarToolBox" id="bxRow"><child><object class="GtkToolButton" id="r"><property name="action-name">.uno:InsertRowsAfter</property></object></child></object></child>
    </object></child></object></child>
    <child type="tab"><object class="GtkLabel" id="TableLabel"><property name="label" translatable="yes" context="T|Table">Table _Layout</property>
      <style><class name="context-Table"/></style></object></child>
  </object>
</interface>
"""
VI = {("T|Home", "~Home"): "Trang đầu", ("T|Table", "Table _Layout"): "Bố trí bảng", ("T|font", "Font"): "Phông chữ",
      ("T|rows", "Rows"): "Hàng và cột", ("T|hstUxLabel", "Find"): "Tìm", ("T|outline", "Outline"): "Viền chữ",
      ("T|hstUxLabel", "Text Effects"): "Hiệu ứng chữ"}
LABELS = {".uno:Bold": "Đậm", ".uno:InsertAnnotation": "~Chú thích", ".uno:Shadowed": "Đổ bóng",
          ".uno:InsertRowsAfter": "Chèn hàng bên dưới", ".uno:Italic": "Nghiêng", ".uno:FontDialog": "Ký tự..."}


def translate(context, msgid):
    return VI.get((context, msgid), msgid)


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.tabs = ribbon_map.parse_ribbon(UI.encode("utf-8"), translate, lambda command: LABELS.get(command, ""))

    def test_tabs_contextual_and_file_left_out(self):
        self.assertEqual([(name, contextual) for name, contextual, _ in self.tabs],
                         [("Trang đầu", False), ("Bố trí bảng", True)])

    def test_group_commands_and_labels(self):
        groups = dict(self.tabs[0][2])
        self.assertEqual(list(groups), ["Phông chữ", ""])
        font = groups["Phông chữ"]
        self.assertEqual([c.key for c in font], ["Bold", "vnd.sun.star.findbar:FocusToFindbar", "InsertAnnotation",
                                                 "btnEffects", "org.hst.office.ai:Help"])
        self.assertEqual([c.text for c in font], ["Đậm", "Tìm", "Chú thích", "Hiệu ứng chữ ▾ (Đổ bóng, Viền chữ)",
                                                  "Hỏi cách dùng"])
        # the launcher in the caption box is not a command of the group; a label-less command keeps its name
        self.assertEqual([(c.key, c.text) for c in groups[""]], [("HstUnknown", "HstUnknown")])

    def test_format_map(self):
        text = ribbon_map.format_map("HST Writer", self.tabs)
        lines = text.splitlines()
        self.assertIn("HST Writer", lines[0])
        self.assertEqual(lines[1], "Trang đầu › Phông chữ: Đậm; Tìm; Chú thích; Hiệu ứng chữ ▾ (Đổ bóng, Viền chữ); "
                                   "Hỏi cách dùng")
        self.assertEqual(lines[2], "Trang đầu: HstUnknown")
        self.assertEqual(lines[3], "Bố trí bảng [ngữ cảnh] › Hàng và cột: Chèn hàng bên dưới")

    def test_long_menus_are_cut(self):
        entries = ["Mục %d" % i for i in range(20)]
        text = ribbon_map._with_menu("Hình dạng", entries)
        self.assertTrue(text.endswith(", …)"))
        self.assertEqual(text.count(","), ribbon_map.MAX_MENU_ITEMS)

    def test_clean(self):
        self.assertEqual(ribbon_map.clean(" ~Chèn  _bảng... "), "Chèn bảng")


class HelpPromptTests(unittest.TestCase):
    def test_map_goes_into_the_system_text(self):
        system = help_system("Bản đồ ribbon của HST Writer\nTrang đầu › Phông chữ: Đậm")
        self.assertTrue(system.startswith(HELP))
        self.assertIn("Thẻ › Nhóm › Lệnh", system)
        self.assertTrue(system.endswith("Trang đầu › Phông chữ: Đậm"))

    def test_without_map_the_task_stays(self):
        self.assertEqual(help_system(""), HELP)

    @unittest.skipUnless(shutil.which("msgfmt"), "GNU gettext required")
    def test_installed_catalog_and_legacy_profile(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(ai_ribbon_map_uno, "_system_path", return_value=tmp):
            root = Path(tmp) / "program/resource/en_US/LC_MESSAGES"
            root.mkdir(parents=True)

            def write(domain, label):
                po = ('msgid ""\nmsgstr "Content-Type: text/plain; charset=UTF-8\\n"\n\n'
                      f'msgctxt "tab"\nmsgid "File"\nmsgstr "{label}"\n')
                subprocess.run(["msgfmt", "-", "-o", str(root / (domain + ".mo"))], input=po, text=True, check=True)

            def lookup(domain):
                return ai_ribbon_map_uno.catalogue(None, domain, "en-US").pgettext("tab", "File")

            write("sw", "Legacy")
            self.assertEqual(lookup("sw"), "Legacy")
            self.assertIsNone(ai_ribbon_map_uno.catalogue(None, "hst-sw", "en-US"))
            write("hst-sw", "HST")
            self.assertEqual(lookup("hst-sw"), "HST")
            self.assertEqual(lookup("sw"), "HST")

    def test_every_app_has_a_ribbon(self):
        self.assertEqual(set(ribbon_map.APPS), {"writer", "calc", "impress", "draw"})


# ---- the real ribbons of a patched tree ------------------------------------------------------------------------------

UI_FILES = {"writer": "sw/uiconfig/swriter/ui/notebookbar.ui", "calc": "sc/uiconfig/scalc/ui/notebookbar.ui",
            "impress": "sd/uiconfig/simpress/ui/notebookbar.ui", "draw": "sd/uiconfig/sdraw/ui/notebookbar.ui"}
V3_APPS = {"writer": "writer", "sheets": "calc", "slides": "impress", "draw": "draw"}
COMMAND_FILES = {"writer": "WriterCommands.xcu", "calc": "CalcCommands.xcu", "impress": "DrawImpressCommands.xcu",
                 "draw": "DrawImpressCommands.xcu"}


def _unescape(text):
    return text.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")


def _catalogue(path):
    from po_io import parse_po
    out = {}
    for entry in parse_po(path):
        out[(_unescape(entry["msgctxt"]), _unescape(entry["msgid"]))] = _unescape(entry["msgstr"])
    return out


def _command_labels(tree):
    """{(xcu file, ".uno:X"): label} from the Vietnamese officecfg catalogue, as theUICommandDescription has them."""
    labels = {}
    path = vi_po_dir(tree) / "officecfg/registry/data/org/openoffice/Office/UI.po"
    for (context, msgid), msgstr in _catalogue(path).items():
        parts = context.split("\n")
        if len(parts) < 3 or "..uno:" not in parts[1]:
            continue
        rank = ("Label", "ContextLabel", "PopupLabel", "TooltipLabel")
        if parts[2] in rank:
            key = (parts[0], ".uno:" + parts[1].split("..uno:")[-1])
            current = labels.get(key)
            if current is None or rank.index(parts[2]) < current[0]:
                labels[key] = (rank.index(parts[2]), msgstr or msgid)
    return {key: value[1] for key, value in labels.items()}


@unittest.skipUnless(os.environ.get("HST_LO_SRC"), "HST_LO_SRC (a patched tree with merged Vietnamese .po) not set")
class RealRibbonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = Path(os.environ["HST_LO_SRC"])
        labels = _command_labels(tree)
        cls.maps = {}
        for kind, (module, domain, _module_id, _app) in ribbon_map.APPS.items():
            catalogue = _catalogue(vi_po_dir(tree) / domain / "messages.po")

            def translate(context, msgid, catalogue=catalogue):
                return catalogue.get((context, msgid)) or msgid

            def command_label(command, kind=kind):
                return labels.get((COMMAND_FILES[kind], command)) or labels.get(("GenericCommands.xcu", command), "")
            with open(tree / UI_FILES[kind], "rb") as handle:
                cls.maps[kind] = ribbon_map.parse_ribbon(handle.read(), translate, command_label)
        data = os.environ.get("HST_RIBBON_DATA") or str(ROOT / "data/ribbon/ribbon-v3.json")
        cls.v3 = None
        if os.path.isfile(data):
            with open(data, encoding="utf-8") as handle:
                cls.v3 = json.load(handle)

    def test_four_apps_with_vietnamese_tabs(self):
        for kind, tabs in self.maps.items():
            names = [name for name, _, _ in tabs]
            self.assertGreaterEqual(len(names), 8, kind)
            self.assertEqual(names[0], "Trang đầu", kind)
            self.assertIn("Chèn", names, kind)
            self.assertIn("Xem", names, kind)
            for name, _, groups in tabs:
                self.assertTrue(groups, (kind, name))
                for caption, commands in groups:
                    self.assertTrue(all(c.text.strip() for c in commands), (kind, name, caption))
            text = ribbon_map.format_map(ribbon_map.APPS[kind][3], tabs)
            self.assertLess(len(text), 16000, kind)  # compact: a few thousand tokens at most

    def test_matches_the_v3_ribbon(self):
        if self.v3 is None:
            self.skipTest("no v3 ribbon data in this tree")
        for app in self.v3["apps"]:
            kind = V3_APPS[app["id"]]
            tabs = self.maps[kind]
            names = [name for name, _, _ in tabs]
            design = [tab["name"] for tab in app["tabs"]]
            self.assertEqual([n for n in names if n in design], design, kind)
            for tab in app["tabs"]:
                groups = next(groups for name, _, groups in tabs if name == tab["name"])
                for group in tab["groups"]:
                    keys = [item["k"] for item in group["items"]]
                    found = [commands for caption, commands in groups if caption == group["cap"]]
                    if not found:  # a group whose caption label has no text in the .ui: find it by its commands
                        found = [commands for caption, commands in groups
                                 if not caption and [c.key for c in commands] == keys]
                    self.assertEqual(len(found), 1, (kind, tab["name"], group["cap"]))
                    self.assertEqual([c.key for c in found[0]], keys, (kind, tab["name"], group["cap"]))

    def test_ai_help_is_on_every_ribbon(self):
        for kind, tabs in self.maps.items():
            paths = [(name, caption) for name, _, groups in tabs for caption, commands in groups
                     if any(c.key == "org.hst.office.ai:Help" for c in commands)]
            if self.v3 is not None:
                self.assertEqual(paths, [("Phần mở rộng", "Trợ lý AI")], kind)


if __name__ == "__main__":
    unittest.main()
