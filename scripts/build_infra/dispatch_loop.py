# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Dispatcher of the local build queue (scripts/build-queue.py): `build-queue.sh dispatch` (systemd unit
hst-build-queue.service, scripts/linux/hst-build-queue.service).

Every poll_seconds it reaps finished jobs, stops jobs whose cancel was requested, runs the build train step
(queue_train_tick.py: merge/push/submit trains, judge finished ones, start the next), starts queued jobs by
priority/FIFO on free slots, and applies output retention (after a job finished, else every RETENTION_SECONDS):
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

from . import data_disk, slot_control
from .dispatch_linux_pool import LinuxPool
from .dispatch_paths import log
from .dispatch_windows import WindowsRunner
from .queue_sign import SignError, sign_job, wants_signing

RETENTION_SECONDS = 600
_last_retention = [0.0]


# ---------------------------------------------------------------- loop
def run_retention(store, core, cfg):
    _last_retention[0] = time.time()
    freed = core.apply_retention(store, cfg)
    if freed:
        reasons = {}
        for _jid, reason, _size in freed:
            kind = reason.split(" of ")[0] if reason.startswith("older") else reason
            reasons[kind] = reasons.get(kind, 0) + 1
        log(f"retention: deleted {len(freed)} outputs, freed {sum(f[2] for f in freed) / 2**30:.2f} GiB "
            f"({', '.join(f'{n} {k}' for k, n in sorted(reasons.items()))})")


def requeue_if_infra(store, core, job, error):
    """Put a job that failed because of the infrastructure back in the queue (at most MAX_INFRA_RETRIES times)."""
    retries = job.get("infra_retries", 0)
    if job.get("cancel_requested"):
        return False
    tail = core.log_tail(job["log"], 80)
    wrong_slot = job.get("incomplete_slot_retries", 0)
    if core.INCOMPLETE_SLOT_RE.search(f"{error}\n{tail}") and wrong_slot < core.MAX_INCOMPLETE_SLOT_RETRIES:
        with open(job["log"], "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%F %T')}] slot {job.get('slot')} has no complete build for --modules: "
                    f"requeued, not counted against the job (retry {wrong_slot + 1}/"
                    f"{core.MAX_INCOMPLETE_SLOT_RETRIES})\n")
        store.update(job["id"], state="queued", incomplete_slot_retries=wrong_slot + 1, slot=None, pid=None,
                     cancel_sent=False, last_infra_error=error)
        log(f"{job['id']}: slot {job.get('slot')} has no complete build, requeued without charge")
        return True
    if retries >= core.MAX_INFRA_RETRIES:
        return False
    if not core.infra_failure(error, tail):
        return False
    with open(job["log"], "a", encoding="utf-8") as f:
        f.write(f"\n[{time.strftime('%F %T')}] infrastructure failure ({error}); requeued "
                f"(retry {retries + 1}/{core.MAX_INFRA_RETRIES})\n")
    store.update(job["id"], state="queued", infra_retries=retries + 1, last_infra_error=error,
                 slot=None, pid=None, cancel_sent=False)
    log(f"{job['id']}: infrastructure failure, requeued: {error}")
    return True


def sign_output(store, job, fields, cfg):
    """An integrator Linux release build: GPG-sign its .rpm/.AppImage (queue_sign.py); a failure fails the job."""
    def to_log(text):
        with open(job["log"], "a", encoding="utf-8") as f:
            f.write(text)
    to_log(f"\n[{time.strftime('%F %T')}] signing the Linux packages (dispatcher, packaging key)\n")
    try:
        output = sign_job(job, store.job_out(job["id"]), cfg, to_log, workroot=store.work_dir)
    except SignError as exc:
        to_log(f"[{time.strftime('%F %T')}] signing FAILED: {exc}\n")
        log(f"{job['id']}: signing failed: {exc}")
        return "failed", {"error": f"dispatcher: signing: {exc}"}
    to_log(f"[{time.strftime('%F %T')}] signed; rpm -K: digests signatures OK\n")
    log(f"{job['id']}: Linux packages signed")
    return "done", dict(fields, output=output, signed=True)


