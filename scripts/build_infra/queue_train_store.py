# SPDX-License-Identifier: AGPL-3.0-only
"""Build train state on disk, under <queue root>/train/:
  branches.json      branch -> candidate record (state ready | in-train | passed | ejected | failed | merged)
  trains/<NNN>.json  one record per train (main train or bisect half), written atomically
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
TRAIN_FILE_RE = re.compile(r"^(\d{1,6})\.json$")


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
    def path(self, number):
        return os.path.join(self.trains_dir, f"{int(number):03d}.json")

    def trains(self):
        """All train records, oldest first (unreadable files are skipped, never fatal)."""
        if not os.path.isdir(self.trains_dir):
            return []
        records = []
        for name in sorted(os.listdir(self.trains_dir), key=lambda n: (len(n), n)):
            if TRAIN_FILE_RE.match(name):
                try:
                    rec = read_json(os.path.join(self.trains_dir, name), None)
                except (OSError, ValueError):
                    continue
                if isinstance(rec, dict):
                    records.append(rec)
        return sorted(records, key=lambda r: r["number"])

    def load(self, name_or_number):
        """A train by number (7, '007') or name ('train/1.0.2-007'); None when unknown."""
        m = re.search(r"(\d+)$", str(name_or_number))
        if not m:
            return None
        rec = read_json(self.path(int(m.group(1))), None)
        if rec and (str(name_or_number).isdigit() or rec["name"] == name_or_number):
            return rec
        return None

    def save(self, rec):
        self.ensure()
        write_json(self.path(rec["number"]), rec)

    def flag(self, name):
        return os.path.join(self.root, name)

    def protected_jobs(self):
        """Job ids an active train still evaluates: retention never deletes their outputs."""
        return {jid for rec in self.trains() if rec["state"] in TRAIN_ACTIVE for jid in rec.get("jobs", {}).values()}
