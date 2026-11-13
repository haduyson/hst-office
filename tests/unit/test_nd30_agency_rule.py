# SPDX-License-Identifier: AGPL-3.0-only
"""Length of the rule under the agency name (ND30 Phụ lục I, II.2b: 1/3 to 1/2 of the line, centred), as chosen in the
wizard: fractions of the longest line of a multi-line name, the line above, a typed length kept inside the cell, the
note when it leaves the ND30 range, the remembered choice, and the wizard row (wizard tests use the fake dialog of
test_nd30_wizard_model_order)."""
import unittest
from unittest import mock

import _paths  # noqa: F401
from test_nd30_wizard_model_order import FakeDialog
from hst_office import nd30_layout, nd30_prefs, nd30_rule_length as rules, wizard_nd30
from hst_office.data_files import load_locale
from hst_office.nd30_metrics import widest_line_mm
from hst_office.nd30_preview import RULE

AGENCY = "Sở Tài nguyên và Môi trường tỉnh Bắc Ninh"
PARENT = "Ủy ban nhân dân tỉnh Bắc Ninh"


def agency_paragraph(rule=None, type_id="cong-van", agency=AGENCY, parent=PARENT):
    fields = {"agency": agency, "parentAgency": parent}
    if rule:
        fields[rules.FIELD] = rule
    layout = nd30_layout.build_layout(type_id, fields)
    header = layout["blocks"][0]
    cell_mm = layout["textWidthMm"] * header["widthsPct"][0] / 100.0
    agency_para = [p for p in header["rows"][0]["cells"][0] if p.get("role") == "Agency"][0]
    return layout, agency_para, cell_mm


class Lengths(unittest.TestCase):
    def test_fractions_of_the_longest_line_of_a_multi_line_name(self):
        _layout, para, cell_mm = agency_paragraph()
        line = widest_line_mm(AGENCY.upper(), 13, True, cell_mm)
        self.assertLess(line, cell_mm)  # wrapped: the longest line, not the whole name, is the reference
        self.assertGreater(widest_line_mm(AGENCY.upper(), 13, True, 1000), cell_mm)
        for choice, fraction in (("1/3", 1 / 3), ("2/5", 0.4), ("1/2", 0.5)):
            self.assertAlmostEqual(agency_paragraph(choice)[1]["rule_mm"], round(line * fraction, 2), places=2)
        self.assertEqual(para["rule_mm"], agency_paragraph("2/5")[1]["rule_mm"])  # no choice: the profile's 2/5

    def test_explicit_line_breaks_count_the_longest_line(self):
        name = "Tổng cục\nThuế"
        _layout, para, cell_mm = agency_paragraph("1/2", agency=name)
        self.assertAlmostEqual(para["rule_mm"], round(widest_line_mm("TỔNG CỤC", 13, True, cell_mm) / 2, 2), places=2)

    def test_as_long_as_the_line_above(self):
        _layout, para, cell_mm = agency_paragraph("parent")
        self.assertAlmostEqual(para["rule_mm"], round(widest_line_mm(PARENT.upper(), 13, False, cell_mm), 2), places=2)
        _layout, para, cell_mm = agency_paragraph("parent", parent="")  # no parent line: the name's own line
        self.assertAlmostEqual(para["rule_mm"], round(widest_line_mm(AGENCY.upper(), 13, True, cell_mm), 2), places=2)

    def test_typed_length_is_kept_inside_the_cell(self):
        self.assertEqual(agency_paragraph("mm:30")[1]["rule_mm"], 30.0)
        _layout, para, cell_mm = agency_paragraph("mm:400")
        self.assertEqual(para["rule_mm"], round(cell_mm, 2))
        self.assertEqual(agency_paragraph("mm:1")[1]["rule_mm"], rules.MIN_MM)

    def test_party_forms_keep_no_rule(self):
        layout = nd30_layout.build_layout("dang-thong-bao", {rules.FIELD: "1/2"})
        self.assertFalse(any(p.get("rule_mm") for p in layout["blocks"][0]["rows"][0]["cells"][0]))

    def test_parse_and_encode(self):
        self.assertEqual(rules.parse_mm("32,5 mm"), 32.5)
        for bad in ("", "abc", "-3", "0", "5000"):
            self.assertIsNone(rules.parse_mm(bad), bad)
        self.assertEqual(rules.parse("mm:30"), ("mm", 30.0))
        for damaged in (None, "", "3/4", "mm:", "mm:x"):
            self.assertEqual(rules.parse(damaged), (rules.DEFAULT, None))
        self.assertEqual(rules.encode("mm", 30.04), "mm:30")
        self.assertIsNone(rules.encode("mm", None))

    def test_out_of_range_note(self):
        for choice in ("1/3", "2/5", "1/2"):
            self.assertFalse(rules.out_of_range(agency_paragraph(choice)[0]), choice)
        self.assertTrue(rules.out_of_range(agency_paragraph("mm:8")[0]))
        self.assertTrue(rules.out_of_range(agency_paragraph("mm:60")[0]))


