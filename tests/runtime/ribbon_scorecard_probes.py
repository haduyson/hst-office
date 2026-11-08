# SPDX-License-Identifier: AGPL-3.0-only
"""Painting and gallery probes of the ribbon scorecard's live part, on the Home tab at the probe width."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ribbon_scorecard_pixels as px  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402
from ribbon_scorecard_walk import PARK, popup_nodes, ribbon_walk, stable_layout  # noqa: E402


def _button(data, name):
    return next((b for b in data["buttons"] if b["name"] == name), None)


def probes(session, home):
    """The ten painting probes on the Home tab at the probe width."""
    display, conf = session.args.display, session.app_conf
    out = {}
    session.resize(session.config["probe_width"])
    session.open_tab(home)
    data = stable_layout()
    target = _button(data, conf["probe_button"])
    if target is not None and target["checked"]:
        session.dispatch(conf.get("checked_command", ".uno:Bold"))
        data = stable_layout()
        target = _button(data, conf["probe_button"])
    base = session.shot("base")
    if target is None:
        for key in ("hover_fill", "pressed", "checked", "focus_ring"):
            out[key] = {"pass": False, "detail": f"button {conf['probe_button']} not found"}
    else:
        box = target["box"]
        centre = (str(box[0] + box[2] // 2), str(box[1] + box[3] // 2))
        gui.xdo(display, "mousemove", *centre)
        time.sleep(1.2)
        hover = session.shot("hover")
        ok, detail = px.flat_fill(base, hover, box)
        out["hover_fill"] = {"pass": ok, "detail": detail}
        gui.xdo(display, "mousedown", "1")
        time.sleep(0.8)
        pressed = session.shot("pressed")
        gui.xdo(display, "mousemove", *map(str, PARK))
        time.sleep(0.3)
        gui.xdo(display, "mouseup", "1")
        time.sleep(0.8)
        ok, detail = px.flat_fill(base, pressed, box)
        moved = len(px.changed(hover, pressed, box)) / max(box[2] * box[3], 1)
        out["pressed"] = {"pass": ok and moved >= 0.1, "detail": dict(detail, vs_hover=round(moved, 3))}
        if _button(stable_layout(), conf["probe_button"])["checked"]:  # a press that toggled: undo it
            session.dispatch(conf.get("checked_command", ".uno:Bold"))
        session.dispatch(conf.get("checked_command", ".uno:Bold"))
        checked = session.shot("checked")
        ok, detail = px.flat_fill(base, checked, box)
        out["checked"] = {"pass": ok, "detail": detail}
        session.dispatch(conf.get("checked_command", ".uno:Bold"))
        out["focus_ring"] = focus_probe(session, base)
    data = stable_layout()
    groups = [g for g in data["groups"] if g["box"][0] + g["box"][2] <= session.config["probe_width"]]
    results = []
    for left, right in zip(groups, groups[1:]):
        lx, ly, lw, lh = left["box"]
        gap = (lx + lw - 4, ly + lh // 5, right["box"][0] - (lx + lw) + 3, lh * 3 // 5)  # stops before the next group
        results.append(px.thin_separator(base, gap))
    out["group_separator"] = {"pass": bool(results) and all(r[0] for r in results), "detail": [r[1] for r in results]}
    results = [px.centred(base, g["caption_box"], g["box"]) for g in groups]
    out["centred_caption"] = {"pass": bool(results) and all(r[0] for r in results), "detail": [r[1] for r in results]}
    selected = next((t for t in data["tabs"] if t["selected"]), None)
    ok, detail = px.underline(base, selected["box"]) if selected else (False, "no selected tab")
    out["tab_underline"] = {"pass": ok, "detail": detail}
    paste = _button(data, conf["paste"])
    ok, detail = px.large_icon_with_label(base, paste["box"]) if paste else (False, "no Paste button")
    out["paste_32"] = {"pass": ok, "detail": detail}
    # a launcher: a small named button (a toolbar button of a 16 px glyph) in the caption row of a group
    launchers = [b for b in data["buttons"] if b["box"][2] <= 24 and b["box"][3] <= 24 and b["name"] and any(
        g["box"][0] <= b["box"][0] <= g["box"][0] + g["box"][2] and abs(b["box"][1] - g["caption_box"][1]) <= 12
        for g in groups)]
    out["launcher_glyph"] = {"pass": bool(launchers), "detail": [b["name"] for b in launchers]}
    captions = {g["caption"] for g in groups}
    narrow = session.resize(session.config["collapsed_width"])
    group_buttons = [b["name"] for b in narrow["buttons"] if b["name"] in captions and b["box"][3] >= 50]
    out["collapsed_group_button"] = {"pass": bool(group_buttons), "detail": group_buttons}
    session.resize(session.config["probe_width"])
    return out


def focus_probe(session, base):
    """Move keyboard focus into the ribbon with F6 and look for a ring around the focused item."""
    import pyatspi
    display = session.args.display
    focused = None
    for _ in range(6):
        gui.xdo(display, "key", "F6")
        time.sleep(0.8)
        for node in ribbon_walk(gui.office_app()):
            try:
                if node.getState().contains(pyatspi.STATE_FOCUSED) and gui.showing(node):
                    box = list(gui.extents(node))
                    if 44 <= box[1] < 180 and node.getRoleName() in ("push button", "toggle button", "menu button"):
                        focused = box
                        break
            except Exception:  # noqa: BLE001
                continue
        if focused:
            break
    shot = session.shot("focus") if focused else None
    for _ in range(3):
        gui.xdo(display, "key", "Escape")
        time.sleep(0.3)
    if not focused:
        return {"pass": False, "detail": "no ribbon item took the keyboard focus"}
    ok, detail = px.ring(base, shot, focused)
    return {"pass": ok, "detail": detail}


def gallery(session, home):
    """Writer's Styles gallery: at least 2 tiles at 1485 and 4 at 1920, never more tiles when narrower (at 1366 a
    "Kiểu" group button, 0 tiles, is fine: the banner takes its room by the owner's choice), More popup, keyboard
    apply."""
    out = {}

    def tiles(width):
        session.resize(width)
        data = stable_layout()
        panel = next((b for b in data["buttons"] if b["name"] == "Xem thử kiểu dáng"), None)
        node = panel or next((g for g in _gallery_nodes()), None)
        if node is None:
            return 0, None
        box = node["box"]
        image = session.shot(f"gallery-{width}")
        return px.gallery_tiles(image, (box[0], box[1], box[2] - 20, box[3])), box

    session.open_tab(home)
    count_probe, box = tiles(session.config["probe_width"])
    count_wide, _ = tiles(1920)
    count_narrow, _ = tiles(1366)
    out["two_tiles_1485"] = {"pass": count_probe >= 2, "detail": count_probe}
    out["four_tiles_1920"] = {"pass": count_wide >= 4, "detail": count_wide}
    out["column_shrink"] = {"pass": count_wide >= count_probe >= count_narrow,
                            "detail": [count_wide, count_probe, count_narrow]}
    session.resize(session.config["probe_width"])
    out["more_popup"] = more_popup(session, box)
    out["keyboard_apply"] = keyboard_apply(session, box)
    return out


def _gallery_nodes():
    for node in ribbon_walk(gui.office_app()):
        try:
            if node.getRoleName() == "panel" and node.name == "Xem thử kiểu dáng" and gui.showing(node):
                yield {"name": node.name, "box": list(gui.extents(node))}
        except Exception:  # noqa: BLE001
            continue


def more_popup(session, box):
    if box is None:
        return {"pass": False, "detail": "no gallery"}
    display = session.args.display
    gui.click(display, (box[0] + box[2] - 16, box[1] + box[3] - 16, 16, 16))
    time.sleep(1.5)
    names = []
    for node in popup_nodes():
        try:
            if gui.showing(node) and node.getRoleName() in ("menu item", "push button", "list item"):
                names.append(node.name or "")
        except Exception:  # noqa: BLE001
            continue
    gui.xdo(display, "key", "Escape")
    time.sleep(0.8)
    wanted = [n for n in names if n.lower().startswith(("tạo kiểu", "xóa định dạng"))]
    return {"pass": bool(wanted), "detail": wanted}


def keyboard_apply(session, box):
    if box is None:
        return {"pass": False, "detail": "no gallery"}
    display = session.args.display
    doc = session.office.desktop().getCurrentComponent()
    cursor = doc.getCurrentController().getViewCursor()
    gui.click(display, (box[0] + 8, box[1] + 8, 40, box[3] - 16))
    time.sleep(1)
    before = cursor.ParaStyleName
    gui.xdo(display, "key", "Right")
    time.sleep(0.4)
    gui.xdo(display, "key", "Return")
    time.sleep(1.2)
    after = cursor.ParaStyleName
    for _ in range(2):
        session.dispatch(".uno:Undo")
    gui.xdo(display, "mousemove", *map(str, PARK))
    return {"pass": after != before, "detail": [before, after]}


