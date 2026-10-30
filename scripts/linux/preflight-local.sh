#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Local preflight for the Linux .deb workflow: lint the CI scripts and the workflow so a
# trivial error does not cost a multi-hour runner build. actionlint is the pinned binary
# that scripts/windows/preflight-local.sh installs into work/tools (ci-quality runs it first).
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
fail=0
bad() { echo "FAIL: $*" >&2; fail=1; }
scripts=(scripts/linux/*.sh)
if command -v shellcheck >/dev/null; then shellcheck "${scripts[@]}" || bad shellcheck; else bad "shellcheck not installed"; fi
for f in "${scripts[@]}"; do bash -n "$f" || bad "bash -n $f"; done
for f in "${scripts[@]}" build-config/linux-x86_64.conf; do
  if grep -q $'\r' "$f"; then bad "CRLF in $f"; fi
done
if [ -x work/tools/actionlint ]; then
  work/tools/actionlint .github/workflows/desktop-linux.yml || bad actionlint
else
  bad "work/tools/actionlint missing: run scripts/windows/preflight-local.sh first"
fi
[ "$fail" -eq 0 ] && echo "linux preflight: ok"
exit "$fail"
