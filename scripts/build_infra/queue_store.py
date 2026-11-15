# SPDX-License-Identifier: AGPL-3.0-only
"""Build queue state on disk: configuration defaults, job records and drain state under HST_QUEUE_ROOT.
"""
import contextlib
import fcntl
import json
import os
import re
import time

QUEUE_ROOT = os.environ.get("HST_QUEUE_ROOT", "/data/hst-build-queue")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLATFORMS = ("linux", "windows")
ACTIVE = ("queued", "running")
TERMINAL = ("done", "failed", "cancelled")
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
MODULE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,79}$")
# What local-build.sh --test accepts: unit/integration test targets that run headless in the slot chroot.
TEST_RE = re.compile(r"^((CppunitTest|PythonTest)_[A-Za-z0-9_]{1,100}|[a-z0-9_]{1,40}\.(check|unitcheck|slowcheck|subsequentcheck))$")
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

    def drains(self):
        try:
            with open(os.path.join(self.root, "drain.json"), encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, ValueError):
            return {}

    def set_drain(self, host, **fields):
        with self.lock():
            drains = self.drains()
            drains.setdefault(host, {}).update(fields)
            tmp = os.path.join(self.root, "drain.json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(drains, f, indent=1, sort_keys=True)
            os.replace(tmp, os.path.join(self.root, "drain.json"))
            return drains[host]

    def log_path(self, job_id):
        return os.path.join(self.logs_dir, job_id + ".log")

    def job_out(self, job_id):
        return os.path.join(self.out_dir, job_id)
