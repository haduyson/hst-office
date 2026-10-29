"""Print a JSON summary of a saved DOCX/XLSX/PPTX for runtime assertions.

Usage: python3 scripts/runtime/inspect-ooxml.py <file>
Reads the package with zipfile + regular expressions only (no third-party
parser) so it also works on files python-docx refuses to open.
"""
import json
import re
import sys
import zipfile


def docx_summary(archive):
    xml = archive.read("word/document.xml").decode("utf-8")
    sect = re.findall(r"<w:sectPr\b.*?</w:sectPr>", xml, re.S)
    last = sect[-1] if sect else ""
    pg_size = dict(re.findall(r'w:(w|h)="(\d+)"', (re.search(r"<w:pgSz[^>]*>", last) or [""])[0]))
    pg_mar = dict(re.findall(r'w:(top|bottom|left|right)="(\d+)"', (re.search(r"<w:pgMar[^>]*>", last) or [""])[0]))
    return {
        "text": "".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml)),
        "pageTwips": {k: int(v) for k, v in pg_size.items()},
        "marginsTwips": {k: int(v) for k, v in pg_mar.items()},
        "tables": len(re.findall(r"<w:tbl>", xml)),
        "fonts": sorted(set(re.findall(r'w:ascii="([^"]+)"', xml))),
        "langs": sorted(set(re.findall(r'<w:lang w:val="([^"]+)"', xml))),
    }


def main(path):
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        names = archive.namelist()
        summary = {"zipOk": bad is None, "parts": len(names)}
        if "word/document.xml" in names:
            summary.update(docx_summary(archive))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
