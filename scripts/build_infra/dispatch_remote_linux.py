# SPDX-License-Identifier: AGPL-3.0-only
"""Remote Linux build host of the dispatcher (config `linux_remote_hosts`, e.g. VM103): the same local-build.sh,
build-slots.py, base chroot, ccache and tarballs as the dev server, run over SSH.

Remote layout under the host's root (default /data/hst-build, set up by scripts/linux/remote-build-host-setup.sh):
  repo.git/          bare clone; the dispatcher pushes the infra commit and each job's commit into it
  infra-<sha12>/     worktree of the deployed infra commit (a running job keeps its version)
  queue/{logs,out,rc}/<id>   the job's log, output and exit status
A job runs as the transient unit hstq-<id>.service in hst-build.slice (MemoryMax/CPUQuota of the whole host's builds,
MemorySwapMax=0) with nice 10, idle I/O and a raised OOM score; local-build.sh puts its make scopes in the same
slice. The output is copied back to out/<id>/ (SHA256SUMS checked), then deleted on the host.
Anti-hang: every SSH call is bounded (remote_host.py); a host that has not answered for remote_offline_seconds is
marked offline, its running jobs are requeued with avoid_hosts=[host] (they then build on the dev server), and when
it answers again its leftover hstq-* units are stopped. A job running longer than remote_job_timeout_hours is stopped
and requeued the same way.
"""
import os
import re
import subprocess
import time

from .dispatch_paths import HERE, log
from .queue_git import git_env
from .queue_store import REPO
from .remote_host import HostStates, RemoteError, RemoteHost

LOG_CHUNK = 4_000_000


def infra_sha():
    done = subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else ""


