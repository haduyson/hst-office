# SPDX-License-Identifier: AGPL-3.0-only
"""Locking and cleaning one build slot (`build-queue.sh slot ...`), without draining its whole host.

State lives in <queue root>/slot-control.json, keyed by the slot id a job records in job["slot"]:
  Windows "hst5:D:\\hst-build-s2", remote Linux "vm103:3", dev server Linux "2".
  {slot: {"locked": bool, "reason", "by", "at",
          "clean": {"state": "requested"|"running"|"done"|"failed", "full": bool, "unlock_after": bool,
                    "requested_at", "started_at", "finished_at", "pid", "log", "result"}}}
- lock: the dispatcher starts no new job on the slot; a job already running there finishes normally.
- clean: the slot is locked, the dispatcher waits until no job runs on it, then starts the clean as a background
  process (it never blocks the dispatch of other slots) and unlocks the slot when it ends, unless it was locked before
  or --keep-locked was given. Windows: damaged (truncated or garbage) object files of lo\\workdir are deleted, which is
  what a build killed while the compiler wrote an object leaves behind (LNK1136 "invalid or corrupt file"); --full
  deletes lo\\workdir and lo\\instdir (the next build there is a full one). Linux: only --full (workdir + instdir),
  run under the slot's own flock so it can never touch a tree a build is using.
"""
import contextlib
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
import time

from .queue_store import QueueError, now_iso

CLEAN_ACTIVE = ("requested", "running")


class SlotControl:
    def __init__(self, store):
        self.store = store
        self.path = os.path.join(store.root, "slot-control.json")

    @contextlib.contextmanager
    def _locked(self):
        self.store.ensure()
        with open(os.path.join(self.store.root, "slot-control.lock"), "a+", encoding="ascii") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield

    def all(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, ValueError):
            return {}

    def get(self, slot):
        return self.all().get(str(slot), {})

    def _write(self, data):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)

    def update(self, slot, fn):
        """fn(entry) mutates the slot's entry under the lock; returns the new entry."""
        with self._locked():
            data = self.all()
            entry = data.setdefault(str(slot), {})
            fn(entry)
            self._write(data)
            return entry

    def locked(self, slot):
        return bool(self.get(slot).get("locked"))

    def locked_slots(self):
        return {s for s, e in self.all().items() if e.get("locked")}


# ---------------------------------------------------------------- slot ids
def known_slots(cfg):
    """{slot id: kind} of every configured slot: 'windows', 'remote' or 'local'."""
    slots = {f"{s['host']}:{s['root']}": "windows" for s in cfg.get("windows_slots", [])}
    for h in cfg.get("linux_remote_hosts", []):
        for n in range(1, int(h.get("slots", 2)) + 1):
            slots[f"{h['name']}:{n}"] = "remote"
    return slots


def resolve_slot(cfg, slot):
    """(slot id, kind) or QueueError. A bare number is a dev server Linux slot (scripts/linux/build-slots.py)."""
    slot = str(slot).strip()
    if re.fullmatch(r"[1-9][0-9]?", slot):
        return slot, "local"
    kinds = known_slots(cfg)
    if slot in kinds:
        return slot, kinds[slot]
    raise QueueError(f"unknown slot {slot!r}; known: {', '.join(sorted(kinds))} or a dev server slot number")


def _user():
    return os.environ.get("SUDO_USER") or os.environ.get("USER", "?")


# ---------------------------------------------------------------- commands (CLI side)
def lock(store, slot, reason, ctl=None):
    if not (reason or "").strip():
        raise QueueError("--reason is required")
    slot, _kind = resolve_slot(store.config(), slot)
    ctl = ctl or SlotControl(store)
    return slot, ctl.update(slot, lambda e: e.update(locked=True, reason=reason.strip(), by=_user(), at=now_iso()))


def unlock(store, slot, ctl=None):
    slot, _kind = resolve_slot(store.config(), slot)
    ctl = ctl or SlotControl(store)
    entry = ctl.get(slot)
    if entry.get("clean", {}).get("state") in CLEAN_ACTIVE:
        raise QueueError(f"{slot}: a clean is {entry['clean']['state']}; it unlocks the slot when it ends")
    if not entry.get("locked"):
        raise QueueError(f"{slot} is not locked")
    return slot, ctl.update(slot, lambda e: e.update(locked=False, unlocked_by=_user(), unlocked_at=now_iso()))


def request_clean(store, slot, reason, full=False, keep_locked=False, ctl=None):
    if not (reason or "").strip():
        raise QueueError("--reason is required")
    slot, kind = resolve_slot(store.config(), slot)
    if kind != "windows" and not full:
        raise QueueError(f"{slot}: a Linux slot is only cleaned with --full (workdir and instdir are deleted)")
    ctl = ctl or SlotControl(store)

    def mark(e):
        if e.get("clean", {}).get("state") in CLEAN_ACTIVE:
            raise QueueError(f"{slot}: a clean is already {e['clean']['state']}")
        was_locked = bool(e.get("locked"))
        e.update(locked=True, reason=f"clean: {reason.strip()}" if not was_locked else e.get("reason"),
                 by=e.get("by") if was_locked else _user(), at=e.get("at") if was_locked else now_iso())
        e["clean"] = {"state": "requested", "full": bool(full), "unlock_after": not (was_locked or keep_locked),
                      "reason": reason.strip(), "by": _user(), "requested_at": now_iso()}
    return slot, ctl.update(slot, mark)


