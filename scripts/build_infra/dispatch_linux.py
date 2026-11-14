# SPDX-License-Identifier: AGPL-3.0-only
"""Linux runner of the dispatcher: local-build.sh jobs on the slots the admission controller frees.
"""
import json
import os
import signal
import subprocess
import sys

from .dispatch_paths import BUILD_SLOTS, LOCAL_BUILD, log

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
        return [str(j["slot"]) for j in jobs if j["platform"] == "linux" and j["state"] == "running"
                and j.get("host", "local") in ("local", None)]

    def free_slot(self, jobs, want, job=None):
        cmd = [sys.executable, "-I", BUILD_SLOTS, "free-slot", "--want", str(want),
               "--exclude", ",".join(self.busy_slots(jobs))]
        done = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if done.returncode == 0 and done.stdout.strip().isdigit():
            return int(done.stdout.strip())
        why = done.stderr.strip()
        if why.startswith("disk") and why != getattr(self, "last_refusal", ""):
            log(f"linux jobs held: {why}")   # names the largest /data/hst-agents consumers
        self.last_refusal = why
        return None

    def start(self, job, slot):
        out = self.store.job_out(job["id"])
        cmd = [LOCAL_BUILD, "--slot", str(slot), "--label", job["label"], "--out", out, "-j", str(self.want(job))]
        if job["modules"]:
            cmd += ["--modules", ",".join(job["modules"])]
        elif not job["package"]:
            cmd.append("--no-package")
        if job.get("tests"):
            cmd += ["--test", " ".join(job["tests"])]
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
                           if n.endswith((".deb", ".rpm", ".AppImage", ".tar.gz"))) if os.path.isdir(out) else []
            if rc == 0:
                fields = {"output": files}
                results = os.path.join(out, "test-results.json")
                if job.get("tests"):
                    try:
                        with open(results, encoding="utf-8") as f:
                            fields["test_results"] = json.load(f)["results"]
                    except (OSError, ValueError, KeyError) as exc:
                        return "failed", {"error": f"test results missing: {exc}"}
                return "done", fields
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
