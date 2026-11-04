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
from dialogs_writer_other_cases import (check_hyperlink, check_page_number, check_page_setup,  # noqa: E402
                                        check_special_character, check_word_count)
from dialogs_writer_paragraph_font_cases import check_font, check_paragraph  # noqa: E402
from hst_dialog_uitest import Checks, DialogHarness  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIALOGS = {"paragraph": check_paragraph, "font": check_font, "word-count": check_word_count, "hyperlink": check_hyperlink,
           "page-setup": check_page_setup, "special-character": check_special_character, "page-number": check_page_number}


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
