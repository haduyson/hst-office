# SPDX-License-Identifier: AGPL-3.0-only
"""Build queue commands that change job or host state: submit, cancel, invalidate, drain (retention and pins:
queue_retention.py).
"""
import os
import sys
import time

from .queue_git import Git, is_docs_only
from .queue_patch_lint import lint_commit
from .queue_rules import (find_duplicate, is_integrator, job_key, job_kind, label_for, last_built, new_id, resolve_ref,
                          superseded, test_merge_target)
from .queue_store import PLATFORMS, TEST_NAME_RE, QueueError, now_iso

# ---------------------------------------------------------------- commands
def submit(store, platform, ref, priority=None, package=True, modules=(), resolver=resolve_ref, submitter=None, tests=(),
           force=False, integrator=False, git=None, err=None, internal=False, train=None, confirm_for=None,
           test_name=None, gdb=False):
    """Queue a build; returns (job, deduplicated). Rules for agents (internal=False):
      - priority above agent_max_priority is capped unless the submit comes from the integrator;
      - priority None (not given): integrator_priority for the integrator, 0 for everyone else;
      - a commit whose diff against the branch's last build (or, without one, its merge base with the integration
        branch) only touches tests/, docs/, plans/ or *.md is refused: that build is still valid (--force: integrator);
      - queued (not running) jobs of the same branch + platform + kind at an older commit are cancelled.
      - a test run (--test) whose commit, platform and modules match a queued job of another test run that has not
        started yet joins that job: the job runs the union of both test lists (merge_test_job).
    internal=True: jobs the build train submits itself (no checks; never supersedes or joins anything; a package
    build may also run tests: the train's Linux build runs its test set before packaging)."""
    if platform not in PLATFORMS:
        raise QueueError(f"--platform must be one of {', '.join(PLATFORMS)}")
    if priority is not None and not -100 <= priority <= 100:
        raise QueueError("--priority must be between -100 and 100")
    modules = list(modules)
    if platform == "windows" and not package and not modules:
        raise QueueError("Windows make always builds the MSI; omit --no-package")
    tests = list(tests)
    if tests and platform != "linux":
        raise QueueError("--test runs on Linux slots only")
    if (test_name or gdb) and not tests:
        raise QueueError("--test-name and --gdb need --test")
    if test_name and not TEST_NAME_RE.match(test_name):
        raise QueueError(f"bad --test-name {test_name!r} (a CppUnit test or fixture name, e.g. TestTdf150606)")
    if modules or (tests and not internal):
        package = False
    cfg = store.config()
    integ = internal or is_integrator(ref, integrator, cfg)
    if force and not integ:
        raise QueueError("--force is reserved for the integrator (rc/1.0.2-batch* refs or --integrator)")
    err = err or sys.stderr
    if priority is None:
        priority = cfg["integrator_priority"] if integ and not internal else 0
    if priority > cfg["agent_max_priority"] and not integ:
        print(f"priority {priority} capped at {cfg['agent_max_priority']} (higher is reserved for the integrator)",
              file=err)
        priority = cfg["agent_max_priority"]
    sha = resolver(ref)
    git = git or Git()
    if not internal and not force:
        refuse_bad_patches(git, cfg, ref, sha)
    key = job_key(platform, sha, package, modules, tests) + (f":name={test_name}" if test_name else "") \
        + (":gdb" if gdb else "")
    label = label_for(ref, sha)
    kind = job_kind({"tests": tests, "modules": modules})
    with store.lock():
        jobs = store.all()
        dup = find_duplicate(jobs, key)
        if dup:
            return dup, True
        target = None if internal or not tests or test_name or gdb \
            else test_merge_target(jobs, platform, sha, package, modules)
        if target:
            return merge_test_job(store, target, tests, priority, err), True
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
        if test_name:
            job["test_name"] = test_name   # CPPUNIT_TEST_NAME: only that test of each target
        if gdb:
            job["gdb"] = True              # tests run under gdb -batch (a diagnosis run: never joined with others)
        if train:
            job["train"] = train
        if confirm_for:
            job["confirm_for"] = confirm_for   # confirmation build of a branch ejected from that train
        job["log"] = store.log_path(job["id"])
        store.save(job)
        return job, False


def merge_test_job(store, target, tests, priority, err=None, merged_from=None):
    """Add `tests` to the queued test job `target` (caller holds the store lock): one build runs the union of the
    test lists, in the order they were asked for; the job keeps the higher priority."""
    union = list(dict.fromkeys([*target["tests"], *tests]))
    added = [t for t in union if t not in target["tests"]]
    target.update(tests=union, priority=max(target["priority"], priority),
                  key=job_key(target["platform"], target["sha"], target["package"], target["modules"], union))
    target.setdefault("merged_tests", []).append({"at": now_iso(), "added": added, "from": merged_from or "submit"})
    store.save(target)
    print(f"joined queued job {target['id']} (same commit, platform and modules): it runs {len(union)} tests, "
          f"{len(added)} added", file=err or sys.stderr)
    return target


def collapse_test_jobs(store, dry_run=False, out=None):
    """Fold queued test jobs that only differ in their test list (same commit, platform, package and modules, not
    started yet) into the oldest one; the others are cancelled with merged_into = the kept job. Returns
    [(kept id, [folded ids])]."""
    out = out or sys.stdout
    done = []
    with store.lock():
        jobs = sorted(store.all(), key=lambda j: (j["submitted"], j["id"]))
        folded = set()
        for job in jobs:
            if job["id"] in folded or not test_merge_target([job], job["platform"], job["sha"], job["package"],
                                                             job["modules"]):
                continue
            group = [j for j in jobs if j is not job and j["id"] not in folded
                     and test_merge_target([j], job["platform"], job["sha"], job["package"], job["modules"])]
            if not group:
                continue
            for other in group:
                folded.add(other["id"])
                if dry_run:
                    continue
                merge_test_job(store, job, other["tests"], other["priority"], out, merged_from=other["id"])
                t = time.time()
                other.update(state="cancelled", finished=t, error=f"merged into {job['id']} (its test list now "
                             f"includes all {len(other['tests'])} tests of this job)", merged_into=job["id"])
                store.save(other)
            done.append((job["id"], [o["id"] for o in group]))
    for kept, others in done:
        print(f"{'would fold' if dry_run else 'folded'} {', '.join(others)} into {kept}", file=out)
    return done


def refuse_bad_patches(git, cfg, ref, sha):
    """QueueError when a patch the commit adds or changes would not apply where it should with `patch -p1`."""
    problems = lint_commit(git, cfg["integration_branch"], sha, cfg.get("lo_reference_tree"))
    if problems:
        raise QueueError(f"{ref}@{sha[:10]}: patch lint failed, the build would apply files in the wrong place:\n  "
                         + "\n  ".join(problems[:20]) + ("\n  ..." if len(problems) > 20 else "")
                         + "\nFix the diff headers (git format-patch / git diff output keeps a/ and b/). The integrator "
                         "can override with --force --integrator")


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
