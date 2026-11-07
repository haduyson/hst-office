# SPDX-License-Identifier: AGPL-3.0-only
"""Live part of the ribbon scorecard: drive one app on an X display and record what its ribbon shows.

Usage (normally started by ribbon_scorecard.py, as the build user under dbus-run-session):
  python3 tests/runtime/ribbon_scorecard_live.py --app writer --mode light --instdir DIR --display :153 --out OBS.json
Writes one observation JSON: the tab strip, a width sweep of every always-visible tab (group captions and boxes,
chevron, collapsed-group buttons, banner box, ribbon height), and the painting and gallery probes. No score is computed
here; ribbon_scorecard.py scores the observations.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ribbon_scorecard_pixels as px  # noqa: E402
import ribbon_tabs_gui as gui  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BAND = 260  # the ribbon lies above this y (window at 0,0)
PARK = (700, 600)  # pointer rest position, over the document


def load_config(path=os.path.join(HERE, "ribbon-scorecard-widths.json")):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _state(node, name):
    import pyatspi
    return node.getState().contains(getattr(pyatspi, name))


def _has_toolbar(panel):
    return any((panel.getChildAtIndex(i) is not None and panel.getChildAtIndex(i).getRoleName() == "tool bar")
               for i in range(min(panel.childCount, 60)))


def group_panel(label):
    """The group a caption belongs to: its parent, or, when the caption sits in a caption row with a launcher, the
    panel above that row (the first ancestor that holds toolbars)."""
    node = label.parent
    for _ in range(3):
        if node is None:
            return None
        if _has_toolbar(node):
            return node
        node = node.parent
    return label.parent


def _labels_group(node, box):
    """A group caption: a label that names its group (Writer exposes the relation), or, where the relation is not
    exposed (Sheets), a label on the bottom row of a panel that holds toolbars."""
    import pyatspi
    if any(r.getRelationType() == pyatspi.RELATION_LABEL_FOR for r in node.getRelationSet()):
        return True
    parent = group_panel(node)
    if parent is None or parent.getRoleName() != "panel" or not _has_toolbar(parent):
        return False
    px_, py_, pw_, ph_ = gui.extents(parent)
    return box[1] + box[3] >= py_ + ph_ - 4 and box[2] >= pw_ - 60


def ribbon_walk(node, depth=0):
    """Like ribbon_tabs_gui.walk, but it does not enter the document area or the sidebar (everything below the ribbon):
    those trees are large, and a walk through them takes seconds once they hold the focus."""
    if node is None:
        return
    yield node
    try:
        if depth >= 16 or node.getRoleName() in gui.SKIP:
            return
        if depth > 2 and gui.extents(node)[1] >= 200:
            return
        children = [node.getChildAtIndex(i) for i in range(min(node.childCount, 400))]
    except Exception:  # noqa: BLE001 - widgets come and go
        return
    for child in children:
        if child is not None:
            yield from ribbon_walk(child, depth + 1)


def popup_nodes():
    """Every node of the office's popup windows and menus (top-level children other than the document frame)."""
    app = gui.office_app()
    for index in range(app.childCount if app else 0):
        try:
            top = app.getChildAtIndex(index)
            if top is None or top.getRoleName() == "frame":
                continue
        except Exception:  # noqa: BLE001
            continue
        yield from gui.walk(top)


