# SPDX-License-Identifier: AGPL-3.0-only
"""Field formatting shared by the style layouts: page ranges, editions, DOI, publisher prefix, quotes, title case."""
import re

from .citation_terms import ordinal, term

QUOTES = {"curly": ("“", "”"), "straight": ("\"", "\""), "single": ("‘", "’"), "none": ("", "")}
_RANGE = re.compile(r"^\s*([A-Za-z]*)(\d+)\s*(?:-{1,3}|–|—|‒)\s*([A-Za-z]*)(\d+)\s*$")
_PUBLISHER_PREFIX = re.compile(r"^(nxb\.?|nhà xuất bản)\s+", re.I)
_DOI_PREFIX = re.compile(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", re.I)
_MINOR = frozenset("a an the and but or for nor on at to from by of in with as vs via into onto per".split())


def _expand(first, last):
    """"123-9" -> "129" (the second number written in full)."""
    if len(last) < len(first) and int(last) < int(first[-len(last):]) + 10 ** len(last):
        full = first[:len(first) - len(last)] + last
        return full if int(full) >= int(first) else last
    return last


def _minimal(first, last):
    """NLM/Vancouver: "123-129" -> "123-9", "1234-1240" -> "1234-40"."""
    if len(first) != len(last) or int(last) < int(first):
        return last
    index = 0
    while index < len(first) - 1 and first[index] == last[index]:
        index += 1
    return last[index:]


def page_range(text, form="expanded", dash="–"):
    """Normalise each range of a page field ("10--16" -> "10–16"); other text is kept."""
    pieces = []
    for piece in re.split(r"\s*,\s*", (text or "").strip()):
        match = _RANGE.match(piece)
        if not match:
            pieces.append(piece)
            continue
        prefix1, first, prefix2, last = match.groups()
        last = _expand(first, last) if not prefix2 or prefix2 == prefix1 else last
        if form == "minimal" and prefix1 == prefix2:
            last = _minimal(first, last)
        pieces.append(prefix1 + first + dash + prefix2 + last)
    return ", ".join(p for p in pieces if p)


def is_range(text):
    return bool(re.search(r"\d\s*(-|–|—|,|&)\s*\d", text or ""))


def edition(value, lang, overrides=None):
    """"2" -> "2nd ed." / "tái bản lần thứ 2"; any other text is printed as written."""
    text = (value or "").strip()
    number = re.match(r"^(\d+)(st|nd|rd|th)?\.?$", text, re.I)
    if not number:
        return text
    return term("edition", lang, overrides=overrides) % ordinal(number.group(1), lang)


def doi(value, prefix):
    return prefix + _DOI_PREFIX.sub("", (value or "").strip()) if value else ""


def publisher(value, prefix):
    """Avoid "Nxb Nxb Giáo dục": a typed "Nxb"/"NXB"/"Nhà xuất bản" gives way to the style's own prefix."""
    return _PUBLISHER_PREFIX.sub("", value) if prefix.strip() else value


def quote(text, kind):
    opening, closing = QUOTES.get(kind, QUOTES["curly"])
    return opening + text + closing


def capfirst(text):
    return text[:1].upper() + text[1:]


def title_case(text):
    """English title case that only raises fully lowercase words (acronyms and names stay as written)."""
    words = text.split(" ")
    result = []
    for index, word in enumerate(words):
        after_colon = index > 0 and words[index - 1].endswith((":", "?", "!", "—"))
        bare = word.strip("“”\"'‘’()[]")
        edge = index in (0, len(words) - 1) or after_colon
        if bare.islower() and (edge or bare not in _MINOR) and not re.search(r"[./@]", bare):
            word = word.replace(bare, "-".join(capfirst(p) for p in bare.split("-")), 1)
        result.append(word)
    return " ".join(result)


def sentence_case(text):
    """"NHÌN LẠI HAI NĂM" -> "Nhìn lại hai năm" (for titles typed or delivered in capitals)."""
    lower = text.lower()
    return re.sub(r"([:?!.]\s+)(\w)", lambda m: m.group(1) + m.group(2).upper(), capfirst(lower))


def is_all_caps(text):
    letters = [c for c in text or "" if c.isalpha()]
    return len(letters) >= 8 and sum(c.isupper() for c in letters) / len(letters) > 0.9
