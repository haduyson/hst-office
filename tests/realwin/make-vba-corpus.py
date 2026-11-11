#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Write the synthetic VBA comparison corpus and its manifest. Usage: make-vba-corpus.py OUTDIR

Every file is generated here; nothing comes from the test machines. The binary .xls/.doc variants are not
written here: the reference run derives them by Save As from the listed source file (manifest `derive_from`).
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vba_corpus_excel as xl  # noqa: E402
import vba_corpus_kit as kit  # noqa: E402
import vba_corpus_language as lang  # noqa: E402
import vba_corpus_word as wd  # noqa: E402

# Reference suite Save As formats: Excel 97-2003 workbook, Word 97-2003 document, and the suite's own
# macro-enabled Open XML (a file as the reference suite writes it, with its compiled caches).
XLS, DOC, XLSM, DOCM = 56, 0, 52, 13


def corpus():
    """[(file name, host, modules, functions, codepage)]."""
    excel = [
        ("xl-ranges.xlsm", [("Cases", xl.RANGES + "\n" + xl.RANGE_HELPERS)]),
        ("xl-formulas.xlsm", [("Cases", xl.FORMULAS)]),
        ("xl-sheets.xlsm", [("Cases", xl.SHEETS)]),
        ("xl-names.xlsm", [("Cases", xl.NAMES)]),
        ("xl-props.xlsm", [("Cases", xl.PROPS)]),
        ("xl-events.xlsm", [("Cases", xl.EVENTS), ("AutoMod", xl.AUTO_OPEN)] + xl.EVENT_MODULES),
        ("xl-language.xlsm", lang.MODULES),
    ]
    word = [
        ("wd-text.docm", [("Cases", wd.TEXT)]),
        ("wd-find.docm", [("Cases", wd.FIND + "\n" + wd.HELPERS)]),
        ("wd-props.docm", [("Cases", wd.PROPS)]),
        ("wd-events.docm", [("Cases", wd.EVENTS), ("AutoMod", wd.AUTO_OPEN)] + wd.EVENT_MODULES),
        ("wd-language.docm", lang.MODULES),
    ]
    out = []
    for host, items in (("excel", excel), ("word", word)):
        for name, modules in items:
            functions = [f for _m, source in modules for f in kit.function_names(source) if f in cases_of(source)]
            out.append((name, host, [("Kit", kit.KIT)] + modules, functions, 1252))
    out.append(("xl-vn-literal.xlsm", "excel", [("Cases", lang.LITERAL)], ["LiteralVn"], 1258))
    out.append(("xl-compile.xlsm", "excel", [("Cases", lang.COMPILE)], ["CompileNextTwo", "CompileDivZero"], 1252))
    return out


def cases_of(source):
    """Case functions are the ones that return the Kit's lines; helpers are called by them, not by the drivers."""
    names = set()
    for block in source.split("End Function"):
        found = kit.function_names(block)
        if found and ("= Take()" in block or block.lstrip().startswith("Public Function LiteralVn")):
            names.add(found[0])
    return names


DERIVED = [("xl-ranges.xls", "xl-ranges.xlsm", XLS), ("xl-events.xls", "xl-events.xlsm", XLS),
           ("xl-language.xls", "xl-language.xlsm", XLS), ("wd-find.doc", "wd-find.docm", DOC),
           ("wd-events.doc", "wd-events.docm", DOC), ("xl-events-office.xlsm", "xl-events.xlsm", XLSM),
           ("xl-language-office.xlsm", "xl-language.xlsm", XLSM), ("wd-events-office.docm", "wd-events.docm", DOCM),
           ("wd-find-office.docm", "wd-find.docm", DOCM)]


def write(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, host, modules, functions, codepage in corpus():
        data = kit.xlsm(modules, codepage) if host == "excel" else kit.docm(modules, codepage)
        (out_dir / name).write_bytes(data)
        manifest.append(dict(file=name, host=host, functions=functions, events=name.split("-")[1].startswith("events")))
    by_name = {entry["file"]: entry for entry in manifest}
    for name, source, save_format in DERIVED:
        manifest.append(dict(by_name[source], file=name, derive_from=source, save_format=save_format))
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return manifest


def main(argv):
    if len(argv) != 2:
        raise SystemExit(__doc__)
    manifest = write(argv[1])
    print(len(manifest), "files", sum(len(m["functions"]) for m in manifest), "case functions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
