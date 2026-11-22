# SPDX-License-Identifier: AGPL-3.0-only
"""Build train commands of agents and the integrator: `train add|remove|start|wait` (the dispatcher's train step is
queue_train_tick.py). A branch is a candidate until a train result decides it:
  ready -> in-train -> passed (its train built on every platform) | ejected (blamed; confirmation build queued)
  a failed train's other branches go back to ready as carry-overs and ride the next train at once.
"""
import os
import sys
import time

from .queue_git import Git
from .queue_ops import refuse_bad_patches
from .queue_rules import is_integrator, label_for, resolve_ref
from .queue_store import PLATFORMS, REF_RE, QueueError, now_iso
from .queue_train_store import CANDIDATE_FINAL, TrainStore


def platforms_of(choice):
    if choice == "both":
        return list(PLATFORMS)
    if choice not in PLATFORMS:
        raise QueueError("--platform must be linux, windows or both")
    return [choice]


def note(cand, text, t=None):
    """Latest note of a candidate plus its history (newest last, bounded)."""
    cand["note"] = text
    cand.setdefault("history", []).append([now_iso(t), text])
    del cand["history"][:-30]


def add(store, branch, platform="both", resolver=resolve_ref, git=None, submitter=None, now=None, tests=()):
    """The branch is ready for the next train. `tests`: the CppunitTest/PythonTest targets that prove the change;
    the train's Linux build runs them with train_tests (a red/green pair or a module-only test build stays a plain
    `submit`)."""
    cfg = store.config()
    tests = list(dict.fromkeys(tests))
    now = time.time() if now is None else now
    if not REF_RE.match(branch) or ".." in branch or branch.startswith(("train/", "rc/")) \
            or is_integrator(branch, False, cfg):
        raise QueueError(f"{branch!r} cannot ride a train (train/*, rc/* and integration branches are not members)")
    sha = resolver(branch)
    if label_for(branch, sha) == "commit":
        raise QueueError("train add takes a branch name, not a commit")
    git = git or Git()
    if git.out("rev-parse", "-q", "--verify", f"origin/{branch}^{{commit}}") is None:
        raise QueueError(f"{branch} is not on origin: push it first (the train merges origin/{branch})")
    refuse_bad_patches(git, cfg, branch, sha)
    tip = git.rev(cfg["integration_branch"])
    if tip and git.is_ancestor(sha, tip):
        raise QueueError(f"{branch}@{sha[:10]} is already merged into {cfg['integration_branch']}")
    plats = platforms_of(platform)
    ts = TrainStore(store)
    with ts.lock():
        branches = ts.branches()
        cand = branches.get(branch)
        if cand and cand["state"] == "in-train":
            raise QueueError(f"{branch} is in {cand['train']} now; add it again when that train has a result "
                             f"(`build-queue.sh train status {branch}`)")
        if cand and cand["state"] == "ready":
            cand.update(platforms=plats, tests=tests)
            note(cand, f"still ready (platforms {','.join(plats)}; {len(tests)} declared tests)", now)
        else:
            cand = {"branch": branch, "state": "ready", "platforms": plats, "tests": tests, "added": now,
                    "added_at": now_iso(now),
                    "ready_since": now, "attempts": 0, "carry": False, "history": (cand or {}).get("history", []),
                    "submitter": submitter or os.environ.get("SUDO_USER") or os.environ.get("USER", "?")}
            note(cand, f"ready at {sha[:10]} (platforms {','.join(plats)}; {len(tests)} declared tests); the "
                       "train merges the branch tip when it starts", now)
        branches[branch] = cand
        ts.save_branches(branches)
        return cand


def remove(store, branch):
    ts = TrainStore(store)
    with ts.lock():
        branches = ts.branches()
        cand = branches.get(branch)
        if cand is None:
            raise QueueError(f"{branch} is not a train candidate")
        if cand["state"] == "in-train":
            cand["removed"] = True
            note(cand, f"removed: {cand['train']} still finishes with it, then the branch is dropped")
        else:
            del branches[branch]
        ts.save_branches(branches)
        return cand


def start(store):
    """The next dispatcher tick builds a train from the ready branches even below the thresholds."""
    ts = TrainStore(store)
    with ts.lock():
        with open(ts.flag("start-requested"), "w", encoding="ascii") as f:
            f.write(now_iso() + "\n")


def flaky_line(rec):
    """The warning for tests of a train that failed once and passed when run again: never blamed, never silent."""
    return (f"    FLAKY    {rec['name']}: {', '.join(rec['flaky_tests'])} failed once, passed when run again: "
            "not blamed, but each one is a defect to fix")


def member_jobs(store, cand):
    """[(platform, job)] of the train result (or confirmation builds) a candidate points at."""
    res = cand.get("result") or {}
    jobs = []
    for platform, jid in sorted({**res.get("jobs", {}), **cand.get("confirm", {})}.items()):
        try:
            jobs.append((platform, store.load(jid)))
        except QueueError:
            jobs.append((platform, None))
    return jobs


def wait(store, branch, timeout=None, interval=15, out=sys.stdout):
    """Until the branch has a train result: 0 passed (prints the outputs), 1 ejected/failed, 2 timeout."""
    ts = TrainStore(store)
    t0 = time.time()
    while True:
        cand = ts.branches().get(branch)
        if cand is None:
            raise QueueError(f"{branch} is not a train candidate")
        if cand["state"] in CANDIDATE_FINAL:
            break
        if timeout is not None and time.time() - t0 > timeout:
            print(f"timeout: {branch} is {cand['state']} ({cand.get('note', '')})", file=out)
            return 2
        time.sleep(interval)
    print(f"{branch}: {cand['state']}: {cand.get('note', '')}", file=out)
    rec = ts.load((cand.get("result") or {}).get("train") or "")
    if rec and rec.get("flaky_tests"):
        print(flaky_line(rec), file=out)
    for platform, job in member_jobs(store, cand):
        if job and job["state"] == "done" and cand["state"] == "passed":
            for path in job.get("output", []):
                print(path, file=out)
        elif job:
            print(f"{platform}: job {job['id']} {job['state']}", file=out)
    return 0 if cand["state"] in ("passed", "merged") else 1
