# SPDX-License-Identifier: AGPL-3.0-only
"""Build queue read-side: job summaries, test results, baseline comparison and `wait`.
"""
import os
import sys
import time

from .queue_store import TERMINAL

def log_tail(path, lines=40):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except FileNotFoundError:
        return "(no log yet)"


def describe(job):
    where = job.get("slot") or "-"
    parts = [f"{job['id']}  {job['state']:<9} {job['platform']:<7} {job['label']}@{job['sha'][:10]}",
             f"prio {job['priority']}", f"slot {where}"]
    if job.get("modules"):
        parts.append("modules " + ",".join(job["modules"]))
    if job.get("tests"):
        res = job.get("test_results") or {}
        failed = sum(1 for r in res.values() if r["result"] != "pass")
        parts.append(f"tests {len(job['tests'])}" + (f" ({len(res) - failed} pass, {failed} fail)" if res else ""))
    elif not job.get("package", True) and not job.get("modules"):
        parts.append("no-package")
    return "  ".join(parts)


def print_tests(store, job, out):
    """PASS/FAIL per test target with its log; returns the number of failures."""
    res = job.get("test_results") or {}
    failed = 0
    base = store.job_out(job["id"])
    for target in job.get("tests", []):
        r = res.get(target)
        if r is None:
            print(f"MISSING {target} (no result recorded)", file=out)
            failed += 1
            continue
        ok = r["result"] == "pass"
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'} {target} ({r['seconds']} s) {os.path.join(base, r['log'])}", file=out)
    for target in job.get("tests", []):
        r = res.get(target)
        if r and r["result"] != "pass":
            print(f"--- tail of {target}", file=out)
            print(log_tail(os.path.join(base, r["log"]), 25), file=out, end="")
    return failed


def compare(store, base_id, job_id, out=sys.stdout):
    """Per-target results of two test jobs (baseline first); exit 3 when a test passes on the base but not the job."""
    a, b = store.load(base_id), store.load(job_id)
    ra, rb = a.get("test_results") or {}, b.get("test_results") or {}
    targets = list(dict.fromkeys(list(a.get("tests", [])) + list(b.get("tests", []))))
    print(f"{'target':<45} {a['label'] + '@' + a['sha'][:8]:<28} {b['label'] + '@' + b['sha'][:8]}", file=out)
    regressions = 0
    for t in targets:
        x = ra.get(t, {}).get("result", "-")
        y = rb.get(t, {}).get("result", "-")
        mark = "  REGRESSION" if x == "pass" and y != "pass" else "  fixed" if x == "fail" and y == "pass" else ""
        regressions += bool(mark.strip() == "REGRESSION")
        print(f"{t:<45} {x:<28} {y}{mark}", file=out)
    return 3 if regressions else 0


def wait(store, job_id, timeout=None, interval=15, out=sys.stdout):
    start = time.time()
    while True:
        job = store.load(job_id)
        if job["state"] in TERMINAL:
            break
        if timeout is not None and time.time() - start > timeout:
            print(f"timeout: job {job_id} still {job['state']}", file=out)
            return 2
        time.sleep(interval)
    if job["state"] == "done":
        for path in job.get("output", []):
            print(path, file=out)
        if job.get("tests"):
            return 3 if print_tests(store, job, out) else 0
        return 0
    print(f"job {job_id} {job['state']}: {job.get('error', '')}", file=out)
    print(log_tail(job["log"]), file=out, end="")
    return 1