def layout():
    """One AT-SPI pass over the ribbon: tabs, groups, chevron, buttons, banner and document-tab row."""
    tabs, groups, buttons, chevron, banner, doc_tabs, frame = [], [], [], None, None, None, None
    for node in ribbon_walk(gui.office_app()):
        try:
            role, name = node.getRoleName(), node.name or ""
            if role == "frame" and frame is None:
                frame = gui.extents(node)[1]
                continue
            if role == "panel" and name == "Thẻ tài liệu":
                doc_tabs = gui.extents(node)[1]
                continue
            if not gui.showing(node):
                continue
            box = list(gui.extents(node))
            if box[1] >= BAND:
                continue
            if role == "page tab" and box[1] < 100:
                tabs.append({"name": name, "box": box, "selected": _state(node, "STATE_SELECTED")})
            elif role == "label" and name and _labels_group(node, box):
                parent = group_panel(node)
                groups.append({"caption": name, "caption_box": box, "box": list(gui.extents(parent)) if parent else box})
            elif role in ("push button", "toggle button", "menu button"):
                if not name and box[2] <= 30 and box[3] >= 30 and 40 < box[1] < 200:
                    chevron = box
                buttons.append({"name": name, "role": role, "box": box,
                                "checked": _state(node, "STATE_CHECKED") or _state(node, "STATE_PRESSED")})
            elif role == "link" and banner is None and box[2] > 100:
                banner = box
        except Exception:  # noqa: BLE001 - widgets come and go while the ribbon re-lays out
            continue
    tabs.sort(key=lambda t: t["box"][0])
    groups.sort(key=lambda g: g["box"][0])
    height = doc_tabs - frame if doc_tabs is not None and frame is not None else None
    return {"tabs": tabs, "groups": groups, "buttons": buttons, "chevron": chevron, "banner": banner, "height": height}


def _summary(data):
    return json.dumps([[g["caption"], g["box"]] for g in data["groups"]] + [data["chevron"], data["banner"], data["height"]])


def stable_layout(tries=8, pause=1.0):
    """Measure until two passes in a row agree (the ribbon re-lays out for a moment after a resize)."""
    last = layout()
    for _ in range(tries):
        time.sleep(pause)
        now = layout()
        if _summary(now) == _summary(last):
            return now
        last = now
    return last


class Session:
    def __init__(self, args, config):
        self.args, self.config = args, config
        self.app_conf = config["apps"][args.app]
        self.office = self.wid = None
        self.shots = 0

    def start(self):
        dark = self.args.mode == "dark"
        conf = [("/org.openoffice.Office.Impress/Misc/NewDoc", "AutoPilot", "false"),
                ("/org.openoffice.Office.Common/Appearance", "ApplicationAppearance", "2" if dark else "1"),
                ("/org.openoffice.Office.Common/Misc", "SymbolStyle", "hst_dark" if dark else "hst")]
        subprocess_env = {"GTK_THEME": "Adwaita:dark" if dark else "Adwaita"}
        subprocess.run(["xprop", "-display", self.args.display, "-root", "-remove", "AT_SPI_BUS"], check=False,
                       stderr=subprocess.DEVNULL)
        self.office = hst_gui.Office(self.args.instdir, self.args.work, self.args.port, display=self.args.display,
                                     extra_args=[f"--{self.args.app}"], nodefault=False, config=conf, env=subprocess_env)
        self.office.start()
        deadline = time.time() + 60
        windows = []
        while not windows and time.time() < deadline:
            time.sleep(2)
            windows = [w for w, n in hst_gui.toplevels(self.args.display, self.office.pid) if self.app_conf["name"] in n]
        if not windows:
            raise RuntimeError(f"no {self.app_conf['name']} window")
        self.wid = windows[0]
        gui.xdo(self.args.display, "windowmove", self.wid, "0", "0")
        self.resize(self.config["probe_width"])
        gui.xdo(self.args.display, "mousemove", *map(str, PARK))

    def resize(self, width):
        gui.xdo(self.args.display, "windowsize", self.wid, str(width), str(self.config["height"]))
        time.sleep(2)
        return stable_layout()

    def shot(self, tag):
        from PIL import Image
        path = os.path.join(self.args.work, "shots", f"{self.args.app}-{self.args.mode}-{tag}.png")
        self.office.screenshot(path)
        with Image.open(path) as image:
            return image.convert("RGB")

    def open_tab(self, name):
        data = layout()
        tab = next((t for t in data["tabs"] if t["name"] == name), None)
        if tab is None:
            return False
        if not tab["selected"]:
            gui.click(self.args.display, tab["box"])
            gui.xdo(self.args.display, "mousemove", *map(str, PARK))
            time.sleep(1)
        return any(t["selected"] and t["name"] == name for t in layout()["tabs"])

    def dispatch(self, command):
        frame = self.office.desktop().getCurrentFrame() or self.office.desktop().getFrames().getByIndex(0)
        self.office.dispatch(frame, command)
        time.sleep(1)

    def stop(self):
        """Close without the save prompt: the probes change character attributes, and a modal "save changes?" dialog
        would block terminate() for good."""
        if self.office is None:
            return
        try:
            components = self.office.desktop().getComponents().createEnumeration()
            while components.hasMoreElements():
                component = components.nextElement()
                if hasattr(component, "setModified"):
                    component.setModified(False)
        except Exception:  # noqa: BLE001 - the office may already be gone
            pass
        self.office.stop()


