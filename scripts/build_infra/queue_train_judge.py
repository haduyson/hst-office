# SPDX-License-Identifier: AGPL-3.0-only
"""Judging finished train builds (mixed into queue_train_tick.TrainStep, which supplies store, core, cfg, ts,
branches, now and the helpers event/release/decide/new_record/next_number/build):
  pass -> members passed; cancelled/infra -> members retried without blame; the base itself broken -> no blame;
  failed -> queue_train.decide_failure: blamed members ejected with a confirmation build, the others carried to the
  next train, or a bisect into two half trains that build only the failing platforms.
"""
import os
import re

from .queue_store import QueueError
from .queue_train import decide_failure, job_outcome, split_halves
from .queue_train_ops import note
from .queue_train_store import TRAIN_FINAL


class TrainJudge:
    # ------------------------------------------------------------ 2. judge finished builds
    def failure_text(self, job):
        text = self.core.log_tail(job["log"], 4000)
        m = re.search(r"logs in (/\S+)", text)
        build_log = os.path.join(m.group(1), "build.log") if m else None
        if build_log and os.path.isfile(build_log):
            with open(build_log, encoding="utf-8", errors="replace") as f:
                text += "\n" + "".join(ln for ln in f if "error" in ln.lower() or "FATAL" in ln or "***" in ln)
        return text

    def base_broken(self, rec, platforms):
        """The integration branch itself fails at this base: no branch is to blame."""
        jobs = [j for j in self.store.all() if j["sha"] == rec["base_sha"] and j["platform"] in platforms
                and not j.get("train")]
        return any(j["state"] == "failed" and job_outcome(j, self.core.infra_failure) == "fail" for j in jobs) \
            and not any(j["state"] == "done" for j in jobs)

    def evaluate(self, rec):
        outcomes, texts = {}, {}
        for platform, jid in sorted(rec["jobs"].items()):
            try:
                job = self.store.load(jid)
            except QueueError:
                job = None
            tail = self.core.log_tail(job["log"], 80) if job and job["state"] == "failed" else ""
            outcome = job_outcome(job, self.core.infra_failure, tail)
            if outcome is None:
                return
            outcomes[platform] = outcome
            if outcome == "fail":
                texts[platform] = self.failure_text(job)
        rec["results"] = outcomes
        fails = sorted(p for p, o in outcomes.items() if o == "fail")
        members = rec["members"]
        if all(o == "pass" for o in outcomes.values()):
            rec["state"] = "passed"
            self.event(rec, "passed on " + ", ".join(sorted(outcomes)))
            where, jobs = "", dict(rec["jobs"])
            parent = self.ts.load(rec["parent"]) if rec.get("parent") else None
            if parent:   # a half rebuilds only the failing platforms: the parent's passing builds hold the rest
                where = f" (bisect half of {parent['name']})"
                jobs = {**{p: parent["jobs"][p] for p, o in parent.get("results", {}).items() if o == "pass"}, **jobs}
            for m in members:
                self.decide(m["branch"], "passed", f"passed in {rec['name']}{where} at {rec['sha'][:10]}",
                            train=rec["name"], result={"train": rec["name"], "sha": rec["sha"], "jobs": jobs})
            return
        if not fails:
            rec["state"] = "error"
            self.event(rec, f"builds did not finish ({outcomes}); members retried without blame")
            for m in members:
                self.release(m["branch"], f"{rec['name']} was cancelled or hit an infrastructure failure")
            return
        if self.base_broken(rec, fails):
            rec["state"] = "error"
            self.event(rec, f"{rec['base_ref']}@{rec['base_sha'][:10]} itself fails on {','.join(fails)}; no blame")
            for m in members:
                self.release(m["branch"], f"{rec['base_ref']} fails to build at {rec['base_sha'][:10]}", carry=False)
            return
        action, method, blamed, detail = decide_failure(members, "\n".join(texts.values()), rec["round"],
                                                        self.cfg["train_bisect_rounds"])
        if action == "bisect":
            self.bisect(rec, fails, detail)
            return
        rec.update(state="failed", attribution={"method": method, "blamed": blamed, "detail": detail,
                                                "platforms": fails})
        self.event(rec, f"failed on {','.join(fails)}: {method}: {', '.join(blamed)} ({detail})")
        for m in members:
            if m["branch"] in blamed:
                self.eject(rec, m, fails, f"{method}: {detail}")
            else:
                self.release(m["branch"], f"{rec['name']} failed because of {', '.join(blamed)}")

    def eject(self, rec, member, platforms, why):
        confirm = {}
        for platform in platforms:
            job, _dup = self.core.submit(self.store, platform, member["branch"], self.cfg["train_confirm_priority"],
                                         resolver=lambda _ref, s=member["sha"]: s, submitter="build-train",
                                         internal=True)
            confirm[platform] = job["id"]
        self.decide(member["branch"], "ejected", f"ejected from {rec['name']} ({why}); confirmation build "
                    + ", ".join(f"{p} {j}" for p, j in sorted(confirm.items())), train=rec["name"], confirm=confirm,
                    result={"train": rec["name"], "sha": rec.get("sha"), "jobs": rec["jobs"]})

    def bisect(self, rec, platforms, detail):
        children = [r for r in self.ts.trains() if r.get("parent") == rec["name"]]
        if not children:
            number = self.next_number()
            for i, half in enumerate(split_halves(rec["members"])):
                child = self.new_record(number + i, half, platforms, rec["base_sha"], "bisect", rec["name"],
                                        rec["round"] + 1)
                self.ts.save(child)
                children.append(child)
        rec.update(state="bisecting", children=[c["name"] for c in children])
        self.event(rec, f"failed on {','.join(platforms)}; {detail}: " + "; ".join(
            f"{c['name']} = {', '.join(m['branch'] for m in c['members'])}" for c in children))
        for c in children:
            for m in c["members"]:
                if m["branch"] in self.branches:
                    self.branches[m["branch"]]["train"] = c["name"]
            if c["state"] == "merging":
                self.build(c)
                self.ts.save(c)

    # ------------------------------------------------------------ 3. close bisected trains
    def close_bisect(self, rec):
        children = [self.ts.load(n) for n in rec.get("children", [])]
        if any(c is None or c["state"] not in TRAIN_FINAL for c in children):
            return
        blamed = sorted({b for c in children for b in (c.get("attribution") or {}).get("blamed", [])})
        if all(c["state"] == "passed" for c in children):
            detail = "each half passes alone: the failure needs branches from both halves (an interaction)"
            for c in children:
                for m in c["members"]:
                    cand = self.branches.get(m["branch"])
                    if cand and cand["state"] == "passed":
                        note(cand, f"{cand['note']}; WARNING: the full {rec['name']} failed, {detail}", self.now)
        else:
            detail = "bisect: " + ", ".join(f"{c['name']} {c['state']}" for c in children)
        rec.update(state="failed", attribution={"method": "bisect", "blamed": blamed, "detail": detail})
        self.event(rec, f"bisect closed: blamed {', '.join(blamed) or 'nobody'} ({detail})")
