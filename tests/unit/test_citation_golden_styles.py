# SPDX-License-Identifier: AGPL-3.0-only
"""Every bundled citation style formats the sample references exactly like its reviewed golden file."""
import os
import unittest

import citation_golden as golden


class GoldenStyles(unittest.TestCase):
    maxDiff = None

    def test_every_case_matches_its_golden_file(self):
        update = os.environ.get("HST_UPDATE_CITATION_GOLDEN") == "1"
        for case in golden.CASES:
            with self.subTest(case=case):
                text = golden.render_case(case)
                path = golden.golden_path(case)
                if update:
                    with open(path, "w", encoding="utf-8") as handle:
                        handle.write(text)
                with open(path, encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), text)

    def test_every_bundled_style_has_a_golden_case(self):
        from hst_office import citation_style
        covered = {case.split("@")[0].split("+")[0] for case in golden.CASES}
        self.assertEqual(set(citation_style.builtin_ids()), covered)

    def test_every_preset_has_a_golden_case(self):
        from hst_office import citation_style
        for info in citation_style.list_styles():
            for preset in info["presets"]:
                self.assertIn("%s@%s" % (info["id"], preset["id"]), golden.CASES)


if __name__ == "__main__":
    unittest.main()
