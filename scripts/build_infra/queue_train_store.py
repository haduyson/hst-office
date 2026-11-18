# SPDX-License-Identifier: AGPL-3.0-only
"""Build train state on disk, under <queue root>/train/:
  branches.json      branch -> candidate record (state ready | in-train | passed | ejected | failed | merged)
  trains/<name>.json one record per train (main train or bisect half), written atomically; the file name is the
                     train name with "/" as "_" (train_1.0.3-001.json). Records of the first trains are NNN.json
                     (one number sequence for all trains); they stay readable and are rewritten in place.
  repo/              the clone the trains are merged and pushed from (queue_train_git.py)
  train.lock         held by every change (the dispatcher's train step, `train add|remove|start`)
"""
import contextlib
import fcntl
import json
import os
import re

TRAIN_ACTIVE = ("merging", "building", "bisecting")
TRAIN_FINAL = ("passed", "failed", "error", "empty")
CANDIDATE_FINAL = ("passed", "ejected", "failed", "merged")
LEGACY_FILE_RE = re.compile(r"^(\d{1,6})\.json$")
TRAIN_FILE_RE = re.compile(r"^train_[A-Za-z0-9._-]{1,100}\.json$")


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


class TrainStore:
    def __init__(self, store):
        self.store = store
        self.root = os.path.join(store.root, "train")
        self.trains_dir = os.path.join(self.root, "trains")
        self.repo = os.path.join(self.root, "repo")

    def ensure(self):
        os.makedirs(self.trains_dir, exist_ok=True)

    @contextlib.contextmanager
    def lock(self):
        self.ensure()
        with open(os.path.join(self.root, "train.lock"), "a+", encoding="ascii") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield

    # ------------------------------------------------------------ candidates
    def branches(self):
        return read_json(os.path.join(self.root, "branches.json"), {})

    def save_branches(self, branches):
        self.ensure()
        write_json(os.path.join(self.root, "branches.json"), branches)

    # ------------------------------------------------------------ trains
    def path(self, name):
        """The file of the train called `name`: its legacy NNN.json when that file holds it, else <name>.json."""
        m = re.search(r"(\d+)$", name)
        if m:
            legacy = os.path.join(self.trains_dir, f"{int(m.group(1)):03d}.json")
            if (read_json(legacy, None) or {}).get("name") == name:
                return legacy
        if not TRAIN_FILE_RE.match(name.replace("/", "_") + ".json") or ".." in name:
            raise ValueError(f"bad train name {name!r}")
        return os.path.join(self.trains_dir, name.replace("/", "_") + ".json")

    def trains(self):
        """All train records, oldest first (unreadable files are skipped, never fatal)."""
        if not os.path.isdir(self.trains_dir):
            return []
        records = []
        for name in os.listdir(self.trains_dir):
            if LEGACY_FILE_RE.match(name) or TRAIN_FILE_RE.match(name):
                try:
                    rec = read_json(os.path.join(self.trains_dir, name), None)
                except (OSError, ValueError):
                    continue
                if isinstance(rec, dict) and isinstance(rec.get("number"), int) and rec.get("name"):
                    records.append(rec)
        return sorted(records, key=lambda r: (r.get("created", 0), r["number"], r["name"]))

    def load(self, name_or_number, prefix=None):
        """A train by name ('train/1.0.3-007') or by number (7, '007') under `prefix` (the configured train_prefix);
        None when unknown."""
        what = str(name_or_number)
        if what.isdigit():
            if not prefix:
                return None
            what = f"{prefix}{int(what):03d}"
        return next((r for r in self.trains() if r["name"] == what), None)

    def save(self, rec):
        self.ensure()
        write_json(self.path(rec["name"]), rec)

    def flag(self, name):
        return os.path.join(self.root, name)

    def protected_jobs(self):
        """Job ids retention never deletes: builds (and base test runs) an active train still evaluates, the train
        result of every candidate (passed or ejected) and confirmation builds of ejected branches."""
        jobs = {jid for rec in self.trains() if rec["state"] in TRAIN_ACTIVE
                for jid in [*rec.get("jobs", {}).values(), *rec.get("baseline", {}).values(),
                                *rec.get("reruns", {}).values()]}
        for cand in self.branches().values():
            jobs |= set((cand.get("result") or {}).get("jobs", {}).values()) | set(cand.get("confirm", {}).values())
        return jobs
