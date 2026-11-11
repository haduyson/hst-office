# SPDX-License-Identifier: AGPL-3.0-only
"""Helper of scripts/macos/app-launchers-probe.sh.

  app-launchers-probe.py seed <profile>                  (system python, stdlib) the default profile of the probe:
                                                          no welcome or default-apps question, UNO acceptor on a pipe
  app-launchers-probe.py wait <kinds> [--timeout S]      (bundled python, uno) until the open documents are exactly
                                                          <kinds> (comma list of writer, calc, impress), one each
  app-launchers-probe.py frames                          (bundled python, uno) list frames and top windows (quit diagnostics)
  app-launchers-probe.py make-odb <file.odb>             (bundled python, uno) store a small dBase-backed database
  app-launchers-probe.py no-base-menu                    (bundled python, uno) File ▸ New (and the Dock menu built
                                                          from it) offers no database

The launchers start HST Office through Launch Services, so the probe cannot pass --accept: the acceptor comes from
the profile (org.openoffice.Setup/Office ooSetupConnectionURL), which the office reads at every start.
"""
import json
import re
import sys
import time
from pathlib import Path

PIPE = "hst-launcher-probe"
KINDS = {"writer": "com.sun.star.text.TextDocument", "calc": "com.sun.star.sheet.SpreadsheetDocument",
         "impress": "com.sun.star.presentation.PresentationDocument", "base": "com.sun.star.sdb.OfficeDatabaseDocument"}
SEED = (("/org.hasontech.hstoffice.Welcome", "Shown", "true"),
        ("/org.hasontech.hstoffice.DefaultApps", "Done", "true"),
        ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false"),
        # a quit the probe had to force must not put the crash question in front of the next checks
        ("/org.hasontech.hstoffice.ErrorReport", "AskAfterCrash", "false"),
        ("/org.openoffice.Setup/Office", "ooSetupConnectionURL", "pipe,name=%s;urp;" % PIPE))


def seed_text(text):
    """registrymodifications.xcu text with the SEED values set once each (pure)."""
    add = ""
    for node, name, value in SEED:
        text = re.sub(r'<item oor:path="%s"><prop oor:name="%s"[^\n]*</item>\n?' % (re.escape(node), name), "", text)
        add += '<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n' % (
            node, name, value)
    if "</oor:items>" not in text:
        raise ValueError("not a registrymodifications.xcu")
    return text.replace("</oor:items>", add + "</oor:items>")


def seed(profile):
    path = Path(profile) / "user" / "registrymodifications.xcu"
    path.write_text(seed_text(path.read_text(encoding="utf-8")), encoding="utf-8")
    print("seeded %s" % path)


def kinds_of(components):
    """{kind: count} of the documents among `components` (objects with supportsService)."""
    counts = {}
    for component in components:
        for kind, service in KINDS.items():
            try:
                if component.supportsService(service):
                    counts[kind] = counts.get(kind, 0) + 1
                    break
            except Exception:  # noqa: BLE001 - a frame without a model (Start Center) is no document
                pass
    return counts


def connect(timeout):
    ctx = context(timeout)
    return ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)


def context(timeout):
    import uno
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    deadline, last = time.time() + timeout, None
    while time.time() < deadline:
        try:
            return resolver.resolve("uno:pipe,name=%s;urp;StarOffice.ComponentContext" % PIPE)
        except Exception as exc:  # noqa: BLE001 - NoConnectException until the office is up
            last = exc
            time.sleep(1)
    raise SystemExit("no UNO connection within %d s: %s" % (timeout, last))


def documents(desktop):
    enum = desktop.getComponents().createEnumeration()
    found = []
    while enum.hasMoreElements():
        found.append(enum.nextElement())
    return kinds_of(found)


def wait(expected, timeout):
    want = {kind: 1 for kind in expected.split(",") if kind}
    unknown = set(want) - set(KINDS)
    if unknown:
        raise SystemExit("unknown kinds %s" % sorted(unknown))
    started = time.time()
    desktop = connect(timeout)
    seen = {}
    while time.time() - started < timeout:
        try:
            seen = documents(desktop)
        except Exception:  # noqa: BLE001 - the office may restart its first window; reconnect
            desktop = connect(max(1, timeout - (time.time() - started)))
            continue
        if seen == want:
            print(json.dumps({"ok": True, "documents": seen, "seconds": round(time.time() - started, 1)}))
            return 0
        time.sleep(1)
    print(json.dumps({"ok": False, "documents": seen, "expected": want}))
    return 1


def frames():
    """Diagnostic: title and document kind of each frame of the desktop (what a quit has to close)."""
    desktop = connect(20)
    rows = []
    for index in range(desktop.Frames.getCount()):
        frame = desktop.Frames.getByIndex(index)
        controller = frame.getController()
        model = controller.getModel() if controller is not None else None
        kind = kinds_of([model]) if model is not None else {}
        rows.append({"title": frame.Title, "kind": next(iter(kind), "none"),
                     "modified": bool(model.isModified()) if model is not None and hasattr(model, "isModified")
                     else None})
    ctx = context(20)
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    windows = []
    for index in range(toolkit.getTopWindowCount()):
        window = toolkit.getTopWindow(index)
        accessible = window.getAccessibleContext() if hasattr(window, "getAccessibleContext") else None
        title = getattr(window, "Title", None) or (accessible.getAccessibleName() if accessible else "")
        windows.append({"title": title, "visible": bool(window.isVisible()) if hasattr(window, "isVisible") else None,
                        "role": accessible.getAccessibleRole() if accessible else None})
    print(json.dumps({"frames": rows, "top_windows": windows}, ensure_ascii=False))
    return 0


def make_odb(path):
    import os
    import uno
    ctx = context(30)
    folder = os.path.splitext(path)[0] + "-tables"
    os.makedirs(folder, exist_ok=True)
    source = ctx.ServiceManager.createInstanceWithContext("com.sun.star.sdb.DatabaseContext", ctx).createInstance()
    source.URL = "sdbc:dbase:" + uno.systemPathToFileUrl(folder)
    document = source.DatabaseDocument
    document.storeAsURL(uno.systemPathToFileUrl(os.path.abspath(path)), ())
    document.close(True)
    print("stored %s" % path)
    return 0


def no_base_menu():
    import uno
    ctx = context(30)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", "/org.openoffice.Office.Common/Menus/New"
    node = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)\
        .createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,))
    urls = [node.getByName(name).getPropertyValue("URL") for name in node.getElementNames()]
    print(json.dumps(urls))
    return 1 if any("sdatabase" in url for url in urls) or not any("swriter" in url for url in urls) else 0


def main(argv):
    if len(argv) >= 2 and argv[0] == "seed":
        seed(argv[1])
        return 0
    if len(argv) >= 2 and argv[0] == "wait":
        timeout = int(argv[3]) if len(argv) >= 4 and argv[2] == "--timeout" else 120
        return wait(argv[1], timeout)
    if argv[:1] == ["frames"]:
        return frames()
    if len(argv) >= 2 and argv[0] == "make-odb":
        return make_odb(argv[1])
    if argv[:1] == ["no-base-menu"]:
        return no_base_menu()
    print(__doc__, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
