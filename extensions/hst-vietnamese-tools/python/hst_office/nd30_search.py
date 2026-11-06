# SPDX-License-Identifier: AGPL-3.0-only
"""Quick Search over document types (pure logic), with the matching of "Tìm tính năng" (hst-feature-search.patch):
case- and diacritic-folded, NFC and NFD alike, "đ" as "d", so "cong van", "ke hoach", "gm" and "giấy mời" all find theirs.
"""
import unicodedata

GROUP_ORDER = ("hanh-chinh", "qppl", "dang", "van-thu")


def fold(text):
    """Search key of a text: no combining marks, case-folded, "đ" as "d"."""
    decomposed = unicodedata.normalize("NFD", str(text or ""))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().replace("đ", "d")


def _haystack(kind):
    return fold(" ".join(str(kind.get(k) or "") for k in ("label", "typeName", "abbr", "words", "form")))


def _rank(kind, query):
    """0 exact abbreviation, 1 label starts with the query, 2 a word of the label starts with it, 3 anywhere."""
    label = fold(kind["label"])
    if fold(kind.get("abbr")) == query:
        return 0
    if label.startswith(query):
        return 1
    return 2 if (" " + query) in (" " + label) else 3


def _has_word_starting(text, token):
    return (" " + token) in (" " + text)


def matches(types, query):
    """The types whose words start with each word of `query`, best first inside each group; when the query as a whole is
    a phrase of some types, only those (so "so di" finds the register, not every type with "ký số" and "điện")."""
    key = " ".join(fold(query).split())
    tokens = key.split()
    found = [t for t in types if all(_has_word_starting(_haystack(t), token) for token in tokens)]
    phrase = [t for t in found if _has_word_starting(_haystack(t), key)]
    return sorted(phrase or found, key=lambda t: (GROUP_ORDER.index(t["group"]), _rank(t, key)))


def rows(types, query, group_names):
    """List rows: [(text, type id or None)]; None marks a group heading, which can't be chosen."""
    result, current = [], None
    for kind in matches(types, query):
        if kind["group"] != current:
            current = kind["group"]
            result.append(("── %s ──" % group_names[current], None))
        result.append(("    " + kind["label"], kind["id"]))
    return result


def next_row(table, index, step):
    """Index of the next choosable row from `index` in direction `step`, or `index` when there is none."""
    probe = index + step
    while 0 <= probe < len(table):
        if table[probe][1]:
            return probe
        probe += step
    return index