def kill_tree(store, runner, job):
    """A cancelled Linux job that still runs cancel_kill_after_seconds after the TERM: its make scopes (which the
    TERM to the runner does not reach) are killed; the runner then ends through its own cleanup."""
    try:
        killed = runner.kill_tree(job)
    except Exception as exc:  # noqa: BLE001 - retried next tick
        log(f"{job['id']}: killing the build's process tree failed: {exc}")
        return
    store.update(job["id"], cancel_killed=True)
    if killed:
        with open(job["log"], "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%F %T')}] dispatcher: still running after the cancel; make scopes of slot "
                    f"{job.get('slot')} killed\n")
        log(f"{job['id']}: still running after the cancel, make scopes of {job.get('slot')} killed")


def tick(store, runners, core):
    cfg = store.config()
    jobs = store.all()
    finished = False
    for job in [j for j in jobs if j["state"] == "running"]:
        runner = runners[job["platform"]]
        if job.get("cancel_requested") and not job.get("cancel_sent"):
            try:
                runner.cancel(job)
                store.update(job["id"], cancel_sent=True, cancel_sent_at=time.time())
                log(f"{job['id']}: cancel sent")
            except Exception as exc:  # noqa: BLE001 - a failed cancel is retried next tick, never fatal
                log(f"{job['id']}: cancel failed: {exc}")
        elif job.get("cancel_sent") and not job.get("cancel_killed") and hasattr(runner, "kill_tree") \
                and time.time() - job.get("cancel_sent_at", time.time()) >= cfg["cancel_kill_after_seconds"]:
            kill_tree(store, runner, job)
        try:
            result = runner.check(job)
        except Exception as exc:  # noqa: BLE001 - keep dispatching other jobs; this one is marked failed
            result = ("failed", {"error": f"dispatcher: {exc}"})
        if result:
            state, fields = result
            t = time.time()
            if state == "failed" and requeue_if_infra(store, core, job, fields.get("error", "")):
                continue
            if state == "done" and wants_signing(dict(job, **fields), cfg):
                state, fields = sign_output(store, job, fields, cfg)
            store.update(job["id"], state=state, finished=t, finished_at=core.now_iso(t), **fields)
            log(f"{job['id']}: {state} {fields}")
            finished = True
    try:
        from .queue_train_tick import tick as train_tick
        train_tick(store, core, cfg, log=log)
    except Exception as exc:  # noqa: BLE001 - the train must never stop the dispatching of other jobs
        log(f"train step failed: {exc!r}")
    try:
        data_disk.check(store, cfg, log)
    except Exception as exc:  # noqa: BLE001 - a disk check problem never stops the dispatching
        log(f"/data check failed: {exc!r}")
    jobs = store.all()
    try:
        slot_control.process(store, cfg, jobs, log)   # `build-queue.sh slot clean`: before slots are handed out
    except Exception as exc:  # noqa: BLE001 - slot maintenance problems are logged, dispatching goes on
        log(f"slot maintenance failed: {exc!r}")
    if hasattr(runners["linux"], "health"):
        runners["linux"].health(jobs)   # remote Linux hosts that stopped answering: offline, their jobs requeued
        jobs = store.all()
    if hasattr(runners["windows"], "enforce_windows"):
        runners["windows"].enforce_windows(jobs)   # jobs on slots whose time window closed: stopped, requeued
        jobs = store.all()
    if hasattr(runners["windows"], "process_drains"):
        runners["windows"].process_drains(jobs, core)
    blocked = set()
    for job in sorted([j for j in jobs if j["state"] == "queued"], key=core.order_key):
        platform = job["platform"]
        if platform in blocked:
            continue   # strict priority per platform: nothing overtakes a waiting higher-priority job
        runner = runners[platform]
        slot = runner.free_slot(jobs, runner.want(job), job) if platform == "linux" else runner.free_slot(jobs)
        if slot is None:
            if not job.get("modules"):
                # Strict priority per platform; a --modules job only waits for a slot with a complete build, so it
                # does not hold back a full build that can use (and seed) a slot without one.
                blocked.add(platform)
            continue
        with store.lock():
            current = store.load(job["id"])
            if current["state"] != "queued":
                continue
            # From here on a submit may no longer add tests to this job (queue_rules.test_merge_target), and the
            # runner gets the record as it is now, not the copy read at the start of the tick.
            current["starting"] = time.time()
            store.save(current)
            job = current
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
    if finished or time.time() - _last_retention[0] >= RETENTION_SECONDS:
        try:
            run_retention(store, core, cfg)
        except Exception as exc:  # noqa: BLE001 - retention problems are logged, dispatching goes on
            log(f"retention failed: {exc!r}")


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
    runners = {"linux": LinuxPool(store, cfg), "windows": WindowsRunner(store, cfg)}
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
