# SPDX-License-Identifier: AGPL-3.0-only
"""What real Office-made VBA projects have and HST's must have: a repeatable comparison.

Usage: python3 tests/runtime/vba_office_rules.py FILE.docm|.xlsm|.xls|.doc [...]

Each rule comes from Office-made files (see plans/reports/vba-261104-1224-vba-authoring-writer-sheets.md,
"Reference files"), and the rule set must pass on those files, or the rule is wrong. Passing does NOT
mean that Office accepts a file: earlier samples passed every structural check and real Office
rejected them. It only catches differences already known to matter or to be required.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vba_cfb import decompress  # noqa: E402
from vba_form_structure import module_sources, open_project  # noqa: E402

FORMS_LIBRARY = b"{0D452EE1-E08F-101A-852E-02608C4D0BB4}"
ZERO_CLSID = "00000000-0000-0000-0000-000000000000"
FRAME_CLSID = "6e182020-f460-11ce-9bcd-00aa00608e01"


def dir_records(data):
    position, out = 0, []
    while position + 6 <= len(data):
        record, size = struct.unpack_from("<HI", data, position)
        if record == 0x0009:  # PROJECTVERSION: the size field holds 4 but 6 bytes follow
            size = 6
        out.append((record, data[position + 6:position + 6 + size]))
        position += 6 + size
    return out


def check_compobj(cfb, entry, name, expected_clsid, program_id, problems):
    data = cfb.read(cfb.children(entry)["\x01CompObj"])
    clsid = data[12:28].hex()
    if expected_clsid == ZERO_CLSID and clsid != "0" * 32:
        problems.append(f"{name}: CompObj has a class; Office writes none on a form")
    if (program_id and program_id not in data) or (not program_id and b"Forms.Form" in data):
        problems.append(f"{name}: CompObj ProgID differs from Office's")


def check_container(cfb, entry, name, problems):
    for child, item in cfb.children(entry).items():
        if item["type"] == 1:
            if not re.fullmatch(r"i\d+", child):
                problems.append(f"{name}/{child}: unexpected storage")
            elif item["clsid"].lower() != FRAME_CLSID:
                continue  # MultiPage and other containers have their own class
            else:
                check_compobj(cfb, item, f"{name}/{child}", FRAME_CLSID, b"Forms.Frame.1", problems)
                check_container(cfb, item, f"{name}/{child}", problems)


def problems_of(path):
    cfb, root = open_project(path)
    top = cfb.children(root)
    project = cfb.read(top["PROJECT"]).decode("cp1252", "replace")
    records = dir_records(decompress(cfb.read(cfb.children(top["VBA"])["dir"])))
    ids = [record for record, _ in records]
    problems = []
    if re.search(r"(?m)^Document=", project) is None:
        problems.append("PROJECT: no document module; every Office-made project has one")
    is_word = re.search(r"(?m)^Document=ThisDocument/", project) is not None or path.lower().endswith((".doc", ".docm"))
    if is_word:
        if "ThisDocument" not in module_sources(path):
            problems.append("no ThisDocument module")
        else:
            source = module_sources(path)["ThisDocument"]
            if b'VB_Base = "1Normal.ThisDocument"' not in source:
                problems.append("ThisDocument: VB_Base is not 1Normal.ThisDocument")
        if 0x000E not in ids:
            problems.append("dir: no project reference (Normal)")
    forms = re.findall(r"(?m)^BaseClass=(.+?)\r?$", project)
    if forms:
        controls = [body for record, body in records if record == 0x0033]
        if not any(FORMS_LIBRARY in body for body in controls) or 0x002F not in ids or 0x0030 not in ids:
            problems.append("dir: MS Forms is not a REFERENCEORIGINAL + REFERENCECONTROL (MS-OVBA 2.3.5 MUST)")
    for form in forms:
        entry = top.get(form)
        if entry is None:
            problems.append(f"{form}: no designer storage")
            continue
        if entry["clsid"] != ZERO_CLSID:
            problems.append(f"{form}: storage has a class; Office writes none")
        check_compobj(cfb, entry, form, ZERO_CLSID, b"", problems)
        check_container(cfb, entry, form, problems)
    return problems


def main(paths):
    failed = 0
    for path in paths:
        problems = problems_of(path)
        print(("FAIL " if problems else "PASS ") + os.path.basename(path))
        for problem in problems:
            print("  " + problem)
        failed += bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
