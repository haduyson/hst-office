# SPDX-License-Identifier: AGPL-3.0-only
"""Admission model of the Linux build slots: configuration, memory budget per -j and the water-filling
of jobs between slots (see slots_cli for the rules).
"""
import os

ROOT = os.environ.get("HST_BUILD_ROOT", "/data/hst-build")
GIB = 1024 ** 3


def env_int(name, default):
    value = os.environ.get(name, "")
    if not value:
        return default
    if not value.isdigit():
        raise SystemExit(f"build-slots: {name} must be a non-negative integer, got {value!r}")
    return int(value)


class Config:
    def __init__(self):
        self.total_jobs = env_int("HST_TOTAL_JOBS", 28)
        self.max_jobs = env_int("HST_MAX_JOBS", 20)
        self.min_jobs = env_int("HST_MIN_JOBS", 4)
        self.headroom_gib = env_int("HST_HEADROOM_GIB", 8)
        self.min_free_gib = env_int("HST_MIN_FREE_GIB", 15)
        self.min_mem_gib = env_int("HST_MIN_MEM_GIB", 6)
        self.swap_grow_gib = env_int("HST_SWAP_GROW_GIB", 1)


def budget_gib(jobs):
    """Scope MemoryMax for a make with this many jobs (clang ~0.4 GiB/job + one heavy link)."""
    return round(min(12.0, max(6.0, 4.0 + 0.4 * jobs)), 1)


def waterfill(wants, total, max_jobs, min_jobs):
    """Share `total` jobs among slots (dict slot -> wanted jobs, in admission order).

    Each slot gets at most min(want, max_jobs); when the caps exceed `total`, the smallest requests are
    satisfied first and the rest share equally (earlier admissions get the remainder). Never below min_jobs."""
    caps = {s: max(min_jobs, min(w, max_jobs)) for s, w in wants.items()}
    alloc = {}
    remaining = dict(caps)
    budget = total
    while remaining:
        share = budget // len(remaining)
        small = {s: c for s, c in remaining.items() if c <= share}
        if not small:
            order = list(remaining)
            extra = budget - share * len(order)
            for i, s in enumerate(order):
                alloc[s] = share + (1 if i < extra else 0)
            break
        for s, c in small.items():
            alloc[s] = c
            budget -= c
            del remaining[s]
    return {s: max(min_jobs, alloc[s]) for s in wants}
