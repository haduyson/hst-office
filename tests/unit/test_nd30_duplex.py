# SPDX-License-Identifier: AGPL-3.0-only
""""In hai mặt" rule per document type: Party documents mirror their margins (05-HD/VPTW IV.4.2), ND30 and Thông tư
types keep them (ND30/2020 Phụ lục I, Phần I, Mục I, khoản 3 and 7; ND78/2025 Phụ lục I, Mục 1, I.3 and I.7 are
silent on two-sided printing). Also the application on a fake page style and the stored document property."""
import sys
import types
import unittest

import _paths  # noqa: F401

for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.awt", "com.sun.star.lang"):
    sys.modules.setdefault(_name, types.ModuleType(_name))

from hst_office import nd30, nd30_duplex as dx  # noqa: E402


class RuleTable(unittest.TestCase):
    def test_every_type_has_a_rule_with_a_clause(self):
        for t in nd30.rules()["documentTypes"]:
            rule = dx.rule(t["profile"])
            self.assertIn(t["profile"], dx.RULES, t["id"])
            self.assertTrue(rule["clause"], t["id"])
            self.assertEqual(rule["mirrored"], t["profile"] == "dang", t["id"])

    def test_clauses(self):
        self.assertIn("05-HD/VPTW", dx.RULES["dang"]["clause"])
        self.assertIn("IV.4.2", dx.RULES["dang"]["clause"])
        self.assertIn("Phụ lục I, Phần I, Mục I, khoản 3 và 7", dx.RULES["nd30"]["clause"])
        self.assertIn("78/2025", dx.RULES["qppl"]["clause"])

    def test_party_front_and_back_margins(self):
        on, off = dx.page_plan("dang", True), dx.page_plan("dang", False)
        self.assertEqual(on["PageStyleLayout"], dx.MIRRORED)
        self.assertEqual((on["LeftMargin"], on["RightMargin"]), (3000, 1500))  # front: 30 / 15 mm (IV.4.1)
        self.assertEqual(dx.back_page_margins(on), (15.0, 30.0))  # back: 15 / 30 mm (IV.4.2)
        self.assertEqual(off["PageStyleLayout"], dx.ALL)
        self.assertEqual(dx.back_page_margins(off), (30.0, 15.0))

    def test_state_types_never_mirror(self):
        for profile in ("nd30", "qppl"):
            for duplex in (True, False):
                plan = dx.page_plan(profile, duplex)
                self.assertEqual(plan["PageStyleLayout"], dx.ALL)
                self.assertEqual(dx.back_page_margins(plan), (30.0, 15.0))


class _Style:
    def __init__(self):
        self.LeftMargin, self.RightMargin, self.PageStyleLayout = 3000, 1500, dx.ALL


class _Styles:
    def __init__(self, styles):
        self.styles = styles

    def hasByName(self, name):
        return name in self.styles

    def getByName(self, name):
        return self.styles[name]


class _Props:
    def __init__(self):
        self.values = {}
        info = types.SimpleNamespace(hasPropertyByName=lambda n: n in self.values)
        self.getPropertySetInfo = lambda: info

    def addProperty(self, name, attributes, value):
        self.values[name] = value

    def setPropertyValue(self, name, value):
        self.values[name] = value

    def getPropertyValue(self, name):
        return self.values[name]


class _Doc:
    def __init__(self, styles):
        self.props, self.modified, self.locked = _Props(), False, 0
        families = types.SimpleNamespace(getByName=lambda name: _Styles(styles))
        self.getStyleFamilies = lambda: families
        self.getDocumentProperties = lambda: types.SimpleNamespace(getUserDefinedProperties=lambda: self.props)

    def setModified(self, value):
        self.modified = value

    def getUndoManager(self):
        doc = self
        return types.SimpleNamespace(lock=lambda: setattr(doc, "locked", doc.locked + 1),
                                     unlock=lambda: setattr(doc, "locked", doc.locked - 1))


