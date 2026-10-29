#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Ported from archive/onlyoffice-plugin-first:scripts/check-doc-links.py
# Source commit: e0517d71c813535087c401b2683bec0784d71fd8.
"""Check relative Markdown file links; external URLs and anchors need separate QA."""
import os
import re
import sys
from urllib.parse import unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r'!?\[[^\]]*\]\((<[^>]+>|[^)\s]+)(?:\s+"[^"]*")?\)')


def markdown_files(paths):
    for target in paths:
        absolute = os.path.join(ROOT, target)
        if not os.path.exists(absolute):
            raise FileNotFoundError(f"declared documentation path missing: {target}")
        if os.path.isfile(absolute):
            yield absolute
            continue
        for dirpath, _, filenames in os.walk(absolute):
            for name in sorted(filenames):
                if name.endswith(".md"):
                    yield os.path.join(dirpath, name)


def broken_links(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    text = re.sub(r"```.*?```|~~~.*?~~~", "", text, flags=re.S)
    for match in LINK.finditer(text):
        target = match.group(1).strip("<>")
        if re.match(r"^(https?:|mailto:|#)", target):
            continue
        file_part = unquote(target.split("#", 1)[0])
        resolved = os.path.normpath(os.path.join(os.path.dirname(path), file_part))
        if not os.path.exists(resolved):
            yield target


def main(argv):
    paths = argv or ["README.md", "NOTICE.md", "THIRD_PARTY_NOTICES.md", "docs", "plans"]
    failures, count = [], 0
    try:
        for path in markdown_files(paths):
            count += 1
            failures.extend(f"{os.path.relpath(path, ROOT)} -> {target}" for target in broken_links(path))
    except OSError as error:
        failures.append(str(error))
    if failures:
        print("Broken links or missing inputs:\n  " + "\n  ".join(failures))
        return 1
    if not count:
        print("FAIL: no Markdown files checked", file=sys.stderr)
        return 1
    print(f"ok: relative Markdown file links resolve ({count} files; anchors/external URLs not checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
