# SPDX-License-Identifier: AGPL-3.0-only
"""Names in bibliography entries and in-text citations, following the style options (citation_style_options).

Vietnamese names are written in full and in their own order by default ("Nguyễn Văn An"); styles may invert them
the APA way ("An, N. V.", ĐH Cần Thơ), treat them as foreign names, or drop the accents (IEEE at ĐH KHTN).
"""
from . import citation_names as names
from . import vietnamese_text as vt
from .citation_terms import localize


def _family(name, upper):
    family = " ".join(p for p in (name.get("non-dropping-particle"), name.get("family")) if p)
    return family.upper() if upper else family


def person(name, opts, form=None, vi_form=None):
    """One name as the style prints it in the bibliography."""
    upper = opts.get("familyUpper", False)
    if name.get("literal"):
        return name["literal"].upper() if upper else name["literal"]
    if names.is_east_asian(name):
        return name.get("family", "") + name.get("given", "")
    ascii_only = opts.get("viAscii", False) and names.is_vietnamese(name)
    clean = vt.remove_diacritics if ascii_only else (lambda text: text)
    vi_form = vi_form or opts.get("viName", "natural")
    if names.is_vietnamese(name) and vi_form != "as-foreign":
        family, given = _family(name, upper), name.get("given", "")
        if vi_form == "given-comma-initials" and given:
            words = given.split(" ")
            return clean(words[-1] + ", " + names.initials(name.get("family", "") + " " + " ".join(words[:-1])))
        return clean(" ".join(p for p in (family, given) if p))
    form = form or opts.get("foreignName", "family-comma-initials")
    family, given = clean(_family(name, upper)), clean(name.get("given", ""))
    suffix = name.get("suffix", "")
    if not given:
        return family
    if form in ("natural", "given-family"):
        text = given + " " + family
        return text + (", " + suffix if suffix else "")
    if form == "family-comma-given":
        return family + ", " + given + (", " + suffix if suffix else "")
    space = opts.get("initialsSpace", True)
    if form == "family-comma-initials":
        return family + ", " + names.initials(given, space=space) + (", " + suffix if suffix else "")
    if form == "family-initials":
        return family + " " + names.initials(given, space=False)
    if form == "family-compact":
        return family + " " + names.initials(given, period=False) + (" " + suffix.rstrip(".") if suffix else "")
    return names.initials(given, space=space) + " " + family + (", " + suffix if suffix else "")  # initials-family


def join(parts, and_word, and_comma, delimiter=", ", et_al=None, et_al_term="et al.", et_al_comma=False):
    """"A, B, & C", "A and B", "A, B, C, et al.", APA's "A, B, … S, . . . Z" (et_al["last"]). With two names,
    "always" puts the comma before "and" only after an inverted name ("Smith, John, and Jane Doe"); a comma before
    "et al." likewise follows an inverted name or a list ("Smith, John, et al." but "Nguyễn Văn An và cộng sự")."""
    count = len(parts)
    if et_al and count >= et_al["min"]:
        if et_al.get("last") and count > et_al["use"] + 1:
            return delimiter.join(parts[:et_al["use"]]) + delimiter + ". . . " + parts[-1]
        if not et_al.get("last"):
            shown = parts[:et_al["use"]]
            comma = et_al_comma and (len(shown) > 1 or "," in shown[0])
            return delimiter.join(shown) + (delimiter if comma else " ") + et_al_term
    if count <= 1:
        return "".join(parts)
    if not and_word:
        return delimiter.join(parts)
    comma = (count >= 3 and and_comma in ("always", "3+")) or (count == 2 and and_comma == "always" and "," in parts[0])
    comma = comma and and_word != "và"  # Vietnamese puts no comma before "và"
    head = delimiter.join(parts[:-1])
    return head + (delimiter.rstrip() if comma else "") + " " + and_word + " " + parts[-1]


def bibliography_names(name_list, opts, lang, form=None, vi_form=None, first_inverted=None, et_al=None,
                       and_comma=None):
    """Names of one variable for an entry. ``lang`` picks the localized "and" / "et al." words; ``et_al``
    replaces the bibliography rule (notes use ``noteEtAl``)."""
    inverted = opts.get("firstInverted", False) if first_inverted is None else first_inverted
    parts = []
    for index, name in enumerate(name_list):
        own_form = form if (index == 0 or not inverted) else "given-family"
        parts.append(person(name, opts, own_form, vi_form))
    return join(parts, localize(opts.get("bibAnd", ""), lang), and_comma or opts.get("bibAndComma", "never"),
                opts.get("nameDelimiter", ", "), et_al or opts.get("bibEtAl"), localize(opts.get("etAlTerm", ""), lang),
                opts.get("etAlComma", False))


def short_person(name, opts):
    """In-text form: family name, organisation in full, Vietnamese full / given / family per citeViName."""
    if name.get("literal"):
        return name["literal"]
    if names.is_east_asian(name):
        return name.get("family", "") + name.get("given", "")
    if names.is_vietnamese(name) and opts.get("viName") != "as-foreign":
        mode = opts.get("citeViName", "full")
        given = name.get("given", "")
        if mode == "given" and given:
            text = given.split(" ")[-1]
        elif mode == "family":
            text = name.get("family", "")
        else:
            text = " ".join(p for p in (name.get("family"), given) if p)
        return vt.remove_diacritics(text) if opts.get("viAscii") else text
    family = _family(name, False)
    return vt.remove_diacritics(family) if opts.get("viAscii") and names.is_vietnamese(name) else family


def cite_names(name_list, opts, lang, et_al=None, initials_for=()):
    """"Nguyễn Văn An & Lê Bình", "Smith et al." for in-text citations and short notes. A first author whose
    family name is in ``initials_for`` gets initials ("J. Smith"), as APA 7 §8.20 asks when two first authors
    share a family name."""
    parts = [short_person(n, opts) for n in name_list]
    first = name_list[0] if name_list else {}
    if parts and parts[0] in initials_for and first.get("given") and not names.is_vietnamese(first) \
            and not names.is_east_asian(first):
        parts[0] = names.initials(first["given"]) + " " + parts[0]
    return join(parts, localize(opts.get("citeAnd", "&"), lang), opts.get("citeAndComma", "never"), ", ",
                et_al if et_al is not None else opts.get("citeEtAl"), localize(opts.get("etAlTerm", ""), lang), False)


def label_text(text, term_text, position):
    if position == "before":
        return term_text + " " + text
    if position == "comma":
        return text + ", " + term_text
    return text + " (" + term_text + ")"
