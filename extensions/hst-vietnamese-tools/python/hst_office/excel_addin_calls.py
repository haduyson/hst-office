# SPDX-License-Identifier: AGPL-3.0-only
"""Formulas of Excel files that call VND() or USD() through a Vietnamese number-words add-in, turned into calls of the
HST functions VND and USD (calc_functions.py). Pure Python; excel_addin_calls_job.py applies it after a load.

What the formula text of an imported cell (XCell.getFormula, the API grammar) looks like for such a call:
  - a function of an add-in workbook (.xla/.xlam): .xlsx stores "[1]!VND(A1)" with an external link to the
    workbook, .xls an external name of that workbook. Calc keeps it as an external name, "'file:///C:/Program%20Files
    %20(x86)/vnTools/Ufunctions.xlam'#VND(A1)", and the cell shows an error. When the link is relative to an Office
    folder (relationship types xlLibrary, xlAlternateStartup) Calc keeps "[1]!VND(A1)" without the file name, which
    is then read from the .xlsx package itself (external_link_files);
  - a function registered by an XLL add-in: .xlsx stores "_xll.VND(A1)", which Calc does not know (#NAME?).
A plain "VND(A1)" (an .xls add-in function, an .xlsx naming the function without a prefix) already reaches the HST
function at import, through its CompatibilityName in CalcAddIns.xcu; an .ods keeps it unresolved ("vnd(A1)").

Only VND and USD of the known add-in files are rewritten; any other external reference, external name or function
stays exactly as it was. Text inside string literals is never touched.
"""
import posixpath
import re
import xml.etree.ElementTree as ET
from urllib.parse import unquote

PROGRAMMATIC = "ORG.HST.OFFICE.VI.CALCFUNCTIONS."  # the add-in service: the API grammar names its functions so
FUNCTIONS = ("VND", "USD")
# file names of the add-ins whose VND()/USD() HST provides (compared ignoring case): the VBA add-in workbook and the
# XLL add-in with its companion workbook for old Excel versions
ADDIN_FILES = frozenset(("ufunctions.xla", "ufunctions.xlam", "acchelper.xll", "acchelperex.xla", "acchelperex.xlam"))

# One pass over the formula: string literals and quoted names are matched whole, so nothing inside them is rewritten.
_TOKENS = re.compile(r"""
    (?P<string>"(?:[^"]|"")*")
  | '(?P<document>(?:[^']|'')*)'\#(?P<external>[A-Za-z_][\w.]*)(?=\s*\()
  | (?P<quoted>'(?:[^']|'')*')
  | (?<![\w.$\]])\[(?P<link>\d+)\]!(?P<linked>[A-Za-z_][\w.]*)(?=\s*\()
  | (?<![\w.$])(?i:_xll)\.(?P<xll>[A-Za-z_][\w.]*)(?=\s*\()
  | (?<![\w.$\]#!])(?P<plain>(?i:VND|USD))(?=\s*\()
""", re.VERBOSE)
# for a quick look before parsing: does the text mention one of the call forms at all
HINT = re.compile(r"_xll\.|'#|\]!|\b(?:VND|USD)\s*\(", re.I)

# a bare VND( / USD( in the API grammar: a name that did not resolve to the HST function
UNRESOLVED = re.compile(r"(?<![\w.$\]#!'])(?:VND|USD)\s*\(", re.I)
# a Basic or VBA function of the document itself with one of these names: its plain calls are left to it
_MACRO_FUNCTION = re.compile(r"^[ \t]*(?:(?:public|private|static)[ \t]+)*function[ \t]+(vnd|usd)\b", re.I | re.M)

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_PACKAGE_RELS = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"


def file_name(path):
    """The lower-case file name of a path as a formula or a package writes it: a URL, a Windows or a relative path."""
    return re.split(r"[\\/]", unquote(path))[-1].strip().lower()


def document_file_name(document):
    """The file name of an external document quoted in a formula ("'file:///C:/a%20b/Ufunctions.xlam'" content,
    doubled quotes undone)."""
    return file_name(document.replace("''", "'"))


def _known_function(name):
    upper = name.upper()
    return upper if upper in FUNCTIONS else None


