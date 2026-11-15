#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Run probe-vba-headless.py with an installed office's own Python, bounded in time (Git Bash on a Windows runner).
#   run-vba-probe.sh <program dir (Windows path)> <output dir> [probe options, e.g. --info-only docm]
# On timeout the office's soffice processes are ended so the next step starts clean; the exit status is the probe's
# (124 on timeout).
set -uo pipefail
program="${1:?program directory required}"; out="${2:?output directory required}"; shift 2
mkdir -p "$out"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
timeout 500 "$(cygpath -u "$program")/python.exe" "$(cygpath -w "$here/probe-vba-headless.py")" \
  --soffice "$(cygpath -w "$program")\\soffice.exe" --out "$(cygpath -w "$out")" "$@"
code=$?
if [ "$code" -ne 0 ]; then
  echo "probe exit $code; soffice log:"
  cat "$out/soffice.log" 2>/dev/null || true
  taskkill //F //T //IM soffice.bin >/dev/null 2>&1 || true
  taskkill //F //T //IM soffice.exe >/dev/null 2>&1 || true
fi
exit "$code"
