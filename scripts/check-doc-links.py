"""Check that relative Markdown links resolve inside the repository.

Usage: python3 scripts/check-doc-links.py [paths...]   (default: README.md NOTICE.md docs plans)
External http(s)/mailto links and pure #anchors are skipped (no network use).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def markdown_files(paths):
    for target in paths:
        absolute = os.path.join(ROOT, target)
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
    text = re.sub(r"```.*?```", "", text, flags=re.S)  # ignore code blocks
    for match in LINK.finditer(text):
        target = match.group(1)
        if re.match(r"^(https?:|mailto:|#)", target):
            continue
        file_part = target.split("#", 1)[0]
        resolved = os.path.normpath(os.path.join(os.path.dirname(path), file_part))
        if not os.path.exists(resolved):
            yield target


def main(argv):
    paths = argv or ["README.md", "NOTICE.md", "THIRD_PARTY_NOTICES.md", "docs", "plans"]
    failures = []
    for path in markdown_files(paths):
        for target in broken_links(path):
            failures.append(f"{os.path.relpath(path, ROOT)} -> {target}")
    if failures:
        print("Broken links:\n  " + "\n  ".join(failures))
        return 1
    print("ok: all relative Markdown links resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
