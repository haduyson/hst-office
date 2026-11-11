# SPDX-License-Identifier: AGPL-3.0-only
"""How W16 tells that a route opened its document: the window census polled until the document's window is shown,
enabled, painted and in front of Explorer, with a timeline and screenshots as evidence."""
from pathlib import Path
import time

from native import screenshot


def painted(rect, covers=()):
    """The document's content is drawn: a window still loading is one flat colour with a progress text in its status
    bar (the frame is shown before the import, loadenv.cxx), a loaded one has the ribbon, rulers or grid. Dialogs
    over the window (`covers`) are blanked out first, so a start-up question over a loaded document still counts."""
    from PIL import ImageDraw, ImageGrab
    left, top, right, bottom = rect
    if right - left < 300 or bottom - top < 200:
        return False
    box = (left + 8, top + 40, right - 8, bottom - 60)  # no title bar, no status bar
    image = ImageGrab.grab(bbox=box, all_screens=True).convert("RGB")
    draw = ImageDraw.Draw(image)
    for c in covers:
        draw.rectangle((c[0] - box[0], c[1] - box[1], c[2] - box[0], c[3] - box[1]), fill=(0, 0, 0))
    return len(set(image.resize((160, 90)).getdata())) > 40


def watch(out, matches, limit, label):
    """Poll the census until the document window is shown, enabled and in front of Explorer, or the limit."""
    from open_routes_windows import census, office_processes, dismiss_system_notices
    start, timeline, last, shots, result, first_window = time.monotonic(), [], None, [], None, None
    marks = [2, 10, 25, 60]
    while True:
        now = round(time.monotonic() - start, 1)
        windows, fg = census()
        dismiss_system_notices()
        office = [w for w in windows if w["proc"] == "soffice.bin" and w["title"]]
        explorer_z = min([w["z"] for w in windows if w["cls"] == "CabinetWClass"] or [10 ** 6])
        doc = next((w for w in office if matches(w["title"]) and not w["owner"]), None)
        state = (tuple((w["title"], w["enabled"], w["z"] < explorer_z) for w in office), fg["title"])
        if state != last:
            timeline.append(dict(t=now, office=[dict(title=w["title"], cls=w["cls"], enabled=w["enabled"],
                                                     above_explorer=w["z"] < explorer_z, owner=bool(w["owner"]),
                                                     iconic=w["iconic"]) for w in office],
                                 foreground=fg, processes=office_processes()))
            last = state
        if marks and now >= marks[0]:
            marks.pop(0)
            shots.append(screenshot(out / ("%s-%02ds.png" % (label, int(now)))))
        if doc and first_window is None:
            first_window = now
        front = doc and not doc["iconic"] and (doc["z"] < explorer_z or fg["proc"] == "soffice.bin")
        over = [w for w in office if w["owner"] or not matches(w["title"])]
        if front and painted(doc["rect"], [w["rect"] for w in over]):
            result = dict(status="OK", seconds=now, window_seconds=first_window, title=doc["title"],
                          foreground=fg["title"], doc_is_foreground=fg["hwnd"] == doc["hwnd"],
                          dialog_over_document=[w["title"] for w in over] if not doc["enabled"] else [])
            break
        if now >= limit:
            dialogs = [w["title"] for w in office if not matches(w["title"])]
            status = ("BLOCKED" if doc and not doc["enabled"] else "BEHIND" if doc and not front else
                      "BLANK" if doc else "DIALOG" if dialogs else "NO WINDOW")
            if status in ("NO WINDOW", "BLANK", "BLOCKED"):
                from open_routes_windows import minidump
                result_dumps = [minidump(p["pid"], out.parent / "crash" / ("hang-%s-%d.dmp" % (label, p["pid"])))
                                for p in office_processes() if p["name"].lower() == "soffice.bin"]
            else:
                result_dumps = []
            result = dict(status=status, seconds=None, window_seconds=first_window, dumps=result_dumps,
                          office_windows=[w["title"] for w in office],
                          dialogs=dialogs, foreground=fg["title"], processes=office_processes())
            break
        time.sleep(0.4)
    shots.append(screenshot(out / ("%s-end.png" % label)))
    result["timeline"] = timeline
    result["screenshots"] = [Path(s).name for s in shots]
    return result


def unblock(out, matches, label):
    """After a failed wait: bring the office's own dialog (or the document) forward, press Escape, wait again;
    tells whether a person who finds the dialog gets the document."""
    from open_routes_windows import census, bring_to_front, close_windows
    office = [w for w in census()[0] if w["proc"] == "soffice.bin" and w["title"]]
    target = next((w for w in office if w["enabled"] and not matches(w["title"])), None) or \
        next((w for w in office), None)
    if target is None:
        return dict(action="nothing to bring forward")
    if matches(target["title"]):
        bring_to_front(target["hwnd"])
        action = "front " + target["title"]
    else:
        close_windows([target["hwnd"]])  # the dialog's own close button, no focus needed
        action = "close " + target["title"]
    again = watch(out, matches, 45, label + "-after")
    return dict(action=action, status=again["status"], seconds=again["seconds"],
                timeline=again["timeline"][-3:], screenshots=again["screenshots"])
