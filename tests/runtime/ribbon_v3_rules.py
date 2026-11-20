# SPDX-License-Identifier: AGPL-3.0-only
"""The v3 rules of one ribbon layout dump: one JSON file per tab page and window width, written by the real app.

Rects are device px relative to the ribbon body's top-left; logical px = device px / scale. caption_needed is
device px like the rects. Each rule yields (rule, ok, detail): ok False per violation, ok True when it passes,
ok None for information. Rules 1-6 skip folded groups (state C); captions, clip and label cut cover every group.
Pure functions, no display, no AT-SPI (tests/unit/test_ribbon_v3_rules.py).
"""
import json
import os
import statistics

from ribbon_mockup_rules import BANNER_MAX_W, BANNER_MIN_W, BANNER_TOP, TOLERANCE, banner_ok

BODY_MIN_H = 106
ROW_TOPS, ROW_BOTTOMS = (6, 32, 58), (30, 56, 82)  # small items, boxes: the three rows of a group
LARGE_TOP, LARGE_BOTTOM, LARGE_W = 6, 82, 96  # large buttons and galleries; widened large buttons
GAP, SLACK = 8, 4  # the banner's gap to the last group, and the slack allowed above it
CHEVRON = 22  # the collapse chevron's own room after the last group (18 px and its 4 px inset), as in the mockup
# a box item (a native list box in its row) may ask for up to this many logical px more height than the row gives
# it: fitItemWindowsToRow sets it to the row and the native control draws its frame and text inside (HST5 shots)
BOX_HEIGHT_SLACK = 4
CLIPBOARD = "gdHomeClipboard"  # Paste (large) with one column of three icons: the only mixed group allowed
RULES = ("body", "band", "edge", "one_size", "equal_width", "lone_col", "cols_3plus1", "banner", "elastic_fill",
         "captions", "clip", "label_cut", "widening", "order")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "ribbon",
                    "ribbon-v3.json")
DATA_APPS = {"writer": "writer", "calc": "sheets", "impress": "slides", "draw": "draw"}  # dump app -> data app
_TAB_ORDERS = {}


def _logical(rect, scale):
    """(left, top, right, bottom) of a device-px rect, in logical px."""
    x, y, w, h = rect["x"] / scale, rect["y"] / scale, rect["w"] / scale, rect["h"] / scale
    return x, y, x + w, y + h


def _near(value, target):
    return abs(value - target) <= TOLERANCE


def _verdict(rule, violations):
    """One (rule, ok, detail) per violation, or a single passing tuple."""
    if not violations:
        return [(rule, True, "pass")]
    return [(rule, False, text) for text in violations]


def _groups(dump, skip_folded=False):
    return [g for g in dump["groups"] if not (skip_folded and g.get("state") == "C")]


def _items(group):
    return [item for block in group["blocks"] for item in block.get("items", [])]


def _large_items(dump):
    return [i for g in _groups(dump, True) for i in _items(g) if i.get("kind") == "L"]


def _width(item, scale):
    return item["rect"]["w"] / scale


def _body(dump):
    h = dump["body"]["h"] / dump["scale"]
    return _verdict("body", [] if h >= BODY_MIN_H - TOLERANCE else [f"body {h:.1f} px is under 106"])


def _band(dump):
    scale, bad = dump["scale"], []
    for g in _groups(dump, True):
        for item in _items(g):
            kind = item.get("kind")
            _l, top, _r, bottom = _logical(item["rect"], scale)
            if kind in ("M", "S", "W"):
                ok = any(_near(top, t) for t in ROW_TOPS) and any(_near(bottom, b) for b in ROW_BOTTOMS)
            elif kind in ("L", "G"):
                ok = _near(top, LARGE_TOP) and _near(bottom, LARGE_BOTTOM)
            else:
                continue
            if not ok:
                bad.append(f"{g['id']} {item['id']} kind {kind} at {top:.1f}..{bottom:.1f}")
    return _verdict("band", bad)


def _edge(dump):
    scale, bad = dump["scale"], []
    for g in _groups(dump, True):
        if not any(i.get("kind") in ("L", "G") for i in _items(g)):
            continue
        for block in g["blocks"]:
            spans = [_logical(i["rect"], scale) for i in block.get("items", [])]
            if not spans:
                continue
            top, bottom = min(s[1] for s in spans), max(s[3] for s in spans)
            if not (_near(top, LARGE_TOP) and _near(bottom, LARGE_BOTTOM)):
                bad.append(f"{g['id']} block {block['type']} spans {top:.1f}..{bottom:.1f}")
    return _verdict("edge", bad)


def _one_size(dump):
    bad, allowed = [], []
    for g in _groups(dump, True):
        kinds = {i.get("kind") for i in _items(g)}
        if "L" in kinds and kinds & {"M", "S", "W"}:
            (allowed if g["id"] == CLIPBOARD else bad).append(g["id"])
    out = _verdict("one_size", [f"{gid} mixes large and small items" for gid in bad])
    if allowed:
        out.append(("one_size", None, f"{CLIPBOARD} mixes large and small items (allowed, reported apart)"))
    return out


