# SPDX-License-Identifier: AGPL-3.0-only
"""Terms for imported CSL styles when the style's own <locale> does not define them. Written by HST (plain English
and Vietnamese words), not taken from the CSL locale files. Key: (name, form) -> (singular, plural)."""
from .citation_terms import MONTHS_EN, MONTHS_EN_ABBR

EN = {
    ("and", "long"): ("and", "and"), ("and", "symbol"): ("&", "&"), ("et-al", "long"): ("et al.", "et al."),
    ("and others", "long"): ("and others", "and others"), ("accessed", "long"): ("accessed", "accessed"),
    ("retrieved", "long"): ("retrieved", "retrieved"), ("from", "long"): ("from", "from"),
    ("in", "long"): ("in", "in"), ("no date", "long"): ("no date", "no date"), ("no date", "short"): ("n.d.", "n.d."),
    ("available at", "long"): ("available at", "available at"), ("ibid", "long"): ("ibid.", "ibid."),
    ("online", "long"): ("online", "online"), ("cited", "long"): ("cited", "cited"), ("circa", "short"): ("c.", "c."),
    ("presented at", "long"): ("presented at", "presented at"), ("anonymous", "long"): ("anonymous", "anonymous"),
    ("anonymous", "short"): ("anon.", "anon."), ("forthcoming", "long"): ("forthcoming", "forthcoming"),
    ("in press", "long"): ("in press", "in press"), ("internet", "long"): ("internet", "internet"),
    ("edition", "long"): ("edition", "editions"), ("edition", "short"): ("ed.", "eds."),
    ("page", "long"): ("page", "pages"), ("page", "short"): ("p.", "pp."), ("issue", "long"): ("issue", "issues"),
    ("issue", "short"): ("no.", "nos."), ("volume", "long"): ("volume", "volumes"), ("volume", "short"): ("vol.", "vols."),
    ("chapter", "long"): ("chapter", "chapters"), ("chapter", "short"): ("chap.", "chaps."),
    ("section", "short"): ("sec.", "secs."), ("figure", "short"): ("fig.", "figs."), ("paragraph", "short"): ("para.", "paras."),
    ("line", "short"): ("l.", "ll."), ("number", "short"): ("no.", "nos."), ("number-of-pages", "long"): ("page", "pages"),
    ("number-of-pages", "short"): ("p.", "pp."),
    ("editor", "long"): ("editor", "editors"), ("editor", "short"): ("ed.", "eds."),
    ("editor", "verb"): ("edited by", "edited by"), ("editor", "verb-short"): ("ed.", "ed."),
    ("translator", "long"): ("translator", "translators"), ("translator", "short"): ("trans.", "trans."),
    ("translator", "verb"): ("translated by", "translated by"), ("translator", "verb-short"): ("trans.", "trans."),
    ("container-author", "verb"): ("by", "by"), ("collection-editor", "short"): ("ed.", "eds."),
    ("ordinal", "long"): ("th", "th"), ("ordinal-01", "long"): ("st", "st"), ("ordinal-02", "long"): ("nd", "nd"),
    ("ordinal-03", "long"): ("rd", "rd"), ("ordinal-11", "long"): ("th", "th"), ("ordinal-12", "long"): ("th", "th"),
    ("ordinal-13", "long"): ("th", "th"), ("open-quote", "long"): ("“", "“"), ("close-quote", "long"): ("”", "”"),
    ("open-inner-quote", "long"): ("‘", "‘"), ("close-inner-quote", "long"): ("’", "’"),
    ("page-range-delimiter", "long"): ("–", "–"),
}
VI = {
    ("and", "long"): ("và", "và"), ("et-al", "long"): ("và cộng sự", "và cộng sự"), ("accessed", "long"):
    ("truy cập ngày", "truy cập ngày"), ("retrieved", "long"): ("truy cập", "truy cập"), ("from", "long"): ("từ", "từ"),
    ("in", "long"): ("trong", "trong"), ("no date", "long"): ("không năm", "không năm"),
    ("no date", "short"): ("k.n.", "k.n."), ("available at", "long"): ("truy cập tại", "truy cập tại"),
    ("ibid", "long"): ("Như trên", "Như trên"), ("online", "long"): ("trực tuyến", "trực tuyến"),
    ("page", "long"): ("trang", "trang"), ("page", "short"): ("tr.", "tr."), ("issue", "short"): ("số", "số"),
    ("volume", "short"): ("tập", "tập"), ("volume", "long"): ("tập", "tập"), ("chapter", "short"): ("chương", "chương"),
    ("edition", "short"): ("tái bản", "tái bản"), ("edition", "long"): ("lần tái bản", "lần tái bản"),
    ("editor", "long"): ("chủ biên", "chủ biên"), ("editor", "short"): ("cb.", "cb."),
    ("editor", "verb"): ("chủ biên", "chủ biên"), ("translator", "long"): ("người dịch", "người dịch"),
    ("translator", "short"): ("dịch", "dịch"), ("translator", "verb"): ("dịch bởi", "dịch bởi"),
    ("ordinal", "long"): ("", ""), ("ordinal-01", "long"): ("", ""), ("ordinal-02", "long"): ("", ""),
    ("ordinal-03", "long"): ("", ""),
}
FALLBACK_FORMS = {"verb-short": "verb", "symbol": "short", "short": "long", "verb": "long"}


def lookup(name, form, plural, own_terms, vietnamese):
    """The term text; the style's own locale terms win; a missing form falls back like CSL (short -> long)."""
    tables = [own_terms, VI if vietnamese else {}, EN]
    while form:
        for table in tables:
            value = table.get((name, form))
            if value is not None:
                return (value[1] if plural else value[0]) or ""
        form = FALLBACK_FORMS.get(form)
    if name.startswith("month-") and name[6:].isdigit() and 1 <= int(name[6:]) <= 12:
        index = int(name[6:]) - 1
        return ("tháng %d" % (index + 1)) if vietnamese else MONTHS_EN[index]
    return ""


def month(number, form, vietnamese):
    if vietnamese:
        return "tháng %d" % number if form in ("long", "short") else str(number)
    return MONTHS_EN_ABBR[number - 1] if form == "short" else MONTHS_EN[number - 1]
