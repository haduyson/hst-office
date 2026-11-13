# SPDX-License-Identifier: AGPL-3.0-only
"""Validate an HST citation style file (JSON) so a mistake names the file and the key instead of failing later.

Template elements (a layout is a list of them) — exactly one of:
  {"v": variable}        a CSL variable: names, dates, numbers and text are formatted by their kind
  {"group": [elements]}  printed only when at least one variable inside printed something
  {"text": "literal"}    literal text (may be {"vi": ..., "other": ...} or "@option")
  {"term": name}         a word from citation_terms ("tr.", "Nxb"…), in the item's language
  {"macro": name}        a named list of elements from "macros"
Common keys: prefix, suffix, italic, bold, sup, quotes, wrap ("()", "[]", "<>"), case (upper, lower, capfirst,
title), delimiter (groups and name lists), if / else (conditions below), form, substitute, label, labelPos,
nameForm, viName, andComma (always/never/3+), etAl (option holding the et-al rule, e.g. "noteEtAl"), noDate, fallbackTerm, plural.
Conditions (a string or a list that must all hold): "VAR", "!VAR", "type=a,b", "type!=a,b", "lang=vi",
"lang!=vi", "opt.NAME", "!opt.NAME", "opt.NAME=value", "pos=first|subsequent|ibid", "loc", "!loc",
"day=VAR" (the date VAR has a day: "ban hành ngày 07 tháng 5 năm 2009" only when the day is known),
"shared-author" (another cited work has the same author; note styles) and "suppress-author".
Presets may add their own "terms", "layouts" and "notes" (merged over the style's) and a "source".
"""
import re

from . import citation_model as model
from . import citation_terms as terms
from .citation_style_options import SCHEMA, check_value

TOP_KEYS = {"id", "name", "description", "source", "class", "options", "presets", "layouts", "alias", "macros",
            "notes", "terms", "version"}
ELEMENT_KEYS = {"v", "group", "text", "term", "macro", "if", "else", "prefix", "suffix", "italic", "bold", "sup",
                "quotes", "wrap", "case", "delimiter", "form", "substitute", "label", "labelPos", "nameForm",
                "noDate", "fallbackTerm", "plural", "viName", "etAl", "andComma"}
SPECIAL_VARS = {"locator", "citation-number", "year-suffix", "title-or-short"}
FLAGS = {"shared-author", "suppress-author"}  # conditions set by the engine (note styles)
VARIABLES = set(model.TEXT_VARS) | set(model.NAME_VARS) | set(model.DATE_VARS) | SPECIAL_VARS
CASES = {"upper", "lower", "capfirst", "title"}
WRAPS = {"()", "[]", "<>"}
_COND = re.compile(r"^(!?[A-Za-z_-]+|type!?=[a-z_,-]+|lang!?=[a-z]+|!?opt\.[A-Za-z]+(=[^\s]+)?|pos=[a-z|]+|!?loc|day=[a-z-]+)$")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


class StyleError(ValueError):
    pass


def check_condition(cond, where, errors):
    for part in cond if isinstance(cond, list) else [cond]:
        if not isinstance(part, str) or not _COND.match(part):
            errors.append("%s.if: điều kiện không hiểu: %r" % (where, part))
        elif re.match(r"^!?[A-Za-z_-]+$", part) and part.lstrip("!") not in VARIABLES | FLAGS | {"loc"}:
            errors.append("%s.if: biến không có: %s" % (where, part))


def check_elements(elements, where, style, errors):
    if not isinstance(elements, list):
        errors.append("%s: phải là danh sách phần tử" % where)
        return
    for index, element in enumerate(elements):
        check_element(element, "%s[%d]" % (where, index), style, errors)


def _check_string(value, where, style, errors):
    values = list(value.values()) if isinstance(value, dict) else [value]
    for text in values:
        if not isinstance(text, str):
            errors.append("%s: phải là chuỗi" % where)
        elif text.startswith("@") and text[1:] not in style.get("options", {}):
            errors.append("%s: tùy chọn không có: %s" % (where, text))