def _spread(values):
    return max(values) - min(values) > TOLERANCE if values else False


def _equal_width(dump):
    scale, bad, tab_large = dump["scale"], [], []
    for g in _groups(dump, True):
        large = [_width(i, scale) for i in _items(g) if i.get("kind") == "L"]
        tab_large += large
        if _spread(large):
            bad.append(f"{g['id']} large widths {[round(w, 1) for w in large]}")
        small = [_width(i, scale) for b in g["blocks"] if b.get("type") == "col" for i in b.get("items", [])
                 if i.get("kind") in ("M", "W")]
        if _spread(small):
            bad.append(f"{g['id']} column widths {[round(w, 1) for w in small]}")
    if _spread(tab_large):
        bad.append(f"tab large widths {sorted({round(w, 1) for w in tab_large})}")
    return _verdict("equal_width", bad)


def _columns(dump):
    return {g["id"]: [len(b.get("items", [])) for b in g["blocks"] if b.get("type") == "col"]
            for g in _groups(dump, True)}


def _lone_col(dump):
    return _verdict("lone_col", [f"{gid} has a column of 1 item" for gid, counts in _columns(dump).items()
                                 if 1 in counts])


def _cols_3plus1(dump):
    return _verdict("cols_3plus1", [f"{gid} columns {counts}" for gid, counts in _columns(dump).items()
                                    if 3 in counts and 1 in counts])


def _banner(dump):
    banner = dump.get("banner")
    if banner is None:
        return _verdict("banner", ["no banner (it is never hidden)"])
    scale = dump["scale"]
    w, h, top = banner["w"] / scale, banner["h"] / scale, banner["y"] / scale
    bad = []
    if not banner_ok(w, h):
        bad.append(f"banner {w:.1f} x {h:.1f} is outside {BANNER_MIN_W}..{BANNER_MAX_W} x 96")
    if not _near(top, BANNER_TOP):
        bad.append(f"banner top {top:.1f} is not {BANNER_TOP}")
    return _verdict("banner", bad)


def _last_right(dump):
    scale = dump["scale"]
    return max((_logical(g["rect"], scale)[2] for g in dump["groups"]), default=0.0)


def _elastic(dump):
    banner = dump.get("banner")
    if banner is None:
        return [("elastic_fill", None, "no banner")]
    scale = dump["scale"]
    free = banner["x"] / scale - _last_right(dump)
    width = banner["w"] / scale
    if width >= BANNER_MAX_W - TOLERANCE:
        return [("elastic_fill", None, f"banner at {BANNER_MAX_W}: {free:.1f} px free (allowed)")]
    if free > GAP + CHEVRON + SLACK + TOLERANCE:
        return _verdict("elastic_fill", [f"{free:.1f} px free before the banner (limit {GAP + CHEVRON + SLACK})"])
    return _verdict("elastic_fill", [])


def _captions(dump):
    scale, bad, bottoms = dump["scale"], [], []
    body_bottom = dump["body"]["h"] / scale
    for g in dump["groups"]:
        cap, needed = g.get("caption_rect"), g.get("caption_needed")
        if cap is None or needed is None:
            bad.append(f"{g['id']} has no caption_rect or caption_needed")
            continue
        _l, top, _r, bottom = _logical(cap, scale)
        bottoms.append(bottom)
        if top < -TOLERANCE or bottom > body_bottom + TOLERANCE:
            bad.append(f"{g['id']} caption outside the body")
        if needed > cap["w"] + TOLERANCE * scale:
            bad.append(f"{g['id']} caption cut: needs {needed} px, rect {cap['w']} px")
    if bottoms and max(bottoms) - min(bottoms) > TOLERANCE:
        bad.append(f"caption bottoms span {min(bottoms):.1f}..{max(bottoms):.1f}")
    return _verdict("captions", bad)


def _clip(dump):
    scale, bad = dump["scale"], []
    body_bottom = dump["body"]["h"] / scale
    banner = dump.get("banner")
    limit = banner["x"] / scale - GAP if banner is not None else None
    for g in dump["groups"]:
        for name, rect in [(g["id"], g["rect"])] + [(i["id"], i["rect"]) for i in _items(g)]:
            _l, _t, right, bottom = _logical(rect, scale)
            if bottom > body_bottom + TOLERANCE:
                bad.append(f"{name} bottom {bottom:.1f} is past the body")
            if limit is not None and right > limit + TOLERANCE:
                bad.append(f"{name} right {right:.1f} is past the banner minus {GAP}")
    return _verdict("clip", bad)


def _row_fitted_box(item, scale):
    """A cut that is only the box's own height request, within BOX_HEIGHT_SLACK of its row: not a cut label."""
    want, rect = item.get("want"), item["rect"]
    return (want is not None and want["w"] <= rect["w"]
            and (want["h"] - rect["h"]) / scale <= BOX_HEIGHT_SLACK)


