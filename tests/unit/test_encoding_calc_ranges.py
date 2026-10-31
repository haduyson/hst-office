# SPDX-License-Identifier: AGPL-3.0-only
"""Pure Calc range and grid tests; legacy text expectations verified with Converter."""
import _paths  # noqa: F401
import itertools
import unittest

from hst_office import encoding_calc_ranges as ranges


def cells(rects):
    return {(sheet, col, row) for sheet, c0, r0, c1, r1 in rects
            for col in range(c0, c1 + 1) for row in range(r0, r1 + 1)}


class Rectangles(unittest.TestCase):
    def test_clip(self):
        used = {0: (4, 6), 1: (2, 3)}
        cases = [
            ((0, 1, 2, 3, 4), (0, 1, 2, 3, 4)),
            ((0, 2, 3, 8, 9), (0, 2, 3, 4, 6)),
            ((0, 5, 0, 8, 2), None),
            ((0, 0, 7, 2, 9), None),
            ((0, 2, 0, 2, 1048575), (0, 2, 0, 2, 6)),
            ((0, 0, 3, 16383, 3), (0, 0, 3, 4, 3)),
            ((1, 0, 0, 8, 9), (1, 0, 0, 2, 3)),
        ]
        for rect, expected in cases:
            with self.subTest(rect=rect):
                self.assertEqual(ranges.clip(rect, used), expected)

    def test_normalize_union_is_disjoint(self):
        used = {0: (4, 4), 1: (2, 3)}
        cases = [
            [],
            [(0, 0, 0, 2, 2), (0, 1, 1, 4, 4)],
            [(0, 1, 1, 3, 3)] * 2,
            [(0, 0, 0, 4, 4), (0, 1, 1, 2, 2)],
            [(0, 1, 1, 3, 3), (1, 1, 1, 3, 3)],
            [(0, 0, 1, 6, 2), (0, 2, 0, 3, 6), (0, 6, 6, 8, 8)],
            [(0, 0, 0, 4, 4), (0, 1, 1, 2, 2), (0, 0, 0, 4, 4), (1, 0, 0, 4, 4)],
        ]
        for rects in cases:
            expected = {(s, c, r) for s, c, r in cells(rects)
                        if c <= used[s][0] and r <= used[s][1]}
            for ordered in (rects, rects[::-1]):
                with self.subTest(rects=ordered):
                    result = ranges.normalize(ordered, used)
                    self.assertEqual(cells(result), expected)
                    self.assertEqual(ranges.cell_count(result), len(expected))
                    for a, b in itertools.combinations(result, 2):
                        self.assertTrue(cells([a]).isdisjoint(cells([b])))

    def test_cell_count(self):
        self.assertEqual(ranges.cell_count([]), 0)
        self.assertEqual(ranges.cell_count([(3, 7, 9, 7, 9)]), 1)
        self.assertEqual(ranges.cell_count([(0, 2, 3, 4, 6), (1, 0, 0, 1, 2)]), 18)
        self.assertEqual(ranges.cell_count([(0, 0, 0, 1, 1)] * 2), 8)

    def test_contains(self):
        rects = [(0, 2, 3, 4, 5), (1, 0, 0, 0, 0)]
        for point in ((0, 2, 3), (0, 4, 5), (0, 3, 4), (1, 0, 0)):
            with self.subTest(point=point):
                self.assertTrue(ranges.contains(rects, *point))
        for point in ((0, 1, 3), (0, 5, 3), (0, 2, 2), (0, 2, 6), (2, 3, 4), (1, 3, 4)):
            with self.subTest(point=point):
                self.assertFalse(ranges.contains(rects, *point))
        self.assertFalse(ranges.contains([], 0, 0, 0))

    def test_chunks_cover_exactly_and_respect_limit(self):
        for rect, limit in [((2, 3, 5, 6, 11), 8), ((2, 3, 5, 6, 11), 9),
                            ((0, 1, 2, 1, 5), 1), ((0, 2, 3, 5, 3), 20),
                            ((0, 2, 3, 101, 205), 10000)]:
            with self.subTest(rect=rect, limit=limit):
                pieces = list(ranges.chunks(rect, limit))
                self.assertEqual(cells(pieces), cells([rect]))
                self.assertEqual(ranges.cell_count(pieces), len(cells([rect])))
                for piece in pieces:
                    self.assertGreater(ranges.cell_count([piece]), 0)
                    self.assertLessEqual(ranges.cell_count([piece]), limit)
        self.assertEqual(list(ranges.chunks(rect)), list(ranges.chunks(rect, 10000)))

    def test_runs_split_at_excluded_cells(self):
        excluded = {(2, 0), (4, 0), (0, 1), (5, 1)} | {(r, 2) for r in range(6)}
        result = list(ranges.runs(6, 4, excluded))
        self.assertEqual(result, [(0, 0, 1), (0, 3, 3), (0, 5, 5), (1, 1, 4), (3, 0, 5)])
        covered = [(r, c) for c, start, end in result for r in range(start, end + 1)]
        self.assertEqual(set(covered), {(r, c) for r in range(6) for c in range(4)} - excluded)
        self.assertEqual(len(covered), len(set(covered)))
        self.assertEqual(list(ranges.runs(0, 2, set())), [])
        self.assertEqual(list(ranges.runs(2, 0, set())), [])


