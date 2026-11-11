#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Quit the office that scripts/perf/startup-timing.py started: close its dialogs, then Desktop.terminate().

Run with the office's own Python (import uno). Connects to the 127.0.0.1 port the harness passed with --accept, so it can only
reach that office. Prints the titles of the dialogs it closed as JSON. Usage: startup-quit-office.py PORT
"""
import json
import sys
import time

import uno


def main():
    port = sys.argv[1]
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    deadline, ctx = time.time() + 60, None
    while ctx is None:
        try:
            ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=%s;urp;StarOffice.ComponentContext" % port)
        except Exception:  # noqa: BLE001 - the office restarting itself or not listening yet
            if time.time() > deadline:
                print(json.dumps({"error": "no UNO socket on port %s" % port}))
                return 1
            time.sleep(0.5)
    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    closed = []
    try:
        close_dialogs(smgr, ctx, desktop, closed)
    except Exception as error:  # noqa: BLE001 - quit anyway; a dialog left open may veto it
        closed.append("error: %s" % error)
    try:
        desktop.terminate()
    except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
        pass
    print(json.dumps({"closed": closed}, ensure_ascii=False))
    return 0


def close_dialogs(smgr, ctx, desktop, closed):
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    for _ in range(5):  # closing one start-up question may open the next
        frames = desktop.getFrames()
        containers = [frames.getByIndex(i).getContainerWindow() for i in range(frames.getCount())]
        found = False
        for index in range(toolkit.getTopWindowCount()):
            window = toolkit.getTopWindow(index)
            try:
                if any(window == c for c in containers) or not window.isVisible():
                    continue
                title = window.getAccessibleContext().getAccessibleName()
                window.endExecute()
                closed.append(title)
                found = True
            except Exception:  # noqa: BLE001 - not a dialog, or gone
                continue
        if not found:
            break
        time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