def wait_clean(store, slot, timeout=None, interval=15, out=sys.stdout, ctl=None):
    ctl = ctl or SlotControl(store)
    t = time.time()
    while ctl.get(slot).get("clean", {}).get("state") in CLEAN_ACTIVE:
        if timeout is not None and time.time() - t > timeout:
            print(f"timeout: the clean of {slot} is still {ctl.get(slot)['clean']['state']}", file=out)
            return 2
        time.sleep(interval)
    clean = ctl.get(slot).get("clean", {})
    print(f"{slot}: clean {clean.get('state')} at {clean.get('finished_at')}: {clean.get('result')}", file=out)
    return 0 if clean.get("state") == "done" else 1


def describe(slot, entry):
    parts = [slot, "LOCKED" if entry.get("locked") else "unlocked"]
    if entry.get("locked"):
        parts.append(f"by {entry.get('by')} at {entry.get('at')}: {entry.get('reason')}")
    clean = entry.get("clean")
    if clean:
        parts.append(f"clean{' --full' if clean.get('full') else ''} {clean.get('state')}"
                     + (f" ({clean.get('result')})" if clean.get("result") else ""))
    return "  ".join(parts)


# ---------------------------------------------------------------- dispatcher side
def clean_command(cfg, slot, kind, full):
    """argv of the background process that cleans the slot (it prints one JSON line as its last output line)."""
    from .dispatch_paths import WIN_HELPER
    if kind == "windows":
        host, root = slot.split(":", 1)
        return [sys.executable, cfg["remote_py"], host, "ps", WIN_HELPER, "-Action", "Clean", "-Root", root,
                *(["-Full"] if full else [])]
    if kind == "remote":
        name, n = slot.split(":", 1)
        h = next(h for h in cfg.get("linux_remote_hosts", []) if h["name"] == name)
        from .remote_host import RemoteHost
        host = RemoteHost(h)
        script = linux_clean_script(f"{h.get('root', '/data/hst-build')}/slots/{n}")
        return [*host.ssh_cmd(), host.target(), "sh -c " + shlex.quote(script)]
    root = os.environ.get("HST_BUILD_ROOT", "/data/hst-build")
    return ["sh", "-c", linux_clean_script(f"{root}/slots/{slot}")]


def linux_clean_script(slot_root):
    """Delete the slot's workdir and instdir while holding the slot lock local-build.sh takes ($ROOT/.lock)."""
    lo = shlex.quote(f"{slot_root}/src/lo")
    lock = shlex.quote(f"{slot_root}/.lock")
    return (f'[ -d {lo} ] || {{ echo \'{{"cleaned": false, "reason": "no tree at {slot_root}/src/lo"}}\'; exit 1; }}; '
            f'if flock -n {lock} rm -rf {lo}/workdir {lo}/instdir; then '
            f'echo \'{{"cleaned": true, "full": true}}\'; else '
            f'echo \'{{"cleaned": false, "reason": "the slot lock is held (a build runs there) or rm failed"}}\'; '
            f'exit 1; fi')


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:   # a finished child of this dispatcher stays a zombie until it is reaped
        done, _status = os.waitpid(pid, os.WNOHANG)
        return done == 0
    except ChildProcessError:
        return True   # not our child (started before a dispatcher restart): kill(0) said it exists


def _result(log_path):
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if line.startswith("{"):
            try:
                return json.loads(line, strict=False)
            except ValueError:
                return None
    return None


def process(store, cfg, jobs, log, popen=subprocess.Popen, ctl=None):
    """One dispatcher step: start the requested cleans of idle slots, finish the ones whose process ended."""
    ctl = ctl or SlotControl(store)
    running = {str(j.get("slot")) for j in jobs if j["state"] == "running"}
    for slot, entry in ctl.all().items():
        clean = entry.get("clean") or {}
        if clean.get("state") == "requested":
            if slot in running:
                continue   # locked: no new job starts there; the clean waits for the running one
            try:
                _, kind = resolve_slot(cfg, slot)
                argv = clean_command(cfg, slot, kind, clean.get("full"))
            except (QueueError, StopIteration, KeyError) as exc:
                _finish(ctl, slot, "failed", f"cannot clean: {exc}", log)
                continue
            path = os.path.join(store.logs_dir, "slot-clean-" + re.sub(r"[^A-Za-z0-9.-]", "_", slot) + ".log")
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%F %T')}] clean{' --full' if clean.get('full') else ''} of {slot}: "
                        f"{' '.join(argv)}\n")
                f.flush()
                proc = popen(argv, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             start_new_session=True)
            ctl.update(slot, lambda e: e["clean"].update(state="running", pid=proc.pid, log=path,
                                                         started_at=now_iso()))
            log(f"slot {slot}: clean{' --full' if clean.get('full') else ''} started (pid {proc.pid}, log {path})")
        elif clean.get("state") == "running" and not _pid_alive(clean.get("pid")):
            res = _result(clean.get("log", ""))
            ok = bool(res and res.get("cleaned"))
            _finish(ctl, slot, "done" if ok else "failed", res if res else "no result (see the log)", log)


def _finish(ctl, slot, state, result, log):
    def mark(e):
        e["clean"].update(state=state, result=result, finished_at=now_iso(), pid=None)
        if e["clean"].get("unlock_after") and state == "done":
            e.update(locked=False, unlocked_by="clean", unlocked_at=now_iso())
    entry = ctl.update(slot, mark)
    log(f"slot {slot}: clean {state}: {result}" + ("" if not entry.get("locked") else " (slot stays locked)"))

