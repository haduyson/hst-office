# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only git queries of the build queue (submit checks, retention, trains) on the queue's repository.

Every query fails soft: it returns None when git cannot answer (unknown object, no network), so a check that
needs git never blocks a submit or a dispatcher tick by itself; callers decide what None means.
"""
import os
import pwd
import subprocess

from .queue_store import REPO

# Paths whose changes never need a build: tests and documentation (plans/ holds reports and plans).
DOCS_ONLY_PREFIXES = ("tests/", "docs/", "plans/")


def is_docs_only(path):
    return path.startswith(DOCS_ONLY_PREFIXES) or path.endswith(".md")


def git_env():
    """The dispatcher runs as a systemd service without HOME: git then misses ~/.gitconfig (credential helper)."""
    env = dict(os.environ)
    if not env.get("HOME"):
        env["HOME"] = pwd.getpwuid(os.getuid()).pw_dir
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


class Git:
    def __init__(self, repo=REPO):
        self.repo = repo

    def run(self, *args, timeout=120):
        """(returncode, stdout, stderr) of `git -C repo args`; (-1, '', reason) when git could not run."""
        try:
            done = subprocess.run(["git", "-C", self.repo, *args], capture_output=True, text=True, check=False,
                                  timeout=timeout, env=git_env())
        except (OSError, subprocess.SubprocessError) as exc:
            return -1, "", str(exc)
        return done.returncode, done.stdout, done.stderr

    def out(self, *args, timeout=120):
        rc, stdout, _err = self.run(*args, timeout=timeout)
        return stdout.strip() if rc == 0 else None

    def rev(self, ref):
        """Commit sha of origin/<ref>, else <ref> itself; None when unknown."""
        for cand in (f"origin/{ref}", ref):
            sha = self.out("rev-parse", "-q", "--verify", f"{cand}^{{commit}}")
            if sha:
                return sha
        return None

    def merge_base(self, a, b):
        return self.out("merge-base", a, b)

    def is_ancestor(self, a, b):
        rc, _out, _err = self.run("merge-base", "--is-ancestor", a, b)
        return {0: True, 1: False}.get(rc)

    def changed(self, a, b):
        """Paths that differ between two commits (renames as delete + add); None on error."""
        rc, stdout, _err = self.run("diff", "--name-only", "--no-renames", a, b)
        return [p for p in stdout.splitlines() if p] if rc == 0 else None
