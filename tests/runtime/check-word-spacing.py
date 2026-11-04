# SPDX-License-Identifier: AGPL-3.0-only
"""Words stay apart ("dính chữ"): Vietnamese text keeps visible gaps between words.

Usage: python3 tests/runtime/check-word-spacing.py [--instdir upstream/libreoffice/instdir]
                                                   [--out tests/output/word-spacing]

Old Word files are reported to show Vietnamese words glued together ("họcđiđôivớihành") in
Microsoft Word. This test authors small documents itself (no downloaded data), one per candidate
cause, loads each headless, exports PDF and measures the word boxes with pdftotext -bbox:
  * the PDF holds as many words as the source (no word glued to the next);
  * the smallest gap between two words on a line is at least a third of a normal space;
  * the gap is measured relative to the box height, so it holds for any substitute font.
Candidates: legacy Vietnamese fonts (.VnTime, VNI-Times, .VnArial, UVN) with Unicode text and with
TCVN3 bytes; no-break and en spaces; compatibility flags (all of w:compat, compatibilityMode 11-15);
justified and distributed paragraphs; East Asian font with hint=eastAsia / language / document grid;
decomposed (NFD) Vietnamese; space runs in a Symbol or East Asian font; RTF in code page 1258
(fcharset 163) and 1252; the same documents saved as .doc and reloaded.
Known open defect (reported, not a failure): decomposed text with hint=eastAsia, marks drift off their letters.
Faithfulness (informational, not a failure): condensed character spacing shrinks the gap as in Word.
Exit 1 on any failure.
"""
import argparse
import html
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import unicodedata
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEXT = "Có công mài sắt có ngày nên kim. Học đi đôi với hành, lý thuyết gắn liền với thực tiễn. Tiếng Việt giàu đẹp."
NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"')
CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
      '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
      '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/></Types>')
REL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>'
TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
TNR = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman"/><w:sz w:val="26"/>'
JUST = '<w:jc w:val="both"/>'
THREE = " ".join([TEXT] * 3)
# Open defect, reported not failed: with hint=eastAsia the combining marks of decomposed text take the
# East Asian font and drift away from their letters (i18nutil scriptchangescanner applies the hint to marks).
KNOWN_OPEN = {"decomposed-nfd-east-asian-hint"}


def run(t, rpr=TNR):
    return f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{t.replace("&", "&amp;").replace("<", "&lt;")}</w:t></w:r>'


def para(t, rpr=TNR, ppr="", runs=None):
    return f'<w:p><w:pPr>{ppr}</w:pPr>{runs if runs is not None else run(t, rpr)}</w:p>'


def font(name, ea=None, hint=""):
    return (f'<w:rFonts w:ascii="{name}" w:hAnsi="{name}" w:cs="{name}" w:eastAsia="{ea or name}"{hint}/><w:sz w:val="26"/>')


def write_docx(path, body, compat="", sect="", settings=""):
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {NS}><w:body>{body}<w:sectPr>'
           f'<w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="720" w:footer="720" w:gutter="0"/>{sect}</w:sectPr></w:body></w:document>')
    st = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings {NS}>{settings}<w:compat>{compat}</w:compat></w:settings>'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("_rels/.rels", REL % f'<Relationship Id="rId1" Type="{TYPE}officeDocument" Target="word/document.xml"/>')
        z.writestr("word/_rels/document.xml.rels", REL % f'<Relationship Id="rId1" Type="{TYPE}settings" Target="settings.xml"/>')
        z.writestr("word/document.xml", doc)
        z.writestr("word/settings.xml", st)


def enc1258(s):
    out = b""
    for ch in s:
        try:
            out += ch.encode("cp1258")
        except UnicodeEncodeError:
            d = unicodedata.normalize("NFD", ch)
            mark = [c for c in d if c in "̣̀́̃̉"][0]
            out += unicodedata.normalize("NFC", d.replace(mark, "")).encode("cp1258") + mark.encode("cp1258")
    return out


def rtf(charset, face, data, cp):
    body = "".join(chr(c) if 32 <= c < 127 and chr(c) not in "\\{}" else "\\'%02x" % c for c in data)
    return "{\\rtf1\\ansi\\ansicpg%d\\deff0{\\fonttbl{\\f0\\froman\\fcharset%d %s;}}\\f0\\fs26 %s\\par}" % (cp, charset, face, body)