class RemoteLinuxRunner:
    def __init__(self, store, cfg, hcfg, host=None, now=time.time):
        self.store, self.cfg, self.hcfg = store, cfg, hcfg
        self.name = hcfg["name"]
        self.host = host or RemoteHost(hcfg)
        self.states = HostStates(store)
        self.now = now
        self.root = hcfg.get("root", "/data/hst-build")
        self.deployed = None
        self.fail_since = None
        self.next_probe = 0.0
        self.next_poll = {}
        self.slot_cache = (0.0, None)

    # ------------------------------------------------------------ paths and environment
    def qpath(self, kind, job_id, ext=""):
        return f"{self.root}/queue/{kind}/{job_id}{ext}"

    def unit(self, job_id):
        return f"hstq-{job_id}"

    def env(self):
        h = self.hcfg
        env = {"HST_BUILD_ROOT": self.root, "HST_TOTAL_JOBS": h.get("total_jobs", 12),
               "HST_MAX_JOBS": h.get("max_jobs", 12), "HST_MIN_FREE_GIB": h.get("min_free_gib", 15),
               "HST_LOCAL_MIN_FREE_GIB": h.get("min_free_gib", 15), "HST_HEADROOM_GIB": h.get("headroom_gib", 4),
               "HST_CCACHE_MAX": h.get("ccache_max", "10G"), "HST_LOCAL_SLICE": h.get("slice", "hst-build.slice"),
               "HST_LOCAL_TARBALL_CACHE": f"{self.root}/tarball-cache"}
        return {k: str(v) for k, v in env.items()}

    def infra_dir(self, sha):
        return f"{self.root}/infra-{sha[:12]}"

    # ------------------------------------------------------------ liveness
    def contact_ok(self):
        self.fail_since = None
        self.states.ok(self.name, self.now())

    def contact_failed(self, exc):
        t = self.now()
        self.fail_since = self.fail_since or t
        log(f"{self.name}: no answer ({exc})")

    def is_offline(self):
        return self.states.get(self.name).get("state") == "offline"

    def usable(self):
        """Online, or offline but answering a probe again (at most one probe a minute)."""
        if not self.hcfg.get("enabled", True):
            return False
        if not self.is_offline():
            return True
        if self.now() < self.next_probe:
            return False
        self.next_probe = self.now() + 60
        try:
            self.host.run(["true"], timeout=30)
        except RemoteError:
            return False
        self.contact_ok()
        log(f"{self.name}: answering again; back online")
        self.stop_orphans(self.store.all())
        return True

    def health(self, jobs):
        """Mark the host offline after remote_offline_seconds without an answer; requeue its running jobs."""
        if self.fail_since is None or self.is_offline():
            return
        if self.now() - self.fail_since < self.cfg.get("remote_offline_seconds", 300):
            return
        self.states.offline(self.name, f"no answer since {time.strftime('%T', time.localtime(self.fail_since))}",
                            self.now())
        log(f"{self.name}: OFFLINE; its running jobs go back to the queue for the dev server")
        for job in jobs:
            if job["platform"] == "linux" and job["state"] == "running" and job.get("host") == self.name:
                self.requeue(job, f"{self.name} stopped answering")

    def requeue(self, job, why):
        with open(job["log"], "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%F %T')}] {why}; requeued for another Linux host\n")
        avoid = sorted(set(job.get("avoid_hosts", [])) | {self.name})
        self.store.update(job["id"], state="queued", slot=None, host=None, pid=None, cancel_sent=False,
                          avoid_hosts=avoid, last_infra_error=why)
        log(f"{job['id']}: {why}; requeued (avoid {','.join(avoid)})")

    def stop_orphans(self, jobs):
        """hstq-* units on the host that no running job of this host owns (left while the host was offline)."""
        mine = {self.unit(j["id"]) for j in jobs if j["state"] == "running" and j.get("host") == self.name}
        try:
            out = self.host.run(["systemctl", "list-units", "--plain", "--no-legend", "--all", "hstq-*"],
                                check=False).stdout
            for unit in re.findall(r"^\s*(hstq-q\d{6}-\d{6}-[0-9a-f]{4})\.service", out, re.M):
                if unit not in mine:
                    self.host.run(["systemctl", "kill", "--signal=TERM", f"{unit}.service"], check=False)
                    log(f"{self.name}: stopped leftover {unit}")
        except RemoteError as exc:
            log(f"{self.name}: leftover check failed: {exc}")

    # ------------------------------------------------------------ deploy and commits
    def push(self, sha, ref):
        url = f"ssh://{self.host.user}@{self.host.address}{self.root}/repo.git"
        done = subprocess.run(["git", "-C", REPO, "push", "-q", "--force", url, f"{sha}:{ref}"], capture_output=True,
                              text=True, timeout=900, check=False, env={**git_env(), "GIT_SSH_COMMAND": self.host.git_ssh()})
        if done.returncode != 0:
            raise RemoteError(f"{self.name}: git push {ref}: {done.stderr.strip()[-300:]}")

    def ensure_deployed(self):
        sha = infra_sha()
        if not sha:
            raise RemoteError("cannot tell the deployed infra commit")
        if self.deployed == sha:
            return self.infra_dir(sha)
        d = self.infra_dir(sha)
        if self.host.run(["test", "-x", f"{d}/scripts/linux/local-build.sh"], check=False).returncode != 0:
            self.push(sha, f"refs/infra/{sha[:12]}")   # refs/infra/* and refs/q/* live only in the host's repo.git
            self.host.run(["git", "-C", f"{self.root}/repo.git", "worktree", "add", "-f", "--detach", d, sha],
                          timeout=300)
            log(f"{self.name}: deployed infra {sha[:12]}")
        self.deployed = sha
        return d

    # ------------------------------------------------------------ runner interface
    def want(self, want):
        return min(want, int(self.hcfg.get("max_jobs", 12)))

    def free_slot(self, jobs, want, job=None):
        if job and self.name in job.get("avoid_hosts", []):
            return None
        if job and (job.get("modules") or job.get("tests")) and not self.hcfg.get("partial_builds", True):
            return None
        if not self.usable():
            return None
        t, cached = self.slot_cache
        if self.now() - t < self.cfg.get("remote_poll_seconds", 30) and cached is None:
            return None
        busy = [str(j["slot"]).split(":")[1] for j in jobs if j["platform"] == "linux" and j["state"] == "running"
                and j.get("host") == self.name]
        try:
            d = self.ensure_deployed()
            argv = ["env", *(f"{k}={v}" for k, v in self.env().items()), "python3", "-I",
                    f"{d}/scripts/linux/build-slots.py", "free-slot", "--want", str(self.want(want)),
                    "--exclude", ",".join(busy)]
            done = self.host.run(argv, check=False)
            self.contact_ok()
        except RemoteError as exc:
            self.contact_failed(exc)
            self.slot_cache = (self.now(), None)
            return None
        slot = f"{self.name}:{done.stdout.strip()}" if done.returncode == 0 and done.stdout.strip().isdigit() else None
        self.slot_cache = (self.now(), slot)
        return slot

    def start(self, job, slot):
        self.slot_cache = (0.0, None)
        n = slot.split(":", 1)[1]
        d = self.ensure_deployed()
        self.push(job["sha"], f"refs/q/{job['id']}")
        out, rc, rlog = self.qpath("out", job["id"]), self.qpath("rc", job["id"], ".rc"), self.qpath("logs", job["id"], ".log")
        self.host.run(["sh", "-c", f"mkdir -p {self.root}/queue/out {self.root}/queue/rc {self.root}/queue/logs "
                       f"&& rm -rf {out} {rc} {rlog}"])
        want = self.want(self.cfg["linux_modules_max_jobs"] if job["modules"] else self.cfg["linux_max_jobs"])
        cmd = [f"{d}/scripts/linux/local-build.sh", "--slot", n, "--label", job["label"], "--out", out, "-j", str(want)]
        if job["modules"]:
            cmd += ["--modules", ",".join(job["modules"])]
        elif not job["package"]:
            cmd.append("--no-package")
        if job.get("tests"):
            cmd += ["--test", " ".join(job["tests"])]
        cmd.append(job["sha"])
        env = {**self.env(), "HST_Q_LOG": rlog, "HST_Q_RC": rc}
        argv = ["systemd-run", f"--unit={self.unit(job['id'])}", "--collect", "--quiet",
                f"--slice={self.hcfg.get('slice', 'hst-build.slice')}", "-p", "Nice=10", "-p", "IOSchedulingClass=idle",
                "-p", "OOMScoreAdjust=500", *(f"--setenv={k}={v}" for k, v in env.items()),
                "/bin/bash", "-c", '"$@" > "$HST_Q_LOG" 2>&1; echo $? > "$HST_Q_RC"', "queue-runner", *cmd]
        self.host.run(argv, timeout=120)
        self.contact_ok()
        with open(job["log"], "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%F %T')}] started on {self.name} slot {n} as {self.unit(job['id'])}.service\n")
        return {"slot": slot, "host": self.name, "pid": None, "remote_log_offset": 0, "command": cmd}

    def check(self, job):
        jid = job["id"]
        if self.now() < self.next_poll.get(jid, 0):
            return None
        self.next_poll[jid] = self.now() + self.cfg.get("remote_poll_seconds", 30)
        off = int(job.get("remote_log_offset", 0))
        script = (f'cat {self.qpath("rc", jid, ".rc")} 2>/dev/null || echo "RUNNING:$(systemctl is-active '
                  f'{self.unit(jid)}.service)"; echo "@@LOG@@"; tail -c +{off + 1} {self.qpath("logs", jid, ".log")} '
                  f'2>/dev/null | head -c {LOG_CHUNK}')
        try:
            raw = self.host.run(["sh", "-c", script], timeout=120, check=False).stdout
            self.contact_ok()
        except RemoteError as exc:
            self.contact_failed(exc)
            return None
        status, _, chunk = raw.partition("\n@@LOG@@\n")
        if chunk:
            with open(job["log"], "a", encoding="utf-8", errors="replace") as f:
                f.write(chunk)
            self.store.update(jid, remote_log_offset=off + len(chunk.encode("utf-8", errors="replace")))
        status = status.strip()
        if status.startswith("RUNNING:"):
            if status.split(":", 1)[1] in ("active", "activating", "deactivating"):
                return self.check_timeout(job)
            return ("cancelled" if job.get("cancel_requested") else "failed"), {"error": "runner exited without a status"}
        rc = int(status) if status.lstrip("-").isdigit() else 1
        if rc != 0:
            self.cleanup(jid)
            return ("cancelled" if job.get("cancel_requested") else "failed"), {"error": f"local-build.sh exit {rc}"}
        return self.collect(job)

    def check_timeout(self, job):
        limit = float(self.cfg.get("remote_job_timeout_hours", 6)) * 3600
        if self.now() - job.get("started", self.now()) < limit:
            return None
        self.cancel(job)
        self.store.update(job["id"], avoid_hosts=sorted(set(job.get("avoid_hosts", [])) | {self.name}))
        return "failed", {"error": f"dispatcher: {self.name} job ran longer than {limit / 3600:g} h; stopped"}

    def collect(self, job):
        import json
        jid = job["id"]
        out = self.store.job_out(jid)
        os.makedirs(out, exist_ok=True)
        try:
            self.host.rsync_from(self.qpath("out", jid) + "/", out + "/")
        except RemoteError as exc:
            self.contact_failed(exc)
            self.next_poll[jid] = 0   # the rc stays on the host: the next check copies again
            return None
        if os.path.exists(os.path.join(out, "SHA256SUMS")):
            if subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=out, check=False).returncode != 0:
                return "failed", {"error": "dispatcher: copied output fails its SHA256SUMS"}
        files = sorted(os.path.join(out, n) for n in os.listdir(out)
                       if n.endswith((".deb", ".rpm", ".AppImage", ".tar.gz")))
        fields = {"output": files}
        if job.get("tests"):
            try:
                with open(os.path.join(out, "test-results.json"), encoding="utf-8") as f:
                    fields["test_results"] = json.load(f)["results"]
            except (OSError, ValueError, KeyError) as exc:
                return "failed", {"error": f"test results missing: {exc}"}
        self.cleanup(jid)
        return "done", fields

    def cleanup(self, jid):
        """The host keeps no output: the copy under out/<id> is the only one (and its log is already here)."""
        try:
            self.host.run(["sh", "-c", f"rm -rf {self.qpath('out', jid)} {self.qpath('rc', jid, '.rc')} "
                           f"{self.qpath('logs', jid, '.log')}; git -C {self.root}/repo.git update-ref -d "
                           f"refs/q/{jid} 2>/dev/null; true"], check=False)
        except RemoteError as exc:
            log(f"{self.name}: cleanup of {jid} failed: {exc}")

    def cancel(self, job):
        self.host.run(["systemctl", "kill", "--signal=TERM", f"{self.unit(job['id'])}.service"], check=False)
