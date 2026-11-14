# SPDX-License-Identifier: AGPL-3.0-only
"""Output retention of the build queue (rules: queue_rules.retention_victims) and pins that exempt a job from it.
"""
import os
import shutil
import time

from .queue_git import Git
from .queue_rules import retention_victims
from .queue_store import ID_RE, QueueError, now_iso
from .queue_train_store import TrainStore


def pin(store, job_id, reason=None):
    """Keep a job's output out of retention (reason given) or release it again (reason None)."""
    with store.lock():
        job = store.load(job_id)
        if reason is not None:
            if job["state"] != "done" or job.get("output_deleted"):
                raise QueueError(f"job {job_id} has no output to pin ({job['state']})")
            if not reason.strip():
                raise QueueError("--reason is required")
            job.update(pinned=reason.strip(), pinned_at=now_iso())
        else:
            job.pop("pinned", None)
            job.pop("pinned_at", None)
        store.save(job)
        return job


def dir_size(path):
    total = 0
    for folder, _dirs, names in os.walk(path):
        for name in names:
            try:
                total += os.lstat(os.path.join(folder, name)).st_size
            except OSError:
                pass
    return total


def free_gib(path):
    try:
        return shutil.disk_usage(path).free / 2**30
    except OSError:
        return float("inf")


def pressure_cfg(cfg):
    """Disk pressure (free space below retention_pressure_free_gib, just above the admission floor): keep only the
    newest output per group and drop the grace periods, so builds are not held for want of disk. Pins, active
    jobs and the outputs trains still point to stay protected as always."""
    return dict(cfg, retention_per_branch=1, retention_trains=1, retention_failed_hours=0, retention_merged_hours=0)


def orphan_outputs(store, jobs, now, min_age=6 * 3600):
    """out/<id> directories without a job record (a crash between creating the output and saving the job)."""
    known = {j["id"] for j in jobs}
    found = []
    for name in sorted(os.listdir(store.out_dir)) if os.path.isdir(store.out_dir) else []:
        path = os.path.join(store.out_dir, name)
        if ID_RE.match(name) and name not in known and os.path.isdir(path) and now - os.path.getmtime(path) >= min_age:
            found.append(name)
    return found


def apply_retention(store, cfg=None, now=None, git=None, dry_run=False, protected=None, free=None):
    """Delete the outputs retention_victims selects; returns [(job id, reason, bytes freed)]. Merged = the job's
    commit is an ancestor of origin/<integration_branch> (unknown when git cannot tell: kept). Below
    retention_pressure_free_gib free on the queue's disk the pressure rules apply (pressure_cfg)."""
    cfg = cfg or store.config()
    now = time.time() if now is None else now
    free = free_gib(store.root) if free is None else free
    pressure = free < cfg["retention_pressure_free_gib"]
    if pressure:
        cfg = pressure_cfg(cfg)
    git = git or Git()
    if protected is None:
        protected = TrainStore(store).protected_jobs()
    tip = git.rev(cfg["integration_branch"])
    cache = {}

    def merged(job):
        if tip and job["sha"] not in cache:
            cache[job["sha"]] = git.is_ancestor(job["sha"], tip) is True
        return cache.get(job["sha"], False)

    freed = []
    with store.lock():
        jobs = store.all()
        for name in orphan_outputs(store, jobs, now):
            path = store.job_out(name)
            freed.append((name, "output without a job record", dir_size(path)))
            if not dry_run:
                shutil.rmtree(path, ignore_errors=True)
        for job, reason in retention_victims(jobs, cfg, now, merged, protected):
            if pressure:
                reason += f" (disk pressure: {free:.1f} GiB free)"
            out = store.job_out(job["id"])
            size = dir_size(out) if os.path.isdir(out) else 0
            freed.append((job["id"], reason, size))
            if dry_run:
                continue
            shutil.rmtree(out, ignore_errors=True)
            job.update(output_deleted=True, output_deleted_reason=reason)
            store.save(job)
    return freed
