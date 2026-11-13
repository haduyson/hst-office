#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""HST Office local build queue: agents submit builds themselves, a dispatcher runs them on the build slots.

  build-queue.sh submit --platform linux|windows --ref <branch|sha> [--priority N] [--no-package] [--modules a,b]
                                                  prints the job id (an existing identical job's id when deduplicated)
  build-queue.sh status <id> [--json]             state, slot/host, output, log
  build-queue.sh wait <id> [--timeout S]          blocks; prints the output path(s) (exit 0) or the log tail (exit 1)
  build-queue.sh list [--all] [--json]            queued/running jobs and the recent finished ones
  build-queue.sh cancel <id>                      queued: dropped at once; running: stopped by the dispatcher
  build-queue.sh dispatch [--once]                the dispatcher (systemd unit hst-build-queue.service)

State lives under HST_QUEUE_ROOT (default /data/hst-build-queue): jobs/<id>.json, logs/<id>.log, out/<id>/,
config.json (optional overrides of DEFAULT_CONFIG). Jobs run by priority (higher first), then FIFO.
Dedupe: a job with the same platform + commit + options that is queued, running, or done with its output still
on disk is returned instead of a new one. Retention: the newest `retention_per_branch` finished outputs per
platform and branch are kept; older outputs are deleted (their job records stay, marked output_deleted).
"""
import argparse
import contextlib
import fcntl
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time

QUEUE_ROOT = os.environ.get("HST_QUEUE_ROOT", "/data/hst-build-queue")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLATFORMS = ("linux", "windows")
ACTIVE = ("queued", "running")
TERMINAL = ("done", "failed", "cancelled")
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
MODULE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,79}$")
ID_RE = re.compile(r"^q\d{6}-\d{6}-[0-9a-f]{4}$")
DEFAULT_CONFIG = {
    "retention_per_branch": 3,
    "linux_max_jobs": 20,
    # Module builds are small and mostly link-bound: a lower cap gives a smaller memory budget (6.4 GiB at -j6),
    # so three fit beside each other under the admission rule (MemAvailable >= budgets + 8 GiB) on ~28 GiB free.
    "linux_modules_max_jobs": 6,
    "remote_py": "/home/wt-realwin-102/tests/realwin/remote.py",
    # Windows slot pool: one entry per slot; a slot's root holds its own repo/lo/stage/pristine trees.
    "windows_slots": [
        {"host": "hst4", "root": "D:\\hst-build", "jobs": 28},
    ],
    "poll_seconds": 10,
    "windows_poll_seconds": 60,
}


class QueueError(Exception):
    pass


def now_iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))


class Store:
    """Job records on disk; every mutation holds an exclusive flock on queue.lock."""

    def __init__(self, root=QUEUE_ROOT):
        self.root = root
        self.jobs_dir = os.path.join(root, "jobs")
        self.logs_dir = os.path.join(root, "logs")
        self.out_dir = os.path.join(root, "out")
        self.work_dir = os.path.join(root, "work")

    def ensure(self):
        for d in (self.jobs_dir, self.logs_dir, self.out_dir, self.work_dir):
            os.makedirs(d, exist_ok=True)

    def config(self):
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        path = os.path.join(self.root, "config.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                try:
                    cfg.update(json.load(f))
                except ValueError as exc:
                    raise QueueError(f"{path}: {exc}") from exc
        return cfg

    @contextlib.contextmanager
    def lock(self):
        self.ensure()
        with open(os.path.join(self.root, "queue.lock"), "a+", encoding="ascii") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield

    def path(self, job_id):
        if not ID_RE.match(job_id):
            raise QueueError(f"bad job id {job_id!r}")
        return os.path.join(self.jobs_dir, job_id + ".json")

    def load(self, job_id):
        try:
            with open(self.path(job_id), encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise QueueError(f"no job {job_id}") from None

    def save(self, job):
        tmp = self.path(job["id"]) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(job, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path(job["id"]))

    def all(self):
        self.ensure()
        jobs = []
        for name in sorted(os.listdir(self.jobs_dir)):
            if name.endswith(".json") and ID_RE.match(name[:-5]):
                try:
                    with open(os.path.join(self.jobs_dir, name), encoding="utf-8") as f:
                        jobs.append(json.load(f))
                except (OSError, ValueError):
                    continue
        return jobs

    def update(self, job_id, **fields):
        with self.lock():
            job = self.load(job_id)
            job.update(fields)
            self.save(job)
            return job

    def log_path(self, job_id):
        return os.path.join(self.logs_dir, job_id + ".log")

    def job_out(self, job_id):
        return os.path.join(self.out_dir, job_id)


# ---------------------------------------------------------------- pure helpers (unit tested)
def job_key(platform, sha, package, modules):
    return f"{platform}:{sha}:{'package' if package else 'nopackage'}:{','.join(sorted(modules))}"


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
            groups.setdefault((job["platform"], job["label"]), []).append(job)
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


# ---------------------------------------------------------------- commands
def submit(store, platform, ref, priority=0, package=True, modules=(), resolver=resolve_ref, submitter=None):
    if platform not in PLATFORMS:
        raise QueueError(f"--platform must be one of {', '.join(PLATFORMS)}")
    if not -100 <= priority <= 100:
        raise QueueError("--priority must be between -100 and 100")
    modules = list(modules)
    if platform == "windows" and not package and not modules:
        raise QueueError("Windows make always builds the MSI; omit --no-package")
    if modules:
        package = False
    sha = resolver(ref)
    key = job_key(platform, sha, package, modules)
    with store.lock():
        dup = find_duplicate(store.all(), key)
        if dup:
            return dup, True
        t = time.time()
        job = {"id": new_id(t), "platform": platform, "ref": ref, "sha": sha, "label": label_for(ref, sha),
               "priority": priority, "package": package, "modules": modules, "key": key, "state": "queued",
               "submitted": t, "submitted_at": now_iso(t), "submitter": submitter or os.environ.get("SUDO_USER")
               or os.environ.get("USER", "?"), "output": []}
        job["log"] = store.log_path(job["id"])
        store.save(job)
        return job, False


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


def log_tail(path, lines=40):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except FileNotFoundError:
        return "(no log yet)"


def describe(job):
    where = job.get("slot") or "-"
    parts = [f"{job['id']}  {job['state']:<9} {job['platform']:<7} {job['label']}@{job['sha'][:10]}",
             f"prio {job['priority']}", f"slot {where}"]
    if job.get("modules"):
        parts.append("modules " + ",".join(job["modules"]))
    elif not job.get("package", True):
        parts.append("no-package")
    return "  ".join(parts)


def wait(store, job_id, timeout=None, interval=15, out=sys.stdout):
    start = time.time()
    while True:
        job = store.load(job_id)
        if job["state"] in TERMINAL:
            break
        if timeout is not None and time.time() - start > timeout:
            print(f"timeout: job {job_id} still {job['state']}", file=out)
            return 2
        time.sleep(interval)
    if job["state"] == "done":
        for path in job.get("output", []):
            print(path, file=out)
        return 0
    print(f"job {job_id} {job['state']}: {job.get('error', '')}", file=out)
    print(log_tail(job["log"]), file=out, end="")
    return 1


def apply_retention(store, keep):
    with store.lock():
        jobs = store.all()
        for job in retention_victims(jobs, keep):
            shutil.rmtree(store.job_out(job["id"]), ignore_errors=True)
            job["output_deleted"] = True
            store.save(job)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="build-queue.sh", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--platform", required=True, choices=PLATFORMS)
    s.add_argument("--ref", required=True)
    s.add_argument("--priority", type=int, default=0)
    s.add_argument("--no-package", action="store_true")
    s.add_argument("--modules", default="")
    st = sub.add_parser("status")
    st.add_argument("id")
    st.add_argument("--json", action="store_true")
    w = sub.add_parser("wait")
    w.add_argument("id")
    w.add_argument("--timeout", type=int)
    li = sub.add_parser("list")
    li.add_argument("--all", action="store_true")
    li.add_argument("--json", action="store_true")
    c = sub.add_parser("cancel")
    c.add_argument("id")
    d = sub.add_parser("dispatch")
    d.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    store = Store()
    try:
        if args.cmd == "submit":
            job, dup = submit(store, args.platform, args.ref, args.priority, not args.no_package,
                              parse_modules(args.modules))
            if dup:
                print(f"deduplicated: identical job {job['id']} is {job['state']}", file=sys.stderr)
            print(job["id"])
            return 0
        if args.cmd == "status":
            job = store.load(args.id)
            if args.json:
                print(json.dumps(job, indent=1, sort_keys=True))
            else:
                print(describe(job))
                for k in ("submitted_at", "started_at", "finished_at", "host", "error"):
                    if job.get(k):
                        print(f"  {k}: {job[k]}")
                for p in job.get("output", []):
                    print(f"  output: {p}{' (deleted by retention)' if job.get('output_deleted') else ''}")
                print(f"  log: {job['log']}")
            return 0
        if args.cmd == "wait":
            return wait(store, args.id, args.timeout)
        if args.cmd == "list":
            jobs = sorted(store.all(), key=lambda j: j["submitted"])
            if not args.all:
                active = [j for j in jobs if j["state"] in ACTIVE]
                jobs = sorted(active, key=order_key) + [j for j in jobs if j["state"] in TERMINAL][-10:]
            if args.json:
                print(json.dumps(jobs, indent=1, sort_keys=True))
            else:
                for job in jobs:
                    print(describe(job))
            return 0
        if args.cmd == "cancel":
            job = cancel(store, args.id)
            print(f"{job['id']}: {'cancel requested' if job['state'] == 'running' else job['state']}")
            return 0
        if args.cmd == "dispatch":
            import importlib.util
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build-queue-dispatcher.py")
            spec = importlib.util.spec_from_file_location("build_queue_dispatcher", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.run(store, once=args.once)
    except QueueError as exc:
        print(f"build-queue: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
