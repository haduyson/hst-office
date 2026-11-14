# SPDX-License-Identifier: AGPL-3.0-only
"""Pure rules of the build train (unit tested without git): when a train starts, which ready branches ride it,
how a finished train build is judged, and which branch a failure is attributed to.

Attribution order (first that names a member wins):
  1. patch:   "does not apply: <patch>" in the log  -> the member whose commits add or change that patch;
  2. compile: error lines naming LibreOffice files  -> the members whose patches touch one of those files;
  3. single:  a one-branch train failed             -> that branch;
  4. bisect:  split the members in halves and build each half (at most train_bisect_rounds rounds);
              still several members after the last round -> all of them (each gets a confirmation build).
"""
import re

PATCH_FAIL_RE = re.compile(r"does not apply: (\S+\.patch)")
ERROR_LINE_RE = re.compile(r"\berror\b|\bFATAL\b|\*\*\*", re.I)
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


def select_members(ready, max_members):
    """Greedy in ready order: a branch whose patches touch a LibreOffice file another chosen branch touches waits
    for the next train (two patches on one file may apply in any order without a git conflict, and the compile
    attribution needs disjoint files). Returns (chosen, {branch: reason})."""
    chosen, deferred, owner = [], {}, {}
    for cand in ready:
        if len(chosen) >= max_members:
            deferred[cand["branch"]] = f"train full ({max_members} branches)"
            continue
        clash = sorted(f for f in cand.get("lo_files", []) if f in owner)
        if clash:
            deferred[cand["branch"]] = (f"touches the same LibreOffice files as {owner[clash[0]]}: "
                                        + ", ".join(clash[:5]))
            continue
        chosen.append(cand)
        for f in cand.get("lo_files", []):
            owner[f] = cand["branch"]
    return chosen, deferred


def job_outcome(job, infra_failure, log_text=""):
    """'pass' | 'fail' | 'error' (cancelled, or a failure of the infrastructure) | None while the job runs."""
    if job is None:
        return "error"
    if job["state"] == "done":
        return "pass"
    if job["state"] == "cancelled":
        return "error"
    if job["state"] == "failed":
        if str(job.get("error") or "").startswith("invalidated"):
            return "error"
        return "error" if infra_failure(job.get("error", ""), log_text) else "fail"
    return None


def failed_patches(text):
    return sorted(set(PATCH_FAIL_RE.findall(text)))


def error_files(text):
    """LibreOffice-relative source paths named on error lines (gcc/clang, MSVC, gla11y FATAL, make ***)."""
    found = set()
    for line in text.splitlines():
        if line.startswith("[build ") or not ERROR_LINE_RE.search(line):
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


def attribute(members, log_text):
    """(method, blamed branches, detail) from the failure text, or None when the log names no member."""
    bad = failed_patches(log_text)
    if bad:
        blamed = sorted(m["branch"] for m in members if set(m.get("patches", [])) & set(bad))
        if blamed:
            return "patch", blamed, "does not apply: " + ", ".join(bad)
    files = error_files(log_text)
    if files:
        blamed = sorted(m["branch"] for m in members if files & set(m.get("lo_files", [])))
        if blamed:
            hit = sorted(files & {f for m in members if m["branch"] in blamed for f in m.get("lo_files", [])})
            return "compile", blamed, "errors in " + ", ".join(hit[:5])
    return None


def split_halves(members):
    half = (len(members) + 1) // 2
    return members[:half], members[half:]


def decide_failure(members, log_text, round_no, max_rounds):
    """What to do with a failed train: ('blame', method, blamed, detail) or ('bisect', None, [], detail)."""
    found = attribute(members, log_text)
    if found:
        return ("blame",) + found
    if len(members) == 1:
        return "blame", "single", [members[0]["branch"]], "the only branch of a failing train"
    if round_no < max_rounds:
        return "bisect", None, [], "no branch named in the log: building each half"
    return ("blame", "bisect-limit", sorted(m["branch"] for m in members),
            f"still {len(members)} branches after {max_rounds} bisect rounds")