def _label_cut(dump):
    """A cut label, or a box that a window above it shows only in part (box_clip: Windows at 125 % text, the toolbox
    cut the fill box's bottom). A box drawing its native frame in less height than it asks for (native_cut) is only
    information (dump_summary): the theme fits the frame to the box, and what shows is measured by box_clip."""
    scale, bad = dump["scale"], []
    for g in dump["groups"]:
        for i in _items(g):
            if i.get("label_cut") and not _row_fitted_box(i, scale):
                bad.append(f"{g['id']} {i['id']} label cut" + (f", want {i['want']}" if i.get("want") else ""))
            clip = i.get("box_clip")
            if clip and clip["shown"] < clip["h"]:
                bad.append(f"{g['id']} {i['id']} box shown {clip['shown']} of {clip['h']} px (cut by {clip.get('by', '?')})")
    return _verdict("label_cut", bad)


def _widening(dump):
    if not dump.get("wide"):
        return [("widening", None, "not wide")]
    scale = dump["scale"]
    return _verdict("widening", [f"{i['id']} width {_width(i, scale):.1f}, want {LARGE_W}"
                                 for i in _large_items(dump) if not _near(_width(i, scale), LARGE_W)])


def _tab_orders(app):
    """[[group id, ...] of every tab] of an app in the v3 data (read once)."""
    if app not in _TAB_ORDERS:
        with open(DATA, encoding="utf-8") as handle:
            data = json.load(handle)
        wanted = DATA_APPS.get(app, app)
        _TAB_ORDERS[app] = [[g["id"] for g in t["groups"]] for a in data["apps"] if a["id"] == wanted
                            for t in a["tabs"]]
    return _TAB_ORDERS[app]


def _order(dump, orders=None):
    """The groups stand left to right in the design's order (a group without a packing position showed first)."""
    shown = [g["id"] for g in sorted(dump["groups"], key=lambda g: g["rect"]["x"])]
    orders = _tab_orders(dump["app"]) if orders is None else orders
    tab = max(orders, key=lambda ids: len(set(ids) & set(shown)), default=[])
    if not set(tab) & set(shown):
        return [("order", None, "tab not in the data")]
    expected = [g for g in tab if g in shown]
    actual = [g for g in shown if g in tab]
    return _verdict("order", [] if actual == expected else [f"groups {actual}, want {expected}"])


_CHECKS = (_body, _band, _edge, _one_size, _equal_width, _lone_col, _cols_3plus1, _banner, _elastic, _captions,
           _clip, _label_cut, _widening, _order)


def dump_findings(dump):
    """[(rule, ok, detail)] of one layout dump: every rule of RULES, False per violation."""
    out = []
    for check in _CHECKS:
        out.extend(check(dump))
    return out


def dump_width(dump):
    """Logical window width of a dump: window.w / scale, rounded."""
    return round(dump["window"]["w"] / dump["scale"])


def dump_summary(dump):
    """Information of one dump: folded groups, the overflow button, the banner width, the used share of the track and
    the boxes drawing their native frame in less height than they ask for (native_cut, not a failure)."""
    scale = dump["scale"]
    banner = dump.get("banner")
    used = sum(g["rect"]["w"] for g in dump["groups"])
    track = dump.get("track_width")
    return {"app": dump["app"], "tab": dump["tab"], "width": dump_width(dump),
            "folded": sum(g.get("state") == "C" for g in dump["groups"]), "more": bool(dump.get("more")),
            "banner_w": round(banner["w"] / scale) if banner else None,
            "used_pct": round(100 * used / track, 1) if track else None,
            "native_cut": [f"{g['id']} {i['id']}" for g in dump["groups"] for i in _items(g) if i.get("native_cut")]}


def _stats(values):
    if not values:
        return None
    return {"min": round(min(values)), "median": round(statistics.median(values)), "max": round(max(values))}


def summarize(dumps):
    """Totals over dumps: failures per rule, banner min/median/max, used-share median, folded and overflow tabs."""
    rules = {name: 0 for name in RULES}
    banners, used, folded, more, native_cut = [], [], [], [], []
    for dump in dumps:
        rules_hit = [rule for rule, ok, _detail in dump_findings(dump) if ok is False]
        for rule in rules_hit:
            rules[rule] += 1
        info = dump_summary(dump)
        label = f"{info['app']} {info['tab']} @{info['width']}"
        if info["banner_w"] is not None:
            banners.append(info["banner_w"])
        if info["used_pct"] is not None:
            used.append(info["used_pct"])
        if info["folded"]:
            folded.append(label)
        if info["more"]:
            more.append(label)
        native_cut += [f"{label}: {box}" for box in info["native_cut"]]
    return {"dumps": len(dumps), "rules": rules, "banner": _stats(banners),
            "used_pct": {"min": min(used), "median": statistics.median(used)} if used else None,
            "folded": folded, "more": more, "native_cut": native_cut}
