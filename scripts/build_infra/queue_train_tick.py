# SPDX-License-Identifier: AGPL-3.0-only
"""The dispatcher's build train step (once per tick, under train.lock). In order:
  1. trains being merged: merge (deterministic), push train/<prefix>NNN, submit one job per platform;
  2. trains being built whose jobs all finished: pass -> members passed; cancelled/infra -> members retried;
     failed -> attribution (queue_train.decide_failure): blamed members ejected with a confirmation build, the
     others carried to the next train, or a bisect into two half trains;
  3. bisected trains whose halves are all decided: closed;
  4. no train active and the start rule holds (queue_train.should_start): a new train from the ready branches;
  5. train branches older than train_keep_days whose builds are over: deleted from origin.
Every step is idempotent: a restart (or a crash between two steps) redoes the step from the saved records.
"""
import json
import os
import time

from .queue_store import PLATFORMS, QueueError, now_iso
from .queue_train import ready_order, select_members, should_start
from .queue_train_git import TrainGitError, TrainRepo
from .queue_train_judge import TrainJudge
from .queue_train_ops import note
from .queue_train_store import TRAIN_ACTIVE, TRAIN_FINAL, TrainStore

GIT_RETRY_SECONDS = 60
GIT_MAX_TRIES = 30
_backoff = {"start": 0.0}   # a failing train start (no network) is retried once a minute, not every tick


def _print_log(msg):
    print(f"[{time.strftime('%F %T')}] {msg}", flush=True)


