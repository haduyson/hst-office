#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: the steps of check-writer-close-with-focused-comment.py in the console user's session. Writer: a content
control, a comment left in edit mode (its window has the focus), a PDF export with the comments in the margin, then
XCloseable.close: the office must survive.

On Linux 1.0.2 crashed in the close (SwPostItMgr::HasActiveSidebarWin from SwEditWin::GetFocus) once the document
window had the input focus. Here the document window is brought to the front and focused through its frame
(XTopWindow.toFront, XWindow.setFocus), as the user's click does. Run with the office's python:
    python.exe check-writer-close-with-focused-comment-win.py --soffice <instdir>\\program\\soffice.exe --out DIR
        [--rounds 5]
Exit 1 when the office of this check went away. Only this check's soffice.bin (by its profile) is watched or stopped.
"""
import argparse, importlib.util, os, subprocess, sys, time  # noqa: E401

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("media_check", os.path.join(HERE, "check-impress-media-close-other-thread.py"))
media_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(media_check)


def make_foreground(pids):
    """The office's visible top-level window becomes the foreground window with the keyboard focus, as after the
    user's click on its title bar (Windows lets a background process do it after an Alt key event)."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(visit, 0)
    for hwnd in found[:1]:
        user32.keybd_event(0x12, 0, 0, 0)  # Alt down/up: the foreground lock lets this process switch windows
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(hwnd)
    return bool(found)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--close", choices=("api", "command"), default="api",
                        help="XCloseable.close, or .uno:CloseDoc as the window's close button does")
    args = parser.parse_args()
    work = os.path.abspath(args.out)
    os.makedirs(work, exist_ok=True)
    soffice = os.path.abspath(args.soffice)
    sys.path.insert(0, os.path.dirname(soffice))
    import uno
    from com.sun.star.beans import PropertyValue

    def prop(name, value):
        item = PropertyValue()
        item.Name, item.Value = name, value
        return item

    profile = os.path.join(work, "profile")
    url = uno.systemPathToFileUrl(profile)
    if not os.path.isdir(profile):
        media_check.settle_profile(soffice, url, profile, work)
    port = media_check.free_port()
    proc = subprocess.Popen([soffice, "-env:UserInstallation=" + url, "--norestore", "--nologo",
                             f"--accept=socket,host=127.0.0.1,port={port};urp;"])
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    ctx = None
    for _ in range(120):
        try:
            ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
            break
        except Exception:  # noqa: BLE001 - still starting
            time.sleep(1)
    if ctx is None:
        print("FAIL  the office did not start", flush=True)
        return 1
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    dispatcher = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
    alive = True
    for round_ in range(args.rounds):
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        time.sleep(3)
        frame = doc.getCurrentController().getFrame()
        for command in (".uno:InsertContentControl", ".uno:GoToEndOfDoc", ".uno:InsertAnnotation"):
            dispatcher.executeDispatch(frame, command, "", 0, ())
        time.sleep(2)
        window = frame.getContainerWindow()
        window.toFront()  # the document window has the input focus, as after the user's click
        window.setFocus()
        time.sleep(1)
        if not make_foreground(set(media_check.office_pids(profile))):
            print("note: no visible office window found", flush=True)
        time.sleep(1)
        if round_ == 0:  # what the close starts from: the comment in edit mode, the window in front
            shot = os.path.join(work, "before-close.png").replace("'", "''")
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                            "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
                            "$i = New-Object System.Drawing.Bitmap $b.Width, $b.Height; "
                            "[System.Drawing.Graphics]::FromImage($i).CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
                            f"$i.Save('{shot}')"], capture_output=True, timeout=60)
        filter_data = (prop("ExportFormFields", True), prop("ExportNotes", False), prop("ExportNotesInMargin", True))
        store_args = (prop("FilterName", "writer_pdf_Export"),
                      prop("FilterData", uno.Any("[]com.sun.star.beans.PropertyValue", filter_data)))
        uno.invoke(doc, "storeToURL", (uno.systemPathToFileUrl(os.path.join(work, f"round{round_}.pdf")),
                                       uno.Any("[]com.sun.star.beans.PropertyValue", store_args)))
        try:
            if args.close == "command":
                doc.setModified(False)
                dispatcher.executeDispatch(frame, ".uno:CloseDoc", "", 0, ())
            else:
                doc.close(True)
        except Exception as error:  # noqa: BLE001 - the bridge goes away when the office crashes
            print(f"close: {type(error).__name__}", flush=True)
        time.sleep(3)
        alive = bool(media_check.office_pids(profile))
        print(("PASS  " if alive else "FAIL  ") + f"round {round_ + 1}: the office survives closing the document",
              flush=True)
        if not alive:
            break
    if alive:
        try:
            desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
            pass
    try:
        proc.wait(60)
    except subprocess.TimeoutExpired:
        proc.kill()
    for pid in media_check.office_pids(profile):
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    return 0 if alive else 1


if __name__ == "__main__":
    sys.exit(main())
