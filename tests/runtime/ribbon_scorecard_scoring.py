# SPDX-License-Identifier: AGPL-3.0-only
"""Pure scoring of the ribbon scorecard (ribbon_scorecard.py): structure, scaling, painting and gallery scores from
saved observations and the offline parity report. No office and no display."""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
APPS = ("writer", "calc", "impress")
PROBES = ("hover_fill", "pressed", "checked", "focus_ring", "group_separator", "centred_caption", "tab_underline",
          "paste_32", "launcher_glyph", "collapsed_group_button")
GALLERY = ("rendered_previews", "four_columns", "column_shrink", "more_popup", "keyboard_apply")
NAMES = {"D1": "Command parity", "D2": "Tab and group structure", "D3": "Scaling", "D4": "Dialog launchers",
         "D5": "Painting", "D6": "Galleries"}



def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parity = _load("check_office_parity", os.path.join(ROOT, "scripts", "ribbon", "check-office-parity.py"))


def lcs(first, second):
    """Length of the longest common subsequence."""
    previous = [0] * (len(second) + 1)
    for a in first:
        current = [0]
        for index, b in enumerate(second):
            current.append(previous[index] + 1 if a == b else max(previous[index + 1], current[index]))
        previous = current
    return previous[-1]


def dedupe(sequence):
    """Drop consecutive repeats (several Office groups can map onto one HST group)."""
    return [item for index, item in enumerate(sequence) if index == 0 or item != sequence[index - 1]]


def ratio(passed, total):
    return round(passed / total, 4) if total else 0.0


def score_structure(spec_app, pages, live_tabs):
    """D2: (score, detail). Tabs: the Office order against the live tab strip; contextual tabs: a page exists; groups:
    the Office group order against the captions of the matching HST page."""
    by_label = parity.page_by_label(pages)
    main = [t["hst_tab"] for t in spec_app["tabs"] if not t["contextual"] and not t.get("merged") and t.get("hst_tab")]
    tab_hits = lcs(main, live_tabs)
    # contextual tabs, and tabs merged into another by an owner decision, count by existence only
    contextual = [t for t in spec_app["tabs"] if t["contextual"] or t.get("merged")]
    ctx_hits = sum(1 for t in contextual if t.get("hst_tab") in by_label)
    group_hits = group_total = 0
    missing_groups = []
    for tab in spec_app["tabs"]:
        wanted = dedupe([g["hst_group"] for g in tab["groups"] if g.get("hst_group")])
        page = by_label.get(tab.get("hst_tab") or "")
        have = [g["caption"] for g in page["groups"]] if page else []
        hits = lcs(wanted, have)
        group_hits += hits
        group_total += len(wanted)
        missing_groups += [f"{tab['hst_tab']} / {g}" for g in wanted if g not in have]
    total = len(main) + len(contextual) + group_total
    detail = {"tabs": [tab_hits, len(main)], "contextual": [ctx_hits, len(contextual)], "groups": [group_hits, group_total],
              "missing_tabs": [t for t in main if t not in live_tabs] + [t["hst_tab"] for t in contextual
                                                                          if t.get("hst_tab") not in by_label],
              "missing_groups": missing_groups}
    return ratio(tab_hits + ctx_hits + group_hits, total), detail


def scaling_checks(page_obs, expected, config, app):
    """D3 checks of one tab: [(width, check, ok, detail)] for the widths widest first."""
    conf, banner = config["apps"][app], config["banner"]
    rows, previous = [], None
    for width in sorted(config["widths"], reverse=True):
        obs = page_obs.get(str(width))
        if obs is None:
            rows += [(width, check, False, "not measured") for check in "abcd"]
            continue
        shown = {g["caption"]: g["box"] for g in obs["groups"]}
        chevron = obs.get("chevron") is not None
        rows.append((width, "a", not chevron or not shown, sorted(shown) if chevron else ""))
        grown = []
        if previous is not None:
            for caption, box in shown.items():
                before = previous.get(caption)
                if before is None or box[2] > before[2] + 2:
                    grown.append(caption)
        rows.append((width, "b", not grown, grown))
        limit = width
        if obs.get("banner"):
            limit = min(limit, obs["banner"][0])
        clipped = [c for c, b in shown.items() if b[0] + b[2] > limit]
        unreachable = [c for c in expected if c not in shown and c not in obs.get("group_buttons", []) and not chevron]
        rows.append((width, "c", not clipped and not unreachable, {"clipped": clipped, "unreachable": unreachable}))
        bx = obs.get("banner")
        if width >= config["compact_below"]:
            want = [width - banner["right_gap"], conf["banner_y"], banner["width"], conf["banner_height"]]
            slot = bx == want
        else:
            want = "inside the window, right of the groups"
            right = max((b[0] + b[2] for b in shown.values()), default=0)
            slot = bx is not None and bx[0] + bx[2] <= width and bx[0] >= right
        ok = slot and obs.get("height") == conf["ribbon_height"]
        rows.append((width, "d", ok, {"banner": bx, "want": want, "height": obs.get("height")}))
        previous = shown
    return rows


