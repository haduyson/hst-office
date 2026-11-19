# SPDX-License-Identifier: AGPL-3.0-only
"""The pilot dialogs of the HST coat screenshots, shared by the Linux and Windows shot scripts."""

# name: (document factory, dispatch command)
DIALOGS = {
    "format-cells": ("scalc", ".uno:FormatCellDialog"),
    "paragraph": ("swriter", ".uno:ParagraphDialog"),
    "page-style": ("swriter", ".uno:PageDialog"),
    "print": ("swriter", ".uno:Print"),
    "options": ("swriter", ".uno:OptionsTreeDialog"),
    "find-replace": ("swriter", ".uno:SearchDialog"),
    "insert-table": ("swriter", ".uno:InsertTable"),
    "character": ("swriter", ".uno:FontDialog"),
    "insert-image": ("swriter", ".uno:InsertGraphic"),
    "spelling": ("swriter", ".uno:SpellingAndGrammarDialog"),
}
# no update check: its modal dialog would interrupt the shots
NO_PROMPTS = [("/org.openoffice.Office.HSTUpdate", "AutoCheck", "false"),
              ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")]
