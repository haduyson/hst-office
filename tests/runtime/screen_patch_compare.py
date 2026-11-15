# SPDX-License-Identifier: AGPL-3.0-only
"""Platform-neutral comparison of screen patch grabs for the tab switch flash checks (Windows and Linux).

A grab is `count` patches of size x size BGRA pixels laid out side by side (rows of size*count pixels), as
screen_patches_win.Patches and screen_patches_x11.Patches produce them; `patches` is such an object (size, count,
patch(data, n)).
"""
NEAR = 12  # mean per-channel difference below which two patches show the same picture


def near(a, b):
    """Mean absolute difference per channel (alpha ignored) below NEAR."""
    total = sum(abs(a[i] - b[i]) + abs(a[i + 1] - b[i + 1]) + abs(a[i + 2] - b[i + 2]) for i in range(0, len(a), 4))
    return total / (3 * len(a) / 4) < NEAR


def mean_colour(data):
    n = len(data) // 4
    return tuple(sum(data[i + c] for i in range(0, len(data), 4)) // n for c in (2, 1, 0))  # RGB


def describe(patches, frame, before, after):
    """Patches of `frame` that show neither the before nor the after picture: [(n, rgb, before rgb, after rgb)]."""
    out = []
    for n in range(patches.count):
        p, b, a = patches.patch(frame, n), patches.patch(before, n), patches.patch(after, n)
        if not (near(p, b) or near(p, a)):
            out.append((n, mean_colour(p), mean_colour(b), mean_colour(a)))
    return out


def classify(patches, frame, before, after, desktop):
    """'desktop': some patch shows the desktop where neither the screen before nor after the switch does;
    'partial': two or more patches show neither the before, the after nor the desktop picture (a blank or half
    painted window; one such patch alone is animated content, e.g. the ribbon banner); '' otherwise."""
    odd = 0
    for n in range(patches.count):
        p, b, a = patches.patch(frame, n), patches.patch(before, n), patches.patch(after, n)
        if near(p, b) or near(p, a):
            continue
        if near(p, patches.patch(desktop, n)):
            return "desktop"
        odd += 1
    return "partial" if odd >= 2 else ""
