# SPDX-License-Identifier: AGPL-3.0-only
"""Inside the disposable container: do the UserForms of real files open, and do their handlers run?

argv: jobs.json with {"file", "skip": [...]}. For up to 4 forms of a file: Load and Show (the watcher records the dialog and closes it), then the
parameterless _Click handlers, called by name through a Public Sub added to the form's module: a real mouse click is covered by check-vba-form-events.py.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandbox_office import Office, call_with_timeout  # noqa: E402
from sandbox_common import FORM, close_all, load, wrap_module  # noqa: E402

CLICK = re.compile(r"(?im)^[ \t]*(?:Private[ \t]+|Public[ \t]+)?Sub[ \t]+(\w+_Click)[ \t]*\(\s*\)")
RUNNER = """Option VBASupport 1
Public Function HstShow()
  On Error GoTo F
  Load {form}
  HstShow = "loaded|" & {form}.Caption & "|" & {form}.Controls.Count
  {form}.Show
  Exit Function
F:
  HstShow = "ERR|" & Err.Number & "|" & Err.Description
End Function
Public Function HstCall(n As String)
  On Error GoTo F
  Load {form}
  CallByName {form}, n, 1
  HstCall = "ok"
  Exit Function
F:
  HstCall = "ERR|" & Err.Number & "|" & Err.Description
End Function
"""


def run_form(office, path, library_name, form, skip):
    state, doc = call_with_timeout(lambda: load(office, path), 60)
    if state != "done" or doc is None:
        return dict(form=form, status="load-" + state)
    office.watcher.take()

    def show():
        library = doc.BasicLibraries.getByName(library_name)
        wrap_module(library, RUNNER.format(form=form))
        script = doc.getScriptProvider().getScript(f"vnd.sun.star.script:{library_name}.HstHarnessRun.HstShow?language=Basic&location=document")
        return script.invoke((), (), ())[0]

    state, value = call_with_timeout(show, 25)
    out = dict(form=form, show=str(value)[:200] if state == "done" else state, dialogs=[d["title"] for d in office.watcher.take()][:4])
    if state != "done":
        return out
    library = doc.BasicLibraries.getByName(library_name)
    source = library.getByName(form)
    handlers = [h for h in CLICK.findall(source) if h.lower() not in skip][:3]
    if handlers:
        added = "\n".join(f"Public Sub Hst{index}()\n  {handler}\nEnd Sub" for index, handler in enumerate(handlers))

        def fire(index):
            script = doc.getScriptProvider().getScript(f"vnd.sun.star.script:{library_name}.HstHarnessRun.HstCall?language=Basic&location=document")
            return script.invoke((f"Hst{index}",), (), ())[0]

        call_with_timeout(lambda: library.replaceByName(form, source + "\n" + added + "\n"), 15)
        out["events"] = []
        for index, handler in enumerate(handlers):
            state, value = call_with_timeout(lambda i=index: fire(i), 15)
            dialogs = office.watcher.take()
            out["events"].append(dict(handler=handler, result=str(value)[:160] if state == "done" else state, dialogs=[(d["text"][1:2] or [""])[0][:100] for d in dialogs][:3]))
            if state != "done":
                break
    return out


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        jobs = json.load(handle)
    office = Office()
    office.start()
    for job in jobs:
        path = os.path.join(os.environ.get("HST_CORPUS", "/corpus"), job["file"])
        state, doc = call_with_timeout(lambda: load(office, path), 60)
        forms = []
        if state == "done" and doc is not None:
            def names():
                libs = doc.BasicLibraries
                found = []
                for name in libs.getElementNames():
                    libs.loadLibrary(name)
                    library = libs.getByName(name)
                    if hasattr(library, "getModuleInfo"):
                        found += [(name, m) for m in library.getElementNames() if library.hasModuleInfo(m) and library.getModuleInfo(m).ModuleType == FORM]
                return found
            forms = call_with_timeout(names, 20)[1] or []
        call_with_timeout(lambda: close_all(office), 20)
        results = []
        skip = {s.lower() for s in job.get("skip", [])}
        for library_name, form in forms[:4]:
            started = time.time()
            results.append(dict(run_form(office, path, library_name, form, skip), seconds=round(time.time() - started, 1)))
            if not office.alive():
                results[-1]["crash"] = True
                office.restart()
            else:
                office.restart() if results[-1].get("show") == "timeout" else call_with_timeout(lambda: close_all(office), 20)
        print("@@R " + json.dumps(dict(file=job["file"], event="forms", found=len(forms), forms=results), ensure_ascii=False), flush=True)
    office.shutdown()


if __name__ == "__main__":
    main()
