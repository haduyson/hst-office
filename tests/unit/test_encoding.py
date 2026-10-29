# SPDX-License-Identifier: AGPL-3.0-only
"""Encoding converter tests against golden vectors derived from glibc iconv and the Wikipedia/vietunicode
VNI tables (tests/fixtures/vietnamese/derive-encoding-data.py) - never from the converter itself."""
import json
import os
import unittest

import _paths  # noqa: F401
from hst_office import encoding, encoding_detect

with open(os.path.join(_paths.FIXTURES, "encoding-vectors.json"), encoding="utf-8") as _f:
    VECTORS = json.load(_f)["cases"]


class GoldenVectors(unittest.TestCase):
    def test_all_vectors(self):
        self.assertGreaterEqual(len(VECTORS), 280)
        conv = {k: encoding.Converter(k) for k in encoding.encodings()}
        for case in VECTORS:
            with self.subTest(case["encoding"], kind=case["kind"], expected=case["expected"]):
                got, _ = conv[case["encoding"]].convert(case["input"], upper=case.get("upperFont", False))
                self.assertEqual(got, case["expected"])

    def test_every_vietnamese_letter_reachable(self):
        letters = {c["expected"] for c in VECTORS if c["encoding"] == "vni" and c["kind"] == "letter"}
        self.assertEqual(len(letters), 134)
        tc = {c["expected"] for c in VECTORS if c["encoding"] == "tcvn3" and c["kind"] in ("letter", "letter-upper-font")}
        self.assertEqual(tc, letters)


class Behaviour(unittest.TestCase):
    def test_unknown_or_auto_encoding_rejected(self):
        for key in ("auto", "", None, "VNI"):
            with self.assertRaises(ValueError):
                encoding.Converter(key)

    def test_mixed_unicode_and_ascii_preserved(self):
        got, stats = encoding.Converter("vni").convert("Vieät Nam 2026 € ‘x’ 日本 😀")
        self.assertEqual(got, "Việt Nam 2026 € ‘x’ 日本 😀")
        self.assertEqual(stats["converted"], 1)

    def test_unmapped_high_byte_counted_not_dropped(self):
        got, stats = encoding.Converter("vni").convert("aà")  # a + 0xE0 is a valid sequence (ầ)
        self.assertEqual(got, "ầ")
        got, stats = encoding.Converter("vni").convert("ç")
        self.assertEqual((got, stats["unmapped"]), ("ç", 1))

    def test_length_changing_mapping(self):
        out, _ = encoding.Converter("vni").convert("Vieät")
        self.assertEqual((out, len("Vieät"), len(out)), ("Việt", 5, 4))  # two-byte sequences collapse to one letter
        self.assertEqual(len(encoding.Converter("tcvn3").convert("ViÖt")[0]), 4)

    def test_font_policy(self):
        self.assertEqual(encoding.font_policy("tcvn3", ".VnTimeH"), (True, "Times New Roman"))
        self.assertEqual(encoding.font_policy("tcvn3", ".VnArial"), (False, "Arial"))
        self.assertEqual(encoding.font_policy("tcvn3", "Times New Roman"), (False, None))
        self.assertEqual(encoding.font_policy("vni", "VNI-Times"), (False, "Times New Roman"))

    def test_suggestion_is_only_a_suggestion(self):
        vni = encoding_detect.suggest("Coäng hoøa xaõ hoäi chuû nghóa Vieät Nam, Haø Noäi")
        self.assertEqual((vni["best"], vni["ambiguous"]), ("vni", False))
        tc = encoding_detect.suggest("Céng hßa x· héi chñ nghÜa ViÖt Nam, Hµ Néi")
        self.assertEqual((tc["best"], tc["ambiguous"]), ("tcvn3", False))
        for text in ("Cộng hòa xã hội", "plain ascii", ""):
            self.assertTrue(encoding_detect.suggest(text)["ambiguous"], text)

    def test_unicode_text_with_wide_letters_is_skipped(self):
        text = "Cộng hòa xã hội chủ nghĩa Việt Nam"
        got, stats = encoding.Converter("tcvn3").convert(text)
        self.assertEqual((got, stats["skipped_unicode"]), (text, True))

    def test_syllable_plausibility(self):
        for ok in ("Việt", "nghĩa", "Hương", "quyết", "một"):
            self.assertTrue(encoding_detect.is_plausible_syllable(ok), ok)
        for bad in ("Vieọt", "hũc", "xyz", "mạch" + "q"):
            self.assertFalse(encoding_detect.is_plausible_syllable(bad), bad)


if __name__ == "__main__":
    unittest.main()
