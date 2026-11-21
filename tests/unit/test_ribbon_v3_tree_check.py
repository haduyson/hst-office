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

    def test_new_uno_command_takes_its_texts_from_the_command(self):
        from lxml import etree as ET
        import ribbon_v3_ui as V
        toolbox = ET.fromstring(
            '<object class="sfxlo-NotebookbarToolBox" id="bxDataTextToColumns"><child>'
            '<object class="GtkToolButton" id="btnDataTextToColumns"><property name="label">TextToColumns</property>'
            '<property name="hst-ribbon-label" translatable="yes">Text to Columns</property>'
            '<property name="hst-ribbon-description" translatable="yes">Split the text</property>'
            '<property name="action-name">.uno:TextToColumns</property></object></child></object>')
        units = V.units_of(toolbox, ET.Element("child"))
        unit = V.new_unit({"k": "FlashFill", "kind": "M", "t": "Tự điền nhanh", "clone": "TextToColumns",
                           "new": True}, units, "Data")
        obj = unit.element.find("object")
        self.assertEqual(obj.get("id"), "btnDataHstFlashFill")
        # the neighbour's label and descriptions go: the command's own label and tooltip show (CalcCommands.xcu)
        self.assertEqual([(p.get("name"), p.text) for p in obj.findall("property")],
                         [("label", "FlashFill"), ("action-name", ".uno:FlashFill")])

    def test_new_group_is_a_skeleton_of_its_tab(self):
        import importlib.util
        from lxml import etree as ET
        spec = importlib.util.spec_from_file_location(
            "generate_ribbon_v3_ui", os.path.join(ROOT, "scripts/patches/generate-ribbon-v3-ui.py"))
        G = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(G)
        commands = TOOL.format(name="Paste", left=0)
        root = ET.fromstring(UI.format(spec="kinds=L", commands=commands).encode("utf-8"))
        template = next(o for o in root.iter("object") if o.get("id") == "gdHomeClipboard")
        caption = next(o for o in template.iter("object") if o.get("id") == "lbClipboard")
        ET.SubElement(ET.SubElement(caption, "accessibility"), "relation", type="label-for", target="gdHomeClipboard")
        ET.SubElement(ET.SubElement(template, "accessibility"), "relation", type="labelled-by", target="lbClipboard")
        used = {o.get("id") for o in root.iter("object")}
        grid = G.new_group([template], {"id": "gdHomeHstAI", "cap": "Trợ lý AI", "new": True, "items": []}, used)
        self.assertIs(grid.getparent().getprevious(), template.getparent())  # after the tab's last group
        self.assertEqual([o.get("class") for o in grid.iter("object")], ["GtkGrid", "GtkLabel", "GtkSeparator"])
        label = grid.find("child/object[@class='GtkLabel']")
        self.assertEqual((label.get("id"), label.find("property[@name='label']").text), ("lbHomeHstAI", "Trợ lý AI"))
        relations = {r.get("type"): r.get("target") for r in grid.iter("relation")}
        self.assertEqual(relations, {"labelled-by": "lbHomeHstAI", "label-for": "gdHomeHstAI"})
        self.assertEqual(grid.find("child/object[@class='GtkSeparator']").get("id"), "sepHomeHstAI")
        self.assertIn("gdHomeHstAI", used)

    def test_merged_box_and_tab_fill_the_page_height(self):
        import importlib.util
        from lxml import etree as ET
        spec = importlib.util.spec_from_file_location(
            "generate_ribbon_v3_ui", os.path.join(ROOT, "scripts/patches/generate-ribbon-v3-ui.py"))
        G = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(G)
        root = ET.fromstring(
            '<object class="sfxlo-PriorityHBox" id="Page"><property name="valign">center</property><child>'
            '<object class="sfxlo-PriorityMergedHBox" id="pmhbPage"><property name="valign">center</property>'
            '</object><packing><property name="fill">True</property></packing></child></object>')
        G.expand_box(root.find("child/object"))
        valign = [o.find("property[@name='valign']").text for o in root.iter("object")]
        self.assertEqual(valign, ["fill", "fill"])
        self.assertEqual(root.find("child/packing/property[@name='expand']").text, "True")

    def test_every_group_gets_a_position_in_its_order(self):
        """A group a feature patch added without a packing position showed first (the builder sorts it before 0)."""
        import importlib.util
        from lxml import etree as ET
        spec = importlib.util.spec_from_file_location(
            "generate_ribbon_v3_ui", os.path.join(ROOT, "scripts/patches/generate-ribbon-v3-ui.py"))
        G = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(G)
        box = ET.fromstring(
            '<object class="sfxlo-PriorityMergedHBox" id="pmhbExport">'
            '<child><object class="GtkGrid" id="gdEdit"/><packing><property name="position">0</property></packing></child>'
            '<child><object class="GtkGrid" id="gdPdf"/><packing><property name="position">1</property></packing></child>'
            '<child><object class="GtkGrid" id="gdSign"/></child>'
            '<child><object class="GtkGrid" id="gdHst"/><packing><property name="fill">True</property></packing></child>'
            '</object>')
        self.assertFalse(G.reorder_tab(box, ["gdEdit", "gdPdf", "gdSign", "gdHst"]))
        positions = [(c.find("object").get("id"), c.find("packing/property[@name='position']").text)
                     for c in box.findall("child")]
        self.assertEqual(positions, [("gdEdit", "0"), ("gdPdf", "1"), ("gdSign", "2"), ("gdHst", "3")])
        self.assertEqual(box.find("child[4]/packing/property[@name='fill']").text, "True")

    def test_a_box_without_positions_stays_without(self):
        import importlib.util
        from lxml import etree as ET
        spec = importlib.util.spec_from_file_location(
            "generate_ribbon_v3_ui", os.path.join(ROOT, "scripts/patches/generate-ribbon-v3-ui.py"))
        G = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(G)
        box = ET.fromstring('<object id="b"><child><object id="a"/></child><child><object id="c"/></child></object>')
        G.number_positions(box)
        self.assertIsNone(box.find("child/packing"))


if __name__ == "__main__":
    unittest.main()
