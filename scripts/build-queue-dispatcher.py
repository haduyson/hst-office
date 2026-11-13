#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Dispatcher of the local build queue (scripts/build-queue.py): `build-queue.sh dispatch` (systemd unit
hst-build-queue.service, scripts/linux/hst-build-queue.service).

Every poll_seconds it reaps finished jobs, stops jobs whose cancel was requested, starts queued jobs by
priority/FIFO on free slots, and applies output retention:
  - linux:   scripts/linux/local-build.sh --slot N on a slot that build-slots.py free-slot reports idle and
             admissible (the admission controller still decides -j and may hold the job until memory allows);
  - windows: the config's windows_slots pool (host + root). The tools are deployed to each host
             (D:\\hst-build\\tools\\scripts) when they change, the build runs as a scheduled task through
             scripts/windows/hst-queue-remote.ps1 + hst4-detach.ps1, and the MSI (or overlay) is pulled back into
             out/<id>/ and removed from the host. Slots whose build.lock is held by someone else are skipped.
Only one dispatcher runs at a time (flock on dispatcher.lock).
"""
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time

# Real directory of this deploy (infra-<sha>, not the infra-current symlink): jobs started by this dispatcher keep
# using this version even after the next deploy switches the symlink (scripts/linux/build-infra-deploy.sh).
HERE = os.path.dirname(os.path.realpath(__file__))
LOCAL_BUILD = os.path.join(HERE, "linux", "local-build.sh")
BUILD_SLOTS = os.path.join(HERE, "linux", "build-slots.py")
WIN_HELPER = os.path.join(HERE, "windows", "hst-queue-remote.ps1")
# Deployed to <host>:D:\hst-build\tools\scripts (relative to scripts/); the checkout being built may predate them.
WIN_TOOLS = ["build-windows.ps1", "windows/hst4-build.ps1", "windows/hst4-detach.ps1", "windows/hst4-setup.ps1",
             "windows/hst4-tree.sh", "windows/hst4-make-targets.sh", "overlay/apply-build-overlay.ps1"]


def _core():
    spec = importlib.util.spec_from_file_location("build_queue", os.path.join(HERE, "build-queue.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def log(msg):
    print(f"[{time.strftime('%F %T')}] {msg}", flush=True)


def win_task_name(job_id):
    return "q-" + job_id[1:]   # hst4-detach.ps1 names: letters, digits, '-'


# ---------------------------------------------------------------- linux
class LinuxRunner:
    def __init__(self, store, cfg):
        self.store = store
        self.cfg = cfg

    def want(self, job):
        return self.cfg["linux_modules_max_jobs"] if job["modules"] else self.cfg["linux_max_jobs"]

    def rc_path(self, job):
        return os.path.join(self.store.work_dir, job["id"] + ".rc")

    def busy_slots(self, jobs):
        return [str(j["slot"]) for j in jobs if j["platform"] == "linux" and j["state"] == "running"]

    def free_slot(self, jobs, want):
        cmd = [sys.executable, "-I", BUILD_SLOTS, "free-slot", "--want", str(want),
               "--exclude", ",".join(self.busy_slots(jobs))]
        done = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return int(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip().isdigit() else None

    def start(self, job, slot):
        out = self.store.job_out(job["id"])
        cmd = [LOCAL_BUILD, "--slot", str(slot), "--label", job["label"], "--out", out, "-j", str(self.want(job))]
        if job["modules"]:
            cmd += ["--modules", ",".join(job["modules"])]
        elif not job["package"]:
            cmd.append("--no-package")
        cmd.append(job["sha"])
        rc = self.rc_path(job)
        if os.path.exists(rc):
            os.remove(rc)
        with open(job["log"], "ab") as logf:
            # The rc file survives a dispatcher restart; the runner is its own process group for cancel.
            proc = subprocess.Popen(["bash", "-c", '"$@"; echo $? > "$HST_QUEUE_RC"', "queue-runner", *cmd],
                                    stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    start_new_session=True, env={**os.environ, "HST_QUEUE_RC": rc})
        return {"pid": proc.pid, "slot": slot, "host": "local", "command": cmd}

    def check(self, job):
        """None while running, else (state, fields)."""
        rc_file = self.rc_path(job)
        if os.path.exists(rc_file):
            with open(rc_file, encoding="ascii") as f:
                text = f.read().strip()
            rc = int(text) if text.lstrip("-").isdigit() else 1
            os.remove(rc_file)
            out = self.store.job_out(job["id"])
            files = sorted(os.path.join(out, n) for n in os.listdir(out)
                           if n.endswith((".deb", ".tar.gz"))) if os.path.isdir(out) else []
            if rc == 0:
                return "done", {"output": files}
            return ("cancelled" if job.get("cancel_requested") else "failed"), {"error": f"local-build.sh exit {rc}"}
        if not _pid_alive(job.get("pid")):
            return ("cancelled" if job.get("cancel_requested") else "failed"), {"error": "runner exited without a status"}
        return None

    def cancel(self, job):
        try:
            os.killpg(job["pid"], signal.SIGTERM)   # local-build.sh stops make and unmounts in its EXIT trap
        except (ProcessLookupError, PermissionError):
            pass


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# ---------------------------------------------------------------- windows
class WindowsRunner:
    def __init__(self, store, cfg):
        self.store = store
        self.cfg = cfg
        self.next_poll = {}
        self.probes = {}   # slot id -> (time, probe result): remote probes at most once a minute per slot

    def remote(self, host, action, *args, timeout=1200):
        cmd = [sys.executable, self.cfg["remote_py"], host, "ps", WIN_HELPER, "-Action", action, *args]
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        for line in reversed(done.stdout.splitlines()):
            if line.startswith("{"):
                return json.loads(line)
        raise RuntimeError(f"{host} {action} rc={done.returncode}: {(done.stdout + done.stderr)[-1500:]}")

    def host_busy(self, host):
        """A build (queued job or a manual one holding a slot's build.lock) is running on the host."""
        if any(j["platform"] == "windows" and j["state"] == "running" and j.get("host") == host for j in self.store.all()):
            return True
        for slot in self.cfg["windows_slots"]:
            if slot["host"] == host and self.remote(host, "Probe", "-Root", slot["root"], timeout=300).get("busy"):
                return True
        return False

    def deploy(self, host):
        digest = hashlib.sha256()
        for rel in WIN_TOOLS:
            with open(os.path.join(HERE, rel), "rb") as f:
                digest.update(rel.encode() + b"\0" + f.read())
        want = digest.hexdigest()[:16]
        state_path = os.path.join(self.store.root, "windows-deployed.json")
        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
        except (FileNotFoundError, ValueError):
            state = {}
        if state.get(host) == want:
            return
        # Cygwin bash reads hst4-tree.sh / hst4-make-targets.sh while it runs them: never replace the tools under a
        # running build. The job then uses the tools already on the host; the update follows when the host is idle.
        if self.host_busy(host):
            log(f"{host}: build running, tools {want} not deployed yet (using {state.get(host)})")
            return
        stage = os.path.join(self.store.work_dir, "deploy", "scripts")
        shutil.rmtree(os.path.dirname(stage), ignore_errors=True)
        for rel in WIN_TOOLS:
            os.makedirs(os.path.dirname(os.path.join(stage, rel)), exist_ok=True)
            shutil.copy2(os.path.join(HERE, rel), os.path.join(stage, rel))
        subprocess.run([sys.executable, self.cfg["remote_py"], host, "push", stage, "D:\\hst-test\\hst-build-tools"],
                       check=True, timeout=900)
        self.remote(host, "Deploy")
        state[host] = want
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f)
        log(f"deployed build tools {want} to {host}")

    def free_slot(self, jobs):
        used = {j.get("slot") for j in jobs if j["platform"] == "windows" and j["state"] == "running"}
        for slot in self.cfg["windows_slots"]:
            sid = f"{slot['host']}:{slot['root']}"
            if sid in used:
                continue
            cached = self.probes.get(sid)
            if cached and time.time() - cached[0] < self.cfg["windows_poll_seconds"]:
                probe = cached[1]
            else:
                try:
                    probe = self.remote(slot["host"], "Probe", "-Root", slot["root"], timeout=300)
                except (RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
                    log(f"windows slot {sid} unreachable: {exc}")
                    probe = {"busy": True}
                self.probes[sid] = (time.time(), probe)
            if probe.get("busy"):
                continue
            return slot
        return None

    def start(self, job, slot):
        self.deploy(slot["host"])
        args = ["-Root", slot["root"], "-Job", win_task_name(job["id"]), "-Ref", job["sha"],
                "-Jobs", str(slot.get("jobs", 28))]
        if job["modules"]:
            args += ["-Modules", ",".join(job["modules"])]
        self.probes.pop(f"{slot['host']}:{slot['root']}", None)
        res = self.remote(slot["host"], "Start", *args)
        if not res.get("started"):
            raise RuntimeError(f"start refused: {res}")
        with open(job["log"], "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%F %T')}] started on {slot['host']} {slot['root']} as task "
                    f"hst-build-{win_task_name(job['id'])}\n")
        return {"slot": f"{slot['host']}:{slot['root']}", "host": slot["host"], "win_root": slot["root"]}

    def check(self, job):
        if time.time() < self.next_poll.get(job["id"], 0):
            return None
        self.next_poll[job["id"]] = time.time() + self.cfg["windows_poll_seconds"]
        try:
            st = self.remote(job["host"], "Status", "-Root", job["win_root"], "-Job", win_task_name(job["id"]),
                             timeout=300)
        except (RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
            log(f"{job['id']}: status failed ({exc}); retrying later")
            return None
        if st.get("state") == "running":
            return None
        with open(job["log"], "a", encoding="utf-8") as f:
            f.write(st.get("log", ""))
        if st.get("state") != "done":
            state = "cancelled" if job.get("cancel_requested") else "failed"
            return state, {"error": st.get("error") or "windows build failed"}
        out = self.store.job_out(job["id"])
        os.makedirs(out, exist_ok=True)
        subprocess.run([sys.executable, self.cfg["remote_py"], job["host"], "pull", st["out"], out],
                       check=True, timeout=3600)
        pulled = os.path.join(out, st["out"].rstrip("\\").split("\\")[-1])
        files = []
        for name in sorted(os.listdir(pulled)):
            shutil.move(os.path.join(pulled, name), os.path.join(out, name))
            os.chmod(os.path.join(out, name), 0o644)   # scp maps the Windows ACLs to odd modes
            if name.endswith((".msi", ".zip")):
                files.append(os.path.join(out, name))
        os.rmdir(pulled)
        sums = os.path.join(out, "SHA256SUMS")
        if os.path.exists(sums):
            subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=out, check=True)
        self.remote(job["host"], "Cleanup", "-Root", job["win_root"], "-Job", win_task_name(job["id"]))
        return "done", {"output": files}

    def cancel(self, job):
        self.remote(job["host"], "Cancel", "-Root", job["win_root"], "-Job", win_task_name(job["id"]))


# ---------------------------------------------------------------- loop
def requeue_if_infra(store, core, job, error):
    """Put a job that failed because of the infrastructure back in the queue (at most MAX_INFRA_RETRIES times)."""
    retries = job.get("infra_retries", 0)
    if job.get("cancel_requested") or retries >= core.MAX_INFRA_RETRIES:
        return False
    if not core.infra_failure(error, core.log_tail(job["log"], 80)):
        return False
    with open(job["log"], "a", encoding="utf-8") as f:
        f.write(f"\n[{time.strftime('%F %T')}] infrastructure failure ({error}); requeued "
                f"(retry {retries + 1}/{core.MAX_INFRA_RETRIES})\n")
    store.update(job["id"], state="queued", infra_retries=retries + 1, last_infra_error=error,
                 slot=None, pid=None, cancel_sent=False)
    log(f"{job['id']}: infrastructure failure, requeued: {error}")
    return True


def tick(store, runners, core):
    cfg = store.config()
    jobs = store.all()
    finished = False
    for job in [j for j in jobs if j["state"] == "running"]:
        runner = runners[job["platform"]]
        if job.get("cancel_requested") and not job.get("cancel_sent"):
            try:
                runner.cancel(job)
                store.update(job["id"], cancel_sent=True)
                log(f"{job['id']}: cancel sent")
            except Exception as exc:  # noqa: BLE001 - a failed cancel is retried next tick, never fatal
                log(f"{job['id']}: cancel failed: {exc}")
        try:
            result = runner.check(job)
        except Exception as exc:  # noqa: BLE001 - keep dispatching other jobs; this one is marked failed
            result = ("failed", {"error": f"dispatcher: {exc}"})
        if result:
            state, fields = result
            t = time.time()
            if state == "failed" and requeue_if_infra(store, core, job, fields.get("error", "")):
                continue
            store.update(job["id"], state=state, finished=t, finished_at=core.now_iso(t), **fields)
            log(f"{job['id']}: {state} {fields}")
            finished = True
    jobs = store.all()
    blocked = set()
    for job in sorted([j for j in jobs if j["state"] == "queued"], key=core.order_key):
        platform = job["platform"]
        if platform in blocked:
            continue   # strict priority per platform: nothing overtakes a waiting higher-priority job
        runner = runners[platform]
        slot = runner.free_slot(jobs, runner.want(job)) if platform == "linux" else runner.free_slot(jobs)
        if slot is None:
            blocked.add(platform)
            continue
        with store.lock():
            current = store.load(job["id"])
            if current["state"] != "queued":
                continue
        try:
            fields = runner.start(job, slot)
        except Exception as exc:  # noqa: BLE001 - a job that cannot start fails visibly instead of looping
            log(f"{job['id']}: start failed: {exc}")
            if not requeue_if_infra(store, core, job, f"start: {exc}"):
                t = time.time()
                store.update(job["id"], state="failed", finished=t, finished_at=core.now_iso(t), error=f"start: {exc}")
            continue
        t = time.time()
        job = store.update(job["id"], state="running", started=t, started_at=core.now_iso(t), **fields)
        log(f"{job['id']}: started {platform} {job['label']}@{job['sha'][:10]} on {fields['slot']}")
        jobs = store.all()
    if finished:
        core.apply_retention(store, cfg["retention_per_branch"])


def run(store, once=False):
    core = _core()
    store.ensure()
    lock = open(os.path.join(store.root, "dispatcher.lock"), "a+", encoding="ascii")  # noqa: SIM115 - held for life
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("build-queue: another dispatcher is running", file=sys.stderr)
        return 1
    cfg = store.config()
    runners = {"linux": LinuxRunner(store, cfg), "windows": WindowsRunner(store, cfg)}
    log(f"dispatcher started (queue {store.root}, windows slots "
        f"{[s['host'] + ':' + s['root'] for s in cfg['windows_slots']]})")
    while True:
        try:
            cfg = store.config()
            for r in runners.values():
                r.cfg = cfg
            tick(store, runners, core)
        except Exception as exc:  # noqa: BLE001 - the service must survive one bad tick; systemd restarts on exit
            log(f"tick failed: {exc!r}")
        if once:
            return 0
        time.sleep(cfg["poll_seconds"])
