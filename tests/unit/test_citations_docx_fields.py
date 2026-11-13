# SPDX-License-Identifier: AGPL-3.0-only
"""tests/runtime/citations_docx_fields.py: reading complex fields from .docx XML the way another
word processor does (code from w:instrText, result from the text between separate and end)."""
import os
import sys
import tempfile
import unittest
import zipfile

from _paths import ROOT

sys.path.insert(0, os.path.join(ROOT, "tests", "runtime"))
import citations_docx_fields as reader  # noqa: E402

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"')


def run(inner):
    return f"<w:r>{inner}</w:r>"


def begin():
    return run('<w:fldChar w:fldCharType="begin"/>')


def instr(text):
    return run(f'<w:instrText xml:space="preserve">{text}</w:instrText>')


def sep():
    return run('<w:fldChar w:fldCharType="separate"/>')


def end():
    return run('<w:fldChar w:fldCharType="end"/>')


def text(value):
    return run(f'<w:t xml:space="preserve">{value}</w:t>')


def document(*paragraphs):
    body = "".join(f"<w:p>{p}</w:p>" for p in paragraphs)
    return f'<w:document {NS}><w:body>{body}</w:body></w:document>'


CODE = 'ADDIN HST_CITATION {&quot;citationID&quot;:&quot;c1&quot;,&quot;t&quot;:&quot;Tên &amp; ăâđ&quot;}'


class FieldsInXml(unittest.TestCase):
    def test_simple_field_code_split_over_runs(self):
        xml = document(text("Theo ") + begin() + instr("ADDIN HST_CITATION ") + instr('{"citationID":"c1"}')
                       + sep() + text("[1]") + end() + text(" sau."))
        fields = reader.fields_in_xml(xml)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].as_dict(), {"part": "word/document.xml", "paragraphs": 1,
                                               "code": 'ADDIN HST_CITATION {"citationID":"c1"}', "result": "[1]"})

    def test_escaped_unicode_code(self):
        fields = reader.fields_in_xml(document(begin() + instr(CODE) + sep() + text("x") + end()))
        self.assertEqual(fields[0].code, 'ADDIN HST_CITATION {"citationID":"c1","t":"Tên & ăâđ"}')

    def test_multi_paragraph_result(self):
        xml = document(begin() + instr("ADDIN HST_BIBLIOGRAPHY") + sep() + text("[1] Một."),
                       text("[2] Hai."), text("[3] Ba.") + end(), text("Sau danh mục."))
        field = reader.fields_in_xml(xml)[0].as_dict()
        self.assertEqual(field["result"], "[1] Một.\n[2] Hai.\n[3] Ba.")
        self.assertEqual(field["paragraphs"], 3)

    def test_nested_field_listed_where_it_begins(self):
        xml = document(begin() + instr("OUTER") + sep() + text("a ") + begin() + instr("INNER") + sep()
                       + text("b") + end() + text(" c") + end())
        fields = [f.as_dict() for f in reader.fields_in_xml(xml)]
        self.assertEqual([f["code"] for f in fields], ["OUTER", "INNER"])
        self.assertEqual([f["result"] for f in fields], ["a b c", "b"])

    def test_vml_fallback_copy_is_ignored(self):
        box = begin() + instr("ADDIN HST_CITATION frame") + sep() + text("[f]") + end()
        alternate = (f"<w:r><mc:AlternateContent><mc:Choice Requires=\"wps\"><w:p>{box}</w:p></mc:Choice>"
                     f"<mc:Fallback><w:p>{box}</w:p></mc:Fallback></mc:AlternateContent></w:r>")
        fields = reader.fields_in_xml(document(alternate))
        self.assertEqual([f.code for f in fields], ["ADDIN HST_CITATION frame"])

    def test_unterminated_field_is_still_listed(self):
        fields = reader.fields_in_xml(document(begin() + instr("ADDIN HST_CITATION x") + sep() + text("[1]")))
        self.assertEqual([(f.code, f.result) for f in fields], [("ADDIN HST_CITATION x", "[1]\n")])


class DocxFile(unittest.TestCase):
    def test_parts_in_order_and_visible_text(self):
        main = document(text("Thân ") + begin() + instr("ADDIN HST_CITATION a") + sep() + text("[1]") + end())
        notes = f'<w:footnotes {NS}><w:footnote><w:p>{begin()}{instr("ADDIN HST_CITATION b")}{sep()}' \
                f'{text("[2]")}{end()}</w:p></w:footnote></w:footnotes>'
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.docx")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", main)
                archive.writestr("word/footnotes.xml", notes)
            fields = reader.docx_fields(path)
            self.assertEqual([(f["part"], f["code"], f["result"]) for f in fields],
                             [("word/document.xml", "ADDIN HST_CITATION a", "[1]"),
                              ("word/footnotes.xml", "ADDIN HST_CITATION b", "[2]")])
            self.assertEqual(reader.visible_text(path), "Thân [1]")


if __name__ == "__main__":
    unittest.main()
