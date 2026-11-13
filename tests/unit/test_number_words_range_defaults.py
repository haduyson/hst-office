# SPDX-License-Identifier: AGPL-3.0-only
""""Đọc số thành chữ": the choice the dialog opens with (file default > last choice > "đồng"), the planning of a
column of cells, and the file's default unit stored as user-defined document properties."""
import os
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

import _paths  # noqa: F401

from hst_office import number_words as nw
from hst_office import number_words_defaults as defaults
from hst_office import number_words_file_default as fd
from hst_office import number_words_prefs as prefs
from hst_office import number_words_range as rg
from hst_office.number_words_choice import formula


def choice(money=False, unit="đồng", sub="", options="", as_formula=False):
    return {"money": money, "unit": unit, "sub_unit": sub, "options": nw.parse_options(options), "formula": as_formula}


class Precedence(unittest.TestCase):
    LAST = {"money": True, "unit": "dollar", "sub_unit": "cent", "thousand": "ngàn", "odd": "linh", "four": "tư",
            "language": "en", "formula": True}

    def test_program_default_is_dong_without_xu(self):
        self.assertEqual(defaults.resolve(), defaults.DEFAULTS)
        self.assertEqual(defaults.resolve(None, None), defaults.DEFAULTS)
        self.assertEqual((defaults.DEFAULTS["unit"], defaults.DEFAULTS["sub_unit"], defaults.DEFAULTS["money"]),
                         ("đồng", "", False))

    def test_user_choice_beats_program_default(self):
        self.assertEqual(defaults.resolve(None, self.LAST), self.LAST)

    def test_file_default_beats_user_choice_for_its_entries_only(self):
        values = defaults.resolve(defaults.unit_layer(("đồng", "xu")), self.LAST)
        self.assertEqual((values["unit"], values["sub_unit"]), ("đồng", "xu"))
        self.assertEqual((values["language"], values["formula"], values["money"]), ("en", True, True))
        self.assertEqual(defaults.resolve(defaults.unit_layer(("USD", ""))), dict(defaults.DEFAULTS, unit="USD"))
        self.assertEqual(defaults.resolve({"thousand": "ngàn"}, self.LAST)["thousand"], "ngàn")

    def test_a_unit_keeps_its_own_sub_unit(self):
        values = defaults.resolve({"unit": "USD"}, {"unit": "đồng", "sub_unit": "xu"})
        self.assertEqual((values["unit"], values["sub_unit"]), ("USD", ""))
        values = defaults.resolve({"sub_unit": "cent"}, {"unit": "đồng", "sub_unit": "xu"})
        self.assertEqual((values["unit"], values["sub_unit"]), ("đồng", "xu"))

    def test_damaged_layers_fall_back_per_entry(self):
        raw = {"money": "yes", "unit": "x" * 41, "sub_unit": "cent", "thousand": "ngan", "odd": "linh",
               "language": 3, "formula": 1}
        self.assertEqual(defaults.resolve(raw), dict(defaults.DEFAULTS, odd="linh"))
        self.assertEqual(defaults.resolve({"unit": "  ", "sub_unit": "xu"})["sub_unit"], "")
        self.assertEqual(defaults.resolve({"unit": "a\nb"})["unit"], "đồng")
        self.assertEqual(defaults.resolve("garbage", ["x"]), defaults.DEFAULTS)
        self.assertEqual(defaults.resolve({"money": True}, {"money": "bad", "language": "en"}),
                         dict(defaults.DEFAULTS, money=True, language="en"))

    def test_from_choice_round_trip(self):
        accepted = choice(True, "dollar", "cent", "ngàn linh tư en", as_formula=True)
        self.assertEqual(prefs.from_choice(accepted), self.LAST)
        self.assertFalse(prefs.from_choice(dict(accepted, formula=False))["formula"])

    def test_load_and_save_use_the_profile_node(self):
        node = mock.Mock()
        node.getPropertyValue.side_effect = lambda name: {"Money": True, "Unit": "dollar", "SubUnit": "cent",
                                                          "Thousand": "ngàn", "Odd": "linh", "Four": "tư",
                                                          "Language": "en", "Formula": True}[name]
        with mock.patch.object(prefs, "_access", return_value=node):
            self.assertEqual(prefs.load(None), self.LAST)
            prefs.save(None, self.LAST, calc=False)
        written = {call.args[0] for call in node.setPropertyValue.call_args_list}
        self.assertNotIn("Formula", written)  # Writer has no text/formula choice
        self.assertIn("Unit", written)
        node.commitChanges.assert_called_once()

    def test_unreadable_profile_gives_program_default(self):
        with mock.patch.object(prefs, "_access", side_effect=RuntimeError("no schema")), \
                mock.patch.object(prefs.diag_log, "exception"):
            self.assertEqual(prefs.load(None), defaults.DEFAULTS)
            prefs.save(None, defaults.DEFAULTS, True)  # does not raise


class Schema(unittest.TestCase):
    def test_schema_matches_the_keys_and_program_default(self):
        ext = os.path.join(_paths.ROOT, "extensions", "hst-vietnamese-tools")
        oor = "{http://openoffice.org/2001/registry}"
        root = ET.parse(os.path.join(ext, "numberwords.xcs")).getroot()
        self.assertEqual("/%s.%s" % (root.get(oor + "package"), root.get(oor + "name")), prefs.CONFIG_PATH)
        stored = {p.get(oor + "name"): p.findtext("value") or "" for p in root.iter("prop")}
        expected = {name: str(defaults.DEFAULTS[key]).lower() if isinstance(defaults.DEFAULTS[key], bool)
                    else defaults.DEFAULTS[key] for key, name in prefs.KEYS.items()}
        self.assertEqual(stored, expected)
        with open(os.path.join(ext, "META-INF", "manifest.xml"), encoding="utf-8") as manifest:
            self.assertIn('full-path="numberwords.xcs"', manifest.read())


