# SPDX-License-Identifier: AGPL-3.0-only
import json
import os
import unittest

import _paths  # noqa: F401
from hst_office import csv_import

with open(os.path.join(_paths.FIXTURES, "csv-cases.json"), encoding="utf-8") as _f:
    CASES = json.load(_f)


class Decode(unittest.TestCase):
    def test_bom_and_no_bom(self):
        self.assertEqual(csv_import.decode_bytes("é,ơ".encode("utf-8")), ("é,ơ", False))
        self.assertEqual(csv_import.decode_bytes(b"\xef\xbb\xbf" + "é,ơ".encode("utf-8")), ("é,ơ", True))

    def test_invalid_bytes_raise_never_replace(self):
        for case in CASES["invalidBytes"]:
            with self.subTest(case["name"]), self.assertRaises(csv_import.CsvError) as ctx:
                csv_import.decode_bytes(bytes.fromhex(case["hex"].replace(" ", "")))
            self.assertEqual(ctx.exception.code, case["code"])

    def test_size_limit(self):
        with self.assertRaises(csv_import.CsvError) as ctx:
            csv_import.decode_bytes(b"a" * (csv_import.limits()["maxBytes"] + 1))
        self.assertEqual(ctx.exception.code, "too-large")


class Parse(unittest.TestCase):
    def test_valid(self):
        for case in CASES["valid"]:
            with self.subTest(case["name"]):
                self.assertEqual(csv_import.parse(case["text"], case["delimiter"]), case["rows"])

    def test_malformed(self):
        for case in CASES["malformed"]:
            with self.subTest(case["name"]), self.assertRaises(csv_import.CsvError) as ctx:
                csv_import.parse(case["text"], case["delimiter"])
            self.assertEqual(ctx.exception.code, case["code"])

    def test_bad_delimiter_and_empty(self):
        for text, delim, code in (("a|b", "|", "bad-delimiter"), ("", ",", "empty")):
            with self.assertRaises(csv_import.CsvError) as ctx:
                csv_import.parse(text, delim)
            self.assertEqual(ctx.exception.code, code)

    def test_limits(self):
        lim = csv_import.limits()
        rows = csv_import.parse("a,b\n" * 5000, ",")
        self.assertEqual((len(rows), len(rows[0])), (5000, 2))
        with self.assertRaises(csv_import.CsvError) as ctx:
            csv_import.parse("a\n" * (lim["maxRows"] + 1), ",")
        self.assertEqual(ctx.exception.code, "too-many-rows")
        with self.assertRaises(csv_import.CsvError) as ctx:
            csv_import.parse(",".join("x" * 1 for _ in range(lim["maxColumns"] + 1)), ",")
        self.assertEqual(ctx.exception.code, "too-many-columns")
        with self.assertRaises(csv_import.CsvError) as ctx:
            csv_import.parse("x" * (csv_import.MAX_CELL_CHARS + 1), ",")
        self.assertIn(ctx.exception.code, ("cell-too-long", "malformed"))

    def test_typed_cells(self):
        for value, mode, kind, want in CASES["typed"]:
            self.assertEqual(csv_import.typed_cell(value, mode), (kind, want), value)
        with self.assertRaises(ValueError):
            csv_import.typed_cell("1", "auto")

    def test_delimiter_suggestion_is_only_advice(self):
        self.assertEqual(csv_import.suggest_delimiter("a;b;c\n1;2;3\n"), ";")
        self.assertEqual(csv_import.suggest_delimiter("a\tb\n1\t2\n"), "\t")
        self.assertEqual(csv_import.suggest_delimiter("a,b\n1,2\n"), ",")


if __name__ == "__main__":
    unittest.main()
