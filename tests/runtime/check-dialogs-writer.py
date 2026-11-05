#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Writer dialogs follow Word's structure: tab order, key controls, and edits that reach the document.

Usage: check-dialogs-writer.py [--instdir DIR] [--work DIR] [dialog ...]   (default: every dialog)
Needs a built instdir with the vi language pack. Runs headless (svp) with a fresh profile.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dialogs_writer_art_cases import check_page_art  # noqa: E402
from dialogs_writer_autofit_cases import check_autofit_large_table, check_autofit_real_documents, check_autofit_typing  # noqa: E402
from dialogs_writer_border_cases import check_borders, check_page_border  # noqa: E402
from dialogs_writer_insert_cases import check_insert_table  # noqa: E402
from dialogs_writer_other_cases import (check_hyperlink, check_page_number, check_page_setup,  # noqa: E402
                                        check_slide_properties, check_special_character, check_word_count)
from dialogs_writer_paragraph_font_cases import check_font, check_paragraph  # noqa: E402
from dialogs_writer_picture_cases import check_frame_style_keeps_size, check_picture  # noqa: E402
from dialogs_writer_table_cases import check_table_properties, check_table_row_navigation, check_table_text_wrapping  # noqa: E402
from hst_dialog_uitest import Checks, DialogHarness  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIALOGS = {"paragraph": check_paragraph, "font": check_font, "word-count": check_word_count, "hyperlink": check_hyperlink,
           "page-setup": check_page_setup, "special-character": check_special_character, "page-number": check_page_number,
           "slide-properties": check_slide_properties, "table-properties": check_table_properties,
           "table-rows": check_table_row_navigation, "table-wrap": check_table_text_wrapping,
           "picture": check_picture, "frame": check_frame_style_keeps_size,
           "borders": check_borders, "page-border": check_page_border, "page-art": check_page_art,
           "insert-table": check_insert_table, "autofit": check_autofit_typing, "autofit-large": check_autofit_large_table,
           "autofit-real": check_autofit_real_documents}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--work", default=os.path.join(ROOT, "tests/output/dialogs-writer"))
    parser.add_argument("dialogs", nargs="*", default=[])
    args = parser.parse_args()
    harness = DialogHarness(args.instdir, args.work, 22979, ":79")
    checks = Checks()
    try:
        for name in args.dialogs or DIALOGS:
            DIALOGS[name](harness, checks)
    finally:
        harness.close()
    return checks.finish()


if __name__ == "__main__":
    sys.exit(main())
