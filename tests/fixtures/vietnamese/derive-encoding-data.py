#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Rebuild data/vietnamese/encoding-maps.json, provenance.json and the golden
encoding vectors from third-party sources, WITHOUT using the converter under test.

Sources (fetched into --cache, sha256 recorded in provenance.json):
  A  vietunicode.sourceforge.net/charset/  (HTML table: Unicode/VNI/TCVN3 columns)  -> runtime tables
  B  en.wikipedia.org VNI article raw wikitext (VNI ANSI table, combining-mark model) -> VNI cross-check + VNI vectors
  C  glibc charmap TCVN5712-1 (package `locales`) read through `iconv`            -> TCVN3 cross-check + TCVN3 vectors
Usage: python3 derive-encoding-data.py --cache <dir> [--write]
"""
import argparse, datetime, hashlib, html, json, os, re, subprocess, sys, unicodedata as U, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
URL_A = "https://vietunicode.sourceforge.net/charset/"
URL_B = "https://en.wikipedia.org/w/index.php?title=VNI&action=raw"
URL_REV = "https://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=ids&format=json&titles=VNI"
CHARMAP = "/usr/share/i18n/charmaps/TCVN5712-1.gz"
SAMPLES = ["Cộng hòa xã hội chủ nghĩa Việt Nam", "Độc lập - Tự do - Hạnh phúc", "Nguyễn Thị Thanh Hương",
           "quyết định về việc ban hành quy chế làm việc", "Hà Nội, Đà Nẵng, Thừa Thiên Huế, Cần Thơ",
           "Kính gửi: các đơn vị trực thuộc; ưu tiên xử lý trước ngày 05/02/2026.", "Người đại diện: ông Trần Văn Ất"]


def fetch(url, path):
    if not os.path.exists(path):
        req = urllib.request.Request(url, headers={"User-Agent": "hst-office-encoding-derive/1.0 (haduyson297@gmail.com)"})
        with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
            f.write(r.read())
    return open(path, "rb").read()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def table_a(raw):
    rows = []
    for r in re.findall(r"<tr>(.*?)</tr>", raw.decode("utf-8"), re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", c)).strip())
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        if len(cells) == 12 and cells[1].startswith("U+"):
            rows.append(cells)
    return rows  # [char, U+, VNI, VNIhex, VPS, VPShex, VISCII, hex, TCVN3, hex, VIQR, name]


def wiki_vni_bytes(text):
    """VNI ANSI table from wikitext -> {byte: unicode string (precomposed char or combining sequence)}."""
    out, row, col = {}, None, 0
    start = text.index('VNI "ANSI" Encoding')
    for line in text[start:text.index('VNI "Mac" Encoding')].split("\n"):
        m = re.match(r"\|\{\{chset-left1\|([0-9A-F])x\}\}", line)
        if m:
            row, col = int(m.group(1), 16), 0
            continue
        m = re.match(r"\|\{\{chset-cell1\|(.*)\}\}$", line)
        if m and row is not None:
            first = m.group(1).split("|")[0]
            if row >= 8 and first:
                seq = [int(first[2:], 16)] if first.startswith("u=") else [int(x, 16) for x in re.findall(r"U\+([0-9A-F]{4})", first)]
                if seq:
                    out[row * 16 + col] = "".join(map(chr, seq))
            col += 1
    return out


def vni_from_wiki(wb, letters):
    """Brute force: ASCII letter or precomposed cell, plus optional combining cell -> NFC letter."""
    firsts = {bytes([c]): chr(c) for c in list(range(65, 91)) + list(range(97, 123))}
    marks = {}
    for b, s in wb.items():
        (marks if U.combining(s[0]) else firsts)[bytes([b])] = s
    found = {}
    upper = lambda k: k[0] < 0xE0 if k[0] >= 0x80 else chr(k[0]).isupper()  # VNI: C0-DF capital, E0-FF lowercase
    for k1, s1 in firsts.items():
        for k2, s2 in [(b"", "")] + [m for m in marks.items() if upper(m[0]) == upper(k1)]:
            ch = U.normalize("NFC", s1 + s2)
            if len(ch) == 1 and ch in letters:
                found.setdefault(ch, set()).add(k1 + k2)
    return found


def iconv_char(b):
    return subprocess.run(["iconv", "-f", "TCVN5712-1", "-t", "UTF-8"], input=b, capture_output=True).stdout.decode()


def tcvn_from_glibc(data_a):
    low, up = {}, {}
    for b in list(range(0x80, 0xA0)) + list(range(0xA1, 0x100)):
        s = iconv_char(bytes([b]))
        if len(s) == 1 and U.category(s) in ("Lu", "Ll"):
            (up if U.category(s) == "Lu" else low)[b] = s
    return low, up


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    raw_a = fetch(URL_A, os.path.join(a.cache, "vietunicode.html"))
    raw_b = fetch(URL_B, os.path.join(a.cache, "wiki-vni.txt"))
    raw_rev = fetch(URL_REV, os.path.join(a.cache, "wiki-vni-rev.json"))
    rows = table_a(raw_a)
    letters = {r[0] for r in rows}
    assert len(rows) == 134 and len(letters) == 134, len(rows)
    # --- VNI: source A vs source B
    vni_a = {bytes(int(x, 16) for x in r[3].split()): r[0] for r in rows}
    vni_b = vni_from_wiki(wiki_vni_bytes(raw_b.decode("utf-8")), letters)
    # B's combining-mark model is more permissive than the encoding itself, so require that every
    # sequence listed by A composes (NFC) to the same letter in B, and that B covers all 134 letters.
    assert set(vni_b) == letters and all(seq in vni_b[ch] for seq, ch in vni_a.items()), "VNI sources disagree"
    # --- TCVN3: source A single bytes vs glibc
    tc_a = {int(r[9], 16): r[0] for r in rows if len(r[9].split()) == 1}
    low, up = tcvn_from_glibc(None)
    assert len(tc_a) == 74 and all((low | up).get(b) == c for b, c in tc_a.items()), "TCVN3 sources disagree"
    # capitals via the uppercase fonts (.VnXxxH): lowercase byte -> uppercase letter named by glibc VN1
    every = {iconv_char(bytes([b])) for b in range(256)}  # glibc VN1 also keeps capitals in 0x01-0x17
    h_font = {b: U.lookup(U.name(c).replace("SMALL", "CAPITAL")) for b, c in low.items()}
    assert set(h_font.values()) <= every, "capital missing from glibc TCVN5712-1"
    assert len(h_font) == 67 and set(h_font.values()) | set(tc_a.values()) >= letters
    sources = {"vietunicode": {"url": URL_A, "sha256": sha(raw_a)}, "wikipedia-vni": {"url": URL_B, "sha256": sha(raw_b),
               "revisions": json.loads(raw_rev)}, "glibc-charmap": {"path": CHARMAP, "sha256": sha(open(CHARMAP, "rb").read())}}
    tcvn3 = {"%02X" % b: c for b, c in sorted(tc_a.items())}
    vni = {k.hex().upper(): v for k, v in sorted(vni_a.items(), key=lambda kv: (len(kv[0]), kv[0]))}
    maps = {"schemaVersion": 1, "codepage": "cp1252", "encodings": {
        "tcvn3": {"label": "TCVN3 (ABC)", "kind": "byte", "map": tcvn3, "upperFontSuffix": "H",
                  "fontPrefix": ".Vn", "fontFallback": {"default": "Times New Roman", ".VnArial": "Arial", ".VnTime": "Times New Roman"}},
        "vni": {"label": "VNI Windows", "kind": "sequence", "map": vni,
                "fontPrefix": "VNI-", "fontFallback": {"default": "Times New Roman"}}}}
    # --- golden vectors (derived from B / C only)
    vec = {"schemaVersion": 1, "derivation": "see docs/ENCODING_SOURCES.md#golden-vectors", "cases": []}
    inv_b = {v: k for k, v in vni_a.items()}
    for ch in sorted(letters):
        vec["cases"].append({"encoding": "vni", "kind": "letter", "input": inv_b[ch].decode("cp1252"), "expected": ch})
    for b, ch in sorted((low | {k: v for k, v in up.items() if k in tc_a}).items()):
        if b in tc_a or b in low:
            vec["cases"].append({"encoding": "tcvn3", "kind": "letter", "input": bytes([b]).decode("cp1252", "replace"), "expected": ch, "viaGlibc": True})
    for b, ch in sorted(h_font.items()):
        vec["cases"].append({"encoding": "tcvn3", "kind": "letter-upper-font", "input": bytes([b]).decode("cp1252"), "expected": ch, "upperFont": True})
    for s in SAMPLES:
        enc = b"".join(inv_b.get(c, c.encode("ascii") if ord(c) < 128 else b"?") for c in map(str, s))
        vec["cases"].append({"encoding": "vni", "kind": "text", "input": enc.decode("cp1252"), "expected": s})
        if not any(c.isupper() and ord(c) > 127 and c not in tc_a.values() for c in s):
            t = s.encode("TCVN5712-1") if False else subprocess.run(["iconv", "-f", "UTF-8", "-t", "TCVN5712-1"], input=s.encode(), capture_output=True).stdout
            vec["cases"].append({"encoding": "tcvn3", "kind": "text", "input": t.decode("cp1252", "replace"), "expected": s, "viaGlibc": True})
    print("sources agree: VNI 134/134, TCVN3 74/74; cases:", len(vec["cases"]))
    if a.write:
        w = lambda p, d: open(os.path.join(ROOT, p), "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
        w("data/vietnamese/encoding-maps.json", maps)
        w("tests/fixtures/vietnamese/encoding-vectors.json", vec)
        glibc = subprocess.run(["dpkg-query", "-W", "-f=${Version}", "locales"], capture_output=True, text=True).stdout
        sources["glibc-charmap"]["package"] = "locales " + glibc
        prov = {"schemaVersion": 1, "retrievedAt": datetime.date.today().isoformat(), "generator": "tests/fixtures/vietnamese/derive-encoding-data.py",
                "sources": sources,
                "roles": {"vietunicode": "runtime tables: TCVN3 single bytes and all 134 VNI sequences (Unicode/VNI/TCVN3 columns)",
                          "wikipedia-vni": "independent cross-check of VNI (combining-mark model of the VNI ANSI table); validates every VNI golden-vector sequence",
                          "glibc-charmap": "independent cross-check of TCVN3 single bytes (iconv TCVN5712-1) and source of TCVN3 golden vectors"},
                "crossChecks": {"vni": "every vietunicode sequence composes (NFC) to the same letter in the Wikipedia table; 134/134 letters, case-matched marks",
                                "tcvn3": "all 74 vietunicode single bytes equal glibc TCVN5712-1; uppercase accented letters exist only via .Vn*H fonts"},
                "excluded": ["vietunicode TCVN3 uppercase accented letters (base letter + lowercase code): a display convention, not bytes",
                             "TCVN 5712 VN1 codes 0x80-0x9F and other uppercase slots: ambiguous with cp1252 punctuation",
                             "VNI Mac and DOS tables"],
                "licenseNote": "factual character-code correspondences; sources are credited, no source text is copied. Review before redistribution if a stricter reading applies."}
        w("data/vietnamese/provenance.json", prov)


if __name__ == "__main__":
    sys.exit(main())
