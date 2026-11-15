# SPDX-License-Identifier: AGPL-3.0-only
"""Pure rules of the ribbon mockup check: ladder levels, vector comparison, monotonic growth and the banner size rule.

No display or AT-SPI here, so the unit tests run without a desktop (tests/unit/test_ribbon_mockup_expected.py).
"""
LEVEL = {"L": 3, "M": 2, "S": 1, "C": 0}


def expected_banner(width):
    """The mockup's banner rule (expected JSON, "banner"): width 260 up to 1440, then growing to 360 at 1920; height w * 104/360."""
    w = 260 if width <= 1440 else min(360, 260 + (width - 1440) * 100 / 480)
    w = round(w)
    return w, round(w * 104 / 360)


def compare_states(expected, measured):
    """[(key, expected, measured)] for every group whose state differs; a group that is missing is a difference too."""
    return [(key, want, measured.get(key, {}).get("state")) for key, want in sorted(expected.items())
            if measured.get(key, {}).get("state") != want]


def is_monotonic(levels):
    """True when, as the window widens, no group moves to a larger ladder level (a smaller letter's rank)."""
    return all(LEVEL[levels[i]] <= LEVEL[levels[i + 1]] for i in range(len(levels) - 1))


TOLERANCE = 1  # px, for sizes (the plan's ±1 px)


def width_findings(tab, width, want_states, got):
    """[(check name, ok, detail)] of one tab at one width: ladder vector, 106 px body, 147 px row, banner, font boxes.

    `got` is {"groups": geometry.groups(...), "tab_top", "strip", "banner", "font_box", "size_box"}."""
    tag = f"[writer {tab} {width}]"
    out = []
    states = {k: v["state"] for k, v in got["groups"].items()}
    diff = compare_states(want_states, {k: {"state": s} for k, s in states.items()})
    out.append((f"{tag} ladder states equal the mockup vector", not diff, diff or states))
    page = got.get("page")  # P4's definition: the selected tab's page is the 106 px body (no 3 px margins)
    if page is not None:
        out.append((f"{tag} page body is 106 px", abs(page[3] - 106) <= TOLERANCE, page[3]))
    else:
        out.append((f"{tag} page body measured", False, "no page panel under the tab row"))
    if got.get("tab_top") is not None and got.get("strip") is not None:
        span = got["strip"][1] - got["tab_top"]
        out.append((f"{tag} tab row to document strip is 147 px", abs(span - 147) <= TOLERANCE, span))
    else:  # a missing measurement is a failure, not a silent pass
        out.append((f"{tag} tab row and document strip measured", False, "not in the accessible tree"))
    ew, eh = expected_banner(width)
    banner = got.get("banner")
    if banner is not None:
        out.append((f"{tag} banner {ew}x{eh}",
                    abs(banner[2] - ew) <= TOLERANCE and abs(banner[3] - eh) <= TOLERANCE, list(banner[2:])))
    else:
        out.append((f"{tag} banner {ew}x{eh} measured", False, "not in the accessible tree"))
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
        out.append((f"[writer {tab}] {key} is monotonic from 1100 to 1920", ok, "" if ok else states))
    return out
