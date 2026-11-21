#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: Slides documents with linked video and audio, played for a while, then closed through UNO from this
script's thread (XCloseable.close, as a script or add-in does). The office must survive.

Closing from another thread destroys the media objects' system windows through the main thread
(WinSalInstance::SendComWndMessage releases the SolarMutex meanwhile); the main thread's idle then painted the slide
window of a shell whose view was already gone: access violation in SdrPaintView::PrePaint, 1.0.2, 3 times out of 3
with a hold of 100 s. Run in the console user's session with the office's python:
    python.exe check-impress-media-close-other-thread.py --soffice <instdir>\\program\\soffice.exe --out DIR
        --video clip.mp4 --audio tone.wav [--cycles 3] [--hold 100]
Exit 1 when the office of this check went away. Only this check's soffice.bin (by its profile) is watched or stopped.
"""
import argparse, os, shutil, socket, subprocess, sys, time  # noqa: E401


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def office_pids(profile):
    """soffice.bin processes started with this profile (the owner's own office is left alone)."""
    script = ("Get-CimInstance Win32_Process -Filter \"Name='soffice.bin'\" | "
              "Where-Object { $_.CommandLine -like '*%s*' } | ForEach-Object { $_.ProcessId }" % profile.replace("\\", "/"))
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True).stdout
    return [int(p) for p in out.split()]


def settle_profile(soffice, url, profile, work):
    """A profile whose bundled extensions are synchronized, then the start questions answered (a profile seeded right
    after --terminate_after_init loses the extensions' values at the next start)."""
    subprocess.run([soffice, "-env:UserInstallation=" + url, "--headless", "--norestore", "--terminate_after_init"],
                   timeout=300)
    settle = os.path.join(work, "settle")
    os.makedirs(settle, exist_ok=True)
    empty = os.path.join(settle, "empty.txt")
    open(empty, "w").close()
    for _ in range(3):
        subprocess.run([soffice, "-env:UserInstallation=" + url, "--headless", "--norestore", "--convert-to", "pdf",
                        "--outdir", settle, empty], timeout=300)
        if os.path.exists(os.path.join(profile, "user", "extensions", "bundled", "lastsynchronized")):
            break
    xcu = os.path.join(profile, "user", "registrymodifications.xcu")
    items = "".join('<item oor:path="%s"><prop oor:name="%s" oor:op="fuse"><value>%s</value></prop></item>\n' % item
                    for item in (("/org.hasontech.hstoffice.Welcome", "Shown", "true"),
                                 ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
                                 ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false")))
    with open(xcu, encoding="utf-8") as handle:
        text = handle.read()
    with open(xcu, "w", encoding="utf-8") as handle:
        handle.write(text.replace("</oor:items>", items + "</oor:items>"))


def make_deck(uno, desktop, path, video, audio):
    """A .pptx with the video on slide 1 and the audio on slide 2, both linked and looping."""
    from com.sun.star.awt import Point, Size
    from com.sun.star.beans import PropertyValue
    doc = desktop.loadComponentFromURL("private:factory/simpress", "_blank", 0, ())
    doc.DrawPages.insertNewByIndex(0)
    for index, media in enumerate((video, audio)):
        shape = doc.createInstance("com.sun.star.presentation.MediaShape")
        doc.DrawPages.getByIndex(index).add(shape)
        shape.Position, shape.Size = Point(3000, 3000), Size(8000, 6000)
        shape.MediaURL = uno.systemPathToFileUrl(os.path.abspath(media))
        shape.Loop = True
    arg = PropertyValue()
    arg.Name, arg.Value = "FilterName", "Impress MS PowerPoint 2007 XML"
    doc.storeToURL(uno.systemPathToFileUrl(path), (arg,))
    doc.close(True)


def show_media(doc):
    """Show each slide and select its media shape, so that the edit view creates the players."""
    controller = doc.CurrentController
    for index in range(doc.DrawPages.Count):
        page = doc.DrawPages.getByIndex(index)
        controller.setCurrentPage(page)
        time.sleep(1)
        for shape_index in range(page.Count):
            if "MediaShape" in page.getByIndex(shape_index).ShapeType:
                controller.select(page.getByIndex(shape_index))
                time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--hold", type=int, default=100, help="seconds the media plays before the close")
    args = parser.parse_args()
    work = os.path.abspath(args.out)
    os.makedirs(work, exist_ok=True)
    soffice = os.path.abspath(args.soffice)
    sys.path.insert(0, os.path.dirname(soffice))
    import uno
    profile = os.path.join(work, "profile")
    url = uno.systemPathToFileUrl(profile)
    if not os.path.isdir(profile):
        settle_profile(soffice, url, profile, work)
    port = free_port()
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
    decks = [os.path.join(work, name) for name in ("media-a.pptx", "media-b.pptx")]
    make_deck(uno, desktop, decks[0], args.video, args.audio)
    shutil.copyfile(decks[0], decks[1])  # two files: the same one twice would stop at the lock question
    alive = True
    for cycle in range(args.cycles):
        docs = [desktop.loadComponentFromURL(uno.systemPathToFileUrl(deck), "_blank", 0, ()) for deck in decks]
        for doc in docs:
            show_media(doc)
        end = time.time() + args.hold
        while alive and time.time() < end:
            alive = bool(office_pids(profile))
            time.sleep(2)
        for doc in docs if alive else []:
            try:
                doc.close(True)
            except Exception as error:  # noqa: BLE001 - the bridge goes when the office crashes
                print(f"close: {type(error).__name__}", flush=True)
        time.sleep(4)
        alive = alive and bool(office_pids(profile))
        print(("PASS  " if alive else "FAIL  ") + f"cycle {cycle + 1}: the office survives closing the documents "
              f"through UNO after {args.hold} s", flush=True)
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
    for pid in office_pids(profile):
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    return 0 if alive else 1


if __name__ == "__main__":
    sys.exit(main())
