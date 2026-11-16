# SPDX-License-Identifier: AGPL-3.0-only
"""Writer's Home tab: the large buttons of the Vietnamese tools show 24 px images (owner rule: every large button
but Paste), not the 32 px or 16 px images they named before. The HST themes draw these glyphs at 24 px
(tests/brand/test-hst-icon-theme.py), and the classic style layers them over Colibre, which lacks them."""
import unittest

from patch_sections import added, removed

PATCH = "hst-ribbon-mockup-writer.patch"
UI = "sw/uiconfig/swriter/ui/notebookbar.ui"
ICONS = {"nd30wizard": "cmd/32/nd30wizard.png", "convertencoding": "cmd/sc_convertencoding.png",
         "numbertowords": "cmd/sc_numbertowords.png"}


class LargeButtonIconTest(unittest.TestCase):
    def test_vietnamese_tools_name_their_24px_images(self):
        new, old = added(PATCH, UI), removed(PATCH, UI)
        for name, before in ICONS.items():
            self.assertIn(f'<property name="icon-name">cmd/lc_{name}.png</property>', new)
            self.assertIn(f'<property name="icon-name">{before}</property>', old)


if __name__ == "__main__":
    unittest.main()
