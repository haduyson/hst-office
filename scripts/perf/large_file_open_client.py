# SPDX-License-Identifier: AGPL-3.0-only
"""UNO side of scripts/perf/large-file-open.py: run with the office's own Python (it imports uno).

    python large_file_open_client.py <pipe name> <file> <hidden 0|1> <save-to path or ->

Connects to the office listening on the pipe, loads the file, then (visible window) processes events until idle,
optionally stores the document again, closes it and prints one JSON line:
{"connect": s, "load": s, "idle": s, "save": s, "kind": ..., "modified": bool, "error": ...}.
"""
import json
import sys
import time


def prop(name, value):
    import uno
    p = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    p.Name, p.Value = name, value
    return p


def main():
    import uno
    pipe, path, hidden, save_to = sys.argv[1], sys.argv[2], sys.argv[3] == "1", sys.argv[4]
    res = {}
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    started = time.monotonic()
    ctx = None
    while time.monotonic() - started < 120:
        try:
            ctx = resolver.resolve("uno:pipe,name=%s;urp;StarOffice.ComponentContext" % pipe)
            break
        except Exception:  # noqa: BLE001 - the office is still starting
            time.sleep(0.25)
    if ctx is None:
        print(json.dumps({"error": "no connection"}))
        return 2
    res["connect"] = round(time.monotonic() - started, 2)
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    toolkit.processEventsToIdle()  # the office's own start-up work first
    url = uno.systemPathToFileUrl(path)
    t0 = time.monotonic()
    doc = None
    try:
        doc = desktop.loadComponentFromURL(url, "_blank", 0, (prop("Hidden", hidden),))
        res["load"] = round(time.monotonic() - t0, 2)
        print(json.dumps(dict(res, stage="loaded")), flush=True)  # kept by the controller if idle never comes
        if not hidden:
            toolkit.processEventsToIdle()
            res["idle"] = round(time.monotonic() - t0, 2)
        res["kind"] = doc.getIdentifier() if hasattr(doc, "getIdentifier") else ""
        res["modified"] = bool(doc.isModified()) if hasattr(doc, "isModified") else None
        if save_to != "-" and hasattr(doc, "storeToURL"):
            t1 = time.monotonic()
            args = {a.Name: a.Value for a in doc.getArgs()}
            res["filter"] = args.get("FilterName", "")
            doc.storeToURL(uno.systemPathToFileUrl(save_to),
                           (prop("Overwrite", True), prop("FilterName", res["filter"])))
            res["save"] = round(time.monotonic() - t1, 2)
    except Exception as e:  # noqa: BLE001 - reported, the controller decides
        res["error"] = "%s: %s" % (type(e).__name__, getattr(e, "Message", str(e))[:200])
    print(json.dumps(res), flush=True)
    try:
        if doc is not None:
            doc.close(True)
        print(json.dumps(dict(res, terminated=bool(desktop.terminate()))), flush=True)
    except Exception:  # noqa: BLE001 - the bridge goes away with the office
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
