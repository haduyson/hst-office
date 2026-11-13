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
_COMPACT = re.compile(r"^(.+?)\s+([A-ZĐ]{1,3})$")              # Vancouver "Fauci AS"
_DOTTED_AFTER = re.compile(r"^(.+?)\s+(" + _INITIALS + r")$")   # "Goedkoop J.B."
_DOTTED_BEFORE = re.compile(r"^(" + _INITIALS + r")\s*(.+)$")   # IEEE "J. K. Author"
LEADING_INITIALS = re.compile(r"^(?:and\s+|và\s+)?" + _INITIALS + r"\S")


def _person(text):
    text = text.strip(" ,.;")
    if not text:
        return None
    if names.is_organization(text):
        return {"literal": text}
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
    text = text[:-1] if text.endswith(".") and not re.search(r"\b[A-ZĐ]\.$", text) else text
    if not text:
        return []
    if names.is_organization(text):
        return [{"literal": text}]
    pairs = _APA_PAIR.findall(text)
    if pairs and not re.sub(r"[\s,&.]|\band\b|\bvà\b", "", _APA_PAIR.sub("", text)):
        return [{"family": family.strip(" &"), "given": names.initials(given)} for family, given in pairs]
    if re.match(r"^[A-ZĐÀ-Ỹ'\- ]+,\s", text):  # ISO 690: "SMITH, John and DOE, Jane"
        parts = re.split(r"\s+(?:and|và)\s+|;\s*", text)
        return [p for p in (_person(part) for part in parts) if p]
    parts = [p.strip() for piece in _AND.split(text) for p in piece.split(",") if p.strip()]
    if len(parts) >= 2 and " " not in parts[0] and len(parts[1].split()) <= 3 and not names.looks_vietnamese(
            parts[0].split()) and not _DOTTED_BEFORE.match(parts[0]):
        parts = [parts[0] + ", " + parts[1]] + parts[2:]  # Chicago/MLA: "Smith, John, Jane Doe, and Bob Lee"
    return [p for p in (_person(part) for part in parts) if p]