class TrainStep(TrainJudge):
    def __init__(self, store, core, cfg, repo=None, now=None, log=_print_log):
        self.store, self.core, self.cfg, self.log = store, core, cfg, log
        self.ts = TrainStore(store)
        self.repo = repo or TrainRepo(self.ts.repo)
        self.now = time.time() if now is None else now
        self.branches = {}

    # ------------------------------------------------------------ helpers
    def event(self, rec, msg):
        rec.setdefault("events", []).append([now_iso(self.now), msg])
        del rec["events"][:-100]
        self.log(f"train {rec['name']}: {msg}")

    def release(self, branch, reason, carry=True):
        """Back to ready (a carry-over rides the next train at once), or failed after train_max_attempts."""
        cand = self.branches.get(branch)
        if cand is None:
            return
        if cand.get("removed"):
            del self.branches[branch]
            return
        cand["attempts"] = cand.get("attempts", 0) + 1
        if cand["attempts"] >= self.cfg["train_max_attempts"]:
            cand.update(state="failed", carry=False)
            note(cand, f"gave up after {cand['attempts']} trains: {reason}", self.now)
        else:
            cand.update(state="ready", carry=carry)
            if not carry:
                cand["ready_since"] = self.now
            note(cand, f"ready again: {reason}", self.now)

    def decide(self, branch, state, text, **fields):
        cand = self.branches.get(branch)
        if cand is None:
            return
        if cand.get("removed"):
            del self.branches[branch]
            return
        cand.update(state=state, carry=False, **fields)
        note(cand, text, self.now)

    def next_number(self):
        nums = [r["number"] for r in self.ts.trains()]
        prefix = self.cfg["train_prefix"]
        for name in self.repo.remote_trains(prefix):
            tail = name[len(prefix):]
            if tail.isdigit():
                nums.append(int(tail))
        return max(nums, default=0) + 1

    def new_record(self, number, members, platforms, base_sha, kind="train", parent=None, round_no=0):
        name = f"{self.cfg['train_prefix']}{number:03d}"
        return {"number": number, "name": name, "kind": kind, "parent": parent, "round": round_no,
                "state": "merging", "base_ref": self.cfg["integration_branch"], "base_sha": base_sha,
                "created": int(self.now), "created_at": now_iso(self.now), "platforms": platforms,
                "members": members, "conflicts": {}, "jobs": {}, "results": {}, "tries": 0}

    # ------------------------------------------------------------ 1. merge, push, submit
    def build(self, rec):
        if self.now < rec.get("next_try", 0):
            return
        try:
            self.repo.ensure()
            self.repo.fetch()
            sha, merged, conflicts = self.repo.merge(rec["base_sha"], rec["members"], rec["created"], rec["name"])
            for branch, files in conflicts.items():
                msha = next(m["sha"] for m in rec["members"] if m["branch"] == branch)
                rec["conflicts"][branch] = files
                if self.repo.conflicts_with_base(rec["base_sha"], msha):
                    self.decide(branch, "ejected", f"merge conflict with {rec['base_ref']} ({', '.join(files[:5])}): "
                                f"rebase onto it, then `train add` again", train=rec["name"])
                else:
                    self.release(branch, f"merge conflict with another branch of {rec['name']} "
                                 f"({', '.join(files[:5])})")
            rec["members"] = [m for m in rec["members"] if m["branch"] in merged]
            if not rec["members"]:
                rec["state"] = "empty"
                self.event(rec, "no branch merged cleanly; nothing to build")
                return
            if rec.get("sha") and rec["sha"] != sha:
                raise TrainGitError(f"merge gave {sha[:12]}, the record says {rec['sha'][:12]}")
            rec["sha"] = sha
            if self.repo.push(rec["name"], sha):
                self.event(rec, f"pushed {sha[:12]} = {rec['base_ref']}@{rec['base_sha'][:10]} + "
                           + ", ".join(f"{m['branch']}@{m['sha'][:10]}" for m in rec["members"]))
            rec["pushed"] = True
        except TrainGitError as exc:
            rec["tries"] = rec.get("tries", 0) + 1
            rec["last_error"] = str(exc)
            rec["next_try"] = self.now + GIT_RETRY_SECONDS
            self.event(rec, f"git step failed (try {rec['tries']}/{GIT_MAX_TRIES}): {exc}")
            if rec["tries"] >= GIT_MAX_TRIES:
                rec["state"] = "error"
                for m in rec["members"]:
                    self.release(m["branch"], f"{rec['name']} could not be merged or pushed: {exc}")
            return
        if rec["kind"] == "train":
            wanted = {p for m in rec["members"] for p in m["platforms"]}
            rec["platforms"] = [p for p in PLATFORMS if p in wanted]
        for platform in rec["platforms"]:
            if platform not in rec["jobs"]:
                job, _dup = self.core.submit(self.store, platform, rec["name"], self.cfg["train_priority"],
                                             resolver=lambda _ref, s=sha: s, submitter="build-train",
                                             internal=True, train=rec["name"])
                rec["jobs"][platform] = job["id"]
        rec["state"] = "building"
        self.event(rec, "building: " + ", ".join(f"{p} {j}" for p, j in sorted(rec["jobs"].items())))

    # ------------------------------------------------------------ 4. start a train
    def maybe_start(self):
        flag = self.ts.flag("start-requested")
        forced = os.path.exists(flag)
        ready = sorted((c for c in self.branches.values() if c["state"] == "ready"), key=ready_order)
        if not should_start(ready, self.now, self.cfg, forced):
            return None
        self.repo.ensure()
        self.repo.fetch()
        base_sha = self.repo.rev(self.cfg["integration_branch"])
        if not base_sha:
            raise TrainGitError(f"origin/{self.cfg['integration_branch']} not found")
        cands = []
        for cand in ready:
            sha = self.repo.rev(cand["branch"])
            if sha is None:
                self.decide(cand["branch"], "failed", "the branch is no longer on origin")
            elif self.repo.is_ancestor(sha, base_sha):
                self.decide(cand["branch"], "merged", f"already merged into {self.cfg['integration_branch']}")
            else:
                patches, files = self.repo.lo_files(base_sha, sha)
                cands.append({"branch": cand["branch"], "sha": sha, "platforms": cand["platforms"],
                              "patches": patches, "lo_files": files, "carry": cand.get("carry")})
        chosen, deferred = select_members(cands, self.cfg["train_max_branches"])
        for branch, reason in deferred.items():
            note(self.branches[branch], f"ready, waiting for the next train: {reason}", self.now)
        if os.path.exists(flag):
            os.remove(flag)
        if not chosen:
            return None
        members = [{k: c[k] for k in ("branch", "sha", "platforms", "patches", "lo_files")} for c in chosen]
        rec = self.new_record(self.next_number(), members, list(PLATFORMS), base_sha)
        rec["deferred"] = deferred
        self.ts.save(rec)
        for m in members:
            cand = self.branches[m["branch"]]
            cand.update(state="in-train", train=rec["name"], carry=False)
            note(cand, f"in {rec['name']} at {m['sha'][:10]}", self.now)
        self.ts.save_branches(self.branches)
        self.event(rec, f"started{' (forced)' if forced else ''} on {rec['base_ref']}@{base_sha[:10]} with "
                   + ", ".join(m["branch"] for m in members))
        return rec

    # ------------------------------------------------------------ 5. delete old train branches
    def cleanup(self, rec):
        if rec["state"] not in TRAIN_FINAL or not rec.get("pushed") or rec.get("ref_deleted"):
            return
        if self.now - rec["created"] < self.cfg["train_keep_days"] * 86400:
            return
        for jid in rec.get("jobs", {}).values():
            try:
                if self.store.load(jid)["state"] in ("queued", "running"):
                    return
            except QueueError:
                pass
        if any(c["state"] == "ejected" and c.get("train") == rec["name"] and any(
                self.store.load(j)["state"] in ("queued", "running") for j in c.get("confirm", {}).values())
               for c in self.branches.values()):
            return
        self.repo.delete_remote(rec["name"])
        rec["ref_deleted"] = True
        self.event(rec, f"branch deleted from origin (older than {self.cfg['train_keep_days']} days)")

    # ------------------------------------------------------------ the step
    def save_if_changed(self, rec, before):
        if json.dumps(rec, sort_keys=True) != before:
            self.ts.save(rec)

    def run(self):
        if not self.cfg["train_enabled"]:
            return
        if not self.ts.branches() and not self.ts.trains():
            return   # nothing to do: no git, no lock
        with self.ts.lock():
            self.branches = self.ts.branches()
            before_branches = json.dumps(self.branches, sort_keys=True)
            try:
                for state, fn in (("merging", self.build), ("building", self.evaluate),
                                  ("bisecting", self.close_bisect)):
                    for rec in self.ts.trains():
                        if rec["state"] == state:
                            before = json.dumps(rec, sort_keys=True)
                            fn(rec)
                            self.save_if_changed(rec, before)
                if not any(r["state"] in TRAIN_ACTIVE for r in self.ts.trains()) and self.now >= _backoff["start"]:
                    try:
                        rec = self.maybe_start()
                    except TrainGitError as exc:
                        _backoff["start"] = self.now + GIT_RETRY_SECONDS
                        self.log(f"train: cannot start a train now, retrying in a minute: {exc}")
                        rec = None
                    if rec:
                        self.build(rec)
                        self.ts.save(rec)
                for rec in self.ts.trains():
                    before = json.dumps(rec, sort_keys=True)
                    try:
                        self.cleanup(rec)
                    except (TrainGitError, QueueError) as exc:
                        self.log(f"train {rec['name']}: branch cleanup failed, retried later: {exc}")
                    self.save_if_changed(rec, before)
            finally:
                if json.dumps(self.branches, sort_keys=True) != before_branches:
                    self.ts.save_branches(self.branches)


def tick(store, core, cfg=None, repo=None, now=None, log=_print_log):
    TrainStep(store, core, cfg or store.config(), repo, now, log).run()
