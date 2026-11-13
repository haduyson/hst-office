# SPDX-License-Identifier: AGPL-3.0-only
"""Pure rules of the build queue: job keys and kinds, input validation, dedupe, dispatch order, retention
and the classification of infrastructure failures.
"""
import os
import re
import secrets
import subprocess
import time

from .queue_store import ACTIVE, MODULE_RE, REF_RE, REPO, TEST_RE, QueueError

# ---------------------------------------------------------------- pure helpers (unit tested)
def job_key(platform, sha, package, modules, tests=()):
    key = f"{platform}:{sha}:{'package' if package else 'nopackage'}:{','.join(sorted(modules))}"
    return key + (":test=" + ",".join(sorted(tests)) if tests else "")


def job_kind(job):
    """Retention group: package builds, module overlays and test runs of a branch are kept separately."""
    return "test" if job.get("tests") else "modules" if job.get("modules") else "build"


def parse_tests(text):
    tests = [t for t in re.split(r"[\s,]+", text or "") if t]
    for t in tests:
        if not TEST_RE.match(t):
            raise QueueError(f"bad test target {t!r} (CppunitTest_*, PythonTest_* or <module>.check/unitcheck/...)")
    if text and not tests:
        raise QueueError("--test needs at least one target")
    return list(dict.fromkeys(tests))


def label_for(ref, sha):
    """Branch label for outputs/retention; a bare sha is grouped under 'commit'."""
    if re.fullmatch(r"[0-9a-f]{7,40}", ref) and sha.startswith(ref):
        return "commit"
    return re.sub(r"[^A-Za-z0-9._-]", "_", ref)


def order_key(job):
    """Dispatch order: higher priority first, then submission order."""
    return (-job["priority"], job["submitted"], job["id"])


def find_duplicate(jobs, key):
    """An identical job worth reusing: active, or done with its output still present."""
    for job in sorted(jobs, key=lambda j: j["submitted"], reverse=True):
        if job.get("key") != key:
            continue
        if job["state"] in ACTIVE:
            return job
        if job["state"] == "done" and not job.get("output_deleted") and all(os.path.exists(p) for p in job.get("output", [])):
            return job
    return None


def retention_victims(jobs, keep):
    """Done jobs whose outputs fall outside the newest `keep` per (platform, label)."""
    groups = {}
    for job in jobs:
        if job["state"] == "done" and not job.get("output_deleted") and not job.get("dedupe_of"):
            groups.setdefault((job["platform"], job["label"], job_kind(job)), []).append(job)
    victims = []
    for group in groups.values():
        group.sort(key=lambda j: j.get("finished") or j["submitted"], reverse=True)
        victims.extend(group[keep:])
    return victims


# Failures of the build infrastructure, not of the commit: the job goes back to the queue (MAX_INFRA_RETRIES).
INFRA_PATTERNS = [
    re.compile(p) for p in (
        r"syntax error near unexpected token",          # runner script changed under a running job
        r"local-build: slot \d+ is busy",
        r"local-build: no idle admissible slot",
        r"could not unmount|chroot still mounted|base chroot changed under us|still has an overlay",
        r"runner exited without a status",
        r"^dispatcher: ",
        r"^start: ",
        r"task vanished|build\.lock is held|is already running",
        r"CERTIFICATE_VERIFY_FAILED|urlopen error|Could not resolve host|remote name could not be resolved",
        r"ssh \S+ rc=255|Connection (timed out|refused|reset)",
        r"Exclude the build and source directories associated with LibreOffice",   # slot root lacks AV exclusion
        r"extracting MergeModule\.CABinet failed",      # host's Cygwin tmp ACL (hst4-setup.ps1 -Step TmpAcl)
    )
]
MAX_INFRA_RETRIES = 2


def infra_failure(error, log_text):
    """True when the failure text points at the build infrastructure rather than the commit being built."""
    text = f"{error}\n{log_text}"
    return any(p.search(line) for line in text.splitlines() for p in INFRA_PATTERNS)


def parse_modules(text):
    if not text:
        return []
    mods = [m.strip() for m in text.split(",") if m.strip()]
    for m in mods:
        if not MODULE_RE.match(m):
            raise QueueError(f"bad module {m!r}")
    if not mods:
        raise QueueError("--modules needs at least one module")
    return mods


def new_id(t=None):
    return time.strftime("q%y%m%d-%H%M%S", time.localtime(t)) + "-" + secrets.token_hex(2)


def resolve_ref(ref, repo=REPO):
    """Full commit sha for a branch/tag/sha (origin/<ref> wins, like local-build.sh)."""
    if not REF_RE.match(ref) or ".." in ref:
        raise QueueError(f"bad ref {ref!r}")
    subprocess.run(["git", "-C", repo, "fetch", "-q", "origin"], check=False, timeout=300)
    for cand in (f"origin/{ref}", ref):
        done = subprocess.run(["git", "-C", repo, "rev-parse", "-q", "--verify", f"{cand}^{{commit}}"],
                              capture_output=True, text=True, check=False)
        if done.returncode == 0:
            return done.stdout.strip()
    raise QueueError(f"unknown ref {ref}")
