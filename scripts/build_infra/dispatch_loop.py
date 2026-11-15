# SPDX-License-Identifier: AGPL-3.0-only
"""Dispatcher of the local build queue (scripts/build-queue.py): `build-queue.sh dispatch` (systemd unit
hst-build-queue.service, scripts/linux/hst-build-queue.service).

Every poll_seconds it reaps finished jobs, stops jobs whose cancel was requested, starts queued jobs by
priority/FIFO on free slots, and applies output retention:
  - linux:   scripts/linux/local-build.sh --slot N on a slot that build-slots.py free-slot reports idle and
             admissible (the admission controller still decides -j and may hold the job until memory allows);
  - windows: the config's windows_slots pool (host + root). The tools are deployed to each host
             (D:\\hst-build\\tools\\scripts) when they change, the build runs as a scheduled task through
             scripts/windows/hst-queue-remote.ps1 + hst4-detach.ps1, and the MSI (or overlay) is pulled back into
             out/<id>/ and removed from the host. Slots whose build.lock is held by someone else are skipped.
Only one dispatcher runs at a time (flock on dispatcher.lock).

"""
import fcntl
import os
import sys
import time

from .dispatch_linux import LinuxRunner
from .dispatch_paths import log
from .dispatch_windows import WindowsRunner

# ---------------------------------------------------------------- loop
def requeue_if_infra(store, core, job, error):
    """Put a job that failed because of the infrastructure back in the queue (at most MAX_INFRA_RETRIES times)."""
    retries = job.get("infra_retries", 0)
    if job.get("cancel_requested") or retries >= core.MAX_INFRA_RETRIES:
        return False
    if not core.infra_failure(error, core.log_tail(job["log"], 80)):
        return False
    with open(job["log"], "a", encoding="utf-8") as f:
        f.write(f"\n[{time.strftime('%F %T')}] infrastructure failure ({error}); requeued "
                f"(retry {retries + 1}/{core.MAX_INFRA_RETRIES})\n")
    store.update(job["id"], state="queued", infra_retries=retries + 1, last_infra_error=error,
                 slot=None, pid=None, cancel_sent=False)
    log(f"{job['id']}: infrastructure failure, requeued: {error}")
    return True


def tick(store, runners, core):
    cfg = store.config()
    jobs = store.all()
    finished = False
    for job in [j for j in jobs if j["state"] == "running"]:
        runner = runners[job["platform"]]
        if job.get("cancel_requested") and not job.get("cancel_sent"):
            try:
                runner.cancel(job)
                store.update(job["id"], cancel_sent=True)
                log(f"{job['id']}: cancel sent")
            except Exception as exc:  # noqa: BLE001 - a failed cancel is retried next tick, never fatal
                log(f"{job['id']}: cancel failed: {exc}")
        try:
            result = runner.check(job)
        except Exception as exc:  # noqa: BLE001 - keep dispatching other jobs; this one is marked failed
            result = ("failed", {"error": f"dispatcher: {exc}"})
        if result:
            state, fields = result
            t = time.time()
            if state == "failed" and requeue_if_infra(store, core, job, fields.get("error", "")):
                continue
            store.update(job["id"], state=state, finished=t, finished_at=core.now_iso(t), **fields)
            log(f"{job['id']}: {state} {fields}")
            finished = True
    jobs = store.all()
    if hasattr(runners["windows"], "process_drains"):
        runners["windows"].process_drains(jobs, core)
    blocked = set()
    for job in sorted([j for j in jobs if j["state"] == "queued"], key=core.order_key):
        platform = job["platform"]
        if platform in blocked:
            continue   # strict priority per platform: nothing overtakes a waiting higher-priority job
        runner = runners[platform]
        slot = runner.free_slot(jobs, runner.want(job)) if platform == "linux" else runner.free_slot(jobs)
        if slot is None:
            blocked.add(platform)
            continue
        with store.lock():
            current = store.load(job["id"])
            if current["state"] != "queued":
                continue
        try:
            fields = runner.start(job, slot)
        except Exception as exc:  # noqa: BLE001 - a job that cannot start fails visibly instead of looping
            log(f"{job['id']}: start failed: {exc}")
            if not requeue_if_infra(store, core, job, f"start: {exc}"):
                t = time.time()
                store.update(job["id"], state="failed", finished=t, finished_at=core.now_iso(t), error=f"start: {exc}")
            continue
        t = time.time()
        job = store.update(job["id"], state="running", started=t, started_at=core.now_iso(t), **fields)
        log(f"{job['id']}: started {platform} {job['label']}@{job['sha'][:10]} on {fields['slot']}")
        jobs = store.all()
    if finished:
        core.apply_retention(store, cfg["retention_per_branch"])


def run(store, once=False):
    from . import queue_core as core
    store.ensure()
    lock = open(os.path.join(store.root, "dispatcher.lock"), "a+", encoding="ascii")  # noqa: SIM115 - held for life
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("build-queue: another dispatcher is running", file=sys.stderr)
        return 1
    cfg = store.config()
    runners = {"linux": LinuxRunner(store, cfg), "windows": WindowsRunner(store, cfg)}
    log(f"dispatcher started (queue {store.root}, windows slots "
        f"{[s['host'] + ':' + s['root'] for s in cfg['windows_slots']]})")
    while True:
        try:
            cfg = store.config()
            for r in runners.values():
                r.cfg = cfg
            tick(store, runners, core)
        except Exception as exc:  # noqa: BLE001 - the service must survive one bad tick; systemd restarts on exit
            log(f"tick failed: {exc!r}")
        if once:
            return 0
        time.sleep(cfg["poll_seconds"])
