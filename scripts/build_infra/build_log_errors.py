# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The lines that explain a failed build, with context: compiler/linker errors, `make: *** ... Error N`, fatal
errors and gla11y FATAL lines. A build log's tail usually shows only the warnings of the jobs that finished after
the failing one, so local-build.sh prints this block before the tail and `build-queue.sh wait|status` show it too.

Stdlib only, no package imports: local-build.sh runs it directly on a build host
  python3 -I scripts/build_infra/build_log_errors.py <build.log>
"""
import re
import sys

ERROR_RE = re.compile(r"\berror:|\berror [A-Z]+\d+:|\bfatal error\b|undefined reference to|\bError \d+\b|"
                      r"\bFATAL\b|No rule to make target|collect2: error|ld(?:\.\w+)?: error")
PROGRESS_RE = re.compile(r"^\[build [A-Z]+\]")   # gbuild progress lines name files that compile fine
HEADER = "--- error lines of the build log (with context) ---"
FOOTER = "--- end of error lines ---"


def error_lines(text, before=3, after=6, max_lines=200):
    """The error lines of `text`, each with `before`/`after` lines of context; separate blocks are divided by "--".
    The first errors matter most: at most max_lines lines are kept (then "... N more error lines")."""
    lines = text.splitlines()
    hits = [i for i, ln in enumerate(lines) if ERROR_RE.search(ln) and not PROGRESS_RE.match(ln)]
    if not hits:
        return []
    keep = []
    for i in hits:
        lo, hi = max(0, i - before), min(len(lines), i + after + 1)
        if keep and lo <= keep[-1][1]:
            keep[-1] = (keep[-1][0], max(keep[-1][1], hi))
        else:
            keep.append((lo, hi))
    out = []
    for lo, hi in keep:
        if out:
            out.append("--")
        out.extend(lines[lo:hi])
    if len(out) > max_lines:
        shown = sum(1 for ln in out[:max_lines] if ERROR_RE.search(ln) and not PROGRESS_RE.match(ln))
        out = out[:max_lines] + [f"... {len(hits) - shown} more error lines"]
    return out


def error_block(text, **kw):
    """error_lines framed by HEADER/FOOTER, or "" when the text has no error line."""
    found = error_lines(text, **kw)
    return "\n".join([HEADER, *found, FOOTER]) + "\n" if found else ""


def main(argv):
    if len(argv) != 2:
        print("usage: build_log_errors.py <build.log>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8", errors="replace") as f:
            sys.stdout.write(error_block(f.read()))
    except OSError as exc:
        print(f"build_log_errors: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
