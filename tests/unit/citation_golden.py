# SPDX-License-Identifier: AGPL-3.0-only
"""Golden outputs of the citation styles: every style (and preset) formats the shared sample references and the
result must equal tests/fixtures/citations/golden/<case>.txt. Notation: *italic*, **bold**, ^superscript^.

Regenerate after an intended change, then review the diff line by line against the style guide:
    HST_UPDATE_CITATION_GOLDEN=1 python3 -m unittest tests/unit/test_citation_golden_styles.py
"""
import json
import os

import _paths

from hst_office import citation_engine, citation_runs, citation_style

FIXTURES = os.path.join(_paths.ROOT, "tests", "fixtures", "citations")
GOLDEN = os.path.join(FIXTURES, "golden")
CASES = ("vn-so", "vn-so@tung-ngoac", "vn-so@thu-tu-trich", "vn-so@khong-nhom", "vn-tac-gia-nam",
         "vn-tac-gia-nam@mot-danh-muc-theo-ho", "vn-tac-gia-nam@et-al", "apa-7", "apa-7@dao-ten-viet", "apa-7+en",
         "ieee", "ieee@ten-viet-bo-dau", "vancouver", "ama-11", "harvard", "chicago-tac-gia-nam",
         "chicago-chu-thich", "chicago-chu-thich@chu-thich-viet-nam", "mla-9", "iso-690-so", "iso-690-tac-gia-nam")


def samples():
    with open(os.path.join(FIXTURES, "samples.json"), encoding="utf-8") as handle:
        return json.load(handle)


def clusters(items):
    """One citation per sample in file order, then clusters that exercise ranges, locators and positions."""
    result = [{"citationID": "c-" + item["id"], "items": [{"id": item["id"]}]} for item in items]
    result += [
        {"citationID": "multi", "items": [{"id": i} for i in ("vi-book", "vi-book-2", "vi-article-3", "en-lecun")]},
        {"citationID": "range", "items": [{"id": i} for i in ("en-watson", "en-lecun", "en-vaswani", "en-krugman")]},
        {"citationID": "locator", "items": [{"id": "en-lecun", "locator": "437-438"}]},
        {"citationID": "locator-vi", "items": [{"id": "vi-book", "locator": "15"}]},
        {"citationID": "same-again", "items": [{"id": "vi-book", "locator": "16"}]},
        {"citationID": "narrative", "items": [{"id": "vi-article-3"}], "mode": "narrative"},
        {"citationID": "same-year", "items": [{"id": "vi-book"}, {"id": "vi-book-b"}]},
        {"citationID": "suppress", "items": [{"id": "en-krugman", "suppressAuthor": True, "locator": "12"}]},
        {"citationID": "prefixed", "items": [{"id": "vi-thesis", "prefix": "xem ", "locator": "3", "label": "chapter"}]},
    ]
    return result


def load(case):
    name, _, lang = case.partition("+")
    style_id, _, preset = name.partition("@")
    options = {"language": "en", "termLanguage": "document"} if lang == "en" else None
    return citation_style.load_style(style_id, options=options, preset=preset or None)


def render_case(case):
    """The golden text of one case."""
    items = samples()
    result = citation_engine.process(load(case), items, clusters(items))
    lines = ["# " + case, "[citations]"]
    for entry in result["citations"]:
        lines.append("%s\t%s" % (entry["citationID"], citation_runs.to_markup(citation_runs.from_public(entry["runs"]))))
    bibliography = result["bibliography"]
    lines.append("[bibliography] " + bibliography["title"])
    for group in bibliography["groups"]:
        if group["heading"]:
            lines.append("== " + group["heading"])
        for entry in group["entries"]:
            markup = citation_runs.to_markup(citation_runs.from_public(entry["runs"]))
            lines.append(("%s\t%s" % (entry["label"], markup)) if entry["label"] else markup)
    return "\n".join(lines) + "\n"


def golden_path(case):
    return os.path.join(GOLDEN, case.replace("@", "__").replace("+", "--") + ".txt")