def check_element(element, where, style, errors):
    if not isinstance(element, dict):
        errors.append("%s: phải là đối tượng" % where)
        return
    kinds = [k for k in ("v", "group", "text", "term", "macro") if k in element]
    if len(kinds) != 1:
        errors.append("%s: cần đúng một trong v, group, text, term, macro" % where)
    for key in set(element) - ELEMENT_KEYS:
        errors.append("%s: khóa không hiểu: %s" % (where, key))
    if "v" in element and element["v"] not in VARIABLES:
        errors.append("%s.v: biến không có: %s" % (where, element["v"]))
    if "term" in element and not terms.known(element["term"]):
        errors.append("%s.term: thuật ngữ không có: %s" % (where, element["term"]))
    if "fallbackTerm" in element and not terms.known(element["fallbackTerm"]):
        errors.append("%s.fallbackTerm: thuật ngữ không có" % where)
    if "etAl" in element and element["etAl"] not in ("bibEtAl", "citeEtAl", "noteEtAl"):
        errors.append("%s.etAl: phải là bibEtAl, citeEtAl hoặc noteEtAl" % where)
    if "macro" in element and element["macro"] not in style.get("macros", {}):
        errors.append("%s.macro: macro không có: %s" % (where, element["macro"]))
    if "group" in element:
        check_elements(element["group"], where + ".group", style, errors)
    for key in ("text", "prefix", "suffix", "delimiter"):
        if key in element:
            _check_string(element[key], "%s.%s" % (where, key), style, errors)
    if element.get("case") is not None and element["case"] not in CASES:
        errors.append("%s.case: %s" % (where, element["case"]))
    if element.get("wrap") is not None and element["wrap"] not in WRAPS:
        errors.append("%s.wrap: %s" % (where, element["wrap"]))
    if "if" in element:
        check_condition(element["if"], where, errors)
    if "else" in element:
        check_elements(element["else"] if isinstance(element["else"], list) else [element["else"]],
                       where + ".else", style, errors)
    if "substitute" in element:
        check_elements(element["substitute"], where + ".substitute", style, errors)


PRESET_KEYS = {"id", "name", "options", "source", "terms", "layouts", "notes"}


def _check_terms(table, where, errors):
    if not isinstance(table, dict):
        errors.append("%s: phải là {\"vi\": {…}, \"en\": {…}}" % where)
        return
    for lang, words in table.items():
        unknown = [name for name in (words if isinstance(words, dict) else {}) if not terms.known(name)]
        if lang not in ("vi", "en") or not isinstance(words, dict) or unknown:
            errors.append("%s.%s: ngôn ngữ hoặc thuật ngữ không hiểu %s" % (where, lang, unknown))


def _check_preset_extras(preset, where, data, errors):
    """A preset may also carry its own terms, layouts and note layouts (merged over the style's)."""
    errors += ["%s: khóa không hiểu: %s" % (where, key) for key in sorted(set(preset) - PRESET_KEYS)]
    if "terms" in preset:
        _check_terms(preset["terms"], where + ".terms", errors)
    for kind, elements in (preset.get("layouts") or {}).items():
        check_elements(elements, "%s.layouts.%s" % (where, kind), data, errors)
    notes = preset.get("notes") or {}
    for kind, elements in (notes.get("layouts") or {}).items():
        check_elements(elements, "%s.notes.layouts.%s" % (where, kind), data, errors)
    if "short" in notes:
        check_elements(notes["short"], where + ".notes.short", data, errors)


def check_style(data, origin):
    """Raise StyleError listing every problem of a parsed style file."""
    errors = []
    if not isinstance(data, dict):
        raise StyleError("%s: tệp kiểu phải là đối tượng JSON" % origin)
    for key in set(data) - TOP_KEYS:
        errors.append("khóa không hiểu: %s" % key)
    if not isinstance(data.get("id"), str) or not _ID.match(data["id"]):
        errors.append("id: phải là chữ thường, số, dấu gạch ngang")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        errors.append("name: thiếu tên kiểu")
    if data.get("class") not in ("numeric", "author-date", "note"):
        errors.append("class: phải là numeric, author-date hoặc note")
    options = data.get("options")
    if not isinstance(options, dict):
        errors.append("options: thiếu")
        options = {}
    errors += ["options: thiếu %s" % name for name in SCHEMA if name not in options]
    errors += ["options: " + e for e in (check_value(k, v) for k, v in options.items()) if e]
    for index, preset in enumerate(data.get("presets", [])):
        if not (isinstance(preset, dict) and isinstance(preset.get("id"), str) and isinstance(preset.get("name"), str)
                and isinstance(preset.get("options"), dict)):
            errors.append("presets[%d]: cần id, name, options" % index)
            continue
        errors += ["presets[%d]: %s" % (index, e) for e in (check_value(k, v) for k, v in preset["options"].items()) if e]
        _check_preset_extras(preset, "presets[%d]" % index, data, errors)
    if "terms" in data:
        _check_terms(data["terms"], "terms", errors)
    for name, elements in (data.get("macros") or {}).items():
        check_elements(elements, "macros." + name, data, errors)
    layouts = data.get("layouts")
    if not isinstance(layouts, dict) or "default" not in layouts:
        errors.append("layouts: cần ít nhất \"default\"")
    for kind, elements in (layouts or {}).items():
        check_elements(elements, "layouts." + kind, data, errors)
    for source, target in (data.get("alias") or {}).items():
        if target not in (layouts or {}):
            errors.append("alias.%s: không có layout %s" % (source, target))
    notes = data.get("notes")
    if data.get("class") == "note":
        if not isinstance(notes, dict) or "default" not in notes.get("layouts", {}) or "short" not in notes:
            errors.append("notes: kiểu chú thích cần notes.layouts.default và notes.short")
        else:
            for kind, elements in notes["layouts"].items():
                check_elements(elements, "notes.layouts." + kind, data, errors)
            check_elements(notes["short"], "notes.short", data, errors)
    if errors:
        raise StyleError("%s: %s" % (origin, "; ".join(errors)))
