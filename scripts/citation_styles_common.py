# SPDX-License-Identifier: AGPL-3.0-only
"""Building blocks of the citation style source (scripts/generate-citation-styles.py): option defaults,
template element constructors and the JSON writer. The generated data/citation/styles/*.json are committed."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extensions",
                                "hst-vietnamese-tools", "python"))
from hst_office.citation_style_options import DEFAULTS  # noqa: E402

BASE = DEFAULTS
VN_PUB = {"vi": "Nxb ", "other": ""}


def intl_opts(**kw):
    """International styles take their words ("tr."/"p.", "và cộng sự"/"et al.") from the document's language."""
    return opts(termLanguage="document", **kw)


def opts(**kw):
    """Every option with the style's own values (unknown names are a mistake)."""
    result = json.loads(json.dumps(BASE))
    for key, value in kw.items():
        assert key in BASE, key
        result[key] = value
    return result


def v(name, **kw):
    return dict({"v": name}, **kw)


def g(*items, **kw):
    return dict({"group": list(items)}, **kw)


def t(text, **kw):
    return dict({"text": text}, **kw)


def term(name, **kw):
    return dict({"term": name}, **kw)


def m(name, **kw):
    return dict({"macro": name}, **kw)


DOT = t(".")
LINK = v("DOI", **{"if": "DOI", "else": [v("URL")]})
ALIAS = {"article-magazine": "article-journal", "article": "article-journal", "post-weblog": "webpage",
         "post": "webpage", "entry-dictionary": "chapter", "entry-encyclopedia": "chapter", "bill": "legislation",
         "regulation": "legislation", "treaty": "legislation", "legal_case": "legislation", "dataset": "report",
         "standard": "report", "patent": "report", "pamphlet": "book", "collection": "book", "classic": "book",
         "software": "report", "speech": "paper-conference", "manuscript": "default", "document": "default"}



def dump(data):
    """Readable JSON: one template element per line."""
    lines = ["{"]
    keys = list(data)
    for index, key in enumerate(keys):
        value = data[key]
        comma = "," if index < len(keys) - 1 else ""
        if key in ("layouts", "macros") or (key == "notes"):
            inner = value if key != "notes" else value
            lines.append('  "%s": {' % key)
            sub = list(inner)
            for j, name in enumerate(sub):
                c2 = "," if j < len(sub) - 1 else ""
                elements = inner[name]
                if key == "notes" and name == "layouts":
                    lines.append('    "layouts": {')
                    names = list(elements)
                    for k, layout_name in enumerate(names):
                        c3 = "," if k < len(names) - 1 else ""
                        body = ",\n".join("      " + json.dumps(e, ensure_ascii=False) for e in elements[layout_name])
                        lines.append('     "%s": [\n%s\n     ]%s' % (layout_name, body, c3))
                    lines.append("    }" + c2)
                    continue
                body = ",\n".join("    " + json.dumps(e, ensure_ascii=False) for e in elements)
                lines.append('   "%s": [\n%s\n   ]%s' % (name, body, c2))
            lines.append("  }" + comma)
        elif key == "options":
            names = list(value)
            body = ",\n".join('   "%s": %s' % (n, json.dumps(value[n], ensure_ascii=False)) for n in names)
            lines.append('  "options": {\n%s\n  }%s' % (body, comma))
        else:
            lines.append('  "%s": %s%s' % (key, json.dumps(value, ensure_ascii=False), comma))
    lines.append("}")
    return "\n".join(lines) + "\n"
