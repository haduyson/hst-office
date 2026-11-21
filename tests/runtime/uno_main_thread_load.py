# SPDX-License-Identifier: AGPL-3.0-only
"""Load documents from a UNO client on the office's main thread (OnMainThread), as a user's open does.

Called over the UNO bridge, loadComponentFromURL builds the frame, sidebar and toolbars in the bridge thread. On
Windows each drop-down box's frame is then created by the main thread with the SolarMutex released
(WinSalInstance::SendWndMessage_impl), and the main thread's own sidebar and notebookbar work ran into the half-built
boxes: Sheets died at start in 3 of 20 fresh-profile starts on HST4 (12 of 20 with 1.0.1), 0 of 20 on the main
thread. Upstream's UI tests pass OnMainThread=True for the same reason. Every Windows check loads through here;
pass OnMainThread=False to test a bridge-thread load on purpose.

Stores go through store() for the same reason. storeToURL called over the bridge exports in the bridge thread. On
Windows, a document with Windows OLE objects (MathType formulas) is still laid out by the main thread's idle layout
right after the load, and the native OLE calls in that layout release the SolarMutex. The bridge thread then takes
the mutex and runs the export's CalcLayout over the half-done layout, and spins there forever: 4 of 4 hangs on a
14-formula DOCX with HST 1.0.3, 2 of 3 with plain LibreOffice 26.2. A user's Ctrl+S, AutoSave and macros save on
the main thread and never hang."""


def properties(**props):
    """PropertyValue tuple of props, OnMainThread=True unless given."""
    from com.sun.star.beans import PropertyValue
    args = []
    for name, value in dict({"OnMainThread": True}, **props).items():
        prop = PropertyValue()
        prop.Name, prop.Value = name, value
        args.append(prop)
    return tuple(args)


def load(desktop, url, target="_blank", flags=0, **props):
    """desktop.loadComponentFromURL(url, target, flags, props) on the office's main thread."""
    return desktop.loadComponentFromURL(url, target, flags, properties(**props))


def store(ctx, doc, url, as_url=False, timeout=None, **props):
    """doc.storeToURL(url, props) (storeAsURL when as_url) on the office's main thread, as a user's save does.

    The call is queued with com.sun.star.awt.AsyncCallback; the office calls back from its main thread and the store
    made inside that callback runs there. Errors of the store are raised here; TimeoutError after timeout seconds."""
    import threading

    import unohelper
    from com.sun.star.awt import XCallback

    done, outcome = threading.Event(), {}

    class Store(unohelper.Base, XCallback):
        def notify(self, _data):
            try:
                args = tuple(_props(props))
                (doc.storeAsURL if as_url else doc.storeToURL)(url, args)
            except Exception as exc:  # noqa: BLE001 - raised in the caller's thread below
                outcome["error"] = exc
            finally:
                done.set()

    callback = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx)
    callback.addCallback(Store(), None)
    if not done.wait(timeout):
        raise TimeoutError("store of %s did not finish within %s s" % (url, timeout))
    if "error" in outcome:
        raise outcome["error"]


def _props(values):
    from com.sun.star.beans import PropertyValue
    for name, value in values.items():
        prop = PropertyValue()
        prop.Name, prop.Value = name, value
        yield prop
