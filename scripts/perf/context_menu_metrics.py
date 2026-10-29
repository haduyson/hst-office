# SPDX-License-Identifier: AGPL-3.0-only
"""Pure analysis helpers for context-menu latency runs (no I/O side effects).

Run files are JSON documents written by run-context-menu.py:
  {"schema": 1, "cell": {"id": ..., "start": "cold"|"warm", ...},
   "trials": [{"i": 1, "ms": 123.4, "timeout": false}, ...], ...}
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

DEFAULT_TARGETS = {"warm_p95_ms": 150.0, "cold_p95_ms": 400.0}


def percentile(values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile (ceil(p/100*n)); None for empty input."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def summarize_trials(trials: list[dict]) -> dict:
    """Median/p90/p95/max over successful trials plus timeout accounting."""
    ok = [float(t["ms"]) for t in trials if t.get("ms") is not None and not t.get("timeout")]
    timeouts = sum(1 for t in trials if t.get("timeout") or t.get("ms") is None)
    return {
        "n": len(trials),
        "ok": len(ok),
        "timeouts": timeouts,
        "median_ms": median(ok),
        "p90_ms": percentile(ok, 90),
        "p95_ms": percentile(ok, 95),
        "max_ms": max(ok) if ok else None,
    }


def load_runs(directory: Path) -> dict[str, dict]:
    """Load every *.json run file in a directory, keyed by cell id."""
    runs: dict[str, dict] = {}
    if not directory.is_dir():
        raise FileNotFoundError(f"run directory missing: {directory}")
    for path in sorted(directory.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or "cell" not in doc or "trials" not in doc:
            continue  # summary or manifest files share the directory
        runs[doc["cell"]["id"]] = doc
    return runs


def check_targets(cell: dict, summary: dict, targets: dict) -> list[str]:
    """Absolute-target violations for one cell (provisional product targets)."""
    problems = []
    if summary["timeouts"]:
        problems.append(f"{summary['timeouts']} timeout(s)/missing menu")
    key = "cold_p95_ms" if cell.get("start") == "cold" else "warm_p95_ms"
    limit = targets.get(key)
    p95 = summary["p95_ms"]
    if limit is not None and p95 is not None and p95 > limit:
        problems.append(f"p95 {p95:.1f} ms > {limit:.0f} ms")
    return problems


def regression(base: dict, cand: dict, percent: float, floor_ms: float) -> bool:
    """Regression only if the candidate is worse by BOTH percent and floor_ms (p95)."""
    b, c = base["p95_ms"], cand["p95_ms"]
    if b is None or c is None:
        return c is None and b is not None
    delta = c - b
    return delta > floor_ms and delta > b * percent / 100.0


def compare_runs(baseline: dict[str, dict], candidate: dict[str, dict], targets: dict,
                 percent: float, floor_ms: float) -> dict:
    """Per-cell comparison; baseline cells absent from candidate (and vice versa) are failures."""
    if not baseline:
        raise ValueError("baseline has no runs: capture it first with the same runner")
    rows, failures = [], []
    for cell_id in sorted(set(baseline) | set(candidate)):
        if cell_id not in baseline or cell_id not in candidate:
            side = "candidate" if cell_id not in candidate else "baseline"
            failures.append(f"{cell_id}: missing in {side}")
            continue
        cell = candidate[cell_id]["cell"]
        bsum = summarize_trials(baseline[cell_id]["trials"])
        csum = summarize_trials(candidate[cell_id]["trials"])
        problems = check_targets(cell, csum, targets)
        if regression(bsum, csum, percent, floor_ms):
            problems.append("regression vs baseline (p95 beyond percent and floor)")
        rows.append({"cell": cell_id, "baseline": bsum, "candidate": csum, "problems": problems})
        failures.extend(f"{cell_id}: {p}" for p in problems)
    return {"rows": rows, "failures": failures, "passed": not failures}


_STACK_LINE = re.compile(r"^[\s+!:|]*(\d+)\s+(.+?)\s+\(in ([^)]+)\)")
_TOP_LINE = re.compile(r"^\s+(\S.*?)\s+\(in ([^)]+)\)\s+(\d+)\s*$")


def parse_sample_top(text: str, limit: int = 15) -> list[dict]:
    """Top frames from macOS `sample` output.

    Prefers the 'Sort by top of stack' section (self samples). Falls back to the
    call graph, aggregating the largest inclusive count per symbol.
    """
    frames: list[dict] = []
    in_top = False
    for line in text.splitlines():
        if line.startswith("Sort by top of stack"):
            in_top = True
            continue
        if in_top:
            m = _TOP_LINE.match(line)
            if m:
                frames.append({"symbol": m.group(1), "image": m.group(2), "samples": int(m.group(3))})
            elif line.strip() == "" and frames:
                break
    if frames:
        return sorted(frames, key=lambda f: -f["samples"])[:limit]
    best: dict[tuple[str, str], int] = {}
    for line in text.splitlines():
        m = _STACK_LINE.match(line)
        if m:
            key = (m.group(2), m.group(3))
            best[key] = max(best.get(key, 0), int(m.group(1)))
    ranked = sorted(best.items(), key=lambda kv: -kv[1])[:limit]
    return [{"symbol": k[0], "image": k[1], "samples": v, "inclusive": True} for k, v in ranked]


SUSPECT_SYMBOLS = (
    "CreateNSImage", "lockFocus", "createCGImage", "MenuBarManager::Activate",
    "GetImageForCommand", "ShowNativePopupMenu", "performClickWithFrame",
    "initWindowAndView", "MenuFloatingWindow", "CreateFromSystemClipboard",
    "AquaClipboard", "NSPasteboard", "ExecSpellPopup", "AutoSpell_", "NSSpellChecker",
    "CreateActionTriggerContainerFromMenu", "ImplCalcSize", "NSAccessibility",
)


def flag_suspects(frames: list[dict]) -> list[str]:
    """Names from SUSPECT_SYMBOLS that occur in any parsed frame symbol."""
    joined = " ".join(f["symbol"] for f in frames)
    return [s for s in SUSPECT_SYMBOLS if s in joined]
