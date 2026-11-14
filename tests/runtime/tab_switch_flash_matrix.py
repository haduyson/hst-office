# SPDX-License-Identifier: AGPL-3.0-only
"""Scenarios and measurement of check-windows-tab-switch-flash.py: switches between document tabs and windows of
every application, sampled with screen_patches_win.

Window modes:
- office: every document opened from the HST Office window (Start Center): one window, tabs of all applications and
  the Start Center; NextDocumentTab walks same-application and cross-application switches.
- tabs: documents opened as from the file manager, each application set to tabs: one window per application.
- windows: documents opened as from the file manager, each application set to separate windows; a switch brings the
  next window to the front (XTopWindow.toFront from the office itself, no key press).
Keys (Ctrl+Alt+. = NextDocumentTab, as a user presses it, so the switch runs in the office's main thread) are sent
only while the foreground window is a verified frame of this office (screen_patches_win.office_in_front).
"""
import os
import subprocess
import time

try:  # Windows; the document helpers below are shared with the Linux check
    import screen_patches_win as sp
except (AttributeError, OSError):
    sp = None

APPS = {  # module -> (factory, extension, filter, DocumentTabs<App> key suffix)
    "writer": ("swriter", "docx", "MS Word 2007 XML", "Writer"),
    "calc": ("scalc", "xlsx", "Calc MS Excel 2007 XML", "Calc"),
    "impress": ("simpress", "pptx", "Impress MS PowerPoint 2007 XML", "Impress"),
    "draw": ("sdraw", "odg", "draw8", "Draw"),
    "pdf": ("swriter", "pdf", "writer_pdf_Export", "Pdf"),
}
MISC = "/org.openoffice.Office.Common/Misc"
SETTLE = 1.4  # seconds after a switch; frames within WINDOW of it are classified
WINDOW = 1.2


def prop(name, value):
    import uno
    p = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    p.Name, p.Value = name, value
    return p


def own_pids(profile):
    """soffice.bin processes started with this profile (never another session's office)."""
    marker = profile.replace("\\", "/").lower()
    script = "Get-CimInstance Win32_Process -Filter \"Name='soffice.bin'\" | % { '{0}|{1}' -f $_.ProcessId, $_.CommandLine }"
    rows = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                          check=False).stdout.splitlines()
    return {int(r.split("|", 1)[0]) for r in rows if "|" in r and marker in r.split("|", 1)[1].replace("\\", "/").lower()}


def make_document(office, app, path, n):
    import uno
    factory, _ext, filter_name, _key = APPS[app]
    doc = office.desktop.loadComponentFromURL("private:factory/" + factory, "_blank", 0, (prop("Hidden", True),))
    if factory == "scalc":
        sheet = doc.Sheets.getByIndex(0)
        for r in range(30):
            for c in range(10):
                sheet.getCellByPosition(c, r).setFormula("=%d*%d" % (r + 1, c + n + 1) if c % 3 else "Muc %d" % r)
    elif factory == "swriter":
        for p in range(15):
            doc.Text.insertString(doc.Text.End, "Tai lieu %d %s, doan %d. " % (n, app, p) + "Noi dung mau. " * 8, False)
            doc.Text.insertControlCharacter(doc.Text.End, 0, False)
    else:
        shape = doc.createInstance("com.sun.star.drawing.RectangleShape")
        doc.DrawPages.getByIndex(0).add(shape)
        shape.Position = uno.createUnoStruct("com.sun.star.awt.Point", 2000 + 1500 * n, 3000)
        shape.Size = uno.createUnoStruct("com.sun.star.awt.Size", 8000, 5000)
        shape.FillColor = 0x3366CC + 0x200000 * n
    url = uno.systemPathToFileUrl(path)
    doc.storeToURL(url, (prop("FilterName", filter_name),))
    doc.close(True)
    return url


def open_documents(office, apps, mode, folder, per_app=2):
    """Open per_app documents of every app; mode 'office' from the Start Center window, else as from outside. In
    'windows' mode every document window is maximized like the first, so a switch only changes the picture."""
    os.makedirs(folder, exist_ok=True)
    for app in apps:
        office.set_config(MISC, "DocumentTabs" + APPS[app][3], mode != "windows")
    props = () if mode == "office" else (prop("Referer", "private:OpenEvent"),)
    for app in apps:
        for n in range(per_app):
            path = os.path.join(folder, "%s-%s%d.%s" % (mode, app, n + 1, APPS[app][1]))
            office.desktop.loadComponentFromURL(make_document(office, app, path, n + 1), "_blank", 0, props)
            time.sleep(2)
    time.sleep(3)
    if mode == "windows":
        for frame in visible_frames(office):
            frame.getContainerWindow().IsMaximized = True


