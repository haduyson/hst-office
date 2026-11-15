# SPDX-License-Identifier: AGPL-3.0-only
"""LaTeX in BibTeX values: decode to Unicode on import ({\\'e} -> é, \\~{\\^a} -> ẫ, \\dj -> đ, -- -> –) and escape
special characters on export (& % $ # _ { } ~ ^ \\). Unicode letters are written as they are on export (biber and
BibTeX with inputenc read UTF-8). Pure Python (no uno)."""
import re
import unicodedata

ACCENTS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303", "=": "\u0304", ".": "\u0307",
           "u": "\u0306", "v": "\u030c", "H": "\u030b", "c": "\u0327", "d": "\u0323", "k": "\u0328", "r": "\u030a",
           "b": "\u0331", "h": "\u0309"}  # \h: hook above (vntex)
LETTERS = {"o": "ø", "O": "Ø", "ss": "ß", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ", "aa": "å", "AA": "Å",
           "l": "ł", "L": "Ł", "i": "ı", "j": "ȷ", "dj": "đ", "DJ": "Đ", "ohorn": "ơ", "OHORN": "Ơ", "uhorn": "ư",
           "UHORN": "Ư", "textendash": "–", "textemdash": "—", "textquoteleft": "‘", "textquoteright": "’",
           "textquotedblleft": "“", "textquotedblright": "”", "S": "§", "P": "¶", "copyright": "©", "dag": "†",
           "ldots": "…", "dots": "…", "textellipsis": "…"}
_ACCENT_BRACED = re.compile(r"\\([`'^\"~=.]|[uvHcdkrbh](?=[\s{]))\s*\{([^\W\d_]?)\}")
_ACCENT_BARE = re.compile(r"\\([`'^\"~=.])\s*([^\W\d_])")
_ACCENT_SPACED = re.compile(r"\\([uvHcdkrbh])\s+([^\W\d_])")
_LETTER = re.compile(r"\\(" + "|".join(sorted(LETTERS, key=len, reverse=True)) + r")(?![A-Za-z])(\{\})?\s?")
_COMMAND_ARG = re.compile(r"\\(?![uvHcdkrbh]\s*\{)[A-Za-z]+\*?\s*\{([^{}]*)\}")
_GROUP = re.compile(r"(?<!\\[uvHcdkrbh`'^\"~=.])\{([^{}\\]*)\}")  # not an accent's own argument
_BARE_COMMAND = re.compile(r"\\[A-Za-z]+\*?\s?")
_ESCAPED = {"\\&": "&", "\\%": "%", "\\$": "$", "\\#": "#", "\\_": "_", "\\{": "\x01", "\\}": "\x02"}


def _accent(match):
    mark, base = match.group(1), match.group(2)
    if not base:
        return {"~": "~", "^": "^"}.get(mark, "")
    base = {"ı": "i", "ȷ": "j"}.get(base, base)  # \'\i is í
    return unicodedata.normalize("NFC", base + ACCENTS[mark])


def decode(text):
    """Unicode text of a BibTeX value: accents, special letters, escapes, dashes and quotes; braces dropped."""
    text = text or ""
    for escaped, plain in _ESCAPED.items():
        text = text.replace(escaped, plain)
    text = _LETTER.sub(lambda m: LETTERS[m.group(1)], text)
    previous = None
    while previous != text:  # innermost first: \~{\^e} -> \~{ê} -> ễ; {\'e} -> {é} -> é
        previous = text
        for pattern in (_ACCENT_BRACED, _ACCENT_BARE, _ACCENT_SPACED):
            text = pattern.sub(_accent, text)
        text = _COMMAND_ARG.sub(r"\1", text)  # \textit{Deep} -> Deep
        text = _GROUP.sub(r"\1", text)
    text = _BARE_COMMAND.sub("", text)
    text = text.replace("{", "").replace("}", "").replace("$", "")
    text = text.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”").replace("~", " ")
    text = text.replace("\x01", "{").replace("\x02", "}")
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", text).strip())


_ENCODE = {"\\": "\\textbackslash{}", "&": "\\&", "%": "\\%", "$": "\\$", "#": "\\#", "_": "\\_", "{": "\\{",
           "}": "\\}", "~": "\\textasciitilde{}", "^": "\\textasciicircum{}"}


def encode(text):
    """Escape the characters that BibTeX/LaTeX treat specially (Unicode letters stay as they are)."""
    return "".join(_ENCODE.get(char, char) for char in text or "")
