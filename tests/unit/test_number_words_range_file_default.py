# SPDX-License-Identifier: AGPL-3.0-only
""""Đọc số thành chữ" in Sheets: planning a column of cells, and the file's own default kept as user-defined
document properties (HST.DocTien.*, HST.DocSo.*)."""
import unittest
from unittest import mock

import _paths  # noqa: F401

from hst_office import number_words as nw
from hst_office import number_words_file_default as fd
from hst_office import number_words_range as rg
from hst_office.number_words_choice import formula


def choice(money=False, unit="đồng", sub="", options=""):
    return {"money": money, "unit": unit, "sub_unit": sub, "options": nw.parse_options(options)}


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

    def test_formula_reference_per_row(self):
        self.assertEqual(rg.reference("A", 4), "A5")
        self.assertEqual(rg.reference("C", 0, "Bảng 'Q'"), "'Bảng ''Q'''.C1")
        self.assertEqual(formula(choice(True, "đồng", "xu"), rg.reference("A", 1)), '=DOCTIEN(A2;"đồng";"xu")')
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


MONEY = {"unit": "đồng", "sub_unit": "xu", "money_options": "ngàn"}
NAMES = fd.PROPERTIES


class FileDefault(unittest.TestCase):
    def test_read(self):
        self.assertEqual(fd.read(None), {})
        self.assertEqual(fd.read(fake_doc(FakeProps())), {})
        stored = FakeProps(**{NAMES["unit"]: "đồng", NAMES["sub_unit"]: "xu", NAMES["money_options"]: "Ngàn",
                              NAMES["number_options"]: ""})
        self.assertEqual(fd.read(fake_doc(stored)), dict(MONEY, number_options=""))
        self.assertEqual(fd.read(fake_doc(FakeProps(**{NAMES["unit"]: "USD"}))), {"unit": "USD", "sub_unit": ""})
        damaged = FakeProps(**{NAMES["unit"]: 5.0, NAMES["number_options"]: "sai"})
        self.assertEqual(fd.read(fake_doc(damaged)), {})  # same names, unusable values: no default

    def test_groups(self):
        layer = dict(MONEY, number_options="linh")
        self.assertTrue(fd.has_group(layer, True) and fd.has_group({"number_options": ""}, False))
        self.assertFalse(fd.has_group({"number_options": ""}, True))
        values = dict(MONEY, number_options="")
        self.assertTrue(fd.matches(layer, True, values))
        self.assertFalse(fd.matches(layer, False, values))
        self.assertFalse(fd.matches({}, True, values))
        self.assertEqual(fd.with_group(layer, True, None), {"number_options": "linh"})
        self.assertEqual(fd.with_group({}, False, {"number_options": "tư"}), {"number_options": "tư"})
        self.assertEqual(fd.group(True, values), MONEY)

    def test_store_and_remove_one_group(self):
        props = FakeProps()
        doc = fake_doc(props)
        self.assertIs(fd.store(doc, True, MONEY), True)
        self.assertEqual(props.values, {NAMES[k]: v for k, v in MONEY.items()})
        doc.setModified.assert_called_once_with(True)
        self.assertIs(fd.store(doc, True, MONEY), False)  # unchanged: the document stays unmodified
        doc.setModified.assert_called_once()
        self.assertIs(fd.store(doc, False, {"number_options": ""}), True)
        self.assertEqual(props.values[NAMES["number_options"]], "")
        self.assertIs(fd.store(doc, True, None), True)
        self.assertEqual(props.values, {NAMES["number_options"]: ""})
        self.assertIs(fd.store(doc, True, None), False)

    def test_store_failure_is_reported(self):
        doc = fake_doc(FakeProps())
        doc.setModified.side_effect = RuntimeError("read-only")
        with mock.patch.object(fd.diag_log, "exception"):
            self.assertIsNone(fd.store(doc, True, MONEY))


if __name__ == "__main__":
    unittest.main()