def label(title):
    if not title.strip() or "HST Office" == title.strip():
        return "start"
    for app, (_f, ext, _flt, key) in APPS.items():
        if ("." + ext) in title:
            return app
    return "start" if "Trang" in title or "Start" in title else "other"


def visible_frames(office):
    frames = office.desktop.getFrames()
    return [frames.getByIndex(i) for i in range(frames.getCount())
            if frames.getByIndex(i).getContainerWindow().isVisible()]


def hwnd_of(frame, pids):
    """The top-level window of `frame` (same title, one of this office's processes)."""
    import windows_gui as wg
    return next((w[0] for w in wg.office_windows() if w[2] == frame.Title and sp.window_process(w[0]) in pids), None)


def measure(office, pids, patches, desktop, mode, switches, chord, frame=None):
    """Run `switches` switches with the office maximized over the work area that `patches` samples (`desktop`: the
    same patches grabbed before the office started), starting in `frame`'s window. Returns [(from, to, driven, frames, desktop, partial, errors)]."""
    frame = frame or office.desktop.getCurrentFrame() or visible_frames(office)[0]
    frame.getContainerWindow().IsMaximized = True
    time.sleep(1)
    hwnd = hwnd_of(frame, pids)
    if hwnd:
        sp.bring_to_front(hwnd)
    time.sleep(1.5)
    recorder = sp.Recorder(patches)
    recorder.start()
    time.sleep(0.6)
    marks = []
    for k in range(switches):
        current = office.desktop.getCurrentFrame()
        before = label(current.Title if current else "")
        start = time.perf_counter()
        if mode == "windows":
            others = [f for f in visible_frames(office) if f != current]
            target = hwnd_of(others[k % len(others)], pids)
            driven = "front" if target and sp.bring_to_front(target) else "skipped: window not found or not in front"
        else:
            try:  # the safe-input layer sends only to this verified office window (else BlockedInput, nothing sent)
                chord(0x11, 0x12, 0xBE, target=hwnd_of(current, pids) if current else hwnd, front=False)
                driven = "keys"
            except Exception as error:  # noqa: BLE001 - BlockedInput: reported, the switch is not counted
                driven = "skipped: %s" % error
        time.sleep(SETTLE)
        after = office.desktop.getCurrentFrame()
        marks.append((before, label(after.Title if after else ""), driven, start))
    recorder.stop.set()
    recorder.join(10)
    frames = recorder.frames
    rate = len(frames) / max(frames[-1][0] - frames[0][0], 0.001) if frames else 0
    rows = []
    for before, after, driven, start in marks:
        prior = [f for t, f in frames if t < start]
        during = [f for t, f in frames if start <= t <= start + WINDOW]
        if not prior or not during:
            continue
        distinct = [f for i, f in enumerate(during) if i == 0 or f != during[i - 1]]  # one per composed picture
        kinds = ["" if f in (prior[-1], during[-1]) else sp.classify(patches, f, prior[-1], during[-1], desktop)
                 for f in distinct]
        odd = next((f for f, k in zip(distinct, kinds) if k), None)
        note = sp.describe(patches, odd, prior[-1], during[-1])[:4] if odd else ""
        rows.append((before, after, driven, len(distinct), kinds.count("desktop"), kinds.count("partial"),
                     "; ".join(sorted(set(recorder.errors)))[:200] or "%.0f grabs/s, %d presents merged" % (
                         rate, getattr(patches, "skipped", 0)), str(note)))
    return rows


def close_all(office):
    """Close every document (the office then shows the Start Center); errors of single documents are ignored."""
    components = office.desktop.getComponents().createEnumeration()
    while components.hasMoreElements():
        component = components.nextElement()
        try:
            component.setModified(False)
            component.close(True)
        except Exception:  # noqa: BLE001 - the Start Center has no model
            pass
    time.sleep(3)
