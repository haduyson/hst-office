# SPDX-License-Identifier: AGPL-3.0-only
"""hst-writer-image-align-and-margin-select.patch (offline: reads the patch hunks).

- A selected picture or embedded object answers Left/Center/Right from the Home tab, Ctrl+L/E/R and
  its context menu: the frame shell offers the paragraph alignment slots and routes them, with the
  object alignment slots, to sw/source/uibase/hst/imagealign.cxx.
- The left page margin selects lines: SwEditWin asks sw/source/uibase/hst/marginlineselect.cxx for
  the pointer, the press, the drag and the release.
- Thin hooks: LibreOffice files get a few lines each, the logic lives in HST-owned files."""
from pathlib import Path
import unittest

PATCHES = Path(__file__).resolve().parents[2] / "patches/libreoffice"
NAME = "hst-writer-image-align-and-margin-select.patch"
NEW_FILES = ("sw/source/uibase/hst/imagealign.cxx", "sw/source/uibase/hst/marginlineselect.cxx",
             "sw/source/uibase/inc/hstimagealign.hxx", "sw/source/uibase/inc/hstmarginlineselect.hxx",
             "sw/qa/uibase/hst/imagealign.cxx", "sw/qa/uibase/hst/marginlineselect.cxx")


def changes():
    """{path: (removed lines, added lines)} of the patch."""
    out, current = {}, None
    for line in (PATCHES / NAME).read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:].split("\t")[0], ([], []))
        elif current is None or line.startswith(("@@", "--- a/")):
            continue
        elif line.startswith("-"):
            current[0].append(line[1:])
        elif line.startswith("+"):
            current[1].append(line[1:])
    return out


class ImageAlignMarginSelectPatch(unittest.TestCase):
    def setUp(self):
        self.changes = changes()

    def added(self, path):
        return "\n".join(self.changes[path][1])

    def test_listed_last_after_its_context(self):
        series = [n.strip() for n in (PATCHES / "series").read_text(encoding="utf-8").splitlines()
                  if n.strip() and not n.startswith("#")]
        # the test makefile hunk sits on the line the large-document warning adds
        self.assertLess(series.index("hst-sw-large-document-warning.patch"), series.index(NAME))

    def test_new_files_are_hst_owned(self):
        for path in NEW_FILES:
            self.assertIn("SPDX-License-Identifier: LicenseRef-HST-Proprietary", self.added(path), path)
            self.assertEqual(self.changes[path][0], [], path)

    def test_lo_files_only_get_hooks(self):
        for path, (removed, added) in self.changes.items():
            if path in NEW_FILES or path.endswith(".sdi"):
                continue
            self.assertEqual(removed, [], path)
            self.assertLessEqual(len(added), 30, path)

    def test_frame_shell_offers_paragraph_alignment(self):
        sdi = self.added("sw/sdi/_frmsh.sdi")
        for slot in ("LEFT", "CENTER", "RIGHT", "START", "END"):
            self.assertIn("SID_ATTR_PARA_ADJUST_" + slot, sdi)
        shell = self.added("sw/source/uibase/shells/frmsh.cxx")
        self.assertIn("hst::imagealign::Execute(rSh, rReq)", shell)
        self.assertIn("hst::imagealign::GetState(rSh, nWhich, rSet)", shell)

    def test_inline_aligns_paragraph_floating_aligns_position(self):
        code = self.added("sw/source/uibase/hst/imagealign.cxx")
        self.assertIn("RndStdIds::FLY_AS_CHAR", code)
        self.assertIn("RES_PARATR_ADJUST", code)
        self.assertIn("css::text::RelOrientation::PRINT_AREA", code)

    def test_edit_window_hooks(self):
        win = self.added("sw/source/uibase/docvw/edtwin.cxx")
        for hook in ("hst::marginselect::IsOverMargin", "hst::marginselect::ButtonDown",
                     "hst::marginselect::Drag", "hst::marginselect::ButtonUp",
                     "PointerStyle::TabSelectE"):
            self.assertIn(hook, win)

    def test_margin_hit_test_visits_only_visible_pages(self):
        code = self.added("sw/source/uibase/hst/marginlineselect.cxx")
        self.assertIn("GetFirstVisPage", code)
        self.assertNotIn("GetPageAtPos", code)


if __name__ == "__main__":
    unittest.main()