class Remembered(unittest.TestCase):
    def test_damaged_or_missing_profile_reads_the_default(self):
        node = mock.Mock()
        node.getPropertyValue.return_value = "mm:abc"
        with mock.patch.object(nd30_prefs, "_access", return_value=node):
            self.assertEqual(nd30_prefs.load_agency_rule(None), "2/5")
            self.assertTrue(nd30_prefs.save_agency_rule(None, "1/3"))
        node.setPropertyValue.assert_called_once_with("AgencyRule", "1/3")
        with mock.patch.object(nd30_prefs, "_access", side_effect=RuntimeError("no schema")), \
                mock.patch.object(nd30_prefs.diag_log, "exception"):
            self.assertEqual(nd30_prefs.load_agency_rule(None), "2/5")
            self.assertFalse(nd30_prefs.save_agency_rule(None, "1/3"))


class WizardRow(unittest.TestCase):
    def wizard(self, remembered):
        wizard_nd30.Dialog, wizard_nd30.palette = FakeDialog, lambda ctx: {"muted": 1, "error": 2, "link": 0}
        with mock.patch.object(nd30_prefs, "load_agency_rule", return_value=remembered):
            return wizard_nd30.Nd30Wizard(None, load_locale("vi"))

    def test_opens_with_the_remembered_choice_and_shows_it_in_the_preview(self):
        w = self.wizard("mm:30")
        model = w.d.model
        self.assertEqual(model.getByName("agencyRule").SelectedItems, (rules.CHOICES.index("mm"),))
        self.assertEqual((model.getByName("agencyRuleMm").Text, model.getByName("agencyRuleMm").Enabled), ("30", True))
        self.assertEqual(w.read()[1][rules.FIELD], "mm:30")
        self.assertEqual(self.wizard("2/5").d.model.getByName("agencyRuleMm").Enabled, False)
        short = self.wizard("1/3").d.model.getByName("preview").Text
        long_ = self.wizard("1/2").d.model.getByName("preview").Text
        self.assertGreater(long_.count(RULE), short.count(RULE))

    def test_typed_length_errors_and_the_gentle_note(self):
        w = self.wizard("mm:30")
        w.d.set_text("agencyRuleMm", "ba mươi")
        self.assertFalse(w.refresh())
        self.assertFalse(w.d.model.getByName("btnOk").Enabled)
        w.d.set_text("agencyRuleMm", "8")
        self.assertTrue(w.refresh())  # outside 1/3-1/2: noted, still allowed
        status = w.d.model.getByName("status")
        self.assertEqual((status.Label, status.TextColor), (load_locale("vi")["nd30"]["agencyRuleWarning"], 1))
        self.assertTrue(w.d.model.getByName("btnOk").Enabled)

    def test_accept_remembers_the_choice(self):
        w = self.wizard("1/2")
        w.d.end = mock.Mock()
        with mock.patch.object(nd30_prefs, "save_agency_rule") as save:
            w._accept()
        w.d.end.assert_called_once_with(1)
        save.assert_called_once_with(None, "1/2")
        self.assertEqual(w.accepted["fields"][rules.FIELD], "1/2")


if __name__ == "__main__":
    unittest.main()
