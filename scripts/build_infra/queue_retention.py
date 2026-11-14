# SPDX-License-Identifier: AGPL-3.0-only
"""Output retention of the build queue (rules: queue_rules.retention_victims) and pins that exempt a job from it.
"""
import os
import shutil
import time

from .queue_git import Git
from .queue_rules import retention_victims
from .queue_store import QueueError, now_iso
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


def apply_retention(store, cfg=None, now=None, git=None, dry_run=False, protected=None):
    """Delete the outputs retention_victims selects; returns [(job id, reason, bytes freed)]. Merged = the job's
    commit is an ancestor of origin/<integration_branch> (unknown when git cannot tell: kept)."""
    cfg = cfg or store.config()
    now = time.time() if now is None else now
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
        for job, reason in retention_victims(store.all(), cfg, now, merged, protected):
            out = store.job_out(job["id"])
            size = dir_size(out) if os.path.isdir(out) else 0
            freed.append((job["id"], reason, size))
            if dry_run:
                continue
            shutil.rmtree(out, ignore_errors=True)
            job.update(output_deleted=True, output_deleted_reason=reason)
            store.save(job)
    return freed
