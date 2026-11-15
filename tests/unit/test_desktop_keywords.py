# SPDX-License-Identifier: AGPL-3.0-only
"""Launcher keywords lose third-party product names, keep generic words and file extensions (desktop_keywords.py)."""
import os
import sys
import tempfile
import unittest

import _paths

sys.path.insert(0, os.path.join(_paths.ROOT, "scripts", "linux"))
import desktop_keywords as kw  # noqa: E402

WRITER = ("[Desktop Entry]\nName=HST Writer\nKeywords=Text;Letter;OpenDocument Text;Microsoft Word;Microsoft Works;"
          "Lotus WordPro;CV;odt;doc;docx;rtf;\nKeywords[vi]=Văn bản;Microsoft Word;\nKeywords[de]=Corel Draw;\n"
          "MimeType=application/msword;application/vnd.ms-excel;\n")


class Keywords(unittest.TestCase):
    def test_clean_text(self):
        out = kw.clean_text(WRITER)
        self.assertIn("Keywords=Text;Letter;OpenDocument Text;CV;odt;doc;docx;rtf;\n", out)
        self.assertIn("Keywords[vi]=Văn bản;\n", out)
        self.assertNotIn("Keywords[de]", out)  # nothing generic left: the line goes
        self.assertIn("MimeType=application/msword;application/vnd.ms-excel;\n", out)  # technical, untouched
        self.assertEqual(kw.clean_text(out), out)
        for generic in ("Slideshow", "Spreadsheet", "Chart", "vsd", "pptx", "Digital signature", "Diagram"):
            self.assertIsNone(kw.THIRD_PARTY.search(generic), generic)

    def test_clean_tree_skips_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "writer.desktop")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(WRITER)
            os.symlink(path, os.path.join(tmp, "link.desktop"))
            self.assertEqual(kw.clean_tree(tmp), 1)
            self.assertEqual(kw.clean_tree(tmp), 0)
            with open(path, encoding="utf-8") as handle:
                self.assertNotIn("Microsoft", handle.read())


if __name__ == "__main__":
    unittest.main()
