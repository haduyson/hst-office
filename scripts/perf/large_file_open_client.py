# SPDX-License-Identifier: AGPL-3.0-only
"""UNO side of scripts/perf/large-file-open.py: run with the office's own Python (it imports uno).

    python large_file_open_client.py <pipe name> <file> <hidden 0|1|cli> <save-to path or ->

Connects to the office listening on the pipe, loads the file, then (visible window) processes events until idle,
optionally stores the document again, closes it and prints one JSON line:
{"connect": s, "load": s, "idle": s, "layout": s, "pages": n, "save": s, "kind": ..., "modified": bool, "error": ...}
(layout/pages: Writer only, the time until the whole document is laid out).
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
    while time.monotonic() - started < (3600 if sys.argv[3] == "cli" else 120):
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
    if sys.argv[3] != "cli":
        toolkit.processEventsToIdle()  # the office's own start-up work first
    url = uno.systemPathToFileUrl(path)
    t0 = time.monotonic()
    doc = None
    try:
        if sys.argv[3] == "cli":  # the office opens the file from its command line, on its main thread
            t0 = started  # measured from the office's launch (this client starts with it)
            while doc is None and time.monotonic() - t0 < 3600:
                comps = desktop.getComponents().createEnumeration()
                while comps.hasMoreElements():
                    c = comps.nextElement()
                    if hasattr(c, "getURL") and c.getURL() == url:
                        doc = c
                if doc is None:
                    time.sleep(0.5)
        else:
            doc = desktop.loadComponentFromURL(url, "_blank", 0, (prop("Hidden", hidden),))
        res["load"] = round(time.monotonic() - t0, 2)
        print(json.dumps(dict(res, stage="loaded")), flush=True)  # kept by the controller if idle never comes
        if not hidden:
            toolkit.processEventsToIdle()
            res["idle"] = round(time.monotonic() - t0, 2)
            if doc.supportsService("com.sun.star.text.TextDocument"):
                # the page count needs the whole document laid out: idle layout may still be running
                res["pages"] = doc.getCurrentController().PageCount
                res["layout"] = round(time.monotonic() - t0, 2)
        res["kind"] = doc.getIdentifier() if hasattr(doc, "getIdentifier") else ""
        res["modified"] = bool(doc.isModified()) if hasattr(doc, "isModified") else None
        if save_to != "-" and hasattr(doc, "storeToURL"):
            t1 = time.monotonic()
            args = {a.Name: a.Value for a in doc.getArgs()}
            res["filter"] = args.get("FilterName", "")
            doc.storeToURL(uno.systemPathToFileUrl(save_to),
                           (prop("Overwrite", True), prop("FilterName", res["filter"])))
            res["save"] = round(time.monotonic() - t1, 2)
            # what AutoRecovery writes every few minutes while the document is modified: an ODF copy
            odf = {"com.sun.star.sheet.SpreadsheetDocument": "calc8", "com.sun.star.text.TextDocument": "writer8",
                   "com.sun.star.presentation.PresentationDocument": "impress8"}
            kind = next((odf[k] for k in odf if doc.supportsService(k)), "")
            if kind:
                t2 = time.monotonic()
                doc.storeToURL(uno.systemPathToFileUrl(save_to + ".odf"), (prop("Overwrite", True),
                                                                           prop("FilterName", kind)))
                res["save_odf"] = round(time.monotonic() - t2, 2)
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
