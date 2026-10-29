#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Discover lightweight repository checks; report every failure, then fail the job.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
if [[ -z "${PYTHON:-}" ]]; then
  if [[ -x .venv/bin/python ]]; then PYTHON="$ROOT/.venv/bin/python"; else PYTHON=python3; fi
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
failures=0
checks=0
run() {
  printf '\nRUN:'; printf ' %q' "$@"; printf '\n'
  checks=$((checks + 1))
  "$@"
  local code=$?
  if (( code != 0 )); then
    printf 'FAIL (exit %s)\n' "$code" >&2
    failures=$((failures + 1))
  fi
}
missing() {
  printf 'FAIL: declared check missing: %s\n' "$1" >&2
  failures=$((failures + 1))
}
script() {
  local path="$1"; shift
  [[ -f "$path" ]] || { missing "$path"; return; }
  case "$path" in
    *.py) run "$PYTHON" "$path" "$@" ;;
    *.sh) run bash "$path" "$@" ;;
    *.js|*.mjs) run node "$path" "$@" ;;
    *) missing "unsupported check interpreter: $path" ;;
  esac
}
for directory in tests/unit tests/brand; do
  count=0
  if [[ -d "$directory" ]]; then
    while IFS= read -r -d '' test_file; do
      run env PYTHONPATH="$ROOT/$(dirname "$test_file"):$PYTHONPATH" "$PYTHON" -m unittest "$test_file" -v
      count=$((count + 1))
    done < <(find "$directory" -type f -name 'test*.py' -print0 | sort -z)
  fi
  (( count > 0 )) || missing "$directory/test*.py"
done
script scripts/generate-brand-assets.py --check
# These are required even before extensions/templates have been integrated.
script scripts/check-doc-links.py
script scripts/check-workflows.py
# Producers precede structural checks; their absence is explicitly reported.
shopt -s nullglob
for name in build-extensions generate-templates; do
  candidates=()
  for path in scripts/"$name".*; do
    case "$path" in *.py|*.sh|*.js|*.mjs) candidates+=("$path") ;; esac
  done
  if (( ${#candidates[@]} == 0 )); then
    printf 'NOT PRESENT: optional scripts/%s\n' "$name"
  fi
  for path in "${candidates[@]}"; do script "$path"; done
done
for path in scripts/check-*.{py,sh,js,mjs}; do
  case "$path" in scripts/check-doc-links.py|scripts/check-workflows.py) continue ;; esac
  script "$path"
done
printf '\nQuality: %s commands executed, %s failures. Runtime/native QA is separate.\n' "$checks" "$failures"
(( failures == 0 ))
