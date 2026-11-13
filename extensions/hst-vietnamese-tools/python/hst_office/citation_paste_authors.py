# SPDX-License-Identifier: AGPL-3.0-only
"""Author lists of pasted references, in the shapes Vietnamese theses and the common styles print them:
"Nguyễn Văn An, Trần Thị Bình", "Smith, J. A., & Doe, B.", "Fauci AS, Lane HC", "J. K. Author and A. B. Other",
"Goedkoop J.B., Grioni M.", "SMITH, John and DOE, Jane". "và cộng sự", "et al." and similar endings are dropped.
Pure Python (no uno)."""
import re

from . import citation_names as names

_ET_AL = re.compile(r"[,\s]*(?:(?:và|&)\s+(?:cộng sự|cs\.?|c\.s\.|ctv\.?)|et\s+al\.?)\s*$", re.I)
_AND = re.compile(r"\s*(?:,\s*)?(?:\s&\s|\sand\s|\svà\s)\s*", re.I)
_CAP = "[A-ZÀ-ÖØ-ÞĐŁŒА-ЯЁ]"
_INITIALS = r"(?:" + _CAP + r"\.\s*-?\s*)+"                         # "J. A.", "J.-P."
_LOOSE_INITIALS = r"(?:" + _CAP + r"\.\s*-?\s*)*" + _CAP + r"\.?"  # APA list end: "Doe, B" after stripping
_APA_PAIR = re.compile(r"([^,&]+?),\s*(" + _LOOSE_INITIALS + r")(?=\s*(?:,|&|and\b|và\b|$))")
_COMPACT = re.compile(r"^(.+?)\s+(" + _CAP + "{1,3})$")              # Vancouver "Fauci AS"
_DOTTED_AFTER = re.compile(r"^(.+?)\s+(" + _INITIALS + r")$")   # "Goedkoop J.B."
_DOTTED_BEFORE = re.compile(r"^(" + _INITIALS + r")\s*(.+)$")   # IEEE "J. K. Author"
LEADING_INITIALS = re.compile(r"^(?:and\s+|và\s+)?" + _INITIALS + r"\S")


def _person(text):
    text = text.strip(" ,;")
    if text.endswith(".") and not re.search(_CAP + r"\.$", text):
        text = text[:-1]  # the period ending the author list, not an initial's
    if not text:
        return None
    if re.fullmatch("[\u3400-\u9fff]{2,4}", text):  # Chinese name written together: family name first
        return {"family": text[0], "given": text[1:]}
    if names.is_organization(text):
        return {"literal": text}
    if "," in text:
        return names.parse_name(text)  # "Smith, John A." (inverted)
    for pattern, family_group in ((_COMPACT, 1), (_DOTTED_AFTER, 1)):
        match = pattern.match(text)
        if match and not names.looks_vietnamese(text.split()):
            family = match.group(family_group)
            given = match.group(2)
            return {"family": family.strip(), "given": names.initials(given)}
    match = _DOTTED_BEFORE.match(text)
    if match:
        return {"family": match.group(2).strip(), "given": names.initials(match.group(1))}
    upper = re.match(r"^([A-ZĐÀ-Ỹ][A-ZĐÀ-Ỹ'\- ]+),\s*(.+)$", text)  # ISO 690 "SMITH, John"
    if upper and upper.group(1).isupper():
        return names.parse_name(upper.group(1).title() + ", " + upper.group(2))
    return names.parse_name(text)


