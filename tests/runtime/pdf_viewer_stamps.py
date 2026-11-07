# SPDX-License-Identifier: AGPL-3.0-only
"""HST PDF keeps red red (PDFium page bitmaps are BGRx): the red-stamp workflows of
pdf_stamp_samples on screen, in the page bitmap that the screen, thumbnails and printing use
(HSTPdfInfo RenderRedPixels/RenderBluePixels), printed to a file, and after signing a copy."""
import os
from pathlib import Path
import subprocess
import threading
import time

import hst_gui
import pdf_stamp_samples
import signature_pki
from pdf_viewer_uno import info, open_viewer, sign_copy, signing_props, wait_info


def stamp_colours(office, frame, page, shot):
    """Red and blue pixels of page `page`: in the rendered page bitmap and on screen."""
    office.dispatch(frame, ".uno:HSTPdfGoToPage", signing_props(Page=page))
    office.dispatch(frame, ".uno:HSTPdfZoom", signing_props(Fit="page"))
    rendered = info(office, frame, RenderPage=page)
    time.sleep(2)  # repaint of the page and the thumbnails
    office.screenshot(str(shot))
    red, blue = pdf_stamp_samples.red_blue_pixels(str(shot))
    return {"render_red": rendered["RenderRedPixels"], "render_blue": rendered["RenderBluePixels"],
            "screen_red": red, "screen_blue": blue}


def wait_dialog(dialogs, child, timeout=30, dismiss_messages=False):
    deadline = time.time() + timeout
    while time.time() < deadline:
        win, kids = dialogs.top()
        if child in kids:
            return win
        if dismiss_messages and kids and kids <= {"", "ok"}:
            # e.g. the file picker's start folder (the test user's home) does not exist
            dialogs.later(win.getChild("ok"))
            time.sleep(1)
        time.sleep(0.3)
    dialogs.shot("no-dialog-" + child)
    raise AssertionError("no dialog with %r (top: %r)" % (child, dialogs.top()[1]))


def print_to_file(office, dialogs, frame, target, workdir):
    """Print from HST PDF through the print dialog's "print to file" entry; returns page PNGs."""
    threading.Thread(target=office.dispatch, args=(frame, ".uno:Print"), daemon=True).start()
    win = wait_dialog(dialogs, "printersbox")
    win.getChild("printersbox").executeAction("SELECT", signing_props(POS="0"))  # print to file
    time.sleep(1)
    dialogs.later(win.getChild("ok"))
    win = wait_dialog(dialogs, "file_name", dismiss_messages=True)
    win.getChild("file_name").executeAction("TYPE", signing_props(TEXT=str(target)))
    dialogs.later(win.getChild("open"))
    deadline, size = time.time() + 60, -1
    while time.time() < deadline:
        produced = sorted(target.parent.glob(target.stem + ".*"))
        if produced and produced[0].stat().st_size == size and size > 0:
            break
        size = produced[0].stat().st_size if produced else -1
        time.sleep(1)
    assert produced, "nothing printed to %s" % target
    stem = workdir / ("printed-" + target.stem)
    subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=png16m", "-r50",
                    "-sOutputFile=%s-%%d.png" % stem, str(produced[0])], check=True)
    return produced[0], sorted(workdir.glob(stem.name + "-*.png"))


def assert_red(colours, where):
    # the stamp is red: clearly more red than blue pixels, both in the bitmap and on screen
    assert colours["render_red"] > 100 and colours["render_red"] > 10 * colours["render_blue"], (where, colours)
    assert colours["screen_red"] > 100 and colours["screen_red"] > colours["screen_blue"], (where, colours)


def check_red_stamps(office, signing, instdir, workdir, signed, checks, result):
    """The 4 red-stamp workflows stay red in HST PDF, before and (with the token) after signing."""
    stamps = pdf_stamp_samples.make_stamp_workflows(instdir, workdir / "stamps")
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", hst_gui.BUILD_USER, str(workdir / "stamps")], check=True)
    cases = [(name, Path(stamps["docx_pdf"]), page) for name, page in pdf_stamp_samples.STAMP_PAGES.items()]
    cases.append(("scanned-page", Path(stamps["scanned_page"]), 1))
    colours = result.setdefault("red_stamps", {})
    dialogs = signing.Dialogs(office, str(workdir / "shots"), [signature_pki.USER_PIN] * 4) if signed else None
    for source in sorted({path for _name, path, _page in cases}):
        frame, _ = open_viewer(office, source)
        for name, path, page in cases:
            if path == source:
                colours[name] = stamp_colours(office, frame, page, workdir / "shots" / ("red-%s.png" % name))
                assert_red(colours[name], name)
        if source.name == "con-dau.pdf":
            # printing renders the same page bitmaps: print the 3 pages to a file once
            printer = signing.Dialogs(office, str(workdir / "shots"), [])
            printed, pages = print_to_file(office, printer, frame, workdir / "in-con-dau.pdf", workdir)
            counts = [pdf_stamp_samples.red_blue_pixels(str(png)) for png in pages]
            result["printed_red_blue"] = {"file": printed.name, "pages": counts}
            assert len(counts) == 3 and all(red > 100 and red > 10 * blue for red, blue in counts), counts
            checks["printed_stamps_stay_red"] = True
        if signed:
            target = workdir / (source.stem + "-da-ky.pdf")
            target.unlink(missing_ok=True)
            office.dispatch(frame, ".uno:HSTPdfSignPanel", signing_props(Show=True))
            done = sign_copy(office, dialogs, frame, target, Reason="Thử con dấu", Page=1, X=60.0, Y=700.0)
            assert done.get("result") is True, (source.name, done, dialogs.prompts, dialogs.unexpected)
        frame.close(True)
        time.sleep(0.5)
        if signed:
            frame, _ = open_viewer(office, target)
            data = wait_info(office, frame, "SignaturesChecked", lambda v: v is True)
            assert data["ValidSignatures"] == 1, data
            for name, path, page in cases:
                if path == source:
                    after = stamp_colours(office, frame, page, workdir / "shots" / ("red-%s-da-ky.png" % name))
                    colours[name + "-signed"] = after
                    assert_red(after, name + " signed")
            frame.close(True)
            time.sleep(0.5)
    checks["red_stamps_stay_red"] = True
    if signed:
        checks["red_stamps_stay_red_after_signing"] = True
