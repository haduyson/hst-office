# SPDX-License-Identifier: AGPL-3.0-only
"""check-ui-po-runs.py judges an added UI.po entry by its neighbour: a known comment hash, the source marker or the
neighbour's "#: <file>.xcu" reference line (HST hashes repeat across files, so they are not trusted)."""
import importlib.util
import os
import tempfile
import unittest

from _paths import ROOT

_spec = importlib.util.spec_from_file_location("check_ui_po_runs", os.path.join(ROOT, "scripts", "l10n", "check-ui-po-runs.py"))
runs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runs)

ENTRY = ['+#. hstNEW', '+#: GenericCommands.xcu', '+msgctxt ""', '+"GenericCommands.xcu\\n"',
         '+"..GenericCommands.UserInterface.Commands..uno:HstNew\\n"', '+"Label\\n"', '+"value.text"',
         '+msgid "New"', '+msgstr "Mới"', '+']


def patch(after_reference):
    lines = ["--- a/" + runs.UI_PO, "+++ b/" + runs.UI_PO, "@@ -10,3 +10,13 @@", ' msgstr "x"', " "] + ENTRY
    lines += [" #. hstOTHER", " #: " + after_reference, ' msgctxt ""']
    return "\n".join(lines) + "\n"


class Neighbour(unittest.TestCase):
    def replay(self, text):
        with tempfile.TemporaryDirectory() as work:
            with open(os.path.join(work, "series"), "w", encoding="utf-8") as handle:
                handle.write("p.patch\n")
            with open(os.path.join(work, "p.patch"), "w", encoding="utf-8") as handle:
                handle.write(text)
            return runs.replay({}, work)

    def test_an_entry_beside_its_own_files_reference_line_passes(self):
        self.assertEqual(self.replay(patch("GenericCommands.xcu")), [])

    def test_an_entry_beside_another_files_reference_line_fails(self):
        problems = self.replay(patch("CalcCommands.xcu"))
        self.assertEqual(len(problems), 1)
        self.assertIn("beside CalcCommands.xcu", problems[0])


if __name__ == "__main__":
    unittest.main()
