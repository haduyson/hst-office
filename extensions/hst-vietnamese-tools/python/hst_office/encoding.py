# SPDX-License-Identifier: AGPL-3.0-only
"""TCVN3 (ABC) and VNI Windows -> Unicode conversion (pure logic, no `uno`).

The mapping tables are data/vietnamese/encoding-maps.json; their sources and cross-checks are recorded in
data/vietnamese/provenance.json and docs/ENCODING_SOURCES.md. Legacy text reaches Writer as characters decoded
with Windows-1252, so each character is first turned back into its legacy byte.

Rules: the caller must name the source encoding (`suggest` only ranks candidates); characters above U+00FF
(already Unicode) and unmapped bytes are left untouched and counted; TCVN3 uppercase accented letters exist only
in the uppercase fonts (.VnTimeH, .VnArialH ...), so `upper=True` upper-cases converted letters of such runs.
"""
import unicodedata

from .data_files import load_data

_CP1252_HIGH = {}
for _b in range(0x80, 0xA0):
    try:
        _CP1252_HIGH[bytes([_b]).decode("cp1252")] = _b
    except UnicodeDecodeError:
        pass  # 0x81, 0x8D, 0x8F, 0x90, 0x9D are undefined in cp1252; U+0081 etc. map to themselves in _to_byte


def encodings(data=None):
    """{key: label} of supported source encodings."""
    return {k: v["label"] for k, v in (data or load_data("encoding-maps.json"))["encodings"].items()}


def _to_byte(ch):
    code = ord(ch)
    return code if code <= 0xFF else _CP1252_HIGH.get(ch)


def has_vietnamese_unicode(text):
    """True if any character above U+00FF is a Latin letter outside the cp1252 punctuation/letters (Ă, Ơ, Ạ ...)."""
    return any(ord(c) > 0xFF and c not in _CP1252_HIGH and unicodedata.category(c) in ("Lu", "Ll")
               and "LATIN" in unicodedata.name(c, "") for c in text)


class Converter:
    """Convert text from one legacy encoding to Unicode (NFC)."""

    def __init__(self, key, data=None):
        spec = (data or load_data("encoding-maps.json"))["encodings"].get(key)
        if spec is None:
            raise ValueError("unknown-encoding: %r (an explicit source encoding is required)" % (key,))
        self.key, self.spec = key, spec
        self.table = {bytes.fromhex(k): v for k, v in spec["map"].items()}
        self.longest = max(len(k) for k in self.table)

    def convert(self, text, upper=False):
        """Return (unicode_text, stats). stats = {'converted': letters produced, 'unmapped': high bytes kept,
        'skipped_unicode': True when the text already holds Vietnamese Unicode letters and is returned unchanged}.
        Latin-1 range letters such as 'à' are valid legacy bytes too, so only letters above U+00FF prove Unicode."""
        if has_vietnamese_unicode(text):
            return text, {"converted": 0, "unmapped": 0, "skipped_unicode": True}
        out, i, converted, unmapped = [], 0, 0, 0
        while i < len(text):
            matched = None
            for size in range(min(self.longest, len(text) - i), 0, -1):
                raw = [_to_byte(c) for c in text[i:i + size]]
                if None in raw:
                    continue
                letter = self.table.get(bytes(raw))
                if letter is not None:
                    matched = (size, letter.upper() if upper and self.key == "tcvn3" else letter)
                    break
            if matched:
                out.append(matched[1])
                i += matched[0]
                converted += 1
                continue
            ch = text[i]
            if 0x80 <= ord(ch) <= 0xFF:
                unmapped += 1
            out.append(ch)
            i += 1
        return unicodedata.normalize("NFC", "".join(out)), {"converted": converted, "unmapped": unmapped, "skipped_unicode": False}


def font_policy(key, font_name, data=None):
    """For a run's font name return (upper, replacement_font_or_None). Replacement is None for non-legacy fonts."""
    spec = (data or load_data("encoding-maps.json"))["encodings"][key]
    name = (font_name or "").strip()
    prefix = spec["fontPrefix"]
    if not name.lower().startswith(prefix.lower()):
        return False, None
    fallback = spec["fontFallback"]
    replacement = next((v for k, v in fallback.items() if k != "default" and name.lower().startswith(k.lower())), fallback["default"])
    upper = key == "tcvn3" and len(name) > len(prefix) and name.endswith(spec.get("upperFontSuffix", "H"))
    return upper, replacement
