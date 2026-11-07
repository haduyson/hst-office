# SPDX-License-Identifier: AGPL-3.0-only
"""Measure a rendered PDF of a document (poppler bbox; PyMuPDF for vector rules when installed). All lengths in mm."""
import html
import re
import subprocess

MM = 25.4 / 72
ASCENT, LINE = 0.891, 1.107  # Times New Roman / Liberation Serif: ascent and line box in em
WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')


def words_by_page(pdf):
    out = subprocess.run(["pdftotext", "-bbox", pdf, "-"], capture_output=True, text=True, timeout=120, check=True).stdout
    pages = []
    for chunk in out.split("<page ")[1:]:
        words = [{"x0": float(a) * MM, "y0": float(b) * MM, "x1": float(c) * MM, "y1": float(d) * MM, "text": html.unescape(t)}
                 for a, b, c, d, t in WORD.findall(chunk)]
        pages.append(words)
    return pages


STROKE = re.compile(r'<path ([^>]*?)/>')
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def top_rule(pdf, page):
    """Top edge (mm) of the highest horizontal line drawn on `page` (1-based), or None: the top rule of a ruled table
    that opens a page is where its body starts, its first glyph sits below the rule and the cell padding."""
    svg = subprocess.run(["pdftocairo", "-svg", "-f", str(page), "-l", str(page), pdf, "-"], capture_output=True, text=True,
                         timeout=120, check=True).stdout.split("</defs>", 1)[-1]
    tops = []
    for attrs in STROKE.findall(svg):
        a = dict(ATTR.findall(attrs))
        points = re.fullmatch(r"\s*M ([\d.-]+) ([\d.-]+) L ([\d.-]+) ([\d.-]+)\s*", a.get("d", ""))
        if "stroke" not in a or a.get("stroke") == "none" or not points:
            continue
        x0, y0, x1, y1 = (float(v) for v in points.groups())
        m = [float(v) for v in re.findall(r"[\d.e-]+", a.get("transform", "matrix(1,0,0,1,0,0)"))]
        if y0 != y1 or abs(x1 - x0) * abs(m[0]) * MM < 3:
            continue
        tops.append((m[1] * x0 + m[3] * y0 + m[5] - float(a.get("stroke-width", 0)) * abs(m[3]) / 2) * MM)
    return round(min(tops), 2) if tops else None


def baseline(word):
    size = (word["y1"] - word["y0"]) / LINE
    return word["y0"] + ASCENT * size


def _first_page_footer(words, text, from_mm):
    """The words of page 1 below `from_mm` when they read exactly `text`, else []: only the expected contact line leaves the body."""
    below = sorted((w for w in words if w["y0"] >= from_mm - 0.5), key=lambda w: (round(w["y1"], 1), w["x0"]))
    return below if below and " ".join(w["text"] for w in below) == " ".join(text.split()) else []


def measure(pdf, top_mm=20.0, footer_text=None, footer_from_mm=None):
    """{'pages', 'bodyTop': [per page], 'left', 'right', 'bottom', 'pageNumbers': [(page, text, centre x, y1)], 'footer'}.

    `footer_text`: the contact details an official letter prints in the footer of its first page (Decree 30, Annex I,
    I.III.4), in the bottom margin from `footer_from_mm`. Those words are reported as 'footer' (top, bottom), not body."""
    pages = words_by_page(pdf)
    result = {"pages": len(pages), "bodyTop": [], "pageNumbers": [], "left": 999.0, "right": 0.0, "bottom": 0.0, "footer": None}
    for index, words in enumerate(pages):
        numbers = [w for w in words if w["y1"] < top_mm + 0.5 and re.fullmatch(r"\d+", w["text"])]
        footer = _first_page_footer(words, footer_text, footer_from_mm) if index == 0 and footer_text else []
        if footer:
            result["footer"] = (round(min(w["y0"] for w in footer), 2), round(max(w["y1"] for w in footer), 2))
        body = [w for w in words if w not in numbers and w not in footer]
        result["pageNumbers"] += [(index + 1, w["text"], round((w["x0"] + w["x1"]) / 2, 2), round(w["y1"], 2)) for w in numbers]
        if not body:
            result["bodyTop"].append(None)
            continue
        rule = top_rule(pdf, index + 1)
        result["bodyTop"].append(round(min([w["y0"] for w in body] + ([rule] if rule is not None else [])), 2))
        result["left"] = round(min(result["left"], min(w["x0"] for w in body)), 2)
        result["right"] = round(max(result["right"], max(w["x1"] for w in body)), 2)
        result["bottom"] = round(max(result["bottom"], max(w["y1"] for w in body)), 2)
    return result


def _line_of(words, start):
    index = next((i for i, w in enumerate(words) if w["text"].startswith(start)), None)
    return None if index is None else words[index]


def number_date_offset(pdf):
    """Baseline distance between the 'Số' word and the 'ngày' of the date on page 1, or None when one is absent."""
    words = words_by_page(pdf)[0]
    number, date = _line_of(words, "Số"), next((w for w in words if w["text"] == "ngày" and w["x0"] > 90), None)
    if number is None or date is None:
        return None
    return round(abs(baseline(number) - baseline(date)), 2)


def rules_on_page_one(pdf):
    """Horizontal vector lines on page 1 as (x0, x1, y); [] without PyMuPDF."""
    try:
        import pymupdf
    except ImportError:
        return []
    found = []
    with pymupdf.open(pdf) as doc:
        for drawing in doc[0].get_drawings():
            rect = drawing["rect"]
            if rect.width > 3 and rect.height < 2:
                found.append((round(rect.x0 * MM, 2), round(rect.x1 * MM, 2), round(rect.y0 * MM, 2)))
    return sorted(found, key=lambda r: r[2])


def line_extent(pdf, start, page=0):
    """(x0, x1) of the first text line beginning with `start`, from PyMuPDF; None without it."""
    try:
        import pymupdf
    except ImportError:
        return None
    with pymupdf.open(pdf) as doc:
        for block in doc[page].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line["spans"])
                if text.startswith(start):
                    return line["bbox"][0] * MM, line["bbox"][2] * MM
    return None
