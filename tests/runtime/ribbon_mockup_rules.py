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
