# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Pages of a merged document, for check-mail-merge-word.py: one page per recipient, as Word gives, on screen, in a
PDF export and on paper (printed to a file). Each recipient restarts the page numbering at 1; Writer would add a
blank page before recipients 2 and 3, the HST mail merge marks its results so that it does not (and does not print
blank pages either)."""
import os
import re
import sys


def pdf_pages(data):
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", data))


def printed_pages(data):
    """Pages of a print file: PostScript (Linux generic printer) or PDF (Windows "Microsoft Print to PDF")."""
    if data.startswith(b"%PDF"):
        return pdf_pages(data)
    return len(re.findall(rb"^%%Page: ", data, re.M))


def check(merged, out, expect, recipients):
    import uno
    from com.sun.star.beans import PropertyValue

    def prop(name, value):
        return PropertyValue(Name=name, Value=value)
    expect("pages: one page per recipient on screen", merged.CurrentController.PageCount, recipients)
    pdf = os.path.join(out, "tron-thu.pdf")
    merged.storeToURL(uno.systemPathToFileUrl(pdf), (prop("FilterName", "writer_pdf_Export"),))
    with open(pdf, "rb") as handle:
        expect("pages: PDF export of the merged document", pdf_pages(handle.read()), recipients)
    printed = os.path.join(out, "tron-thu.prn")
    try:
        if sys.platform == "win32":  # a printer that writes a file; Linux uses the office's generic printer
            merged.setPrinter((prop("Name", "Microsoft Print to PDF"),))
        merged.print((prop("FileName", uno.systemPathToFileUrl(printed)), prop("Wait", True)))
        with open(printed, "rb") as handle:
            sheets = printed_pages(handle.read())
    except Exception as error:  # noqa: BLE001 - recorded as the check's result
        sheets = "%s: %s" % (type(error).__name__, error)
    expect("pages: sheets printed to a file", sheets, recipients)
