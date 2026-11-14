# SPDX-License-Identifier: AGPL-3.0-only
"""Windows runner of the dispatcher: the HST4/HST5 slot pool driven over SSH with hst-queue-remote.ps1.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

from .dispatch_paths import HERE, WIN_HELPER, WIN_TOOLS, log, win_task_name

# ---------------------------------------------------------------- windows
class WindowsRunner:
    def __init__(self, store, cfg):
        self.store = store
        self.cfg = cfg
        self.next_poll = {}
        self.probes = {}   # slot id -> (time, probe result): remote probes at most once a minute per slot
        self.low_noted = {}   # slot id -> time a low-disk skip was logged
        self.warned = {}      # host -> time of the last low-disk warning

    def remote(self, host, action, *args, timeout=1200):
        cmd = [sys.executable, self.cfg["remote_py"], host, "ps", WIN_HELPER, "-Action", action, *args]
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        for line in reversed(done.stdout.splitlines()):
            if line.startswith("{"):
                # Windows PowerShell 5.1's ConvertTo-Json leaves some control characters (from build logs) raw.
                return json.loads(line, strict=False)
        raise RuntimeError(f"{host} {action} rc={done.returncode}: {(done.stdout + done.stderr)[-1500:]}")

    def host_busy(self, host):
        """A build (queued job or a manual one holding a slot's build.lock) is running on the host."""
        if any(j["platform"] == "windows" and j["state"] == "running" and j.get("host") == host for j in self.store.all()):
            return True
        for slot in self.cfg["windows_slots"]:
            if slot["host"] == host and self.remote(host, "Probe", "-Root", slot["root"], timeout=300).get("busy"):
                return True
        return False

    def draining(self, host):
        return self.store.drains().get(host, {}).get("state") in ("draining", "held")

    def process_drains(self, jobs, core):
        """Finish a drain once its host is idle: deploy the tools unconditionally, then resume scheduling."""
        for host, info in self.store.drains().items():
            if info.get("state") != "draining":
                continue
            if any(j["platform"] == "windows" and j["state"] == "running" and j.get("host") == host for j in jobs):
                continue
            try:
                if self.host_busy(host):
                    continue
                tools = self.deploy(host, force=True)
            except (RuntimeError, subprocess.SubprocessError, OSError, ValueError) as exc:
                log(f"{host}: drain deploy failed ({exc}); retrying")
                continue
            t = time.time()
            state = "held" if info.get("hold") else "done"
            self.store.set_drain(host, state=state, finished=t, finished_at=core.now_iso(t), tools=tools)
            log(f"{host}: drained, tools {tools} deployed, " + ("held (maintenance)" if state == "held" else "scheduling resumed"))

    def deploy(self, host, force=False):
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
        if state.get(host) == want and not force:
            return want
        # Cygwin bash reads hst4-tree.sh / hst4-make-targets.sh while it runs them: never replace the tools under a
        # running build. The job then uses the tools already on the host; the update follows when the host is idle.
        if not force and self.host_busy(host):
            log(f"{host}: build running, tools {want} not deployed yet (using {state.get(host)}; "
                f"`build-queue.sh drain {host}` forces it)")
            return state.get(host)
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
        return want

    def free_slot(self, jobs):
        used = {j.get("slot") for j in jobs if j["platform"] == "windows" and j["state"] == "running"}
        for slot in self.cfg["windows_slots"]:
            sid = f"{slot['host']}:{slot['root']}"
            if sid in used or self.draining(slot["host"]):
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
            free = probe.get("free_gib")
            if isinstance(free, (int, float)):
                self.check_disk(slot["host"], free)
                if free < self.cfg.get("windows_min_free_gib", 15):
                    if self.low_noted.get(sid, 0) < time.time() - 3600:
                        self.low_noted[sid] = time.time()
                        log(f"windows slot {sid} skipped: {free} GiB free, below "
                            f"{self.cfg.get('windows_min_free_gib', 15)} GiB (no job would build there)")
                    continue
            return slot
        return None

    # ------------------------------------------------------------ disk report (read only: nothing is deleted)
    def disk_report(self, host, top=15):
        """Free space and the largest D:\\hst-test folders of a host, saved in windows-disk.json."""
        rep = self.remote(host, "DiskReport", "-Top", str(top), timeout=900)
        rep["host"], rep["fetched"] = host, time.time()
        path = os.path.join(self.store.root, "windows-disk.json")
        try:
            with open(path, encoding="utf-8") as f:
                all_reports = json.load(f)
        except (FileNotFoundError, ValueError):
            all_reports = {}
        all_reports[host] = rep
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(all_reports, f, indent=1, sort_keys=True)
        os.replace(path + ".tmp", path)
        return rep

    def check_disk(self, host, free):
        """Below windows_warn_free_gib: a warning (journal + alerts.log) naming the largest D:\\hst-test folders,
        at most once an hour per host."""
        if free >= self.cfg.get("windows_warn_free_gib", 25) or self.warned.get(host, 0) > time.time() - 3600:
            return
        self.warned[host] = time.time()
        try:
            rep = self.disk_report(host)
            top = ", ".join(f"{d['name']} {d['gib']} GiB (newest {d['newest'][:16]}"
                            f"{', owner ' + d['owner'] if d.get('owner') else ''})" for d in rep.get("folders", [])[:5])
        except (RuntimeError, subprocess.SubprocessError, OSError, ValueError) as exc:
            top = f"(disk report failed: {exc})"
        msg = (f"WARNING {host} D: {free} GiB free (< {self.cfg.get('windows_warn_free_gib', 25)} GiB); "
               f"largest D:\\hst-test folders: {top}")
        log(msg)
        with open(os.path.join(self.store.root, "alerts.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%F %T')} {msg}\n")

    def jobs_for(self, slot):
        """-Jobs for a new build: the slot's threads shared with the builds already running on the same host
        (HST5: 28 alone, 14 beside a running build), so two builds stay within the host's RAM."""
        running = sum(1 for j in self.store.all()
                      if j["platform"] == "windows" and j["state"] == "running" and j.get("host") == slot["host"])
        return max(4, slot.get("jobs", 28) // (running + 1))

    def start(self, job, slot):
        self.deploy(slot["host"])
        args = ["-Root", slot["root"], "-Job", win_task_name(job["id"]), "-Ref", job["sha"],
                "-Jobs", str(self.jobs_for(slot))]
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