class Apply(unittest.TestCase):
    def setUp(self):
        self.main, self.annex = _Style(), _Style()
        self.doc = _Doc({"Default": self.main, "HST Default kèm theo": self.annex})
        self.cursor = types.SimpleNamespace(PageStyleName="Default")

    def test_party_toggle_mirrors_both_styles_and_back(self):
        dx.apply(self.doc, self.cursor, False, "dang")
        result = dx.toggle(self.doc, self.cursor)
        self.assertEqual((result["duplex"], result["mirrored"]), (True, True))
        self.assertEqual((self.main.PageStyleLayout, self.annex.PageStyleLayout), (dx.MIRRORED, dx.MIRRORED))
        self.assertEqual((self.main.LeftMargin, self.main.RightMargin), (3000, 1500))  # inner 30, outer 15
        self.assertEqual(dx.read_choice(self.doc), (True, "dang"))
        dx.toggle(self.doc, self.cursor)
        self.assertEqual(self.main.PageStyleLayout, dx.ALL)
        self.assertTrue(self.doc.modified)

    def test_state_document_records_the_choice_only(self):
        result = dx.apply(self.doc, self.cursor, True, "nd30")
        self.assertEqual((result["duplex"], result["mirrored"]), (True, False))
        self.assertEqual(self.main.PageStyleLayout, dx.ALL)
        self.assertEqual(self.doc.props.values[dx.PROPERTY], True)

    def test_copy_blocks_never_change_the_page_layout(self):
        # sao y / sao lục / Party copy blocks are appended to an existing document: its layout stays as it is
        for flow in ("append", "prepend"):
            for duplex in (False, True):
                self.assertFalse(dx.applies_to({"flow": flow}, {"apply_page": True, "duplex": duplex}), (flow, duplex))
        self.assertTrue(dx.applies_to({}, {"apply_page": True, "duplex": False}))
        self.assertTrue(dx.applies_to({}, {"apply_page": False, "duplex": True}))
        self.assertFalse(dx.applies_to({}, {"apply_page": False, "duplex": False}))

    def test_toggle_from_the_attachment_changes_the_whole_group(self):
        dx.apply(self.doc, self.cursor, True, "dang")
        in_annex = types.SimpleNamespace(PageStyleName="HST Default kèm theo")
        off = dx.toggle(self.doc, in_annex)
        self.assertFalse(off["duplex"])
        self.assertEqual((self.main.PageStyleLayout, self.annex.PageStyleLayout), (dx.ALL, dx.ALL))
        self.assertEqual(dx.read_choice(self.doc, self.cursor), (False, "dang"))
        on = dx.toggle(self.doc, in_annex)
        self.assertTrue(on["duplex"])
        self.assertEqual((self.main.PageStyleLayout, self.annex.PageStyleLayout), (dx.MIRRORED, dx.MIRRORED))
        self.assertEqual(dx.read_choice(self.doc, in_annex), (True, "dang"))

    def test_party_state_reads_from_the_page_layout(self):
        dx.apply(self.doc, self.cursor, False, "dang")
        self.main.PageStyleLayout = dx.MIRRORED  # e.g. set by hand in Định dạng trang
        self.assertEqual(dx.read_choice(self.doc, self.cursor), (True, "dang"))
        self.assertFalse(dx.toggle(self.doc, self.cursor)["duplex"])  # the next toggle turns it off, not on again
        self.assertEqual(self.main.PageStyleLayout, dx.ALL)

    def test_layout_read_back_as_a_uno_enum(self):
        dx.apply(self.doc, self.cursor, False, "dang")
        self.main.PageStyleLayout = types.SimpleNamespace(typeName="com.sun.star.style.PageStyleLayout", value="MIRRORED")
        self.assertEqual(dx.read_choice(self.doc, self.cursor), (True, "dang"))
        self.main.PageStyleLayout = types.SimpleNamespace(typeName="com.sun.star.style.PageStyleLayout", value="ALL")
        self.assertEqual(dx.read_choice(self.doc, self.cursor), (False, "dang"))

    def test_unmarked_document_guesses_from_the_party_heading(self):
        para = types.SimpleNamespace(getString=lambda: "Đảng Cộng sản Việt Nam",
                                     supportsService=lambda name: name == "com.sun.star.text.Paragraph")
        items = iter([para])
        enum = types.SimpleNamespace(hasMoreElements=lambda: True, nextElement=lambda: next(items))
        self.doc.getText = lambda: types.SimpleNamespace(createEnumeration=lambda: enum)
        self.assertEqual(dx.guess_profile(self.doc), "dang")
        self.doc.getText = lambda: None  # unreadable: no mirroring
        self.assertEqual(dx.guess_profile(self.doc), "nd30")


if __name__ == "__main__":
    unittest.main()
