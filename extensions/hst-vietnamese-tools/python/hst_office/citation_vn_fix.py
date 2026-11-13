# SPDX-License-Identifier: AGPL-3.0-only
"""The "sửa tên Việt" step of every import and online lookup: suggestions the user confirms in a preview table.

External data often gets Vietnamese references wrong: Crossref writes {"family": "Hòa", "given": "Quản Minh"},
VJOL {"family": "Lê Thị", "given": "Ngọc Thương"} or the literal "Ngọc Thương Lê Thị", and titles come in
CAPITALS. A suggestion is {"item", "field", "index", "kind", "old", "new", "message"}; kinds: ``name-order``
(put the Vietnamese family name first), ``mark-vi`` (store the Vietnamese-name flag), ``sentence-case`` and
``language``. Nothing changes until ``apply`` runs with the suggestions the user kept. Pure Python (no uno).
"""
import copy

from . import citation_language as language
from . import citation_names as names
from .citation_render_fields import is_all_caps, sentence_case

NAME_FIELDS = ("author", "editor", "translator")


def vietnamese_order(words):
    """Family-first word order of a Vietnamese name written in any order, or None when no family name is found:
    ["Ngọc", "Thương", "Lê", "Thị"] -> ["Lê", "Thị", "Ngọc", "Thương"]."""
    for index, word in enumerate(words):
        if names.is_vn_surname(word):
            return words[index:] + words[:index]
    return None


def _proposal(name):
    if name.get("literal"):
        words = name["literal"].split()
        if names.is_organization(name["literal"]) or len(words) < 2:
            return None
    else:
        words = (name.get("given", "") + " " + name.get("family", "")).split()
    if not names.looks_vietnamese(words):
        return None
    family = name.get("family", "")
    if family and " " not in family and names.is_vn_surname(family):
        ordered = [family] + name.get("given", "").split()  # already right ("Lê Hà" stays Lê + Hà)
    else:
        ordered = vietnamese_order(words)
    if not ordered:
        return None
    return {"family": ordered[0], "given": " ".join(ordered[1:]), "hst-vi": True}


def _name_suggestions(item, field):
    result = []
    for index, name in enumerate(item.get(field) or []):
        proposal = _proposal(name)
        if not proposal:
            continue
        same = (name.get("family"), name.get("given")) == (proposal["family"], proposal["given"])
        if same and name.get("hst-vi") is True:
            continue
        kind = "mark-vi" if same else "name-order"
        message = ("Đánh dấu “%s” là tên người Việt" if same else "Đổi thành “%s” (họ đứng trước)") % \
            names.full_name(proposal)
        result.append({"item": item["id"], "field": field, "index": index, "kind": kind,
                       "old": name, "new": proposal, "message": message})
    return result


def suggest(items):
    """Suggestions for a list of imported items."""
    result = []
    for item in items:
        for field in NAME_FIELDS:
            result += _name_suggestions(item, field)
        for field in ("title", "container-title"):
            if is_all_caps(item.get(field, "")):
                new = sentence_case(item[field])
                result.append({"item": item["id"], "field": field, "index": None, "kind": "sentence-case",
                               "old": item[field], "new": new, "message": "Đổi chữ IN HOA thành “%s”" % new})
        if not language.normalize(item.get("language")):
            guess = language.guess(item)
            result.append({"item": item["id"], "field": "language", "index": None, "kind": "language",
                           "old": item.get("language", ""), "new": guess,
                           "message": "Ngôn ngữ: %s" % language.heading(guess)})
    return result


def apply(items, accepted):
    """Copies of ``items`` with the accepted suggestions applied (suggestions for other items are ignored)."""
    result = {item["id"]: copy.deepcopy(item) for item in items}
    for suggestion in accepted:
        item = result.get(suggestion.get("item"))
        if item is None:
            continue
        field, index = suggestion["field"], suggestion.get("index")
        if index is None:
            item[field] = suggestion["new"]
        elif isinstance(item.get(field), list) and 0 <= index < len(item[field]):
            item[field][index] = dict(suggestion["new"])
    return [result[item["id"]] for item in items]