def _single_argument_end(formula, start):
    """For the call whose "(" is at or after `start`: the index of its ")" when it has exactly one non-empty argument,
    else None. String literals and quoted names are skipped; nested parentheses are followed."""
    index = formula.index("(", start)
    depth, begin, quote = 0, index + 1, None
    for position in range(index, len(formula)):
        char = formula[position]
        if quote:
            if char == quote:
                quote = None  # a doubled quote closes and reopens: the same result
        elif char in "\"'":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                return position if formula[begin:position].strip() else None
        elif char == ";" and depth == 1:
            return None
    return None


def rewrite(formula, link_files=None, plain=False):
    """The formula with every add-in VND/USD call replaced by the HST function; the same text when there is none.
    `link_files`: {external link number: file name} of an .xlsx package, for "[n]!VND(" calls. `plain`: also a bare
    "VND(" / "USD(", which the API grammar only shows when the name did not resolve to the HST function (an .ods
    written by another program); the caller passes False when the document's own macros define such a function.

    The XLL add-in reads the unit even for VND(amount)/USD(amount), where HST's VND/USD (the add-in workbook's
    reading) read only the number: its one-argument calls get the argument TRUE() that asks HST for the unit."""
    if not formula or not HINT.search(formula):
        return formula
    edits = []  # (start, end, replacement) on the original text
    for match in _TOKENS.finditer(formula):
        name, xll = None, False
        if match.group("external") is not None:
            document = document_file_name(match.group("document"))
            if document in ADDIN_FILES:
                name, xll = _known_function(match.group("external")), document.startswith("acchelper")
        elif match.group("linked") is not None:
            document = (link_files or {}).get(int(match.group("link")))
            if document in ADDIN_FILES:
                name, xll = _known_function(match.group("linked")), document.startswith("acchelper")
        elif match.group("xll") is not None:
            name, xll = _known_function(match.group("xll")), True
        elif match.group("plain") is not None and plain:
            name = _known_function(match.group("plain"))
        if not name:
            continue
        edits.append((match.start(), match.end(), PROGRAMMATIC + name))
        end = _single_argument_end(formula, match.end()) if xll else None
        if end is not None:
            edits.append((end, end, ";TRUE()"))
    for start, end, text in sorted(edits, reverse=True):
        formula = formula[:start] + text + formula[end:]
    return formula


def _relationships(package, part):
    """{relationship id: target} of a package part ("xl/workbook.xml" -> "xl/_rels/workbook.xml.rels")."""
    folder, name = posixpath.split(part)
    rels = posixpath.join(folder, "_rels", name + ".rels")
    if rels not in package.namelist():
        return {}
    root = ET.fromstring(package.read(rels))
    return {r.get("Id"): r.get("Target", "") for r in root.iter(_PACKAGE_RELS)}


def external_link_files(package):
    """{external link number (1-based, as in "[1]!VND"): lower-case file name} of an open .xlsx zipfile.ZipFile, from
    workbook.xml <externalReferences> and each externalLink part's relationship. {} when the package has none."""
    workbook = "xl/workbook.xml"
    if workbook not in package.namelist():
        return {}
    root = ET.fromstring(package.read(workbook))
    references = root.find(_MAIN + "externalReferences")
    if references is None:
        return {}
    workbook_rels = _relationships(package, workbook)
    files = {}
    for number, reference in enumerate(references.findall(_MAIN + "externalReference"), 1):
        target = workbook_rels.get(reference.get(_REL_ID))
        if not target:
            continue
        part = posixpath.normpath(posixpath.join("xl", target)) if not target.startswith("/") else target[1:]
        if part not in package.namelist():
            continue
        book = ET.fromstring(package.read(part)).find(_MAIN + "externalBook")
        link_target = _relationships(package, part).get(book.get(_REL_ID)) if book is not None else None
        if link_target:
            files[number] = file_name(link_target)
    return files


def macro_defined_functions(sources):
    """Upper-case names among VND/USD that the given Basic/VBA module sources define as functions."""
    return {name.upper() for source in sources for name in _MACRO_FUNCTION.findall(source or "")}
