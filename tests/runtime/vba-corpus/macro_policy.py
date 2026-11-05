# SPDX-License-Identifier: AGPL-3.0-only
"""Decide from static analysis alone what may run in the sandbox, per procedure.

Blocked in any file unless its source is listed as a benign test: Shell or process launches, downloads, system COM objects.
A procedure is blocked when it, or anything it calls by name, uses one; the whole file is blocked when code that runs by itself
(Auto_Open, Workbook_Open, Document_Open...) reaches one. File writes stay allowed: the sandbox has only a private tmpfs.
"""
import re

SHELL = re.compile(r'\bShell\b\s*[("\w]|WScript\.|Shell\.Application|ShellExecute|CreateProcess|WinExec|powershell|cmd(\.exe)?\s*/c|\bcscript\b|\bmshta\b|regsvr32|rundll32', re.I)
NET = re.compile(r"URLDownloadToFile|XMLHTTP|WinHttp|InternetOpen|Net\.WebClient|ServerXMLHTTP|\bftp://|Winsock|MSInet|bitsadmin|certutil", re.I)
OBJECT = re.compile(r'\b(?:CreateObject|GetObject)\s*\(\s*"([^"]*)"', re.I)
SAFE_OBJECTS = re.compile(r"^(scripting\.(dictionary|filesystemobject)|vbscript\.regexp|adodb\.(connection|recordset|command)|"
                          r"(excel|word|outlook|access|powerpoint)\.\w+(\.\d+)?|new:|msforms\.\w+)", re.I)
AUTO_NAME = re.compile(r"^(auto_?(open|close|exec|new|exit)|workbook_\w+|document_\w+|worksheet_\w+|\w+_activate|\w+_initialize|main_?auto)$", re.I)
PROC_HEAD = re.compile(r"^[ \t]*(?:(?:Public|Private|Friend|Static)[ \t]+)*(Sub|Function|Property[ \t]+(?:Get|Let|Set))[ \t]+([^\s(]+)", re.I | re.M)
TOKEN = re.compile(r"[^\W\d]\w*")
COMMENT = re.compile(r"(?m)^[ \t]*(?:'|Rem\b).*$", re.I)


def flags_of(code):
    code = COMMENT.sub("", code)
    found = set()
    if SHELL.search(code):
        found.add("shell")
    if NET.search(code):
        found.add("network")
    for match in OBJECT.finditer(code):
        if not SAFE_OBJECTS.match(match.group(1)):
            found.add("object:" + match.group(1).lower())
    return found


def split_procedures(code):
    heads = list(PROC_HEAD.finditer(code))
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(code)
        yield head.group(2), code[head.start():end]


def decide(scan, benign):
    """{'run': bool, 'why': [...], 'skip': [proc names], 'flags': [...]}. benign: source is a known test file."""
    procs, module_level = {}, set()
    for module in scan.get("modules", []):
        code = module["code"] or ""
        heads = list(PROC_HEAD.finditer(code))
        module_level |= flags_of(code[:heads[0].start()] if heads else code)
        for name, body in split_procedures(code):
            entry = procs.setdefault(name.lower(), dict(flags=set(), calls=set()))
            entry["flags"] |= flags_of(body)
            entry["calls"] |= {t.lower() for t in TOKEN.findall(body)}
    names = set(procs)
    bad = {n for n, p in procs.items() if p["flags"]}
    changed = True
    while changed:
        changed = False
        for name, proc in procs.items():
            if name not in bad and proc["calls"] & names & bad:
                bad.add(name)
                changed = True
    flags = sorted(set().union(*[p["flags"] for p in procs.values()], module_level) if procs else module_level)
    autos = sorted(n for n in bad if AUTO_NAME.match(n))
    result = dict(flags=flags, skip=sorted(bad), why=[], run=True, benign=benign)
    if benign:
        result["skip"] = []
    elif autos or module_level:
        result.update(run=False, why=[f"runs by itself into flagged code: {', '.join(autos)[:120]}" if autos else "flagged module-level code"])
    return result
