# SPDX-License-Identifier: AGPL-3.0-only
"""Shared helpers of the VBA compatibility cases (vba_cases.py: Excel idioms, vba_cases_writer.py: Word idioms).

Each case is one VBA function body run in its own fresh document, in a module that starts with
"Option VBASupport 1" inside a VBA-mode library (what "Macro VBA" creates). The body stores
its answer in `r`; the case passes when `r` equals `want` and the optional `doc` check (Python,
reading the document over UNO) is true.

status "ok" = must pass (a failure fails the check); "limited" = known gap, reported, and a pass
is flagged so the help page and report get updated.
"""

LOGO = "/home/office/assets/brand/hst-office-logo.png"  # readable by the build user
WRITER_TEXT = "Xin chào thế giới. Đây là câu thứ hai.\nĐoạn hai có từ HST và HST.\nĐoạn ba."


def _cell(doc, name):
    return doc.Sheets.getByIndex(0).getCellRangeByName(name)


def _sheet_names(doc):
    return list(doc.Sheets.ElementNames)


def _paragraphs(doc):
    enum = doc.Text.createEnumeration()
    while enum.hasMoreElements():
        yield enum.nextElement()


def _text(doc):
    return doc.Text.String.replace("\r\n", "\n").replace("\r", "\n")


