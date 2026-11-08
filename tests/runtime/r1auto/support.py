# SPDX-License-Identifier: AGPL-3.0-only
"""Shared imports and evidence for the native probes."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
ROOT = RUNTIME.parents[1]
sys.path.insert(0, str(RUNTIME))


def existing(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), RUNTIME / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    saved = sys.path[:]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = saved
    return module


def wait(predicate, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.2)
    raise TimeoutError("Hết thời gian chờ trạng thái bắt buộc")


def background(fn, *args):
    thread = threading.Thread(target=fn, args=args, daemon=True)
    thread.start()
    return thread


def native(action, *args):
    command = [os.environ.get("R1_TOOLS_PYTHON", sys.executable), str(HERE / "native.py"), action]
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "URE_BOOTSTRAP", "PYTHONNOUSERSITE")}
    done = subprocess.run(command + [str(a) for a in args], env=env, check=True, capture_output=True,
                          text=True, encoding="utf-8", timeout=60)
    return json.loads(done.stdout or "null")


class Evidence:
    def __init__(self, item, out, office):
        self.item, self.out, self.office = item, Path(out), office
        self.checks, self.shots, self.owner = [], [], []
        self.out.mkdir(parents=True, exist_ok=True)

    def require(self, condition, message, **values):
        self.checks.append(dict(ok=bool(condition), message=message, **values))
        if not condition:
            raise AssertionError(message)

    def shot(self, label):
        path = self.out / (label + ".png")
        self.office.screenshot(str(path))
        self.shots.append(path.relative_to(self.out.parent).as_posix())
        return path

    def review(self, detail, label):
        path = self.shot(label)
        self.owner.append(dict(item=self.item, detail=detail,
                               screenshot=path.relative_to(self.out.parent).as_posix()))

    def detail(self, message):
        return dict(message=message, checks=self.checks, screenshots=self.shots,
                    windows=self.office.titles() if self.office.ctx else [])
