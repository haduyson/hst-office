# SPDX-License-Identifier: AGPL-3.0-only
"""Judging finished train builds (mixed into queue_train_tick.TrainStep, which supplies store, core, cfg, ts,
branches, now and the helpers event/release/decide/new_record/next_number/build):
  pass (every build, and every test of the Linux build) -> members passed; cancelled/infra -> members retried without
  blame; the base itself broken -> no blame; failed -> queue_train.decide_failure: blamed members ejected with a
  confirmation build, the others carried to the next train, or a bisect into two half trains that build only the
  failing platforms. Failing tests are first run on the base commit (one Linux test job, deduplicated across trains):
  a target that fails there too is reported but never blamed on a branch.
"""
import os
import re

from .queue_store import QueueError, now_iso
from .queue_train import ASSERT_LINE_RE, decide_failure, failed_tests, job_outcome, split_halves
from .queue_train_ops import note
from .queue_train_store import TRAIN_FINAL, write_json


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

    def test_failure_text(self, job, targets):
        """"test <target> failed" plus the assertion lines of each failing target's log (out/<id>/test-logs/)."""
        res = job.get("test_results") or {}
        lines = []
        for target in targets:
            lines.append(f"test {target} failed")
            rel = (res.get(target) or {}).get("log")
            path = os.path.join(self.store.job_out(job["id"]), rel) if rel else None
            if path and os.path.isfile(path):
                with open(path, encoding="utf-8", errors="replace") as f:
                    lines += [ln.rstrip("\n") for ln in f if ASSERT_LINE_RE.search(ln)][:50]
        return "\n".join(lines)

    def base_test_failures(self, rec, targets):
        """Which of `targets` fail on the base commit too: a set, None while the base run is queued or running,
        or an error text when the base run could not finish (then nobody is blamed)."""
        key = ",".join(sorted(targets))
        baseline = rec.setdefault("baseline", {})
        if key not in baseline:
            job, _dup = self.core.submit(self.store, "linux", rec["base_sha"], self.cfg["train_priority"],
                                         package=False, resolver=lambda _ref, s=rec["base_sha"]: s,
                                         submitter="build-train", internal=True, tests=sorted(targets))
            baseline[key] = job["id"]
            self.event(rec, f"tests failed: {', '.join(sorted(targets))}; running them on {rec['base_ref']}@"
                       f"{rec['base_sha'][:10]} ({job['id']}) before blaming anyone")
        try:
            job = self.store.load(baseline[key])
        except QueueError:
            job = None
        tail = self.core.log_tail(job["log"], 80) if job and job["state"] == "failed" else ""
        outcome = job_outcome(job, self.core.infra_failure, tail)
        if outcome is None:
            return None
        if outcome != "pass":
            return f"the base test run {baseline[key]} did not finish ({outcome})"
        return set(failed_tests(job))

    def evaluate(self, rec):
        outcomes, texts, jobs, tested = {}, {}, {}, {}
        for platform, jid in sorted(rec["jobs"].items()):
            try:
                job = self.store.load(jid)
            except QueueError:
                job = None
            tail = self.core.log_tail(job["log"], 80) if job and job["state"] == "failed" else ""
            outcome = job_outcome(job, self.core.infra_failure, tail)
            if outcome is None:
                return
            outcomes[platform], jobs[platform] = outcome, job
            if outcome == "fail":
                texts[platform] = self.failure_text(job)
            elif outcome == "pass" and failed_tests(job):
                tested[platform] = failed_tests(job)
        test_fails = {}
        if tested:
            on_base = self.base_test_failures(rec, sorted({t for ts in tested.values() for t in ts}))
            if on_base is None:
                return   # the base run of the failing targets is still building
            if isinstance(on_base, str):
                rec.update(state="error", results=outcomes)
                self.event(rec, f"tests failed but {on_base}; members retried without blame")
                for m in rec["members"]:
                    self.release(m["branch"], f"{rec['name']}: {on_base}", owner=rec["name"], count=True)
                return
            excused = sorted({t for ts in tested.values() for t in ts} & on_base)
            if excused:
                rec["base_test_failures"] = excused
                self.event(rec, f"also failing on {rec['base_ref']}@{rec['base_sha'][:10]}, not blamed: "
                           + ", ".join(excused))
            for platform, targets in tested.items():
                real = [t for t in targets if t not in on_base]
                if real:
                    outcomes[platform], test_fails[platform] = "fail", real
        rec["results"] = outcomes
        if test_fails:
            rec["test_failures"] = test_fails
        fails = sorted(p for p, o in outcomes.items() if o == "fail")
        members = rec["members"]
        if all(o == "pass" for o in outcomes.values()):
            rec["state"] = "passed"
            ntests = len(rec.get("tests", []))
            self.event(rec, "passed on " + ", ".join(sorted(outcomes))
                       + (f" with {ntests} tests" if ntests else " (no test set)"))
            where, result_jobs = "", dict(rec["jobs"])
            parent = self.ts.load(rec["parent"]) if rec.get("parent") else None
            if parent:   # a half rebuilds only the failing platforms: the parent's passing builds hold the rest
                where = f" (bisect half of {parent['name']})"
                result_jobs = {**{p: parent["jobs"][p] for p, o in parent.get("results", {}).items() if o == "pass"},
                               **result_jobs}
            tested_text = f"; {ntests} tests passed" if ntests else "; build only, no tests ran"
            if rec.get("base_test_failures"):
                tested_text += f" ({len(rec['base_test_failures'])} failing on the base too, not counted)"
            for m in members:
                self.decide(m["branch"], "passed", f"passed in {rec['name']}{where} at {rec['sha'][:10]}{tested_text}",
                            owner=rec["name"], result={"train": rec["name"], "sha": rec["sha"], "jobs": result_jobs})
            return
        if not fails:
            rec["state"] = "error"
            self.event(rec, f"builds did not finish ({outcomes}); members retried without blame")
            for m in members:
                self.release(m["branch"], f"{rec['name']} was cancelled or hit an infrastructure failure",
                             owner=rec["name"], count=True)
            return
        build_fails = [p for p in fails if p not in test_fails]
        if build_fails and self.base_broken(rec, build_fails):
            rec["state"] = "error"
            self.event(rec, f"{rec['base_ref']}@{rec['base_sha'][:10]} itself fails on {','.join(build_fails)}; "
                       "no blame; no train starts until it moves")
            write_json(self.ts.flag("base-hold.json"), {"sha": rec["base_sha"], "since": now_iso(self.now)})
            for m in members:
                self.release(m["branch"], f"{rec['base_ref']} fails to build at {rec['base_sha'][:10]}; the next "
                             "train waits for a new commit there", carry=False, owner=rec["name"])
            return
        if build_fails:   # a failed build explains everything: blame from its log (test text would only add noise)
            text, files_method = "\n".join(texts[p] for p in build_fails), "compile"
        else:
            text = "\n".join(self.test_failure_text(jobs[p], t) for p, t in sorted(test_fails.items()))
            files_method = "test"
        action, method, blamed, detail = decide_failure(members, text, rec["round"],
                                                        self.cfg["train_bisect_rounds"], files_method)
        if test_fails and not build_fails:
            detail += "; failing tests: " + ", ".join(sorted({t for ts in test_fails.values() for t in ts}))
        if action == "bisect":
            self.bisect(rec, fails, detail)
            return
        rec.update(state="failed", attribution={"method": method, "blamed": blamed, "detail": detail,
                                                "platforms": fails})
        self.event(rec, f"failed on {','.join(fails)}: {method}: {', '.join(blamed)} ({detail})")
        for m in members:
            if m["branch"] in blamed:
                self.eject(rec, m, fails, f"{method}: {detail}", test_fails)
            else:
                self.release(m["branch"], f"{rec['name']} failed because of {', '.join(blamed)}", owner=rec["name"])

    def eject(self, rec, member, platforms, why, test_fails=None):
        """Blamed: ejected, with a confirmation build of the branch alone per failing platform (a Linux test
        failure: the confirmation build runs the failing targets)."""
        if self.owned(member["branch"], rec["name"]) is None:
            return   # already decided (a redo after a restart)
        confirm = {}
        for platform in platforms:
            job, _dup = self.core.submit(self.store, platform, member["branch"], self.cfg["train_confirm_priority"],
                                         resolver=lambda _ref, s=member["sha"]: s, submitter="build-train",
                                         internal=True, confirm_for=rec["name"],
                                         tests=(test_fails or {}).get(platform, ()))
            confirm[platform] = job["id"]
        self.decide(member["branch"], "ejected", f"ejected from {rec['name']} ({why}); confirmation build "
                    + ", ".join(f"{p} {j}" for p, j in sorted(confirm.items())), owner=rec["name"], confirm=confirm,
                    result={"train": rec["name"], "sha": rec.get("sha"), "jobs": rec["jobs"]})

    def bisect(self, rec, platforms, detail):
        children = [r for r in self.ts.trains() if r.get("parent") == rec["name"]]
        if not children:
            number = self.next_number()
            for i, half in enumerate(split_halves(rec["members"])):
                child = self.new_record(number + i, half, platforms, rec["base_sha"], "bisect", rec["name"],
                                        rec["round"] + 1, tests=rec.get("tests", []))
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
            # Each half builds, the whole does not: the branches only fail together. None of them is reported as
            # passed (the integrator would merge a set known to fail); the half builds act as their confirmation.
            detail = "each half passes alone: the failure needs branches from both halves (an interaction)"
            for c in children:
                for m in c["members"]:
                    cand = self.branches.get(m["branch"])
                    if cand and cand["state"] == "passed" and cand.get("train") == c["name"]:
                        cand["state"] = "ejected"
                        note(cand, f"ejected: {cand['note']}, but the full {rec['name']} failed: {detail}; "
                                   "tell the integrator", self.now)
        else:
            detail = "bisect: " + ", ".join(f"{c['name']} {c['state']}" for c in children)
        rec.update(state="failed", attribution={"method": "bisect", "blamed": blamed, "detail": detail})
        self.event(rec, f"bisect closed: blamed {', '.join(blamed) or 'nobody'} ({detail})")
