# SPDX-License-Identifier: AGPL-3.0-only
"""Offline ribbon parity check (scripts/ribbon/check-office-parity.py): .ui parsing, statuses, launchers, .po reading."""
import importlib.util
import json
import os
import tempfile
import unittest

from _paths import ROOT

_spec = importlib.util.spec_from_file_location("check_office_parity",
                                               os.path.join(ROOT, "scripts", "ribbon", "check-office-parity.py"))
parity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parity)

UI = """<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <object class="GtkMenu" id="Menu Home">
    <child><object class="GtkMenuItem"><property name="action-name">.uno:ChangeCaseToUpper</property></object></child>
  </object>
  <object class="GtkMenu" id="Menu Lang">
    <child><object class="GtkMenuItem"><property name="action-name">org.hst.office.vi:UILanguageVi</property></object></child>
  </object>
  <object class="sfxlo-NotebookbarTabControl" id="tabs">
    <child>
      <object class="GtkBox" id="HomeBox">
        <child>
          <object class="GtkGrid" id="gdFont">
            <child><object class="GtkLabel" id="lbFont">
              <property name="label" translatable="yes" context="Tabbed|labelFont">Font</property>
              <accessibility><relation type="label-for" target="gdFont"/></accessibility>
            </object></child>
            <child><object class="GtkToolButton" id="btnBold"><property name="action-name">.uno:Bold</property></object></child>
            <child><object class="GtkToolButton" id="btnGone"><property name="visible">False</property>
              <property name="action-name">.uno:Shadowed</property></object></child>
            <child><object class="GtkToolButton" id="btnHstLaunchFont">
              <property name="action-name">.uno:FontDialog</property></object></child>
          </object>
        </child>
        <child><object class="svtlo-ManagedMenuButton" id="Home-HomeButton:Menu Home"/></child>
        <child><object class="svtlo-ManagedMenuButton" id="btnLang:Menu Lang"/></child>
      </object>
    </child>
    <child type="tab">
      <object class="GtkLabel" id="HomeTab">
        <property name="label" translatable="yes" context="Tabbed|HomeLabel">~Home</property>
        <style><class name="context-default"/></style>
      </object>
    </child>
    <child>
      <object class="GtkBox" id="InsertBox">
        <child>
          <object class="GtkGrid" id="gdNoRelation">
            <child><object class="GtkToolButton" id="btnStyle">
              <property name="action-name">.uno:StyleApply?Style:string=Good&amp;FamilyName:string=CellStyles</property>
            </object><packing><property name="left-attach">0</property><property name="top-attach">0</property></packing></child>
            <child><object class="GtkLabel" id="lbNoRelation">
              <property name="label" translatable="yes" context="Tabbed|labelStyles">Styles</property>
            </object><packing><property name="left-attach">0</property><property name="top-attach">2</property></packing></child>
          </object>
        </child>
        <child><object class="GtkToolButton" id="btnTable"><property name="action-name">.uno:InsertTable</property></object></child>
        <child><object class="GtkToolButton" id="btnItalic"><property name="action-name">.uno:Italic</property></object></child>
      </object>
    </child>
    <child type="tab">
      <object class="GtkLabel" id="InsertTab"><property name="label">~Insert</property></object>
    </child>
  </object>
</interface>
"""

PO = '''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

#: notebookbar.ui:1
msgctxt "Tabbed|HomeLabel"
msgid "~Home"
msgstr "T~rang đầu"

msgctxt "Tabbed|labelFont"
msgid "Font"
msgstr ""
"Phông "
"chữ"
'''


def command(name, uno, feasible=True):
    return {"office": name, "uno": uno, "feasible": feasible}


SPEC_APP = {"tabs": [
    {"office": "Home", "hst_tab": "Trang đầu", "contextual": False, "groups": [
        {"office": "Font", "hst_group": "Phông chữ", "launcher": {"command": "FontDialog", "feasible": True},
         "commands": [command("Bold", ["Bold"]), command("Italic", ["Italic"]), command("Change Case", ["ChangeCaseToUpper"]),
                      command("Shadow", ["Shadowed"]), command("Dictate", [], feasible=False)]},
        {"office": "Paragraph", "hst_group": "Đoạn văn", "launcher": {"command": "ParagraphDialog", "feasible": True},
         "commands": [command("UI language", ["org.hst.office.vi:UILanguageVi"])]}]}]}


class ParityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ui = os.path.join(self.tmp.name, "notebookbar.ui")
        self.po = os.path.join(self.tmp.name, "messages.po")
        with open(self.ui, "w", encoding="utf-8") as handle:
            handle.write(UI)
        with open(self.po, "w", encoding="utf-8") as handle:
            handle.write(PO)
        self.pages = parity.parse_notebookbar(self.ui, parity.Translator(po_path=self.po))

    def tearDown(self):
        self.tmp.cleanup()

    def test_po_reader_joins_continued_lines(self):
        entries = parity.read_po(self.po)
        self.assertEqual(entries[("Tabbed|labelFont", "Font")], "Phông chữ")
        self.assertEqual(entries[("Tabbed|HomeLabel", "~Home")], "T~rang đầu")

    def test_pages_groups_and_menus(self):
        home, insert = self.pages
        self.assertEqual(home["label"], "Trang đầu")
        self.assertEqual(home["contexts"], ["default"])
        self.assertEqual(insert["label"], "Insert")  # untranslated label stays, without the mnemonic
        self.assertEqual([g["caption"] for g in home["groups"]], ["Phông chữ"])
        self.assertEqual(home["groups"][0]["commands"], ["Bold"])
        self.assertNotIn("Shadowed", home["commands"])  # hidden items are not on the ribbon
        self.assertIn("ChangeCaseToUpper", home["menu_commands"])  # tab menu (≡)
        self.assertIn("org.hst.office.vi:UILanguageVi", home["commands"])  # "btn…" drop-down is on the ribbon
        self.assertEqual(home["launchers"], [{"id": "btnHstLaunchFont", "command": "FontDialog", "group": "Phông chữ"}])
        self.assertNotIn("FontDialog", home["commands"])

    def test_caption_without_relation_and_command_arguments(self):
        insert = self.pages[1]
        self.assertEqual([g["caption"] for g in insert["groups"]], ["Styles"])  # bottom-row label of the grid
        self.assertIn("StyleApply", insert["commands"])  # arguments are not part of the command name

    def test_statuses_and_scores(self):
        result = parity.app_report(SPEC_APP, self.pages)
        status = {r["command"]: r["status"] for r in result["rows"]}
        self.assertEqual(status, {"Bold": "present", "Italic": "elsewhere", "Change Case": "elsewhere", "Shadow": "missing",
                                  "Dictate": "infeasible", "UI language": "present"})
        where = {r["command"]: r["where"] for r in result["rows"]}
        self.assertEqual(where["Change Case"], ["≡ Trang đầu"])
        self.assertEqual(result["counts"], {"present": 2, "elsewhere": 2, "missing": 1, "infeasible": 1})
        self.assertEqual(result["d1"], round(2 / 5, 4))
        self.assertEqual(result["raw_coverage"], round(2 / 6, 4))
        self.assertEqual([l["present"] for l in result["launchers"]], [True, False])
        self.assertEqual(result["d4"], 0.5)

    def test_missing_target_tab_makes_nothing_present(self):
        spec = json.loads(json.dumps(SPEC_APP))
        spec["tabs"][0]["hst_tab"] = "Trợ giúp"
        result = parity.app_report(spec, self.pages)
        self.assertEqual(result["counts"]["present"], 0)
        self.assertEqual(result["d4"], 0.0)

    def test_repository_spec_is_consistent(self):
        spec = parity.load_spec()
        for app, data in spec["apps"].items():
            for tab in data["tabs"]:
                for group in tab["groups"]:
                    for entry in group["commands"]:
                        if entry["feasible"]:
                            self.assertTrue(entry["uno"], f"{app} {tab['office']} {entry['office']} has no UNO command")
                        else:
                            self.assertTrue(entry["reason"], f"{app} {tab['office']} {entry['office']} needs a reason")
                    launcher = group.get("launcher")
                    if launcher and launcher["feasible"]:
                        self.assertTrue(launcher["command"])
        clipboard = [g for t in spec["apps"]["writer"]["tabs"] for g in t["groups"] if g["office"] == "Clipboard"]
        self.assertFalse(clipboard[0]["launcher"]["feasible"])  # owner: no Clipboard launcher


if __name__ == "__main__":
    unittest.main()
