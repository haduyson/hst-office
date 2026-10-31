# SPDX-License-Identifier: AGPL-3.0-only
"""scripts/dict/generate-vi-tone-variants.py adds the other tone placement of open oa/oe/uy syllables, nothing else."""
import importlib.util
import os
import unittest

import _paths

_spec = importlib.util.spec_from_file_location(
    "tone_variants", os.path.join(_paths.ROOT, "scripts", "dict", "generate-vi-tone-variants.py"))
tone = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tone)


class ToneVariants(unittest.TestCase):
    def test_new_style_gives_old_style(self):
        for given, expected in (("hoá", "hóa"), ("khoẻ", "khỏe"), ("thuỷ", "thủy"), ("tuỳ", "tùy"), ("uỷ", "ủy"), ("toà", "tòa")):
            self.assertEqual(tone.other_placement(given), expected)

    def test_old_style_gives_new_style(self):
        self.assertEqual(tone.other_placement("hóa"), "hoá")
        self.assertEqual(tone.other_placement("thủy"), "thuỷ")

    def test_no_variant_when_placement_does_not_vary(self):
        # closed syllables, single vowels, toneless words, qu + y, other vowel pairs
        for word in ("hoàn", "hoài", "hoa", "quý", "quỳ", "của", "tuyến", "ngoại", "ba", "đa", "hóex"):
            self.assertIsNone(tone.other_placement(word), word)

    def test_case_is_kept(self):
        self.assertEqual(tone.other_placement("Hoá"), "Hóa")

    def test_merge_is_idempotent_and_updates_the_count(self):
        lines = ["3", "hoá", "tuỳ", "xe"]
        merged, added = tone.merge(lines)
        self.assertEqual(sorted(added), ["hóa", "tùy"])
        self.assertEqual(merged[0], "5")
        again, more = tone.merge(merged)
        self.assertEqual(more, [])
        self.assertEqual(again, merged)

    def test_shipped_dictionary_is_complete_after_merge(self):
        path = os.path.join(_paths.ROOT, "upstream", "libreoffice", "dictionaries", "vi", "vi_VN.dic")
        if not os.path.isfile(path):
            self.skipTest("LibreOffice tree not present")
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        entries = set(lines[1:])
        merged, _ = tone.merge(lines)
        # entries only ever grow: every upstream entry stays
        self.assertTrue(entries <= set(merged[1:]))
        self.assertEqual(int(merged[0]), len(merged) - 1)


if __name__ == "__main__":
    unittest.main()
