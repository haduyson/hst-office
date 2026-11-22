# SPDX-License-Identifier: AGPL-3.0-only
"""SSH transport to a remote Linux build host (config `linux_remote_hosts`) and its liveness state.

Every call is bounded: ssh runs with BatchMode, a pinned known_hosts file (StrictHostKeyChecking=yes), a 10 s
connect timeout, keep-alives (a dead peer is noticed within ~45 s) and a hard subprocess timeout, so a host that
stops answering can never block the dispatcher. Liveness lives in <queue root>/hosts.json:
  {name: {"state": "online"|"offline", "last_ok": t, "since": t, "reason": text}}
"""
import json
import os
import shlex
import subprocess
import time

from .queue_store import now_iso

SSH_OPTS = ("-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
            "-o", "LogLevel=ERROR")


class RemoteError(Exception):
    pass


class RemoteHost:
    def __init__(self, hcfg):
        self.name = hcfg["name"]
        self.address = hcfg["address"]
        self.user = hcfg.get("user", "root")
        self.key = hcfg["key"]
        self.known_hosts = hcfg["known_hosts"]

    def ssh_cmd(self):
        return ["ssh", "-i", self.key, "-o", f"UserKnownHostsFile={self.known_hosts}", *SSH_OPTS]

    def target(self):
        return f"{self.user}@{self.address}"

    def run(self, argv, timeout=60, check=True):
        """Run argv (a list, quoted for the remote shell) on the host; RemoteError on ssh failure or timeout."""
        cmd = [*self.ssh_cmd(), self.target(), " ".join(shlex.quote(a) for a in argv)]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RemoteError(f"{self.name}: {type(exc).__name__}") from exc
        if done.returncode == 255:
            raise RemoteError(f"{self.name}: ssh failed: {done.stderr.strip()[-300:]}")
        if check and done.returncode != 0:
            raise RemoteError(f"{self.name}: {argv[0]} rc={done.returncode}: {(done.stderr or done.stdout)[-500:]}")
        return done

    def rsync_from(self, remote_path, local_path, timeout=3600, append=False):
        """Copy a remote file or directory (trailing / for contents) to local_path."""
        ssh = " ".join(shlex.quote(a) for a in self.ssh_cmd())
        flags = ["-a", "--append-verify"] if append else ["-a"]
        cmd = ["rsync", *flags, "--timeout=60", "-e", ssh, f"{self.target()}:{remote_path}", local_path]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RemoteError(f"{self.name}: rsync {type(exc).__name__}") from exc
        if done.returncode != 0:
            raise RemoteError(f"{self.name}: rsync rc={done.returncode}: {done.stderr.strip()[-300:]}")

    def git_ssh(self):
        """GIT_SSH_COMMAND for `git push ssh://<user>@<address>/<path>` to the host's repository."""
        return " ".join(shlex.quote(a) for a in self.ssh_cmd())


class HostStates:
    def __init__(self, store):
        self.path = os.path.join(store.root, "hosts.json")

    def all(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, ValueError):
            return {}

    def get(self, name):
        return self.all().get(name, {})

    def update(self, name, **fields):
        states = self.all()
        states.setdefault(name, {}).update(fields)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(states, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)
        return states[name]

    def ok(self, name, t=None):
        t = time.time() if t is None else t
        cur = self.get(name)
        if cur.get("state") != "online":
            return self.update(name, state="online", since=t, since_at=now_iso(t), last_ok=t, reason="")
        if t - cur.get("last_ok", 0) >= 30:   # bounded writes: at most every 30 s
            return self.update(name, last_ok=t)
        return cur

    def offline(self, name, reason, t=None):
        t = time.time() if t is None else t
        return self.update(name, state="offline", since=t, since_at=now_iso(t), reason=reason)