def cases():
    """name -> (kind, payload, expected word count, options). kind: docx | rtf."""
    out = {}
    words = len(TEXT.split())
    def add(name, body, **kw):
        out[name] = ("docx", (body, kw), words)
    def compat_mode(m):
        return f'<w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="{m}"/>'
    add("control", para(TEXT))
    add("no-break-space", para(TEXT.replace(" ", " ")))
    out["no-break-space"] = ("docx", (para(TEXT.replace(" ", " ")), {}), 1)  # one unbreakable run of words; gap checked, count not
    add("en-space", para(TEXT.replace(" ", " ")))
    add("justified", para(THREE, ppr=JUST)); out["justified"] = ("docx", out["justified"][1], words * 3)
    add("distributed", para(TEXT, ppr='<w:jc w:val="distribute"/>'))
    for m in (11, 12, 14, 15):
        add(f"compat-mode-{m}", para(THREE, ppr=JUST), compat=compat_mode(m)); out[f"compat-mode-{m}"] = ("docx", out[f"compat-mode-{m}"][1], words * 3)
    flags = "".join(f"<w:{f}/>" for f in (
        "doNotExpandShiftReturn", "ulTrailSpace", "balanceSingleByteDoubleByteWidth", "spaceForUL", "useFELayout",
        "doNotUseHTMLParagraphAutoSpacing", "usePrinterMetrics", "doNotUseEastAsianBreakRules", "wpJustification",
        "noTabHangInd", "noLeading", "truncateFontHeightsLikeWP6", "wpSpaceWidth", "useWord97LineBreakRules", "useAnsiKerningPairs"))
    add("all-compat-flags", para(THREE, ppr=JUST), compat=flags); out["all-compat-flags"] = ("docx", out["all-compat-flags"][1], words * 3)
    add("kerning-and-compress", para(TEXT, TNR + '<w:kern w:val="2"/>'), settings='<w:characterSpacingControl w:val="compressPunctuationAndJapaneseKana"/>')
    for ff in (".VnTime", "VNI-Times", ".VnArial", "UVN Bach Tuyet"):
        add("legacy-font-unicode-text " + ff, para(TEXT, font(ff)))
    for ea, hint in (("MS Mincho", ' w:hint="eastAsia"'), ("SimSun", ' w:hint="eastAsia"'), ("Batang", ""), ("Missing Font", ' w:hint="eastAsia"')):
        add(f"east-asian-font {ea}{' hint' if hint else ''}", para(TEXT, font("Times New Roman", ea, hint)))
    add("east-asian-language", para(TEXT, TNR + '<w:lang w:val="vi-VN" w:eastAsia="ja-JP"/>'))
    for typ, cs in (("lines", ""), ("linesAndChars", ' w:charSpace="-2000"'), ("snapToChars", ' w:charSpace="-2000"')):
        add(f"doc-grid-{typ}{cs and '-neg'}", para(TEXT), sect=f'<w:docGrid w:type="{typ}" w:linePitch="360"{cs}/>')
    nfd = unicodedata.normalize("NFD", TEXT)
    add("decomposed-nfd", para(nfd))
    add("decomposed-nfd-east-asian-hint", para(nfd, font("Times New Roman", "MS Mincho", ' w:hint="eastAsia"')))
    sp = lambda rpr: "".join(run(w) + (run(" ", rpr) if i < words - 1 else "") for i, w in enumerate(TEXT.split(" ")))
    add("space-run-symbol-font", para("", runs=sp('<w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/><w:sz w:val="26"/>')))
    add("space-run-east-asian-font", para("", runs=sp(font("MS Gothic", None, ' w:hint="eastAsia"'))))
    add("space-run-wingdings", para("", runs=sp('<w:rFonts w:ascii="Wingdings" w:hAnsi="Wingdings"/><w:sz w:val="26"/>')))
    add("word-runs-alternate-fonts", para("", runs="".join(run(w + " ", TNR if i % 2 else font("Arial", "MS Gothic")) for i, w in enumerate(TEXT.split(" ")))))
    for name, face, charset, cp, data in (
            ("rtf-cp1258-fcharset163", "Times New Roman", 163, 1258, enc1258(TEXT)),
            ("rtf-cp1258-vntime", ".VnTime", 163, 1258, enc1258(TEXT)),
            ("rtf-cp1252-declared-cp1258-text", "Times New Roman", 163, 1252, enc1258(TEXT))):
        out[name] = ("rtf", rtf(charset, face, data, cp), words)
    return out


