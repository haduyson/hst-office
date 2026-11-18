# SPDX-License-Identifier: AGPL-3.0-only
"""scripts/patches/ribbon_v3_tree_check.py: a notebookbar.ui against the v3 ribbon data."""
import json
import os
import sys
import tempfile
import unittest

from _paths import ROOT

sys.path.insert(0, os.path.join(ROOT, "scripts/patches"))
import ribbon_v3_tree_check as C  # noqa: E402

UI = """<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <object class="sfxlo-NotebookbarTabControl" id="ContextContainer">
    <child>
      <object class="sfxlo-PriorityHBox" id="Home Tab">
        <child>
          <object class="sfxlo-PriorityMergedHBox" id="pmhbHome">
            <child>
              <object class="GtkGrid" id="gdHomeClipboard">
                <property name="hst-ribbon-layout">{spec}</property>
                {commands}
                <child>
                  <object class="GtkLabel" id="lbClipboard"><property name="label">Clipboard</property></object>
                  <packing><property name="left-attach">0</property><property name="top-attach">3</property></packing>
                </child>
                <child>
                  <object class="GtkSeparator" id="sepClipboard"/>
                  <packing><property name="left-attach">2</property><property name="top-attach">0</property></packing>
                </child>
              </object>
            </child>
          </object>
        </child>
      </object>
    </child>
    <child type="tab">
      <object class="GtkLabel" id="HomeLabel"><property name="label">Home</property></object>
    </child>
  </object>
</interface>
"""
TOOL = """<child>
                  <object class="sfxlo-NotebookbarToolBox" id="bx{name}">
                    <child>
                      <object class="GtkToolButton" id="btn{name}">
                        <property name="action-name">.uno:{name}</property>
                      </object>
                    </child>
                  </object>
                  <packing><property name="left-attach">{left}</property><property name="top-attach">0</property></packing>
                </child>"""
DATA = {"apps": [{"id": "writer", "tabs": [{"id": "HomeLabel", "groups": [
    {"id": "gdHomeClipboard", "cap": "Bảng tạm", "items": [{"k": "Paste", "kind": "L"}, {"k": "Cut", "kind": "S"}]}]}]}]}


class TreeCheckTest(unittest.TestCase):
    def run_check(self, spec, names):
        commands = "\n".join(TOOL.format(name=name, left=i) for i, name in enumerate(names))
        with tempfile.TemporaryDirectory() as tree:
            path = os.path.join(tree, "sw/uiconfig/swriter/ui")
            os.makedirs(path)
            with open(os.path.join(path, "notebookbar.ui"), "w", encoding="utf-8") as handle:
                handle.write(UI.format(spec=spec, commands=commands))
            data = os.path.join(tree, "data.json")
            with open(data, "w", encoding="utf-8") as handle:
                json.dump(DATA, handle)
            return C.check_tree(tree, data)

    def test_matching_group_passes(self):
        problems, totals = self.run_check("kinds=LS", ["Paste", "Cut"])
        self.assertEqual(problems, [])
        self.assertEqual(totals, [1, 1, 2])

    def test_wrong_kinds_and_order_are_reported(self):
        problems, _ = self.run_check("kinds=SL", ["Cut", "Paste"])
        texts = " ".join(problem[3] for problem in problems)
        self.assertIn("kinds SL", texts)
        self.assertIn("commands ['Cut', 'Paste']", texts)

    def test_malformed_layout_is_reported(self):
        problems, _ = self.run_check("kinds=LS;rows=0.7", ["Paste", "Cut"])
        self.assertEqual(len(problems), 1)
        self.assertIn("malformed", problems[0][3])

    def test_parse_spec(self):
        self.assertEqual(C.parse_spec("kinds=LSSS;rows=0.1.|.3/2;nofill"),
                         ("LSSS", [["0", "1", "|", "3"], ["2"]], True))
        self.assertIsNone(C.parse_spec("kinds=LX"))

    def test_new_protocol_command_is_a_labelled_copy_of_its_neighbour(self):
        from lxml import etree as ET
        import ribbon_v3_ui as V
        child = ET.fromstring(
            '<child><object class="sfxlo-NotebookbarToolBox" id="bxSup"><child>'
            '<object class="GtkToolButton" id="btnHomeSuperScript">'
            '<property name="action-name">.uno:SuperScript</property></object></child></object></child>')
        units = V.units_of(child.find("object"), child)
        item = {"k": "org.hst.office.vi:ChemFormula", "kind": "S", "t": "Formula", "clone": "SuperScript",
                "new": True, "icon": "cmd/sc_chemformula.png"}
        unit = V.new_unit(item, units)
        obj = unit.element.find("object")
        props = {p.get("name"): p.text for p in obj.findall("property")}
        self.assertEqual(obj.get("id"), "btnHomeHstChemFormula")
        self.assertEqual(props["action-name"], "org.hst.office.vi:ChemFormula")
        self.assertEqual((props["label"], props["tooltip-text"], props["icon-name"]),
                         ("Formula", "Formula", "cmd/sc_chemformula.png"))
        self.assertEqual(unit.key, item["k"])
        self.assertEqual([u.key for u in V.units_of(unit.toolbox, child)], ["SuperScript"])  # model untouched

    def test_command_fills_its_cell(self):
        from lxml import etree as ET
        import ribbon_v3_ui as V
        obj = ET.fromstring('<object class="svtlo-ManagedMenuButton" id="b"><property name="can-focus">True</property>'
                            '<property name="valign">center</property><property name="halign">start</property>'
                            '<property name="margin-top">6</property></object>')
        V.fill_cell(obj)
        props = [(p.get("name"), p.text) for p in obj.findall("property")]
        self.assertEqual(props, [("can-focus", "True"), ("halign", "fill"), ("valign", "fill")])


if __name__ == "__main__":
    unittest.main()