class RangePlanning(unittest.TestCase):
    def test_addresses(self):
        self.assertEqual(rg.parse_address("$a$2"), (None, "A2"))
        self.assertEqual(rg.parse_address("A2:A20"), (None, "A2:A20"))
        self.assertEqual(rg.parse_address("'Bảng 2'.B3"), ("Bảng 2", "B3"))
        self.assertIsNone(rg.parse_address("A2:A20", allow_range=False))
        for bad in ("", "A", "2", "A2:", "A2;B3", None):
            self.assertIsNone(rg.parse_address(bad), bad)

    def test_clip_and_overlap(self):
        self.assertEqual(rg.clip_rows(0, 1048575, 40), (0, 40))
        self.assertEqual(rg.clip_rows(50, 1048575, 40), (50, 50))
        self.assertEqual(rg.clip_rows(2, 9, 40), (2, 9))
        self.assertTrue(rg.overlaps((0, 1, 0, 9), (0, 1, 9, 18)))
        self.assertFalse(rg.overlaps((0, 1, 0, 9), (0, 2, 0, 9)))
        self.assertFalse(rg.overlaps((0, 1, 0, 9), (1, 1, 0, 9)))
        self.assertFalse(rg.overlaps((0, 1, 0, 9), (0, 1, 10, 19)))

    def test_plan_skips_empty_counts_non_numbers_and_occupied(self):
        values = [1000.0, "", "Số tiền", 2.0, "1.250.000", "   ", 1e16]
        existing = ["", "x", "", "cũ", "", "", ""]
        result = rg.plan(values, existing, choice(True))
        self.assertEqual([offset for offset, _text in result.writes], [0, 3, 4])
        self.assertEqual(result.writes[0][1], "Một nghìn đồng chẵn")
        self.assertEqual(result.writes[2][1], "Một triệu hai trăm năm mươi nghìn đồng chẵn")
        self.assertEqual(result.skipped, 2)  # the header text and the 17-digit number
        self.assertEqual(result.occupied, 1)  # row 1 holds "x" but its source is empty: not written, not counted
        self.assertEqual(result.error.code, "not-a-number")

    def test_fifteen_digit_guard_per_cell(self):
        result = rg.plan([999999999999999.0, 1e15], ["", ""], choice())
        self.assertEqual(([w[0] for w in result.writes], result.skipped), ([0], 1))
        self.assertEqual(result.error.code, "too-many-digits")

    def test_formula_args_per_row(self):
        self.assertEqual(rg.reference("A", 4), "A5")
        self.assertEqual(rg.reference("C", 0, "Bảng 'Q'"), "'Bảng ''Q'''.C1")
        self.assertEqual(formula(choice(True), rg.reference("A", 1)), "=DOCTIEN(A2)")
        self.assertEqual(formula(choice(True, "đồng", "xu"), rg.reference("A", 1)), '=DOCTIEN(A2;"đồng";"xu")')
        self.assertEqual(formula(choice(True, "USD", ""), "A2"), '=DOCTIEN(A2;"USD";"")')
        self.assertEqual(formula(choice(), rg.reference("B", 9)), "=DOCSO(B10)")


class FakeProps:
    """com.sun.star user-defined properties: XPropertyContainer + XPropertySet."""

    def __init__(self, **values):
        self.values = dict(values)

    def getPropertySetInfo(self):
        return mock.Mock(hasPropertyByName=lambda name: name in self.values)

    def getPropertyValue(self, name):
        return self.values[name]

    def setPropertyValue(self, name, value):
        self.values[name] = value

    def addProperty(self, name, attributes, value):
        assert attributes == fd.REMOVEABLE
        self.values[name] = value

    def removeProperty(self, name):
        del self.values[name]


def fake_doc(props):
    doc = mock.Mock()
    doc.getDocumentProperties.return_value.getUserDefinedProperties.return_value = props
    return doc


class FileDefault(unittest.TestCase):
    def test_read(self):
        self.assertIsNone(fd.read(fake_doc(FakeProps())))
        self.assertEqual(fd.read(fake_doc(FakeProps(**{fd.UNIT: "đồng", fd.SUB_UNIT: "xu"}))), ("đồng", "xu"))
        self.assertEqual(fd.read(fake_doc(FakeProps(**{fd.UNIT: "USD"}))), ("USD", ""))
        self.assertIsNone(fd.read(fake_doc(FakeProps(**{fd.UNIT: 5.0}))))  # same name, another type

    def test_store_and_remove(self):
        props = FakeProps()
        doc = fake_doc(props)
        self.assertTrue(fd.store(doc, ("đồng", "xu")))
        self.assertEqual(props.values, {fd.UNIT: "đồng", fd.SUB_UNIT: "xu"})
        doc.setModified.assert_called_once_with(True)
        self.assertTrue(fd.store(doc, ("đồng", "xu")))  # unchanged: the document stays unmodified
        doc.setModified.assert_called_once()
        self.assertTrue(fd.store(doc, ("dollar", "cent")))
        self.assertEqual(props.values[fd.UNIT], "dollar")
        self.assertTrue(fd.store(doc, None))
        self.assertEqual(props.values, {})

    def test_store_failure_is_reported(self):
        doc = fake_doc(FakeProps())
        doc.setModified.side_effect = RuntimeError("read-only")
        with mock.patch.object(fd.diag_log, "exception"):
            self.assertFalse(fd.store(doc, ("đồng", "xu")))


if __name__ == "__main__":
    unittest.main()
