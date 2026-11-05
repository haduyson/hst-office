# SPDX-License-Identifier: AGPL-3.0-only
"""Inside the disposable container: run the macros of each file and print one JSON line per result.

argv: jobs.json. Each job: {"file": path under /corpus, "kind": "calc"|"writer", "only": optional
[{"module","proc","want"}] (upstream assertions), "max_procs": N}. Every procedure gets a fresh load of the
file, through a generated wrapper module that catches runtime errors with their number, text and line.
"""
import json
import os
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandbox_common import CLASS, CORPUS, FORM, HARNESS, WRAPPER, close_all, emit, enumerate_modules, load, wrap_module  # noqa: E402
from sandbox_office import Office, call_with_timeout  # noqa: E402
from sandbox_trace import trace_failure  # noqa: E402


def run_one(office, path, target, timeout, shown_name):
    """One procedure in a fresh load: {status, dialogs, ...}."""
    state, doc = call_with_timeout(lambda: load(office, path, shown_name), 60)
    load_dialogs = office.watcher.take()
    if state != "done" or doc is None:
        return dict(status="load-" + state, dialogs=load_dialogs, detail=str(doc)[:200])
    result = dict(load_dialogs=load_dialogs)

    def invoke():
        library = doc.BasicLibraries.getByName(target["library"])
        call = f"hstR = {target['module']}.{target['proc']}({target.get('args', '')})" if target.get("kind") == "Function" else f"{target['module']}.{target['proc']}"
        wrap_module(library, WRAPPER.format(call=call))
        script = doc.getScriptProvider().getScript(
            f"vnd.sun.star.script:{target['library']}.{HARNESS}.HstCall?language=Basic&location=document")
        return script.invoke((), (), ())[0]

    state, value = call_with_timeout(invoke, timeout)
    result["dialogs"] = office.watcher.take()
    if state == "timeout":
        result["status"] = "timeout"
    elif state == "raised":
        result.update(status="exception", detail=f"{type(value).__name__}: {getattr(value, 'Message', value)}"[:400])
    else:
        result["return"] = str(value)[:300]
        if value is None:
            result["status"] = "no-return"  # compile error shown as a dialog, or the wrapper never ended
        elif str(value).startswith("OK|"):
            result["status"] = "pass" if "want" not in target or str(value)[3:] == target["want"] else "wrong-result"
        else:
            parts = str(value).split("|", 4)
            result.update(status="error", err=parts[1:] if len(parts) == 5 else parts)
    return result


def run_job(office, job):
    path = os.path.join(CORPUS, job["file"])
    shown_name = os.path.basename(job["path"]) if job.get("path") else None
    state, doc = call_with_timeout(lambda: load(office, path, shown_name), 90)
    head = dict(file=job["file"], event="file", load_dialogs=office.watcher.take())
    if state != "done" or doc is None:
        head.update(status="load-" + state, detail=str(doc)[:200])
        emit(head)
        office.restart()
        return
    state, info = call_with_timeout(lambda: enumerate_modules(doc), 30)
    if state != "done":
        head.update(status="enumerate-" + state, detail=str(info)[:200])
        emit(head)
        office.restart()
        return
    modules, vba_mode = info
    head.update(status="loaded", vba_mode=vba_mode, modules=modules, type=doc.getImplementationName())
    if job.get("recalc") and hasattr(doc, "calculateAll"):
        from sandbox_recalc import compare_recalc
        names = [p["name"] for m in modules if m["type"] not in (CLASS, FORM) for p in m["all_functions"]] if modules else []
        state, value = call_with_timeout(lambda: compare_recalc(doc, path, names), 60)
        head["recalc"] = value if state == "done" else dict(status=state, detail=repr(value)[:200])
    emit(head)
    call_with_timeout(lambda: close_all(office), 20)
    targets = []
    for module in modules:
        if module["type"] in (CLASS, FORM):
            continue
        for proc in module["procs"]:
            if proc["kind"] == "Sub" or job.get("functions"):
                targets.append(dict(library=module["library"], module=module["module"], proc=proc["name"], kind=proc["kind"]))
    if job.get("only"):
        by_form = {unicodedata.normalize("NFC", m["module"]): m["module"] for m in modules}
        targets = [dict(t, module=by_form.get(unicodedata.normalize("NFC", t["module"]), t["module"])) for t in job["only"]]
    skip = {name.lower() for name in job.get("skip", [])}
    blocked = [t["proc"] for t in targets if t["proc"].lower() in skip]
    targets = [t for t in targets if t["proc"].lower() not in skip]
    if blocked:
        emit(dict(file=job["file"], event="policy-skip", procs=blocked))
    limit = job.get("max_procs", 60)
    budget = time.time() + job.get("budget", 300)
    over_budget = 0
    for target in targets[:limit]:
        if time.time() > budget:
            over_budget += 1
            continue
        started = time.time()
        result = run_one(office, path, target, job.get("timeout", 25), shown_name)
        if result["status"] == "error" and office.alive():
            call_with_timeout(lambda: close_all(office), 20)
            result["where"] = trace_failure(office, path, target, job.get("timeout", 25), shown_name)
        result.update(file=job["file"], event="proc", library=target["library"], module=target["module"], proc=target["proc"],
                      seconds=round(time.time() - started, 2))
        if "want" in target:
            result["want"] = target["want"]
        if "label" in target:
            result["label"] = target["label"]
        emit(result)
        ide_open = any("BASIC" in text for dialog in result.get("dialogs", []) + result.get("load_dialogs", []) for text in dialog["text"])
        if result["status"] in ("timeout", "load-timeout") or not office.alive() or ide_open:
            result_status = "office-dead" if not office.alive() else "ide-open" if ide_open else result["status"]
            emit(dict(file=job["file"], event="restart", why=result_status, proc=target["proc"]))
            office.restart()
        else:
            state, _ = call_with_timeout(lambda: close_all(office), 20)
            if state == "timeout":
                office.restart()
    emit(dict(file=job["file"], event="file-done", skipped_over_limit=max(0, len(targets) - limit) + over_budget))


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        jobs = json.load(handle)
    office = Office()
    office.start()
    try:
        for job in jobs:
            try:
                run_job(office, job)
            except Exception as error:  # noqa: BLE001 - one file must not end the run
                emit(dict(file=job["file"], event="harness-error", detail=repr(error)[:400]))
                office.restart()
    finally:
        office.shutdown()


if __name__ == "__main__":
    main()
