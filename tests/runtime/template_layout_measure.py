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


def horizontal_lines(pdf, page):
    """Horizontal stroked lines longer than 3 mm on `page` (1-based), as (x0, x1, y centre, top edge) in mm, read from
    poppler's SVG output (pdftocairo). A missing tool or unreadable PDF raises: the checks never pass without it."""
    svg = subprocess.run(["pdftocairo", "-svg", "-f", str(page), "-l", str(page), pdf, "-"], capture_output=True, text=True,
                         timeout=120, check=True).stdout.split("</defs>", 1)[-1]
    found = []
    for attrs in STROKE.findall(svg):
        a = dict(ATTR.findall(attrs))
        points = re.fullmatch(r"\s*M ([\d.-]+) ([\d.-]+) L ([\d.-]+) ([\d.-]+)\s*", a.get("d", ""))
        if a.get("stroke", "none") == "none" or not points:
            continue
        x0, y0, x1, y1 = (float(v) for v in points.groups())
        m = [float(v) for v in re.findall(r"[\d.e-]+", a.get("transform", "matrix(1,0,0,1,0,0)"))]
        if y0 != y1:
            continue
        left, right = sorted(((m[0] * x + m[2] * y0 + m[4]) * MM for x in (x0, x1)))
        if right - left < 3:
            continue
        centre = (m[1] * x0 + m[3] * y0 + m[5]) * MM
        found.append((round(left, 2), round(right, 2), round(centre, 2), round(centre - float(a.get("stroke-width", 0)) * abs(m[3]) / 2 * MM, 2)))
    return sorted(found, key=lambda r: r[2])


def top_rule(pdf, page):
    """Top edge (mm) of the highest horizontal line on `page`, or None: the top rule of a ruled table that opens a page
    is where its body starts, its first glyph sits below the rule and the cell padding."""
    lines = horizontal_lines(pdf, page)
    return min(r[3] for r in lines) if lines else None


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
    """Baseline distance between the 'Số' word and the 'ngày' of the date on the first page that has both (page 1, or
    the page of a copy's own header at the end of the document), or None when no page has them."""
    for words in words_by_page(pdf):
        number, date = _line_of(words, "Số"), next((w for w in words if w["text"] == "ngày" and w["x0"] > 90), None)
        if number is not None and date is not None:
            return round(abs(baseline(number) - baseline(date)), 2)
    return None


def text_lines(pdf, page=1, gap_mm=3.0):
    """Text lines of `page` (1-based) as {'text', 'x0', 'y0', 'x1', 'y1'} in mm, built from words: words on one baseline
    farther apart than `gap_mm` belong to different columns (pdftotext -bbox-layout joins the two header columns)."""
    words = sorted(words_by_page(pdf)[page - 1], key=lambda w: (round(w["y1"], 1), w["x0"]))
    lines = []
    for w in words:
        last = lines[-1] if lines else None
        if last and abs(last["y1"] - w["y1"]) < 0.3 and 0 <= w["x0"] - last["x1"] < gap_mm:
            last.update(text=last["text"] + " " + w["text"], x1=w["x1"], y0=min(last["y0"], w["y0"]))
        else:
            lines.append(dict(w))
    return lines