def score_scaling(observation, pages, config, app):
    by_label = parity.page_by_label(pages)
    rows = []
    for tab, page_obs in sorted((observation.get("pages") or {}).items()):
        if "error" in page_obs:
            rows += [(tab, 0, c, False, page_obs["error"]) for c in "abcd"]
            continue
        page = by_label.get(tab)
        widest = page_obs.get(str(max(config["widths"])), {"groups": []})
        expected = [g["caption"] for g in page["groups"]] if page else [g["caption"] for g in widest["groups"]]
        rows += [(tab, *row) for row in scaling_checks(page_obs, expected, config, app)]
    passed = sum(1 for r in rows if r[3])
    return ratio(passed, len(rows)), rows


def score_probes(observations):
    """D5: passed probes / (10 per mode measured or expected)."""
    rows = []
    for mode in ("light", "dark"):
        probes = (observations.get(mode) or {}).get("probes") or {}
        rows += [(mode, name, bool(probes.get(name, {}).get("pass")), probes.get(name, {}).get("detail", "not measured"))
                 for name in PROBES]
    return ratio(sum(1 for r in rows if r[2]), len(rows)), rows


def score_galleries(per_app):
    """D6 over all apps: the five Writer gallery checks plus a large Paste in each app."""
    gallery = ((per_app.get("writer") or {}).get("light") or {}).get("gallery") or {}
    rows = [(name, bool(gallery.get(name, {}).get("pass")), gallery.get(name, {}).get("detail", "not measured"))
            for name in GALLERY]
    for app in APPS:
        probe = (((per_app.get(app) or {}).get("light") or {}).get("probes") or {}).get("paste_32", {})
        rows.append((f"paste_32 {app}", bool(probe.get("pass")), probe.get("detail", "not measured")))
    return ratio(sum(1 for r in rows if r[1]), len(rows)), rows


def score(per_app, parity_report, pages_by_app, spec, config, apps=APPS):
    """The whole scorecard from observations ({app: {mode: observation}}) and the offline parity report."""
    dims = {d: {} for d in ("D1", "D2", "D3", "D4", "D5")}
    details = {}
    for app in apps:
        obs = per_app.get(app) or {}
        light = obs.get("light") or {}
        dims["D1"][app] = parity_report[app]["d1"]
        dims["D4"][app] = parity_report[app]["d4"]
        dims["D2"][app], d2 = score_structure(spec["apps"][app], pages_by_app[app], light.get("tabs") or [])
        dims["D3"][app], d3 = score_scaling(light, pages_by_app[app], config, app)
        dims["D5"][app], d5 = score_probes(obs)
        details[app] = {"D2": d2, "D3_failed": [r for r in d3 if not r[3]], "D3_checks": len(d3),
                        "D5": d5, "errors": [e for m in obs.values() for e in m.get("errors", [])],
                        "parity_counts": parity_report[app]["counts"], "raw_coverage": parity_report[app]["raw_coverage"],
                        "launchers": [parity_report[app]["launchers_present"], parity_report[app]["launchers_feasible"]]}
    d6, d6_rows = score_galleries(per_app)
    means = {d: round(sum(v.values()) / len(v), 4) if v else 0.0 for d, v in dims.items()}
    means["D6"] = d6
    weights, floors = config["weights"], config["floors"]
    total = round(sum(weights[d] * means[d] for d in weights), 4)
    return {"total": total, "dimensions": means, "per_app": dims, "floors": floors, "weights": weights,
            "below_floor": [d for d in weights if means[d] < floors[d]], "details": details, "D6": d6_rows}

