# SPDX-License-Identifier: AGPL-3.0-only
"""Git side of the build train: a private clone under <queue root>/train/repo where trains are merged, pushed as
train/<prefix>NNN and deleted again. Safety rules enforced here, not by callers:
  - only refs/heads/train/... is ever pushed or deleted; there is no force push at all;
  - merges are deterministic (fixed identity, dates and messages), so redoing a train after a restart gives the
    same commit and the push is a no-op;
  - patches/libreoffice/series and l10n/vi-overrides.jsonl merge as a union, like the integrator merges them
    (series: append in merge order; vi-overrides: the row merged last wins, superseded rows are dropped).
"""
import json
import os
import re
import subprocess

from .queue_git import git_env
from .queue_store import REPO

UNION_FILES = ("patches/libreoffice/series", "l10n/vi-overrides.jsonl")
PATCH_DIR = "patches/libreoffice/"
TRAIN_REF_RE = re.compile(r"^train/[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
IDENTITY = {"GIT_AUTHOR_NAME": "HST build train", "GIT_AUTHOR_EMAIL": "build-train@hst-office.invalid",
            "GIT_COMMITTER_NAME": "HST build train", "GIT_COMMITTER_EMAIL": "build-train@hst-office.invalid"}


class TrainGitError(Exception):
    pass


def train_ref(name):
    """refs/heads/<name> for a train branch; anything else is refused before git runs."""
    if not TRAIN_REF_RE.match(name) or ".." in name:
        raise TrainGitError(f"refusing to touch {name!r}: not a train/ branch")
    return f"refs/heads/{name}"


def scrub(text):
    """Error text without credentials embedded in URLs."""
    return re.sub(r"(https?://)[^/@\s]+@", r"\1***@", text)[-1500:]


def dedupe_series(text):
    seen, out = set(), []
    for line in text.splitlines(keepends=True):
        name = line.strip()
        if name and not name.startswith("#"):
            if name in seen:
                continue
            seen.add(name)
        out.append(line)
    return "".join(out)


def dedupe_overrides(text):
    """One row per (file, msgctxt, msgid): the last one (the branch merged last) wins, in its own position."""
    lines = text.splitlines(keepends=True)
    keys = []
    for line in lines:
        try:
            row = json.loads(line)
            keys.append((row.get("file"), row.get("msgctxt"), row.get("msgid")) if isinstance(row, dict) else None)
        except ValueError:
            keys.append(None)
    last = {k: i for i, k in enumerate(keys) if k is not None}
    return "".join(line for i, (line, k) in enumerate(zip(lines, keys)) if k is None or last[k] == i)


def patch_files(text):
    """LibreOffice paths a patch touches (+++ b/ and --- a/ lines)."""
    found = set()
    for m in re.finditer(r"^(?:\+\+\+ b|--- a)/(\S+)", text, re.M):
        found.add(m.group(1))
    return found


class TrainRepo:
    def __init__(self, path, source=REPO, remote_url=None):
        self.path = path
        self.source = source
        self.remote_url = remote_url

    def git(self, *args, env=None, timeout=600, check=True, cwd_repo=True):
        cmd = ["git", "-C", self.path, *args] if cwd_repo else ["git", *args]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout,
                                  env={**git_env(), **(env or {})})
        except (OSError, subprocess.SubprocessError) as exc:
            raise TrainGitError(f"git {args[0]}: {exc}") from exc
        if check and done.returncode != 0:
            raise TrainGitError(f"git {' '.join(args[:3])}: rc={done.returncode}: {scrub(done.stderr + done.stdout)}")
        return done

    def ensure(self):
        if not os.path.isdir(os.path.join(self.path, ".git")):
            url = self.remote_url or subprocess.run(
                ["git", "-C", self.source, "remote", "get-url", "origin"], capture_output=True, text=True,
                check=True, env=git_env()).stdout.strip()
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            # Objects are borrowed from the local repository, then copied (--dissociate): the clone never depends
            # on a deploy worktree that build-infra-deploy.sh may prune later.
            common = subprocess.run(["git", "-C", self.source, "rev-parse", "--path-format=absolute",
                                     "--git-common-dir"], capture_output=True, text=True, check=True,
                                    env=git_env()).stdout.strip()
            self.git("clone", "-q", "--no-checkout", "--reference", common, "--dissociate", url, self.path,
                     cwd_repo=False, timeout=1800)
        attrs = os.path.join(self.path, ".git", "info", "attributes")
        os.makedirs(os.path.dirname(attrs), exist_ok=True)
        with open(attrs, "w", encoding="utf-8") as f:
            f.writelines(f"{p} merge=union\n" for p in UNION_FILES)

    def fetch(self):
        self.git("fetch", "-q", "--prune", "origin")

    def rev(self, ref):
        done = self.git("rev-parse", "-q", "--verify", f"origin/{ref}^{{commit}}", check=False)
        return done.stdout.strip() if done.returncode == 0 else None

    def is_ancestor(self, a, b):
        return self.git("merge-base", "--is-ancestor", a, b, check=False).returncode == 0

    def lo_files(self, base, sha):
        """(patches, LibreOffice files) the branch adds or changes relative to its merge base with `base`."""
        mb = self.git("merge-base", base, sha).stdout.strip()
        names = self.git("diff", "--name-only", "--no-renames", "--diff-filter=AM", mb, sha, "--", PATCH_DIR).stdout
        patches, files = [], set()
        for path in names.split():
            if not path.endswith(".patch"):
                continue
            patches.append(path[len(PATCH_DIR):])
            files |= patch_files(self.git("show", f"{sha}:{path}").stdout)
        return sorted(patches), sorted(files)

    def conflicts_with_base(self, base, sha):
        return self.git("merge-tree", "--write-tree", "--name-only", base, sha, check=False).returncode != 0

    def merge(self, base, members, when, name):
        """Merge members (dicts with branch + sha) one by one onto base. Returns (head sha, merged branches,
        {branch: conflicting files}); a conflicting member is skipped, the others still merge."""
        env = {**IDENTITY, "GIT_AUTHOR_DATE": f"@{int(when)} +0700", "GIT_COMMITTER_DATE": f"@{int(when)} +0700"}
        self.git("checkout", "-q", "-f", "--detach", base)
        self.git("reset", "-q", "--hard", base)
        self.git("clean", "-q", "-fdx")
        merged, conflicts = [], {}
        for m in members:
            if self.is_ancestor(m["sha"], "HEAD"):
                merged.append(m["branch"])
                continue
            done = self.git("merge", "-q", "--no-ff", "--no-commit", m["sha"], env=env, check=False)
            if done.returncode != 0:
                files = self.git("diff", "--name-only", "--diff-filter=U", check=False).stdout.split()
                self.git("merge", "--abort", check=False)
                self.git("reset", "-q", "--hard", "HEAD")
                conflicts[m["branch"]] = files or [scrub(done.stderr + done.stdout)[-300:]]
                continue
            for rel, fix in zip(UNION_FILES, (dedupe_series, dedupe_overrides)):
                full = os.path.join(self.path, rel)
                if os.path.isfile(full):
                    with open(full, encoding="utf-8", newline="") as f:
                        text = f.read()
                    if fix(text) != text:
                        with open(full, "w", encoding="utf-8", newline="") as f:
                            f.write(fix(text))
                        self.git("add", "--", rel)
            self.git("commit", "-q", "--no-verify", "-m", f"Merge {m['branch']} @{m['sha'][:12]} into {name}", env=env)
            merged.append(m["branch"])
        return self.git("rev-parse", "HEAD").stdout.strip(), merged, conflicts

    def remote_sha(self, name):
        out = self.git("ls-remote", "origin", train_ref(name)).stdout.split()
        return out[0] if out else None

    def remote_trains(self, prefix):
        """{name: sha} of the remote train branches under prefix (train/1.0.2-)."""
        train_ref(prefix + "0")
        lines = self.git("ls-remote", "--heads", "origin", f"refs/heads/{prefix}*").stdout.splitlines()
        return {ref[len("refs/heads/"):]: sha for sha, ref in (ln.split("\t", 1) for ln in lines if "\t" in ln)}

    def push(self, name, sha):
        """Create the train branch (never a force push; an existing branch must already be at sha)."""
        current = self.remote_sha(name)
        if current == sha:
            return False
        if current:
            raise TrainGitError(f"{name} already exists on origin at {current[:12]}, not {sha[:12]}")
        self.git("push", "-q", "origin", f"{sha}:{train_ref(name)}")
        return True

    def delete_remote(self, name):
        if self.remote_sha(name) is None:
            return False
        self.git("push", "-q", "origin", "--delete", train_ref(name))
        return True
