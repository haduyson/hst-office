# SPDX-License-Identifier: AGPL-3.0-only
"""Measurements of the multi-page template check, read from the exported files only (poppler and the DOCX XML).

`pdf_problems` judges margins, page numbers, repeated header blocks, blank pages, contact details and fonts on every
page; `docx_problems` judges the section properties Word lays out from; `drift` compares two renderings of one document.
"""
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

MM = 72 / 25.4
TW = 1440 / 25.4
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def pdf_lines(path):
    """[[{'text', 'x0', 'y0', 'x1', 'y1'} in mm]] per page, from pdftotext -bbox-layout."""
    out = subprocess.run(["pdftotext", "-bbox-layout", path, "-"], capture_output=True, text=True, timeout=120, check=True).stdout
    pages = []
    for page in re.findall(r"<page .*?</page>", out, re.S):
        lines = []
        for attrs, body in re.findall(r"<line ([^>]*)>(.*?)</line>", page, re.S):
            box = dict(re.findall(r'(\w+)="([\d.]+)"', attrs))
            text = " ".join(w for w in re.findall(r"<word [^>]*>(.*?)</word>", body))
            text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
            lines.append({"text": text, "x0": float(box["xMin"]) / MM, "y0": float(box["yMin"]) / MM, "x1": float(box["xMax"]) / MM, "y1": float(box["yMax"]) / MM})
        pages.append(lines)
    return pages


def pdf_fonts(path):
    out = subprocess.run(["pdffonts", path], capture_output=True, text=True, timeout=60, check=True).stdout.splitlines()[2:]
    return sorted({line.split()[0].split("+")[-1] for line in out if line.strip()})


def attached_starts(pages, rules):
    return [k + 1 for k, lines in enumerate(pages) if k and any(h in ln["text"] for ln in lines for h in rules["headerTexts"])]


def pdf_problems(path, profile, rules, attached=False):
    """Problems of one PDF, each 'pN: ...'; also returns per-page facts."""
    p = rules["profiles"][profile]
    m, tol = p["marginsMm"], rules["toleranceMm"]
    pages = pdf_lines(path)
    starts = attached_starts(pages, rules) if attached else []
    problems, facts, expected = [], [], 0
    for k, lines in enumerate(pages, 1):
        first = k == 1 or k in starts
        expected = 1 if k in starts else expected + 1
        numbers = [ln for ln in lines if ln["y1"] <= m["top"][0] + 0.5 and re.fullmatch(r"\d+", ln["text"].strip())]
        body = [ln for ln in lines if ln not in numbers]
        fact = {"page": k}
        if first and numbers:
            problems.append("p%d: page number on a first page" % k)
        if not first:
            if len(numbers) != 1:
                problems.append("p%d: %d page numbers in the top margin" % (k, len(numbers)))
            else:
                n = numbers[0]
                centre, wanted = (n["x0"] + n["x1"]) / 2, (m["left"][0] + 210 - m["right"][0]) / 2
                fact["number"] = [int(n["text"]), round(centre, 2), round(n["y0"], 2)]
                if int(n["text"]) != expected:
                    problems.append("p%d: page number %s, expected %d" % (k, n["text"], expected))
                if abs(centre - wanted) > 1.0:
                    problems.append("p%d: page number centred at %.2f mm, text area centre %.2f" % (k, centre, wanted))
                if "pageNumberTopMm" in p and not p["pageNumberTopMm"][0] <= n["y0"] <= p["pageNumberTopMm"][1]:
                    problems.append("p%d: page number %.2f mm from the top edge" % (k, n["y0"]))
        footer = []
        if k == 1 and profile in rules["contactOnFirstPage"]:
            footer = [ln for ln in body if rules["contactText"] in ln["text"] and ln["y0"] >= 297 - m["bottom"][0] - 0.5]
            body = [ln for ln in body if ln not in footer]
        if not body:
            problems.append("p%d: blank page" % k)
            facts.append(fact)
            continue
        ext = {"left": min(ln["x0"] for ln in body), "right": 210 - max(ln["x1"] for ln in body),
               "top": min(ln["y0"] for ln in body), "bottom": 297 - max(ln["y1"] for ln in body)}
        fact["extent"] = {s: round(v, 2) for s, v in ext.items()}
        for side in ("left", "right", "top", "bottom"):
            if ext[side] < m[side][0] - tol:
                problems.append("p%d: text %.2f mm from the %s edge, margin %s mm" % (k, ext[side], side, m[side][0]))
        # a full-width body line at the top of a page shows where the body frame starts (space above a signature does not)
        top_line = min(body, key=lambda ln: ln["y0"])
        full = abs(top_line["x0"] - m["left"][0]) < 1.0 and top_line["x1"] > 210 - m["right"][0] - 3
        if not first and full and top_line["y0"] > m["top"][1] + 2.0:
            problems.append("p%d: body starts %.2f mm from the top edge" % (k, top_line["y0"]))
        if not first and any(h in ln["text"] for ln in body for h in rules["headerTexts"]):
            problems.append("p%d: header block repeated" % k)
        facts.append(fact)
    whole = ["\n".join(ln["text"] for ln in lines) for lines in pages]
    contact = [k for k, t in enumerate(whole, 1) if rules["contactText"] in t]
    if contact and profile in rules["contactOnFirstPage"] and contact[0] != 1:
        problems.append("p%d: contact details not on the first page" % contact[0])
    received, names = [k for k, t in enumerate(whole, 1) if "Nơi nhận" in t], [k for k, t in enumerate(whole, 1) if "[Họ và tên]" in t]
    if received and names and not starts and received[-1] != names[-1]:
        problems.append("Nơi nhận on p%d, signer name on p%d" % (received[-1], names[-1]))
    for font in pdf_fonts(path):
        if not font.replace("-", "").startswith(tuple(rules["fonts"])):
            problems.append("font %s is not Times New Roman or its metric substitute" % font)
    return problems, {"pages": len(pages), "attachedStarts": starts, "perPage": facts}


