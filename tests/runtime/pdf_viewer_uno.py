# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF over UNO for the runtime checks: open a PDF in the viewer, .uno:HSTPdfInfo, sign a
copy, and the handover to HST Draw (hidden loads, "Edit in HST Draw", the option off)."""
import threading
import time

VIEWER = "org.hasontech.comp.PdfViewerController"


def info(office, frame, **args):
    result = office.dispatch(frame, ".uno:HSTPdfInfo", signing_props(**args))
    return {item.Name: item.Value for item in result.Result}


def signing_props(**values):
    import uno  # noqa: F401
    from com.sun.star.beans import PropertyValue
    out = []
    for name, value in values.items():
        prop = PropertyValue()
        prop.Name, prop.Value = name, value
        out.append(prop)
    return tuple(out)


def wait_info(office, frame, key, predicate, timeout=30, **args):
    deadline = time.time() + timeout
    while True:
        data = info(office, frame, **args)
        if predicate(data.get(key)) or time.time() > deadline:
            return data
        time.sleep(0.1)


def open_viewer(office, path):
    import uno
    start = time.monotonic()
    component = office.load(uno.systemPathToFileUrl(str(path)))
    wall_ms = int((time.monotonic() - start) * 1000)
    assert component is not None and component.ImplementationName == VIEWER, component
    frame = component.getFrame()
    data = wait_info(office, frame, "OpenMillis", lambda v: v is not None and v >= 0)
    data["WallMillis"] = wall_ms
    return frame, data


def sign_copy(office, dialogs, frame, target, **placement):
    """HSTPdfSign into `target` with a visible box, answering token PIN prompts on the way."""
    import uno
    done = {}

    def sign():
        done["result"] = office.dispatch(frame, ".uno:HSTPdfSign", signing_props(
            TargetURL=uno.systemPathToFileUrl(str(target)), Visible=True, Width=200.0, Height=70.0,
            **placement)).Result
    thread = threading.Thread(target=sign, daemon=True)
    thread.start()
    deadline = time.time() + 90
    while thread.is_alive() and time.time() < deadline:
        win, kids = dialogs.top()
        if "newpassEntry" in kids:
            dialogs._answer_pin(win)
        time.sleep(0.5)
    thread.join(5)
    return done


def check_draw_handover(office, samples, checks):
    import uno
    url = uno.systemPathToFileUrl(str(samples[6]))
    hidden = office.load(url, hidden=True)
    assert hidden is not None and hidden.supportsService("com.sun.star.drawing.DrawingDocument"), hidden
    hidden.close(True)
    checks["hidden_load_uses_draw"] = True

    frame, _ = open_viewer(office, samples[6])
    threading.Thread(target=office.dispatch, args=(frame, ".uno:HSTPdfEditInDraw"), daemon=True).start()
    deadline, draw = time.time() + 120, None
    while time.time() < deadline and draw is None:
        time.sleep(1)
        enum = office.desktop().getComponents().createEnumeration()
        while enum.hasMoreElements():
            candidate = enum.nextElement()
            if hasattr(candidate, "supportsService") and candidate.supportsService("com.sun.star.drawing.DrawingDocument"):
                draw = candidate
    assert draw is not None
    time.sleep(2)
    frames = office.desktop().getFrames()
    viewers = [frames.getByIndex(i) for i in range(frames.getCount())
               if getattr(frames.getByIndex(i).getController(), "ImplementationName", "") == VIEWER]
    assert not viewers, "the viewer window stays open after Edit in HST Draw"
    draw.close(True)
    checks["edit_in_draw_replaces_viewer"] = True

    office.set_config("/org.openoffice.Office.HSTPdfViewer/Viewer", "OpenPdfInViewer", False)
    try:
        doc = office.load(url)
        assert doc is not None and doc.supportsService("com.sun.star.drawing.DrawingDocument"), doc
        doc.close(True)
    finally:
        office.set_config("/org.openoffice.Office.HSTPdfViewer/Viewer", "OpenPdfInViewer", True)
    checks["option_off_opens_draw"] = True
