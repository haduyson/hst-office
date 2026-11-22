# SPDX-License-Identifier: AGPL-3.0-only
"""Pure rules of the build train (unit tested without git): when a train starts, which ready branches ride it,
how a finished train build is judged, and which branch a failure is attributed to.

A train passes only when every build passes AND the Linux build's test set (train_test_set) passes; a test that
fails on the integration branch too (a base run of the failing targets) is not counted against the train.

Attribution order (first that names a member wins):
  1. patch:   "does not apply: <patch>" in the log  -> the member whose commits add or change that patch;
  2. compile: error lines naming LibreOffice files  -> the members whose patches touch one of those files;
     test:    (test failures only) the assertion lines of the failing tests name a file a member's patch touches;
  3. single:  a one-branch train failed             -> that branch;
  4. bisect:  split the members in halves and build each half (at most train_bisect_rounds rounds);
              still several members after the last round -> all of them (each gets a confirmation build).
"""
import re

PATCH_FAIL_RE = re.compile(r"does not apply: (\S+\.patch)")
ERROR_LINE_RE = re.compile(r"\berror\b|\bFATAL\b|\*\*\*", re.I)
# Where a CppUnit test failed: "<file>:<line>:Assertion" (or an uncaught exception); SAL_WARN noise is ignored.
ASSERT_LINE_RE = re.compile(r"\.(?:cxx|cpp|hxx|h):\d+:\s*(?:Assertion|Exception)")
SOURCE_RE = re.compile(r"((?:[A-Za-z]:)?[\w.+/\\-]*?[\w+-]+[/\\][\w.+/\\-]+\.(?:cxx|hxx|cpp|hpp|cc|c|h|hrc|mm|m|ui|xcu|xcs|"
                       r"xml|xhp|idl|sdi|mk|py|java|inc|src))(?=[:(\s,'\"]|$)")
GENERATED = ("workdir/", "instdir/", "solenv/gbuild/", "external/tarballs/")


def ready_order(cand):
    """Carry-overs from a failed train first, then the longest waiting; the branch name breaks ties."""
    return (not cand.get("carry"), cand.get("ready_since", 0), cand["branch"])


def should_start(ready, now, cfg, forced=False):
    """A train starts when forced, when a carry-over waits, when train_min_branches are ready, or when the oldest
    ready branch has waited train_interval_minutes."""
    if not ready:
        return False
    if forced or any(c.get("carry") for c in ready) or len(ready) >= cfg["train_min_branches"]:
        return True
    return now - min(c.get("ready_since", now) for c in ready) >= cfg["train_interval_minutes"] * 60


def select_members(ready, max_members, busy=None):
    """Greedy in ready order: a branch whose patches touch a LibreOffice file another chosen branch touches waits
    for the next train (two patches on one file may apply in any order without a git conflict, and the compile
    attribution needs disjoint files). `busy` maps the files of trains still in flight to their train: a branch
    touching one of them waits as well, so trains built side by side never share a file. Returns
    (chosen, {branch: reason})."""
    chosen, deferred, owner = [], {}, {}
    busy = busy or {}
    for cand in ready:
        if len(chosen) >= max_members:
            deferred[cand["branch"]] = f"train full ({max_members} branches)"
            continue
        files = cand.get("lo_files", [])
        clash = sorted(f for f in files if f in busy)
        if clash:
            deferred[cand["branch"]] = (f"touches the same LibreOffice files as {busy[clash[0]]}, still building: "
                                        + ", ".join(clash[:5]))
            continue
        clash = sorted(f for f in files if f in owner)
        if clash:
            deferred[cand["branch"]] = (f"touches the same LibreOffice files as {owner[clash[0]]}: "
                                        + ", ".join(clash[:5]))
            continue
        chosen.append(cand)
        for f in files:
            owner[f] = cand["branch"]
    return chosen, deferred


def in_flight_files(trains, active_states):
    """{LibreOffice file: train} for the members of every train still in flight (a bisect half's files are its
    parent's). None when a member predates the recorded file list: nothing can be proven disjoint from it."""
    busy = {}
    for rec in trains:
        if rec["state"] not in active_states:
            continue
        for m in rec["members"]:
            if "lo_files" not in m:
                return None
            for f in m["lo_files"]:
                busy.setdefault(f, rec.get("parent") or rec["name"])
    return busy


