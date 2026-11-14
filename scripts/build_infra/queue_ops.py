# SPDX-License-Identifier: AGPL-3.0-only
"""Build queue commands that change job or host state: submit, cancel, invalidate, drain (retention and pins:
queue_retention.py).
"""
import os
import sys
import time

from .queue_git import Git, is_docs_only
from .queue_rules import (find_duplicate, is_integrator, job_key, job_kind, label_for, last_built, new_id, resolve_ref,
                          superseded)
from .queue_store import PLATFORMS, QueueError, now_iso

# ---------------------------------------------------------------- commands
def submit(store, platform, ref, priority=0, package=True, modules=(), resolver=resolve_ref, submitter=None, tests=(),
           force=False, integrator=False, git=None, err=None, internal=False, train=None, confirm_for=None):
    """Queue a build; returns (job, deduplicated). Rules for agents (internal=False):
      - priority above agent_max_priority is capped unless the submit comes from the integrator;
      - a commit whose diff against the branch's last build (or, without one, its merge base with the integration
        branch) only touches tests/, docs/, plans/ or *.md is refused: that build is still valid (--force: integrator);
      - queued (not running) jobs of the same branch + platform + kind at an older commit are cancelled.
    internal=True: jobs the build train submits itself (no checks; never supersedes anything)."""
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
    cfg = store.config()
    integ = internal or is_integrator(ref, integrator, cfg)
    if force and not integ:
        raise QueueError("--force is reserved for the integrator (rc/1.0.2-batch* refs or --integrator)")
    err = err or sys.stderr
    if priority > cfg["agent_max_priority"] and not integ:
        print(f"priority {priority} capped at {cfg['agent_max_priority']} (higher is reserved for the integrator)",
              file=err)
        priority = cfg["agent_max_priority"]
    sha = resolver(ref)
    key = job_key(platform, sha, package, modules, tests)
    label = label_for(ref, sha)
    kind = job_kind({"tests": tests, "modules": modules})
    git = git or Git()
    with store.lock():
        jobs = store.all()
        dup = find_duplicate(jobs, key)
        if dup:
            return dup, True
        if not internal and not force:
            refuse_docs_only(jobs, cfg, git, platform, ref, label, kind, sha)
        t = time.time()
        job_id = new_id(t)
        if not internal:
            for old in superseded(jobs, platform, label, kind, sha):
                old.update(state="cancelled", finished=t, error=f"superseded by {job_id} ({sha[:10]})",
                           superseded_by=job_id)
                store.save(old)
                print(f"cancelled queued job {old['id']} ({old['sha'][:10]}): superseded by this commit", file=err)
        job = {"id": job_id, "platform": platform, "ref": ref, "sha": sha, "label": label,
               "priority": priority, "package": package, "modules": modules, "tests": tests, "key": key,
               "state": "queued",
               "submitted": t, "submitted_at": now_iso(t), "submitter": submitter or os.environ.get("SUDO_USER")
               or os.environ.get("USER", "?"), "output": []}
        if integ:
            job["integrator"] = True
        if force:
            job["forced"] = True
        if train:
            job["train"] = train
        if confirm_for:
            job["confirm_for"] = confirm_for   # confirmation build of a branch ejected from that train
        job["log"] = store.log_path(job["id"])
        store.save(job)
        return job, False


def refuse_docs_only(jobs, cfg, git, platform, ref, label, kind, sha):
    """QueueError when the commit only changes tests/docs/plans/*.md against its baseline (git errors: allowed)."""
    base_job = last_built(jobs, platform, label, kind, sha)
    if base_job:
        base, use = base_job["sha"], f"job {base_job['id']} ({', '.join(base_job['output'])})"
    else:
        integ = git.rev(cfg["integration_branch"])
        base = integ and git.merge_base(integ, sha)
        use = f"the {cfg['integration_branch']} build (or a train build)"
        if base == sha:
            return   # the commit is part of the integration branch: nothing to compare against
    paths = git.changed(base, sha) if base else None
    if paths is None or (paths and not all(is_docs_only(p) for p in paths)) or (not paths and not base_job):
        return
    what = f"only changes tests/, docs/, plans/ or *.md ({len(paths)} files)" if paths else "has the same files"
    raise QueueError(f"{ref}@{sha[:10]} {what} since {base[:10]}: no new build needed, use {use}; run tests "
                     f"from your checkout. The integrator can override with --force --integrator")


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
