# SPDX-License-Identifier: AGPL-3.0-only
"""Pre-submit lint of the LibreOffice patches a commit adds or changes (patches/libreoffice/*.patch against its
merge base with the integration branch). The series is applied with `patch -p1`, so:
  - every `diff --git` header needs the a/ and b/ prefixes ("diff --git sw/x sw/x" makes -p1 strip the module
    directory and write x at the source root);
  - every `--- `/`+++ ` header outside a hunk is /dev/null or a/<path> / b/<path>, and <path> (after -p1) lies under
    a top-level directory of the LibreOffice tree, or is an existing file at its root. A file created from
    /dev/null may start a new top-level directory (an HST-owned module such as hst/), but never sit at the root.
`submit` and `train add` refuse a commit with such a patch (the integrator can override with --force).
"""
import os
import re

PATCH_DIR = "patches/libreoffice/"
HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def tree_layout(tree):
    """(top-level directories, files at the root) of a LibreOffice source tree; (None, None) when unreadable."""
    try:
        names = os.listdir(tree)
    except OSError:
        return None, None
    dirs = {n for n in names if os.path.isdir(os.path.join(tree, n))}
    return dirs, set(names) - dirs


def _check_path(path, prefix, where, dirs, root_files, problems, new_file=False):
    if path == "/dev/null":
        return
    if not path.startswith(prefix):
        problems.append(f"{where}: path {path!r} lacks the {prefix} prefix (patch -p1 would strip a real directory)")
        return
    rel = path[len(prefix):]
    if dirs is None:
        return
    top = rel.split("/", 1)[0]
    if "/" in rel and (top in dirs or new_file):
        return                            # a new file may start a new HST-owned module (e.g. hst/)
    if "/" not in rel and rel in root_files:
        return
    problems.append(f"{where}: {rel!r} is not under a LibreOffice module directory (with -p1 it lands at "
                    f"{'the source root' if '/' not in rel else top + '/, which the tree does not have'})")


def lint_patch(name, text, dirs=None, root_files=None):
    """Problems ("<patch>:<line>: ...") of one patch; dirs/root_files from tree_layout (None: prefixes only)."""
    problems = []
    old_left = new_left = 0
    old_is_devnull = False
    for no, line in enumerate(text.splitlines(), 1):
        if old_left > 0 or new_left > 0:   # inside a hunk: "--- x" may be a removed line starting with "-- "
            tag = line[:1]
            if tag == "\\":
                continue                      # "\ No newline at end of file"
            if tag in (" ", ""):
                old_left, new_left = old_left - 1, new_left - 1
                continue
            if tag == "-" and old_left > 0:
                old_left -= 1
                continue
            if tag == "+" and new_left > 0:
                new_left -= 1
                continue
            old_left = new_left = 0           # the hunk ended early (malformed): read the line as a header
        where = f"{name}:{no}"
        m = HUNK_RE.match(line)
        if m:
            old_left = int(m.group(1)) if m.group(1) is not None else 1
            new_left = int(m.group(2)) if m.group(2) is not None else 1
        elif line.startswith("diff --git "):
            parts = line[len("diff --git "):].split()
            if len(parts) != 2 or not parts[0].startswith("a/") or not parts[1].startswith("b/"):
                problems.append(f"{where}: {line.strip()!r} lacks the a/ and b/ prefixes")
        elif line.startswith("--- "):
            old = line[4:].split("\t")[0].strip()
            old_is_devnull = old == "/dev/null"
            _check_path(old, "a/", where, dirs, root_files, problems)
        elif line.startswith("+++ "):
            _check_path(line[4:].split("\t")[0].strip(), "b/", where, dirs, root_files, problems,
                        new_file=old_is_devnull)
            old_is_devnull = False
    return problems


def changed_patches(git, base_ref, sha):
    """Patch files the commit adds or changes against its merge base with base_ref; None when git cannot tell."""
    tip = git.rev(base_ref)
    base = tip and git.merge_base(tip, sha)
    if not base:
        return None
    rc, out, _err = git.run("diff", "--name-only", "--no-renames", "--diff-filter=AM", base, sha, "--", PATCH_DIR)
    if rc != 0:
        return None
    return [p for p in out.splitlines() if p.endswith(".patch")]


def lint_commit(git, base_ref, sha, tree):
    """Problems of the patches a commit adds or changes (empty: clean, or git could not tell)."""
    dirs, root_files = tree_layout(tree) if tree else (None, None)
    problems = []
    for path in changed_patches(git, base_ref, sha) or []:
        rc, text, _err = git.run("show", f"{sha}:{path}")
        if rc == 0:
            problems += lint_patch(path[len(PATCH_DIR):], text, dirs, root_files)
    return problems
