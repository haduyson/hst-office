# SPDX-License-Identifier: AGPL-3.0-only
"""A scratch git world for the build train tests: a bare `origin` with an integration branch (series, patches,
vi-overrides, docs) and helpers to push member branches; plus a local clone that plays the queue's repository."""
import json
import os
from pathlib import Path
import subprocess

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t", "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}
BASE = "rc/1.0.2-batch5"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True,
                          env=ENV).stdout.strip()


def patch_text(path, line="x"):
    return f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-old\n+{line}\n"


def override(msgid, msgstr):
    return json.dumps({"file": "sw/messages.po", "msgctxt": "c", "msgid": msgid, "msgstr": msgstr, "reason": "r"})


class GitWorld:
    def __init__(self, root):
        self.root = Path(root)
        self.origin = self.root / "origin.git"
        self.work = self.root / "work"
        self.clone = self.root / "clone"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], check=True, env=ENV)
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.work)], check=True, env=ENV,
                       capture_output=True)
        self.write({"patches/libreoffice/series": "hst-base.patch\n",
                    "patches/libreoffice/hst-base.patch": patch_text("sw/source/base.cxx"),
                    "l10n/vi-overrides.jsonl": override("Open", "Mở") + "\n" + override("Save", "Lưu") + "\n",
                    "docs/a.md": "a\n", "scripts/x.py": "x = 1\n"})
        git(self.work, "add", "-A")
        git(self.work, "commit", "-qm", "base")
        git(self.work, "push", "-q", "origin", f"HEAD:refs/heads/{BASE}")
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.clone)], check=True, env=ENV,
                       capture_output=True)

    def write(self, files):
        for rel, text in files.items():
            p = self.work / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

    def branch(self, name, files, base=BASE, append=None):
        """Push `name` = base + one commit writing files and appending lines (series/vi-overrides)."""
        git(self.work, "fetch", "-q", "origin")
        git(self.work, "checkout", "-q", "-B", name, f"origin/{base}")
        self.write(files)
        for rel, line in (append or {}).items():
            with open(self.work / rel, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        git(self.work, "add", "-A")
        git(self.work, "commit", "-qm", f"change {name}")
        git(self.work, "push", "-q", "-f", "origin", f"HEAD:refs/heads/{name}")
        git(self.clone, "fetch", "-q", "origin")
        return git(self.work, "rev-parse", "HEAD")

    def member(self, name, patch_name, lo_file, extra=None):
        """A typical member: one new patch on lo_file, appended to the series."""
        files = {f"patches/libreoffice/{patch_name}": patch_text(lo_file), **(extra or {})}
        return self.branch(name, files, append={"patches/libreoffice/series": patch_name})

    def orphan(self, name):
        """A branch with no history in common with the integration branch."""
        git(self.work, "checkout", "-q", "--orphan", name)
        git(self.work, "rm", "-rqf", ".")
        self.write({"other.txt": "o\n"})
        git(self.work, "add", "-A")
        git(self.work, "commit", "-qm", "orphan")
        git(self.work, "push", "-q", "-f", "origin", f"HEAD:refs/heads/{name}")
        git(self.clone, "fetch", "-q", "origin")

    def remote_heads(self):
        out = git(self.origin, "for-each-ref", "--format=%(refname:short)", "refs/heads")
        return set(out.split())

    def show(self, sha, rel):
        return git(self.origin, "show", f"{sha}:{rel}")