def train_test_set(cfg, members):
    """Linux test targets of a train: the fixed set train_tests, then the targets the members declared with
    `train add --test`, without duplicates."""
    return list(dict.fromkeys([*cfg.get("train_tests", []), *(t for m in members for t in m.get("tests", []))]))


def failed_tests(job):
    """Test targets of a finished job that did not pass (a target without a recorded result counts as failed)."""
    res = job.get("test_results") or {}
    return sorted(t for t in job.get("tests", []) if (res.get(t) or {}).get("result") != "pass")


def job_outcome(job, infra_failure, log_text=""):
    """'pass' | 'fail' | 'error' (cancelled, or a failure of the infrastructure) | None while the job runs."""
    if job is None:
        return "error"
    if job["state"] == "done":
        # A package build that delivered no package did not finish its work (never a pass, never a branch's fault).
        return "error" if job.get("package") and not job.get("output") else "pass"
    if job["state"] == "cancelled":
        return "error"
    if job["state"] == "failed":
        if str(job.get("error") or "").startswith("invalidated"):
            return "error"
        return "error" if infra_failure(job.get("error", ""), log_text) else "fail"
    return None


def failed_patches(text):
    return sorted(set(PATCH_FAIL_RE.findall(text)))


def error_files(text, line_re=ERROR_LINE_RE):
    """LibreOffice-relative source paths named on error lines (gcc/clang, MSVC, gla11y FATAL, make ***), or on the
    lines line_re picks (ASSERT_LINE_RE: where failing CppUnit tests stopped)."""
    found = set()
    for line in text.splitlines():
        if line.startswith("[build ") or not line_re.search(line):
            continue   # gbuild progress lines name files that compile fine (e.g. "[build CXX] .../error.cxx")
        for raw in SOURCE_RE.findall(line):
            path = raw.replace("\\", "/")
            if "/lo/" in path:   # /data/hst-office-build/src/lo/..., D:/hst-build/lo/..., /cygdrive/d/hst-build/lo/...
                path = path.rsplit("/lo/", 1)[1]
            elif re.match(r"^(?:[A-Za-z]:)?/", path):
                continue          # an absolute path outside the LibreOffice tree
            if not path.startswith(GENERATED):
                found.add(path)
    return found


def attribute(members, log_text, files_method="compile"):
    """(method, blamed branches, detail) from the failure text, or None when the log names no member.
    files_method names a blame by file ("compile"; "test" when the text holds the assertion lines of failing tests)."""
    bad = failed_patches(log_text)
    if bad:
        blamed = sorted(m["branch"] for m in members if set(m.get("patches", [])) & set(bad))
        if blamed:
            return "patch", blamed, "does not apply: " + ", ".join(bad)
    files = error_files(log_text, ASSERT_LINE_RE if files_method == "test" else ERROR_LINE_RE)
    if files:
        blamed = sorted(m["branch"] for m in members if files & set(m.get("lo_files", [])))
        if blamed:
            hit = sorted(files & {f for m in members if m["branch"] in blamed for f in m.get("lo_files", [])})
            return files_method, blamed, "errors in " + ", ".join(hit[:5])
    return None


def split_halves(members):
    half = (len(members) + 1) // 2
    return members[:half], members[half:]


def decide_failure(members, log_text, round_no, max_rounds, files_method="compile"):
    """What to do with a failed train: ('blame', method, blamed, detail) or ('bisect', None, [], detail)."""
    found = attribute(members, log_text, files_method)
    if found:
        return ("blame",) + found
    if len(members) == 1:
        return "blame", "single", [members[0]["branch"]], "the only branch of a failing train"
    if round_no < max_rounds:
        return "bisect", None, [], "no branch named in the log: building each half"
    return ("blame", "bisect-limit", sorted(m["branch"] for m in members),
            f"still {len(members)} branches after {max_rounds} bisect rounds")