def split_authors(text):
    """CSL names of an author segment (empty list when nothing looks like a name)."""
    text = _ET_AL.sub("", (text or "").strip(" ,;"))
    text = text[:-1] if text.endswith(".") and not re.search(r"(?<!\w)" + _CAP + r"\.$", text) else text
    if not text:
        return []
    if names.is_organization(text):
        return [{"literal": text}]
    pairs = _APA_PAIR.findall(text)
    if pairs and not re.sub(r"[\s,&.]|\band\b|\bvà\b", "", _APA_PAIR.sub("", text)):
        families = [re.sub(r"^(?:and|và)\s+", "", family.strip(" &")) for family, _ in pairs]
        return [{"family": family.title() if family.isupper() and len(family) > 1 else family,  # ISO "WATSON"
                 "given": names.initials(given)} for family, (_, given) in zip(families, pairs)]
    if re.match(r"^[A-ZĐÀ-Ỹ'\- ]+,\s", text):  # ISO 690: "SMITH, John, DOE, Jane and LEE, Bob"
        result, family = [], None
        for token in re.split(r",\s*|\s+(?:and|và)\s+|;\s*", text):
            if token.isupper() and len(token) > 1 and not re.fullmatch(r"(?:[A-Z]\.\s*)+", token):
                if family:
                    result.append(names.parse_name(family.title(), organization=False))
                family = token
            elif family:
                result.append(names.parse_name(family.title() + ", " + token))
                family = None
        if family:
            result.append(names.parse_name(family.title(), organization=False))
        return result
    parts = [p.strip() for piece in _AND.split(text) for p in piece.split(",") if p.strip()]
    if len(parts) >= 2 and " " not in parts[0] and len(parts[1].split()) <= 3 and not names.looks_vietnamese(
            parts[0].split()) and not _DOTTED_BEFORE.match(parts[0]):
        parts = [parts[0] + ", " + parts[1]] + parts[2:]  # Chicago/MLA: "Smith, John, Jane Doe, and Bob Lee"
    return [p for p in (_person(part) for part in parts) if p]


_JOINERS = re.compile(r"^(?:and|và|&)\s+", re.I)
_LOWER_OK = frozenset("van von de der den da di du del della le la bin al et".split())


def looks_like_name(token, first=False):
    """Whether a comma-separated piece of a reference line is (part of) a name: an organisation, capitalised words
    ("Trần Văn Bình", "LeCun", "Yann"), initials ("J. K. Author"), "et al." or a Chinese name at the start."""
    token = token.strip(" ;")
    if re.search(r"\w{2,}\.\s+\S", token):
        return False  # "Tổng cục Thống kê. Niên giám…": a sentence ends inside
    if re.fullmatch(r"et al\.?|(?:và|&) (?:cộng sự|cs\.?|ctv\.?)", token, re.I):
        return True
    token = _JOINERS.sub("", token)
    if not token or re.search(r"\d", token):
        return False
    if names.is_organization(token):
        return True
    if first and re.fullmatch("[\u3400-\u9fff]{2,4}", token):
        return True
    words = [w for w in re.split(r"\s+|(?<=\.)(?=\w)", token) if w]
    if any(w.endswith(".") and len(w) > 2 and w not in ("Jr.", "Sr.") for w in words[:-1]):
        return False  # "Pfaller. Medical": a sentence ends inside, so this is not a name
    return 0 < len(words) <= 6 and all(w[:1].isupper() or w.lower() in _LOWER_OK for w in words)


def leading_names(text):
    """Length of the names list at the start of ``text`` ("Trần Văn Bình, Kinh tế…" -> len("Trần Văn Bình, "))."""
    taken, position = 0, 0
    for match in re.finditer(r"[^,]+(?:,\s*|$)", text):
        piece = re.sub(r"\s+(?:và|&)\s+(?:cộng sự|cs\.?|ctv\.?)[,.]?\s*$|,?\s+et al\.?\s*$", "",
                       match.group(0).strip(" ,"))
        parts = re.split(r"\s+(?:và|and|&)\s+", piece.strip(" ,"))
        whole = names.is_organization(piece) and not re.search(r"\w{2,}\.\s+\S", piece)  # "Bộ … và Đào tạo"
        if not whole and not all(looks_like_name(p, first=taken == 0) for p in parts):
            break
        taken += 1
        position = match.end()
    return position
