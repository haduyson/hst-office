# SPDX-License-Identifier: AGPL-3.0-only
"""Build queue commands that change job or host state: submit, cancel, invalidate, drain, retention.
"""
import os
import shutil
import sys
import time

from .queue_rules import find_duplicate, job_key, label_for, new_id, resolve_ref, retention_victims
from .queue_store import PLATFORMS, QueueError, now_iso

# ---------------------------------------------------------------- commands
def submit(store, platform, ref, priority=0, package=True, modules=(), resolver=resolve_ref, submitter=None, tests=()):
    if platform not in PLATFORMS:
        raise QueueError(f"--platform must be one of {', '.join(PLATFORMS)}")
    if not -100 <= priority <= 100:
        raise QueueError("--priority must be between -100 and 100")
    modules = list(modules)
    if platform == "windows" and not package and not modules:
        raise QueueError("Windows make always builds the MSI; omit --no-package")
    tests = list(tests)
    if tests and platform != "linux":
        raise QueueError("--test runs on Linux slots only")
    if modules or tests:
        package = False
    sha = resolver(ref)
    key = job_key(platform, sha, package, modules, tests)
    with store.lock():
        dup = find_duplicate(store.all(), key)
        if dup:
            return dup, True
        t = time.time()
        job = {"id": new_id(t), "platform": platform, "ref": ref, "sha": sha, "label": label_for(ref, sha),
               "priority": priority, "package": package, "modules": modules, "tests": tests, "key": key,
               "state": "queued",
               "submitted": t, "submitted_at": now_iso(t), "submitter": submitter or os.environ.get("SUDO_USER")
               or os.environ.get("USER", "?"), "output": []}
        job["log"] = store.log_path(job["id"])
        store.save(job)
        return job, False


def cancel(store, job_id):
    with store.lock():
        job = store.load(job_id)
        if job["state"] == "queued":
            job.update(state="cancelled", finished=time.time(), error="cancelled before start")
        elif job["state"] == "running":
            job["cancel_requested"] = True
        else:
            raise QueueError(f"job {job_id} already {job['state']}")
        store.save(job)
        return job


def invalidate(store, job_id, reason):
    if not reason.strip():
        raise QueueError("--reason is required")
    with store.lock():
        job = store.load(job_id)
        if job["state"] != "done":
            raise QueueError(f"job {job_id} is {job['state']}, only done jobs can be invalidated")
        job.update(state="failed", error=f"invalidated: {reason.strip()}", invalidated_at=now_iso())
        store.save(job)
        return job


def drain(store, host, wait_done=True, interval=15, timeout=None, out=sys.stdout, cancel=False, hold=False):
    hosts = {s["host"] for s in store.config()["windows_slots"]}
    if host not in hosts:
        raise QueueError(f"unknown Windows host {host!r}; known: {', '.join(sorted(hosts))}")
    t = time.time()
    if cancel:
        if store.drains().get(host, {}).get("state") not in ("draining", "held"):
            raise QueueError(f"{host} is not draining or held")
        store.set_drain(host, state="cancelled", finished=t, finished_at=now_iso(t))
        print(f"{host}: drain cancelled; scheduling resumed (tools update when the host is next idle)", file=out)
        return 0
    store.set_drain(host, state="draining", hold=hold, requested=t, requested_at=now_iso(t), finished_at=None, tools=None)
    print(f"{host}: draining (no new jobs; tools are deployed when its builds end"
          f"{'; then held until `drain ' + host + ' --cancel`' if hold else ''})", file=out)
    if not wait_done:
        return 0
    while store.drains().get(host, {}).get("state") == "draining":
        if timeout is not None and time.time() - t > timeout:
            print(f"timeout: {host} still draining", file=out)
            return 2
        time.sleep(interval)
    info = store.drains()[host]
    held = info.get("state") == "held"
    print(f"{host}: tools {info.get('tools')} deployed at {info.get('finished_at')}; "
          f"{'held: idle, no new jobs until `drain ' + host + ' --cancel`' if held else 'scheduling resumed'}", file=out)
    return 0


def apply_retention(store, keep):
    with store.lock():
        jobs = store.all()
        for job in retention_victims(jobs, keep):
            shutil.rmtree(store.job_out(job["id"]), ignore_errors=True)
            job["output_deleted"] = True
            store.save(job)
