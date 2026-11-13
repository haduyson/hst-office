# SPDX-License-Identifier: AGPL-3.0-only
"""Fields after the authors and year of a pasted reference: title (quoted or first segment), container, volume
(issue), pages, publisher and place ("Nxb X, Hà Nội" or "Place: Publisher"), thesis wording, editors, edition,
translator and original year; then the most likely CSL type. Used by citation_paste_parse. Pure Python (no uno)."""
import re

from .citation_paste_authors import split_authors

_YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")
_QUOTED = re.compile(r"[“\"‘]([^”\"’]{3,}?)[,.]?[”\"’]")
_PAGES = re.compile(r"(?:\btr\.|\btrang|\bpp?\.)\s*([A-Za-z]?\d+(?:\s*[-–]\s*\d+)?)", re.I)
_VOL_ISSUE = re.compile(r"(?:\bvol\.|\btập)\s*(\d+)(?:,?\s*(?:\bno\.|\bsố)\s*(\d+))?|\b(\d+)\s*\((\d+)\)", re.I)
_PUBLISHER_VI = re.compile(r"\b(?:Nxb\.?|NXB|Nhà xuất bản)\s+([^,.;]+)(?:[,.;]\s*([^,.;]+))?")
_PLACE_PUBLISHER = re.compile(r"([A-Z][\w .]+?):\s*([^,.;:]+?)(?:[,;]\s*(1[5-9]\d\d|20\d\d))?\.?$")
_THESIS = re.compile(r"(Luận án [^,.;\]]+|Luận văn [^,.;\]]+|Ph\.?D\.? (?:thesis|dissertation)|Doctoral dissertation|"
                     r"Master'?s thesis|M\.S\. thesis|dissertation)", re.I)
_LEGAL = re.compile(r"^(Thông tư|Nghị định|Luật|Quyết định|Nghị quyết|Chỉ thị|Hiến pháp|Pháp lệnh|Bộ luật)\b")
_CONFERENCE = re.compile(r"\b(Kỷ yếu|Hội thảo|Hội nghị|Proceedings|Proc\.|Conference|Symposium|Workshop)\b", re.I)
_BRACKET_THESIS = re.compile(r"\[([^\]]*(?:Luận|thesis|dissertation)[^\]]*)\]", re.I)
_EDITION = re.compile(r"\(?\b(\d+)(?:st|nd|rd|th)? (?:ed\.|edn\.?)\)?|\(?\bxuất bản lần thứ (\d+)\)?|\(?\btái bản lần thứ (\d+)\)?", re.I)
_TRANSLATOR = re.compile(r"\(([^()]+?),\s*(?:dịch|Trans\.|trans\.)\)|,?\s*dịch bởi ([^,.]+)")
_ORIGINAL = re.compile(r"\((?:Sách gốc xuất bản năm|Original work published)\s+(\d{4})\)", re.I)
_EDITORS = re.compile(r"\b(?:[Tt]rong|In:?)\s+(.+?)\s*[(,]\s*(?:chủ biên|cb\.|eds?\.|editors?)\)?[,.]?\s*"
                      r"|,\s*(?:edited by|chủ biên|ed\.)\s+([^,.(]+)", re.I)


def take(pattern, text):
    """(match, text without the match)."""
    match = pattern.search(text)
    return (match, text[:match.start()] + text[match.end():]) if match else (None, text)


def split_segments(text):
    return [s.strip(" ,.;") for s in re.split(r"(?<!\b[A-ZĐ])[.,;]\s+", text) if s.strip(" ,.;")]


def _extras(item, rest):
    """Pieces that sit in brackets or parentheses: thesis description, edition, translator, original year."""
    match, rest = take(_BRACKET_THESIS, rest)
    if match:
        genre, _, school = match.group(1).partition(",")
        item.update({"type": "thesis", "genre": genre.strip()})
        if school.strip():
            item["publisher"] = school.strip()
    match, rest = take(_EDITION, rest)
    if match:
        # "tái bản lần thứ 2" is the third printing in Vietnamese usage; "xuất bản lần thứ 2" the second
        item["edition"] = match.group(1) or match.group(2) or str(int(match.group(3)) + 1)
    match, rest = take(_TRANSLATOR, rest)
    if match:
        item["translator"] = split_authors(match.group(1) or match.group(2))
    match, rest = take(_ORIGINAL, rest)
    if match:
        item["original-date"] = {"date-parts": [[int(match.group(1))]]}
    return re.sub(r"\(\s*\)", "", rest)


def fill_fields(item, rest):
    rest = _extras(item, rest)
    quoted = _QUOTED.search(rest)
    if quoted:
        item["title"], after = quoted.group(1).strip(" ,."), rest[quoted.end():]
    else:
        segments = split_segments(rest)
        item["title"] = segments[0] if segments else ""
        after = rest[rest.find(item["title"]) + len(item["title"]):] if item["title"] else rest
    editors = _EDITORS.search(after)
    if editors:
        item["editor"] = split_authors(editors.group(1) or editors.group(2))
        item["type"] = "chapter"
        after = after[:editors.start()] + " " + after[editors.end():]
    for pattern, handler in ((_THESIS, _thesis), (_PUBLISHER_VI, _publisher_vi), (_PAGES, _pages),
                             (_VOL_ISSUE, _volume)):
        match = pattern.search(after)
        if match:
            after = after[:match.start()] + "|" + after[match.end():]
            handler(item, match)
    after = re.sub(r"\(\s*\|?\s*\)", "", after)
    segments = [re.sub(r"^(?:In|Trong):?\s+", "", s) for s in split_segments(after.replace("|", ". "))
                if not _YEAR.fullmatch(s)]
    if segments and not item.get("publisher") and item.get("type") != "thesis":
        place_pub = _PLACE_PUBLISHER.search(segments[-1]) if len(segments) > 1 or not quoted else None
        if place_pub and not item.get("volume"):
            item["publisher-place"], item["publisher"] = place_pub.group(1).strip(), place_pub.group(2).strip()
            segments = segments[:-1]
    if segments and not quoted and item["type"] == "document" and not (item.get("volume") or item.get("page")):
        item.setdefault("publisher", segments[0])  # APA/Harvard book: "Title. Publisher."
        segments = []
    if segments and item.get("type") in ("document", "chapter", "thesis") and not item.get("container-title"):
        target = "publisher" if item["type"] == "thesis" else "container-title"
        item.setdefault(target, segments[0])
        if item["type"] == "thesis" and len(segments) > 1:
            item.setdefault("publisher-place", segments[1])
    if item["type"] == "document":
        item["type"] = _guess_type(item)


def _thesis(item, match):
    item["type"], item["genre"] = "thesis", match.group(1).strip()


def _publisher_vi(item, match):
    item["publisher"] = match.group(1).strip()
    if match.group(2) and not _YEAR.fullmatch(match.group(2).strip()):
        item["publisher-place"] = match.group(2).strip()


def _pages(item, match):
    item.setdefault("page", match.group(1).replace(" ", ""))


def _volume(item, match):
    volume, issue = (match.group(1), match.group(2)) if match.group(1) else (match.group(3), match.group(4))
    item.setdefault("volume", volume)
    if issue:
        item.setdefault("issue", issue)


def _guess_type(item):
    title, container = item.get("title", ""), item.get("container-title", "")
    if _LEGAL.match(title):
        return "legislation"
    if _CONFERENCE.search(container):
        return "paper-conference"
    if container and (item.get("volume") or item.get("page")):
        return "article-journal"
    if item.get("publisher"):
        return "book"
    if item.get("URL"):
        return "webpage"
    return "article-journal" if container else "book"
