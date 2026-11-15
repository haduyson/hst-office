# SPDX-License-Identifier: AGPL-3.0-only
"""An imported CSL file as an engine style (kind "csl"): bibliography sort, citation clusters (sorting,
citation-number ranges, note positions) and entries. ``install`` copies a user-chosen .csl into the user's style
folder after it parsed cleanly. Pure Python (no uno)."""
import os

from . import citation_csl_eval as csl_eval
from . import citation_csl_parse as csl_parse
from . import citation_dates as dates
from . import citation_names as names
from . import citation_notes as notes
from . import citation_runs as runs_mod
from . import citation_style_options as style_options
from .citation_model import DATE_VARS, NAME_VARS
from .citation_runs import Out
from .citation_store import atomic_write


def _uses(node, variable):
    return node.get("variable") == variable or any(_uses(c, variable) for c in node.children)


class CslEngineStyle:
    kind = "csl"

    def __init__(self, parsed, style_id, options=None):
        self.parsed, self.id, self.name = parsed, style_id, parsed.title
        parsed.explicit_year_suffix = _uses(parsed.root, "year-suffix")
        self.terms = {}
        numeric = any(_uses(n, "citation-number") for n in [parsed.citation] + list(parsed.macros.values()))
        self.cls = "numeric" if numeric else "note" if parsed.cls == "note" else "author-date"
        bibliography = parsed.bibliography
        own = {"yearSuffix": parsed.citation.get("disambiguate-add-year-suffix") == "true",
               "language": "vi" if parsed.default_locale.lower().startswith("vi") else "en",
               "hangingIndent": bibliography is not None and bibliography.get("hanging-indent") == "true",
               "bibLabel": ""}
        self.options, self.warnings = style_options.merge(style_options.DEFAULTS, own, options)
        self.warnings = parsed.warnings + self.warnings

    def _wrap(self, layout, runs):
        if not runs:
            return []
        out = Out()
        flags = "i" if layout.get("font-style") == "italic" else ""
        out.add(layout.get("prefix", ""))
        out.extend(runs, flags + ("s" if layout.get("vertical-align") == "sup" else ""))
        out.add(layout.get("suffix", ""))
        merged = runs_mod.merge(out.runs)
        return runs_mod.quote_punctuation(merged) if self.parsed.default_locale == "en-US" else merged

    def _sort_key(self, key, item, section):
        ctx = csl_eval.Context(self.parsed, item, section)
        variable = key.get("variable")
        if variable in DATE_VARS:
            year, month, day = dates.parts(item.get(variable) or {})
            return "%05d%02d%02d" % (year, month, day)
        if variable in NAME_VARS:
            return " ".join(names.full_name(n) for n in item.get(variable) or [])
        if variable:
            return str(item.get(variable, ""))
        out = Out()
        csl_eval.render_children(self.parsed.macros[key.get("macro")], ctx, out)
        return runs_mod.plain(out.runs)

    def _sorted(self, items, section, fallback):
        sort = section.child("sort") if section is not None else None
        result = sorted(items, key=fallback)
        for key in reversed(sort.all("key") if sort is not None else []):
            result.sort(key=lambda item: names.collation_key(self._sort_key(key, item, section)),
                        reverse=key.get("sort") == "descending")
        return result

    def arrange(self, items, first_index):
        ordered = self._sorted(items, self.parsed.bibliography, lambda item: first_index.get(item["id"], 1e9))
        return [(None, ordered)]

    def entry(self, item, number=None, year_suffix=""):
        bibliography = self.parsed.bibliography
        if bibliography is None:
            return [(names.full_name((item.get("author") or [{}])[0]) + ". " + item.get("title", ""), "")]
        ctx = csl_eval.Context(self.parsed, item, bibliography, number=number, year_suffix=year_suffix)
        out = Out()
        csl_eval.render_children(bibliography.child("layout"), ctx, out)
        return self._wrap(bibliography.child("layout"), runs_mod.merge(out.runs))

    def clusters(self, clusters, items, number_of, suffixes):
        citation, result = self.parsed.citation, []
        layout = citation.child("layout")
        for cluster, positions in zip(clusters, notes.positions(clusters)):
            cites = [(c, p) for c, p in zip(cluster["items"], positions) if c["id"] in items]
            cites = self._sorted_cites(cites, items, number_of)
            pieces = []
            for cite, position, range_end in self._collapse(cites, number_of, citation):
                ctx = csl_eval.Context(self.parsed, items[cite["id"]], citation, position, cite.get("locator", ""),
                                       cite.get("label", "page"), number_of.get(cite["id"]), range_end,
                                       suffixes.get(cite["id"], ""))
                out = Out()
                out.add(cite.get("prefix", ""))
                csl_eval.render_children(layout, ctx, out)
                out.add(cite.get("suffix", ""))
                pieces.append(runs_mod.merge(out.runs))
            joined = Out()
            for index, piece in enumerate(pieces):
                if index:
                    joined.add(layout.get("delimiter", ""))
                joined.extend(piece)
            result.append(self._wrap(layout, runs_mod.merge(joined.runs)) or [("?", "")])
        return result

    def _sorted_cites(self, cites, items, number_of):
        if self.parsed.citation.child("sort") is None:
            return cites
        order = self._sorted([items[c["id"]] for c, _ in cites], self.parsed.citation, lambda i: number_of.get(i["id"], 0))
        rank = {item["id"]: index for index, item in enumerate(order)}
        return sorted(cites, key=lambda pair: rank[pair[0]["id"]])

    def _collapse(self, cites, number_of, citation):
        """[(cite, position, range end or None)]: three or more consecutive numbers print as "3–5"."""
        if citation.get("collapse") != "citation-number":
            return [(c, p, None) for c, p in cites]
        result, index = [], 0
        while index < len(cites):
            end = index
            while (end + 1 < len(cites) and not cites[end + 1][0].get("locator") and not cites[end][0].get("locator")
                   and number_of.get(cites[end + 1][0]["id"]) == (number_of.get(cites[end][0]["id"]) or 0) + 1):
                end += 1
            last = number_of.get(cites[end][0]["id"]) if end - index >= 2 else None
            result.append((cites[index][0], cites[index][1], last))
            if last is None:
                result += [(c, p, None) for c, p in cites[index + 1:end + 1]]
            index = end + 1
        return result


def load(path, style_id, options=None):
    with open(path, "rb") as handle:
        data = handle.read(csl_parse.MAX_BYTES + 1)
    return CslEngineStyle(csl_parse.parse(data), style_id, options)


def install(user_dir, data):
    """Check a user-chosen .csl and copy it into the user's style folder; returns (style id, warnings)."""
    from .citation_style import new_user_id, user_styles_dir
    parsed = csl_parse.parse(data)
    folder = user_styles_dir(user_dir)
    base = style_id = new_user_id(parsed.title)
    number = 1
    while os.path.exists(os.path.join(folder, style_id + ".csl")) or os.path.exists(os.path.join(folder, style_id + ".json")):
        number += 1
        style_id = "%s-%d" % (base, number)
    atomic_write(os.path.join(folder, style_id + ".csl"), data)
    return style_id, parsed.warnings