def sweep(session):
    """Tab strip at the widest width, then every always-visible tab at every width, widest first."""
    widths = sorted(session.config["widths"], reverse=True)
    top = session.resize(widths[0])
    names = [t["name"] for t in top["tabs"]]
    result = {"tabs": names, "pages": {}}
    for name in names:
        if name in session.config["skip_tabs"]:
            continue
        session.resize(widths[0])
        if not session.open_tab(name):
            result["pages"][name] = {"error": "tab did not open"}
            continue
        page = {}
        for width in widths:
            data = session.resize(width)
            page[str(width)] = {"groups": [{"caption": g["caption"], "box": g["box"]} for g in data["groups"]],
                                "chevron": data["chevron"], "banner": data["banner"], "height": data["height"],
                                "group_buttons": [b["name"] for b in data["buttons"] if b["name"] and b["box"][3] >= 50]}
        result["pages"][name] = page
    session.resize(session.config["probe_width"])
    return result


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
    """Writer's Styles gallery: rendered previews, columns at 1485, column shrink, More popup, keyboard apply."""
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
    out["rendered_previews"] = {"pass": count_probe >= 2, "detail": count_probe}
    out["four_columns"] = {"pass": count_probe >= 4, "detail": count_probe}
    out["column_shrink"] = {"pass": count_wide > count_narrow >= 1, "detail": [count_wide, count_narrow]}
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, choices=("writer", "calc", "impress"))
    parser.add_argument("--mode", default="light", choices=("light", "dark"))
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--display", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--port", type=int, default=7650)
    parser.add_argument("--out", required=True)
    parser.add_argument("--stages", default="sweep,probes,gallery", help="a subset, to debug one stage")
    args = parser.parse_args()
    os.environ.update(NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge")
    hst_gui.setup_uno(args.instdir)
    config = load_config()
    session = Session(args, config)
    observation = {"app": args.app, "mode": args.mode, "errors": []}

    def save():
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(observation, handle, ensure_ascii=False, indent=1)

    home = "Trang đầu"
    stages = [("probes", lambda: probes(session, home))]
    if args.mode == "light":
        stages.insert(0, (None, lambda: sweep(session)))
        if args.app == "writer":  # last: the gallery's More button may open the Styles deck
            stages.append(("gallery", lambda: gallery(session, home)))
    stages = [(k, f) for k, f in stages if (k or "sweep") in args.stages.split(",")]
    try:
        session.start()
        for key, stage in stages:
            try:
                result = stage()
                if key is None:
                    observation.update(result)
                else:
                    observation[key] = result
            except Exception as error:  # noqa: BLE001 - recorded; the scorer counts missing parts as failed
                observation["errors"].append(f"{key or 'sweep'}: {error!r}")
            save()
    except Exception as error:  # noqa: BLE001
        observation["errors"].append(f"start: {error!r}")
    finally:
        session.stop()
        save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