def drift(a, b, ignore=()):
    """Largest vertical shift (mm) of a line that occurs once on the same page in both PDFs."""
    worst = (0.0, "")
    for k, (pa, pb) in enumerate(zip(pdf_lines(a), pdf_lines(b)), 1):
        ya = {t: y for t, y in _unique(pa).items() if not any(i in t for i in ignore)}
        yb = _unique(pb)
        for text, y in ya.items():
            if text in yb and abs(yb[text] - y) > worst[0]:
                worst = (round(abs(yb[text] - y), 1), "p%d %s" % (k, text[:30]))
    return worst


def _unique(lines):
    seen, out = set(), {}
    for ln in lines:
        t = ln["text"].strip()
        if t in seen:
            out.pop(t, None)
        elif t:
            seen.add(t)
            out[t] = ln["y1"]
    return out


def docx_problems(path, profile, rules):
    """Section properties Word lays out from: A4, margins, gutter, first page without number, PAGE field size."""
    m = rules["profiles"][profile]["marginsMm"]
    lo, hi = rules["profiles"][profile]["pageNumberPt"]
    z = zipfile.ZipFile(path)
    doc = ET.fromstring(z.read("word/document.xml"))
    target = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("word/_rels/document.xml.rels"))}
    styles = ET.fromstring(z.read("word/styles.xml"))
    problems = []
    for index, sect in enumerate(doc.iter(W + "sectPr"), 1):
        size, mar = sect.find(W + "pgSz"), sect.find(W + "pgMar")
        if (size.get(W + "w"), size.get(W + "h")) != ("11906", "16838"):
            problems.append("section %d: page is not A4 portrait" % index)
        if int(mar.get(W + "gutter", "0")):
            problems.append("section %d: gutter" % index)
        for side in ("top", "bottom", "left", "right"):
            value = int(mar.get(W + side)) / TW
            if not m[side][0] - 0.05 <= value <= m[side][1] + 0.05:
                problems.append("section %d: w:%s %.2f mm" % (index, side, value))
        heads = {h.get(W + "type"): ET.fromstring(z.read("word/" + target[h.get(R + "id")])) for h in sect.findall(W + "headerReference")}
        if "default" in heads:
            title = sect.find(W + "titlePg")
            if title is None or title.get(W + "val", "true") in ("false", "0"):
                problems.append("section %d: no w:titlePg, Word shows the number on page 1" % index)
            if "first" in heads and "PAGE" in _instr(heads["first"]):
                problems.append("section %d: first-page header shows the number" % index)
            if "PAGE" not in _instr(heads["default"]):
                problems.append("section %d: no PAGE field in the header" % index)
            size_pt = _header_size(heads["default"], styles)
            if size_pt is not None and not lo <= size_pt <= hi:
                problems.append("section %d: page number %.1f pt" % (index, size_pt))
            if int(mar.get(W + "header")) / TW > int(mar.get(W + "top")) / TW - 5:
                problems.append("section %d: header distance leaves under 5 mm above the body" % index)
    return problems


def _instr(header):
    return "".join(t.text or "" for t in header.iter(W + "instrText")) + " ".join(f.get(W + "instr", "") for f in header.iter(W + "fldSimple"))


def _header_size(header, styles):
    sizes = [x.get(W + "val") for x in header.iter(W + "sz")]
    if sizes:
        return int(sizes[0]) / 2
    style = header.find(".//" + W + "pStyle")
    if style is None:
        return None
    for s in styles.iter(W + "style"):
        if s.get(W + "styleId") == style.get(W + "val"):
            sz = s.find(".//" + W + "sz")
            return int(sz.get(W + "val")) / 2 if sz is not None else None
    return None
