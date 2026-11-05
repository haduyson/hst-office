# SPDX-License-Identifier: AGPL-3.0-only
"""Inside the disposable container: what the runners share: loading a private copy, the modules of a document, the wrapper module."""
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, "/opt/hst/program")
os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:/opt/hst/program/fundamentalrc"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandbox_office import pv  # noqa: E402

PROC_RE = re.compile(r"^[ \t]*(?:Public[ \t]+)?(?:Static[ \t]+)?(Sub|Function)[ \t]+([^\s(]+)[ \t]*\(\s*\)", re.I | re.M)
FUNC_RE = re.compile(r"^[ \t]*(?:Public[ \t]+)?Function[ \t]+([^\s(]+)", re.I | re.M)
ANY_PROC_RE = re.compile(r"^[ \t]*(?:(?:Public|Private|Friend|Static)[ \t]+)*(?:Sub|Function)[ \t]+[^\s(]+", re.I | re.M)
CORPUS = os.environ.get("HST_CORPUS", "/corpus")
HARNESS = "HstHarnessRun"
WRAPPER = """Option VBASupport 1
Public Function HstCall()
  On Error GoTo HstFail
  Dim hstR As Variant
  {call}
  HstCall = "OK|" & CStr(hstR)
  Exit Function
HstFail:
  HstCall = "ERR|" & Err.Number & "|" & Erl & "|" & Err.Source & "|" & Err.Description
End Function
"""
NORMAL, CLASS, FORM, DOCUMENT = 1, 2, 3, 4  # com.sun.star.script.ModuleType (UNKNOWN = 0)


def emit(obj):
    print("@@R " + json.dumps(obj, ensure_ascii=False), flush=True)


def load(office, path, shown_name=None):
    """Load a private copy; shown_name keeps the original file name, which some macros test."""
    import uno
    folder = os.path.join("/tmp/work", str(time.monotonic_ns()))
    os.makedirs(folder)
    work = os.path.join(folder, shown_name or os.path.basename(path))
    shutil.copyfile(path, work)
    os.chmod(work, 0o600)
    return office.desktop.loadComponentFromURL(uno.systemPathToFileUrl(work), "_blank", 0, (pv("MacroExecutionMode", 4),))


def close_all(office):
    enum = office.desktop.getComponents().createEnumeration()
    while enum.hasMoreElements():
        try:
            enum.nextElement().close(True)
        except Exception:  # noqa: BLE001 - a document that cannot close is dropped with the office
            pass


def enumerate_modules(doc):
    libs = doc.BasicLibraries
    out = []
    for name in libs.getElementNames():
        libs.loadLibrary(name)
        library = libs.getByName(name)
        for module in library.getElementNames():
            source = library.getByName(module)
            mtype = library.getModuleInfo(module).ModuleType if hasattr(library, "getModuleInfo") and library.hasModuleInfo(module) else NORMAL
            procs = [{"kind": m.group(1).title(), "name": m.group(2)} for m in PROC_RE.finditer(source)
                     if not m.group(0).lstrip().lower().startswith("private")]
            functions = [{"name": m.group(1)} for m in FUNC_RE.finditer(source)]
            if re.sub(r"(?im)^\s*(rem\b.*|'.*|option .*|attribute .*)?$", "", source).strip():
                out.append(dict(library=name, module=module, type=mtype, lines=source.count("\n") + 1, procs=procs, all_functions=functions, parameters=sum(1 for _ in ANY_PROC_RE.finditer(source)) - len(procs)))
    return out, bool(libs.VBACompatibilityMode)


def wrap_module(library, code):
    import uno
    if hasattr(library, "insertModuleInfo") and not library.hasModuleInfo(HARNESS):
        info = uno.createUnoStruct("com.sun.star.script.ModuleInfo")
        info.ModuleType = NORMAL
        library.insertModuleInfo(HARNESS, info)
    library.insertByName(HARNESS, code)
