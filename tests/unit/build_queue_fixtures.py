# SPDX-License-Identifier: AGPL-3.0-only
"""Shared helpers of the build queue tests: the queue and dispatcher modules loaded from their stable paths,
a temporary queue store, and a fake runner."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bq = load("build_queue_for_test", "scripts/build-queue.py")
bqd = load("build_queue_dispatcher_for_test", "scripts/build-queue-dispatcher.py")
SHA_A = "a" * 40
SHA_B = "b" * 40


class QueueTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = bq.Store(tmp.name)
        self.shas = {"rc/1.0.2-batch4": SHA_A, "feat/x": SHA_B}

    def submit(self, platform="linux", ref="rc/1.0.2-batch4", **kw):
        return bq.submit(self.store, platform, ref, resolver=lambda r: self.shas.get(r, r), submitter="t", **kw)

    def finish(self, job, files=("HSTOffice.deb",), finished=None):
        out = self.store.job_out(job["id"])
        os.makedirs(out, exist_ok=True)
        paths = []
        for name in files:
            p = os.path.join(out, name)
            Path(p).write_text("x")
            paths.append(p)
        return self.store.update(job["id"], state="done", output=paths, finished=finished or job["submitted"])


class FakeRunner:
    def __init__(self, slots):
        self.slots = list(slots)
        self.started = []
        self.results = {}
        self.cancelled = []

    def want(self, job):
        return 8 if job["modules"] else 20

    def free_slot(self, jobs, want=None):
        running = {j.get("slot") for j in jobs if j["state"] == "running"}
        for s in self.slots:
            if s not in running:
                return s
        return None

    def start(self, job, slot):
        if slot == "broken":
            raise RuntimeError("cannot start")
        self.started.append(job["id"])
        return {"slot": slot, "host": "fake"}

    def check(self, job):
        return self.results.pop(job["id"], None)

    def cancel(self, job):
        self.cancelled.append(job["id"])
