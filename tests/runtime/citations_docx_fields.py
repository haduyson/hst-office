# SPDX-License-Identifier: AGPL-3.0-only
"""Read the complex fields of a .docx with the standard library only (no office code).

This is what another word processor sees: for each w:fldChar begin/separate/end group, the field
code (the joined w:instrText) and the result text shown to the reader, per document part, in
part order. Nested fields are supported; an outer result includes the inner results. Used by
tests/runtime/check-citations-fieldmarks.py and tested offline by
tests/unit/test_citations_docx_fields.py.
"""
import re
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# A text box is written twice, as DrawingML and as a VML fallback; a reader uses one of them.
FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
PART_ORDER = ("word/document.xml", "word/footnotes.xml", "word/endnotes.xml")
HEADER_PART = re.compile(r"word/(header|footer)\d*\.xml$")


class DocxField:
    def __init__(self, part):
        self.part, self.in_result, self._code, self._result = part, False, [], []
        self.paragraphs = 0  # paragraph ends inside the result: >0 for a multi-paragraph field

    @property
    def code(self):  # pieces are joined once: Word splits a long code into thousands of w:instrText runs
        return "".join(self._code)

    @property
    def result(self):
        return "".join(self._result)

    def as_dict(self):
        return {"part": self.part, "code": self.code.strip(), "result": self.result,
                "paragraphs": self.paragraphs + 1}


def fields_in_xml(data, part="word/document.xml"):
    """[DocxField] of one part, in document order (a field is listed where it begins)."""
    stack, order, fallback = [], [], 0
    for event, elem in ET.iterparse(_as_stream(data), events=("start", "end")):
        tag = elem.tag
        if tag == FALLBACK:
            fallback += 1 if event == "start" else -1
            continue
        if fallback:
            continue
        if event == "start" and tag == W + "fldChar":
            kind = elem.get(W + "fldCharType")
            if kind == "begin":
                field = DocxField(part)
                stack.append(field)
                order.append(field)
            elif kind == "separate" and stack:
                stack[-1].in_result = True
            elif kind == "end" and stack:
                stack.pop()
        elif event == "end" and tag == W + "instrText" and stack and not stack[-1].in_result:
            stack[-1]._code.append(elem.text or "")
        elif event == "end" and tag in (W + "t", W + "tab", W + "br"):
            piece = (elem.text or "") if tag == W + "t" else ("\t" if tag == W + "tab" else "\n")
            for field in stack:
                if field.in_result:
                    field._result.append(piece)
        elif event == "end" and tag == W + "p":
            for field in stack:
                if field.in_result:
                    field._result.append("\n")
                    field.paragraphs += 1
    return order  # an unterminated field is still listed, with what was read of it


def _as_stream(data):
    import io
    return io.BytesIO(data if isinstance(data, bytes) else data.encode("utf-8"))


def docx_fields(path):
    """[dict(part, code, result, paragraphs)] of every complex field in a .docx."""
    out = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        parts = [p for p in PART_ORDER if p in names] + sorted(p for p in names if HEADER_PART.match(p))
        for part in parts:
            out.extend(f.as_dict() for f in fields_in_xml(archive.read(part), part))
    return out


def visible_text(path, part="word/document.xml"):
    """All w:t text of a part with paragraph breaks: what a reader of the document sees."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read(part))
    lines = []
    for para in root.iter(W + "p"):
        lines.append("".join(t.text or "" for t in para.iter(W + "t")))
    return "\n".join(lines)
