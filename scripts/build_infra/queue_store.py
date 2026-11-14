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
# Git repository used to resolve refs and diffs (HST_QUEUE_REPO: tests point it at a scratch repository).
REPO = os.environ.get("HST_QUEUE_REPO") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLATFORMS = ("linux", "windows")
ACTIVE = ("queued", "running")
TERMINAL = ("done", "failed", "cancelled")
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
MODULE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]{0,79}$")
# What local-build.sh --test accepts: unit/integration test targets that run headless in the slot chroot.
TEST_RE = re.compile(r"^((CppunitTest|PythonTest)_[A-Za-z0-9_]{1,100}|[a-z0-9_]{1,40}\.(check|unitcheck|slowcheck|subsequentcheck))$")
ID_RE = re.compile(r"^q\d{6}-\d{6}-[0-9a-f]{4}$")
DEFAULT_CONFIG = {
    # Retention (queue_rules.retention_victims): newest outputs kept per platform + branch + job kind; train builds
    # are one group; failed/cancelled/invalidated outputs and builds of commits already merged into the integration
    # branch go after a grace period. Pinned jobs and jobs an active train still uses are never deleted.
    "retention_per_branch": 2,
    "retention_trains": 3,
    "retention_failed_hours": 6,
    "retention_merged_hours": 12,
    # Below this much free disk (the Linux admission floor is 17 GiB) retention keeps 1 per group, no grace.
    "retention_pressure_free_gib": 22,
    # The integration branch (trains are built on it; merged = an ancestor of it) and who counts as the integrator:
    # refs matching integrator_refs or `submit --integrator`. Everyone else is capped at agent_max_priority.
    "integration_branch": "rc/1.0.2-batch5",
    "integrator_refs": ["rc/1.0.2-batch*"],
    "agent_max_priority": 50,
    # Build train (queue_train*.py): batch5 + ready branches merged into train/<prefix>NNN, one build per platform.
    "train_enabled": True,
    "train_prefix": "train/1.0.2-",
    "train_interval_minutes": 90,
    "train_min_branches": 4,
    "train_max_branches": 8,
    "train_priority": 70,
    "train_confirm_priority": 40,
    "train_bisect_rounds": 2,
    "train_max_attempts": 3,
    "train_keep_days": 2,
    "linux_max_jobs": 20,
    # Module builds are small and mostly link-bound: a lower cap gives a smaller memory budget (6.4 GiB at -j6),
    # so three fit beside each other under the admission rule (MemAvailable >= budgets + 8 GiB) on ~28 GiB free.
    "linux_modules_max_jobs": 6,
    "remote_py": "/home/wt-realwin-102/tests/realwin/remote.py",
    # Windows slot pool: one entry per slot; a slot's root holds its own repo/lo/stage/pristine trees.
    "windows_slots": [
        {"host": "hst4", "root": "D:\\hst-build", "jobs": 28},
    ],
    # Remote Linux build hosts (dispatch_remote_linux.py), e.g. VM103:
    #   {"name": "vm103", "address": "192.168.1.166", "key": "/root/.ssh/hst-vm103_ed25519",
    #    "known_hosts": "/data/hst-build-queue/known_hosts-vm103", "slots": 2, "total_jobs": 12, "max_jobs": 12,
    #    "min_free_gib": 15, "ccache_max": "10G", "enabled": true}
    "linux_remote_hosts": [],
    # false: no new Linux job is admitted on the dev server's slots; Linux builds run on linux_remote_hosts only.
    "linux_local_enabled": True,
    "remote_poll_seconds": 30,
    "remote_offline_seconds": 300,
    "remote_job_timeout_hours": 6,
    "poll_seconds": 10,
    "windows_poll_seconds": 60,
    # A Windows slot whose drive has less than windows_min_free_gib free gets no job (it would fail at once);
    # below windows_warn_free_gib the dispatcher warns (journal + alerts.log) with the largest D:\hst-test folders.
    "windows_min_free_gib": 15,
    "windows_warn_free_gib": 25,
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
