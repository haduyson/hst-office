# SPDX-License-Identifier: AGPL-3.0-only
"""Bibliography order: language groups (Vietnamese first), alphabetical or first-citation order, numbers and year
suffixes (2010a, 2010b). Pure Python (no uno).

Alphabetical keys use the Vietnamese alphabet for every language (``vietnamese_text.sort_key``); Vietnamese authors
sort by given name then family and middle names unless the style sorts them letter by letter (``viSort`` =
"family", as ĐH Kinh tế Quốc dân does). An organisation sorts by its first word ("Bộ Giáo dục…" under B). A work
without author sorts by its title. Works without a date come before dated works of the same author (APA).
"""
import string

from . import citation_language as language
from . import citation_names as names
from . import citation_render_names as render_names
from .citation_render_dates import year_text

_LEADING_ARTICLES = ("the ", "a ", "an ")
_INFINITY = float("inf")


def creators(item):
    """The names that stand first in an entry: authors, else editors, else nothing."""
    return item.get("author") or item.get("editor") or []


def _title_key(item):
    title = (item.get("title") or "").strip().strip("“”\"'‘’")
    lower = title.lower()
    for article in _LEADING_ARTICLES:
        if lower.startswith(article) and language.group_of(item) == "en":
            title = title[len(article):]
            break
    return names.collation_key(title)


def alpha_key(item, opts):
    people = creators(item)
    if people:
        author = tuple(names.name_sort_key(n, opts["viSort"]) for n in people)
    else:
        author = ((_title_key(item), names.collation_key("")),)
    issued = item.get("issued") or {}
    years = issued.get("date-parts") or [[-1]]
    return author, years[0][0] if years and years[0] else -1, _title_key(item)


def arrange(items, style, first_index):
    """[(language code or None, [items])] in bibliography order; ``first_index`` maps id -> first citation index."""
    opts = style.options

    def key(item):
        if opts["order"] == "cite":
            return first_index.get(item["id"], _INFINITY), alpha_key(item, opts)
        return alpha_key(item, opts)

    if not opts["groupByLanguage"]:
        return [(None, sorted(items, key=key))]
    groups = {}
    for item in items:
        groups.setdefault(language.group_of(item), []).append(item)
    order = sorted(groups, key=lambda code: language.group_rank(code, opts["groupOrder"]))
    return [(code, sorted(groups[code], key=key)) for code in order]


def numbers(arranged):
    """{id: number} counting through the groups in order (Vietnamese thesis style: number = place in the list)."""
    result, count = {}, 0
    for _, group in arranged:
        for item in group:
            count += 1
            result[item["id"]] = count
    return result


def _suffix(index):
    letters = string.ascii_lowercase
    return letters[index] if index < 26 else letters[index // 26 - 1] + letters[index % 26]


def year_suffixes(arranged, style):
    """{id: "a"} for works whose in-text author and year would otherwise be identical."""
    opts = style.options
    if not opts["yearSuffix"]:
        return {}
    buckets = {}
    for _, group in arranged:
        for item in group:
            people = creators(item)
            who = render_names.cite_names(people, opts, language.group_of(item)) if people else item.get("title", "")
            buckets.setdefault((who, year_text(item.get("issued"))), []).append(item["id"])
    result = {}
    for ids in buckets.values():
        if len(ids) > 1:
            for index, item_id in enumerate(ids):
                result[item_id] = _suffix(index)
    return result


def same_author_as_previous(arranged, style):
    """Ids whose author list equals the previous entry's (MLA prints "---" instead)."""
    if not style.options["subsequentAuthor"]:
        return set()
    result, previous = set(), None
    for _, group in arranged:
        for item in group:
            current = tuple(names.full_name(n) for n in item.get("author") or []) or None
            if current and current == previous:
                result.add(item["id"])
            previous = current
    return result
