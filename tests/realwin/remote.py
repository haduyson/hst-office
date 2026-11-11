#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""SSH/SCP to the owner's LAN Windows test PCs. Everything lives under C:\\hst-test (D:\\hst-test for big files).

PowerShell is always sent as a script file and run with -File: `-Command -` on stdin silently drops multi-line
blocks. Usage:
  remote.py HOST ps SCRIPT.ps1 [ARGS...]     run a script (copied to C:\\hst-test\\ps) in the SSH session
  remote.py HOST push LOCAL... REMOTE_DIR     copy files/dirs into REMOTE_DIR (must be under the test root)
  remote.py HOST pull REMOTE LOCAL_DIR         copy a remote file/dir back
  remote.py HOST ui COMMANDLINE [--timeout S]  run COMMANDLINE in the console user's session (interactive task)
"""
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys

HERE = Path(__file__).resolve().parent
HOSTS = {"hst4": "192.168.1.124", "hst5": "192.168.1.163"}
KEY = os.environ.get("HST_WINTEST_KEY", "/root/.ssh/hst-wintest_ed25519")
USER = "kiemtra"
ROOTS = ("C:\\hst-test", "D:\\hst-test")
SSH_OPTS = ["-i", KEY, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=30"]


def address(host):
    if host not in HOSTS:
        raise SystemExit(f"unknown host {host!r}; known: {', '.join(HOSTS)}")
    return f"{USER}@{HOSTS[host]}"


def inside_root(remote):
    """Writes are confined to the test roots; refuse anything else before it reaches the machine."""
    path = str(PureWindowsPath(remote))
    lowered = path.lower()
    if ".." in PureWindowsPath(remote).parts:
        return False
    return any(lowered == root.lower() or lowered.startswith(root.lower() + "\\") for root in ROOTS)


def ssh(host, command, timeout=600, check=True):
    """Run a cmd.exe command line; returns CompletedProcess with text output."""
    done = subprocess.run(["ssh", *SSH_OPTS, address(host), command], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    if check and done.returncode != 0:
        raise RuntimeError(f"ssh {host} rc={done.returncode}: {done.stderr.strip()[-800:]}")
    return done


def scp_path(remote):
    return remote.replace("\\", "/")


def push(host, locals_, remote_dir, timeout=1800):
    if not inside_root(remote_dir):
        raise ValueError(f"refusing to write outside the test roots: {remote_dir}")
    ssh(host, f'if not exist "{remote_dir}" mkdir "{remote_dir}"', check=False)
    args = ["scp", "-q", "-r", *SSH_OPTS, *[str(p) for p in locals_], f"{address(host)}:{scp_path(remote_dir)}/"]
    subprocess.run(args, check=True, timeout=timeout)


def pull(host, remote, local_dir, timeout=1800):
    Path(local_dir).mkdir(parents=True, exist_ok=True)
    subprocess.run(["scp", "-q", "-r", *SSH_OPTS, f"{address(host)}:{scp_path(remote)}", str(local_dir)],
                   check=True, timeout=timeout)


def run_ps(host, script, *args, timeout=1800, check=True):
    """Copy a .ps1 to C:\\hst-test\\ps and run it with -File; arguments are passed through literally."""
    script = Path(script)
    push(host, [script], "C:\\hst-test\\ps")
    quoted = " ".join('"' + str(a).replace('"', '\\"') + '"' for a in args)
    command = f"powershell -NoProfile -ExecutionPolicy Bypass -File C:\\hst-test\\ps\\{script.name} {quoted}"
    done = ssh(host, command, timeout=timeout, check=False)
    if check and done.returncode != 0:
        raise RuntimeError(f"{script.name} on {host} rc={done.returncode}\n{done.stdout[-2000:]}\n{done.stderr[-2000:]}")
    return done


def run_ui(host, commandline, timeout=900, idle_minutes=1):
    """Run in the console user's interactive session through interactive-task.ps1 (idle check, cleanup)."""
    return run_ps(host, HERE / "interactive-task.ps1", commandline, str(timeout), str(idle_minutes),
                  timeout=timeout + 1200, check=False)


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    host, verb, rest = argv[1], argv[2], argv[3:]
    if verb == "ps":
        done = run_ps(host, rest[0], *rest[1:], check=False)
    elif verb == "push":
        push(host, rest[:-1], rest[-1])
        return 0
    elif verb == "pull":
        pull(host, rest[0], rest[1])
        return 0
    elif verb == "ui":
        timeout = int(rest[rest.index("--timeout") + 1]) if "--timeout" in rest else 900
        done = run_ui(host, rest[0], timeout)
    else:
        raise SystemExit(__doc__)
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
