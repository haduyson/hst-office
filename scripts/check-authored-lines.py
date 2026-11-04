#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Enforce the 199-line limit on authored Python changed since the branch's upstream base."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def changed(root, base):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True).splitlines()
    if base is None:
        event_base = os.environ.get('HST_AUTHORING_BASE', '')
        base = event_base if event_base and set(event_base) != {'0'} else git('merge-base', 'HEAD', 'origin/main')[0]
        if base == git('rev-parse', 'HEAD')[0]:
            base = git('rev-parse', 'HEAD^')[0]
    return sorted(set(git('diff', '--name-only', '--diff-filter=ACMR', base, '--', '*.py')
                      + git('ls-files', '--others', '--exclude-standard', '--', '*.py')))


def check(root, base=None):
    paths = [root / name for name in changed(root, base)]
    failures = [path for path in paths if path.is_file() and path.read_text().count('\n') + 1 > 199]
    for path in failures:
        print('FAIL exceeds 199 lines:', path.relative_to(root))
    print(f'Authored Python: {len(paths)} files checked, {len(failures)} failures.')
    return bool(failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', help='explicit comparison revision; default: merge-base with origin/main')
    args = parser.parse_args()
    return check(ROOT, args.base)


if __name__ == '__main__':
    raise SystemExit(main())
