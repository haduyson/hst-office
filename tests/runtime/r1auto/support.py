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


def says(text, *variants):
    """The variant shown, or None; mnemonics (~) are ignored. The core UI is Vietnamese on the English runners too
    (checked before every item in probe.py), so the checks name the vi msgstr only."""
    text = str(text).replace("~", "")
    return next((variant for variant in variants if variant in text), None)


def claim_port(port):
    """Fail only on a live listener: macOS refuses a plain bind while a closed connection of the previous item
    sits in TIME_WAIT on the port. Windows keeps the plain bind (its SO_REUSEADDR would hide a live listener)."""
    import socket
    with socket.socket() as sock:
        if os.name != "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))


def background(fn, *args):
    thread = threading.Thread(target=fn, args=args, daemon=True)
    thread.start()
    return thread


def native(action, *args, timeout=60):
    command = [os.environ.get("R1_TOOLS_PYTHON", sys.executable), str(HERE / "native.py"), action]
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "URE_BOOTSTRAP", "PYTHONNOUSERSITE")}
    done = subprocess.run(command + [str(a) for a in args], env=env, capture_output=True,
                          text=True, encoding="utf-8", timeout=timeout)
    if done.returncode:  # the tooling side's own traceback is the evidence
        raise RuntimeError(f"native {action}: " + (done.stderr.strip().splitlines() or ["exit %d" % done.returncode])[-1][-400:])
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
        try:
            windows = self.office.titles() if self.office.ctx else []
        except Exception as error:  # a dead bridge must not cost the item its evidence
            windows = [f"{type(error).__name__}: {error}"]
        proc = getattr(self.office, "proc", None)
        exit_code = proc.poll() if proc is not None else None
        return dict(message=message, checks=self.checks, screenshots=self.shots, windows=windows,
                    **({} if exit_code is None else dict(office_exit_code=exit_code)))