class TextConversion(unittest.TestCase):
    def test_legacy_text_and_memo_reuse(self):
        for key, legacy in (("tcvn3", "ViÖt Nam"), ("vni", "Vieät Nam")):
            with self.subTest(key=key):
                convert = ranges.TextConverter(key)
                self.assertEqual(convert(legacy), "Việt Nam")
                cached = convert.memo[(legacy, False)]
                self.assertEqual(convert(legacy), "Việt Nam")
                self.assertIs(convert.memo[(legacy, False)], cached)
                self.assertEqual(len(convert.memo), 1)
                self.assertEqual(convert.unicode_skipped, 0)

    def test_tcvn3_upper_flag_has_separate_cache_entry(self):
        convert = ranges.TextConverter("tcvn3")
        for upper, expected in ((False, "VIệT NAM"), (True, "VIỆT NAM"), (False, "VIệT NAM")):
            with self.subTest(upper=upper):
                self.assertEqual(convert("VIÖT NAM", upper=upper), expected)
        self.assertEqual(set(convert.memo), {("VIÖT NAM", False), ("VIÖT NAM", True)})

    def test_unicode_skipped_counts_cached_calls(self):
        for key in ("tcvn3", "vni"):
            with self.subTest(key=key):
                convert = ranges.TextConverter(key)
                self.assertEqual(convert.unicode_skipped, 0)
                for count, text in enumerate(("Việt Nam", "Việt Nam", "Hà Nội"), 1):
                    self.assertEqual(convert(text), text)
                    self.assertEqual(convert.unicode_skipped, count)
                self.assertEqual(convert("ASCII"), "ASCII")
                self.assertEqual(convert.unicode_skipped, 3)
                self.assertEqual(len(convert.memo), 3)

    def test_convert_grid_mixed_rows(self):
        grid = ((1.25, -2.0, 0.0, 7.0), ("", "", "", ""),
                ("Vieät Nam", 42.5, "ASCII", ""), ("Việt Nam", "Haø Noäi", 9.0, "Vieät Nam"))
        convert = ranges.TextConverter("vni")
        output, changed = ranges.convert_grid(grid, convert)
        self.assertEqual(output, [[1.25, -2.0, 0.0, 7.0], ["", "", "", ""],
                                  ["Việt Nam", 42.5, "ASCII", ""], ["Việt Nam", "Hà Nội", 9.0, "Việt Nam"]])
        self.assertEqual(changed, {(2, 0), (3, 1), (3, 3)})
        self.assertEqual(set(convert.memo), {(s, False) for s in ("Vieät Nam", "ASCII", "Việt Nam", "Haø Noäi")})
        self.assertEqual(convert.unicode_skipped, 1)
        self.assertEqual(grid[2][0], "Vieät Nam")
        for r, row in enumerate(grid):
            for c, value in enumerate(row):
                if isinstance(value, float):
                    self.assertIs(output[r][c], value)

    def test_convert_grid_upper_and_empty_rows(self):
        grid = [[], ["VIÖT NAM", 3.5, ""]]
        output, changed = ranges.convert_grid(grid, ranges.TextConverter("tcvn3"), upper=True)
        self.assertEqual(output, [[], ["VIỆT NAM", 3.5, ""]])
        self.assertEqual(changed, {(1, 0)})
        self.assertEqual(grid, [[], ["VIÖT NAM", 3.5, ""]])
        self.assertIsNot(output[0], grid[0])
        self.assertIsNot(output[1], grid[1])
        self.assertEqual(ranges.convert_grid([], ranges.TextConverter("vni")), ([], set()))


if __name__ == "__main__":
    unittest.main()
