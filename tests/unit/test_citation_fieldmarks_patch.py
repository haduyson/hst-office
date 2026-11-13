# SPDX-License-Identifier: AGPL-3.0-only
"""hst-citation-fieldmarks.patch: citation fields (UNHANDLED text fieldmarks carrying their code
as a parameter) keep the code through Undo/Redo, field updates undo the code with the result,
Backspace/Delete next to such a field selects it instead of unwrapping it, and .odt reload keeps
fields in footnotes, endnotes and frames. Offline: reads the patch hunks; the behaviour is
checked on a build by tests/runtime/check-citations-fieldmarks.py."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "patches/libreoffice"
PATCH = PATCHES / "hst-citation-fieldmarks.patch"
FILES = {
    "sw/source/core/inc/rolbck.hxx", "sw/source/core/undo/rolbck.cxx",
    "sw/source/core/inc/UndoBookmark.hxx", "sw/source/core/undo/unbkmk.cxx",
    "sw/source/uibase/shells/textfld.cxx", "sw/source/uibase/wrtsh/delete.cxx",
    "xmloff/source/text/XMLTextMarkImportContext.cxx",
}


def added_lines():
    """{path: [added lines]} of the unified diff."""
    out, current = {}, None
    for line in PATCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            current = out.setdefault(line[6:], [])
        elif current is not None and line.startswith("+"):
            current.append(line[1:])
    return out


class CitationFieldmarksPatch(unittest.TestCase):
    def setUp(self):
        self.added = added_lines()

    def text(self, path):
        return "\n".join(self.added[path])

    def test_in_series_once_and_licensed(self):
        series = [n for n in (PATCHES / "series").read_text(encoding="utf-8").splitlines()
                  if n and not n.startswith("#")]
        self.assertEqual(series.count(PATCH.name), 1)
        self.assertIn("License: modified upstream files keep their license (MPL-2.0).",
                      PATCH.read_text(encoding="utf-8"))

    def test_touches_only_the_expected_files(self):
        self.assertEqual(set(self.added), FILES)

    def test_history_keeps_parameters(self):
        self.assertIn("m_aParameters;", self.text("sw/source/core/inc/rolbck.hxx"))
        cxx = self.text("sw/source/core/undo/rolbck.cxx")
        self.assertIn("m_aParameters(*rFieldMark.GetParameters())", cxx)  # recorded
        self.assertIn("*pFieldmark->GetParameters() = m_aParameters;", cxx)  # restored by SetInDoc
        self.assertIn("m_aParameters = *pFieldmark->GetParameters();", cxx)  # refreshed by ResetInDoc

    def test_update_commands_undo_the_code(self):
        self.assertIn("class SwUndoTextFieldmarkParameters final : public SwUndo",
                      self.text("sw/source/core/inc/UndoBookmark.hxx"))
        undo = self.text("sw/source/core/undo/unbkmk.cxx")
        self.assertIn("SetParameters(rContext.GetDoc(), m_aOldParameters);", undo)
        self.assertIn("SetParameters(rContext.GetDoc(), m_aNewParameters);", undo)
        textfld = self.text("sw/source/uibase/shells/textfld.cxx")
        # both .uno:TextFormFields and .uno:UpdateTextFormField record the code change
        self.assertEqual(textfld.count("std::make_unique<SwUndoTextFieldmarkParameters>"), 2)
        self.assertEqual(textfld.count("GetIDocumentUndoRedo().DoesUndo()"), 2)

    def test_backspace_and_delete_select_unhandled_fields(self):
        delete = self.text("sw/source/uibase/wrtsh/delete.cxx")
        self.assertEqual(delete.count("pFm->GetFieldname() == ODF_UNHANDLED"), 2)
        self.assertIn("lcl_SelectWholeFieldmark(*this, *pFm, false);", delete)  # Backspace
        self.assertIn("lcl_SelectWholeFieldmark(*this, *pFm, true);", delete)  # Delete

    def test_odt_import_checks_text_by_position(self):
        xmloff = self.text("xmloff/source/text/XMLTextMarkImportContext.cxx")
        self.assertIn("createTextCursorByRange(xRange)", xmloff)
        self.assertIn("if (lcl_IsInHelperText(rHelper, xField->getAnchor()))", xmloff)


if __name__ == "__main__":
    unittest.main()
