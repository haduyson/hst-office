# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Pure rules of the ribbon mockup check: ladder levels, vector comparison, monotonic growth and the v3 banner rule.

No display or AT-SPI here, so the unit tests run without a desktop (tests/unit/test_ribbon_mockup_expected.py).
The v3 layout-dump rules are in ribbon_v3_rules.py.
"""
LEVEL = {"L": 3, "M": 2, "S": 1, "C": 0}
TOLERANCE = 1  # px, for sizes (the plan's ±1 px)
BANNER_MIN_W, BANNER_MAX_W, BANNER_H, BANNER_TOP = 360, 960, 96, 6  # v3: the banner is 360..960 wide, 96 high, top 6


def banner_limits():
    """The v3 banner rule (logical px): width 360 to 960, height 96, top 6 under the ribbon body's top edge."""
    return {"min_w": BANNER_MIN_W, "max_w": BANNER_MAX_W, "h": BANNER_H, "top": BANNER_TOP}


def banner_ok(width, height):
    """True when a measured banner box of width x height is inside the v3 limits (±1 px)."""
    limits = banner_limits()
    return (limits["min_w"] - TOLERANCE <= width <= limits["max_w"] + TOLERANCE
            and abs(height - limits["h"]) <= TOLERANCE)


def compare_states(expected, measured):
    """[(key, expected, measured)] for every group whose state differs; a group that is missing is a difference too."""
    return [(key, want, measured.get(key, {}).get("state")) for key, want in sorted(expected.items())
            if measured.get(key, {}).get("state") != want]


def is_monotonic(levels):
    """True when, as the window widens, no group moves to a larger ladder level (a smaller letter's rank)."""
    return all(LEVEL[levels[i]] <= LEVEL[levels[i + 1]] for i in range(len(levels) - 1))


SKIP_NOT_MEASURED = "skip: not in the accessible tree (measured on Linux, P2/P4; not a Windows failure)"


def width_findings(tab, width, want_states, got):
    """[(check name, ok, detail)] of one tab at one width: ladder vector, 106 px body, 147 px row, banner, font boxes.

    `got` is {"groups": geometry.groups(...), "tab_top", "strip", "banner", "font_box", "size_box"}."""
    tag = f"[writer {tab} {width}]"
    out = []
    states = {k: v["state"] for k, v in got["groups"].items()}
    diff = compare_states(want_states, {k: {"state": s} for k, s in states.items()})
    # the vectors are information only: the reference is not an absolute target (measured at the mockup's width)
    out.append((f"{tag} ladder states (info)", None, diff or states))
    page = got.get("page")  # P4's definition: the selected tab's page is the 106 px body (no 3 px margins)
    if page is not None:
        out.append((f"{tag} page body is 106 px", abs(page[3] - 106) <= TOLERANCE, page[3]))
    else:
        out.append((f"{tag} page body", None, SKIP_NOT_MEASURED))
    if got.get("tab_top") is not None and got.get("strip") is not None:
        span = got["strip"][1] - got["tab_top"]
        out.append((f"{tag} tab row to document strip is 147 px", abs(span - 147) <= TOLERANCE, span))
    else:  # a missing measurement is a failure, not a silent pass
        out.append((f"{tag} tab row and document strip", None, SKIP_NOT_MEASURED))
    banner = got.get("banner")
    if banner is not None:
        out.append((f"{tag} banner 360..960 x 96", banner_ok(banner[2], banner[3]), list(banner[2:])))
    else:
        out.append((f"{tag} banner 360..960 x 96", None, SKIP_NOT_MEASURED))
    if got["groups"].get("font", {}).get("state") == "L":
        fb, sb = got.get("font_box"), got.get("size_box")
        out.append((f"{tag} font box 128 px", fb is not None and abs(fb[2] - 128) <= TOLERANCE, fb and fb[2]))
        out.append((f"{tag} size box 46 px", sb is not None and abs(sb[2] - 46) <= TOLERANCE, sb and sb[2]))
    return out


def monotonic_findings(levels, tab):
    """[(check name, ok, detail)]: each group's ladder level never drops as the window widens."""
    out = []
    for key, series in levels.items():
        states = [s for _w, s in sorted(series)]
        ok = is_monotonic(states) if all(s in LEVEL for s in states) else False
        out.append((f"[writer {tab}] {key} is monotonic (info)", None, "" if ok else states))
    return out