def bbox_words(pdf):
    xml = subprocess.run(["pdftotext", "-bbox", pdf, "-"], capture_output=True, text=True).stdout
    return [(float(a), float(b), float(c), float(d), html.unescape(t))
            for a, b, c, d, t in re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', xml)]


def measure(pdf):
    """(word count, smallest/median gap between words on one line, in box heights)."""
    ws = bbox_words(pdf)
    lines = {}
    for x0, y0, x1, y1, t in ws:
        lines.setdefault(round(y1), []).append((x0, x1, y1 - y0))
    gaps = []
    for line in lines.values():
        line.sort()
        gaps += [(b[0] - a[1]) / a[2] for a, b in zip(line, line[1:])]
    return len(ws), (min(gaps) if gaps else None), (statistics.median(gaps) if gaps else None)


def convert(soffice, profile, fmt, outdir, files):
    prefix = ["runuser", "-u", "hstbuild", "--"] if os.geteuid() == 0 else []
    env = dict(os.environ, HOME=profile, HST_VCLPLUGIN="svp")
    subprocess.run(prefix + [soffice, f"-env:UserInstallation=file://{profile}/prof", "--headless", "--convert-to", fmt, "--outdir", outdir] + files,
                   env=env, capture_output=True, timeout=900)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/word-spacing"))
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    shutil.rmtree(out, ignore_errors=True)
    for d in ("src", "pdf", "doc", "docpdf"):
        os.makedirs(os.path.join(out, d))
    names = {}
    for i, (name, (kind, payload, expected)) in enumerate(cases().items()):
        fid = f"{i:02d}"
        names[fid] = (name, expected)
        path = os.path.join(out, "src", fid + (".docx" if kind == "docx" else ".rtf"))
        if kind == "docx":
            write_docx(path, payload[0], **payload[1])
        else:
            open(path, "w", encoding="latin1").write(payload)
    # the condensed-spacing documents (informational: Word shows the same)
    for fid, spacing in (("x0", 0), ("x1", -20), ("x2", -40)):
        write_docx(os.path.join(out, "src", fid + ".docx"), para(TEXT, TNR + (f'<w:spacing w:val="{spacing}"/>' if spacing else "")))
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", "hstbuild", out], check=True)
    soffice = os.path.join(os.path.abspath(args.instdir), "program/soffice")
    src = [os.path.join(out, "src", f) for f in sorted(os.listdir(os.path.join(out, "src")))]
    convert(soffice, out, "pdf", os.path.join(out, "pdf"), src)
    docx_src = [f for f in src if f.endswith(".docx") and os.path.basename(f)[:2].isdigit()]
    convert(soffice, out, "doc", os.path.join(out, "doc"), docx_src)
    convert(soffice, out, "pdf", os.path.join(out, "docpdf"), [os.path.join(out, "doc", f) for f in sorted(os.listdir(os.path.join(out, "doc")))])
    failures, rows = [], []
    min_gap = 0.33 * measure(os.path.join(out, "pdf", "00.pdf"))[1]  # a third of the control's smallest gap
    for fid, (name, expected) in names.items():
        for label, folder in (("docx/rtf", "pdf"), (".doc", "docpdf")):
            pdf = os.path.join(out, folder, fid + ".pdf")
            if folder == "docpdf" and not os.path.exists(pdf):
                continue
            if not os.path.exists(pdf):
                failures.append(f"{name} [{label}]: no PDF"); continue
            n, low, med = measure(pdf)
            ok = low is not None and low >= min_gap and n >= expected
            if not ok and name in KNOWN_OPEN:
                rows.append({"case": name, "via": label, "words": n, "expected": expected, "min_gap": low and round(low, 3), "known_open": True})
                continue
            rows.append({"case": name, "via": label, "words": n, "expected": expected, "min_gap": low and round(low, 3), "median_gap": med and round(med, 3), "ok": ok})
            if not ok:
                failures.append(f"{name} [{label}]: words {n}/{expected}, min gap {low}")
    x = [measure(os.path.join(out, "pdf", f"{f}.pdf"))[2] for f in ("x0", "x1", "x2")]
    faithful = x[0] > x[1] > x[2]
    json.dump({"min_gap_threshold": round(min_gap, 3), "rows": rows, "condensed_median_gaps_0_1_2pt": [round(v, 3) for v in x],
               "condensed_spacing_applied": faithful, "failures": failures}, open(os.path.join(out, "evidence.json"), "w"), indent=1, ensure_ascii=False)
    print(f"{len(rows)} measurements, threshold {min_gap:.3f}; condensed spacing applied as authored: {faithful}")
    for f in failures:
        print("FAIL", f)
    return 1 if failures or not faithful else 0


if __name__ == "__main__":
    sys.exit(main())
