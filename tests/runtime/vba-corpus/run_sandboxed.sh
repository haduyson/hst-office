#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Run macros from untrusted files in one disposable container: no network, not root, read-only root and
# mounts, private tmpfs. Results come back as JSON lines on stdout only; nothing is writable from the host.
#   run_sandboxed.sh IMAGE INSTDIR CORPUS_DIR JOBS.json OUT.jsonl [TIMEOUT_SECONDS]
set -euo pipefail
IMAGE="$1"; INSTDIR="$(realpath "$2")"; CORPUS="$(realpath "$3")"; JOBS="$(realpath "$4")"; OUT="$5"; LIMIT="${6:-3000}"
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME="hst-vba-sb-$$-$RANDOM"
[ -f "$INSTDIR/program/soffice.bin" ] && [ -f "$JOBS" ] || { echo "no office in $INSTDIR or no jobs $JOBS"; exit 2; }
trap 'docker kill "$NAME" >/dev/null 2>&1 || true' EXIT
timeout "$LIMIT" docker run --rm --name "$NAME" --network none --read-only --user 54321:54321 \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 768 --memory 4g --cpus 4 \
  --tmpfs /tmp:rw,size=1500m,mode=1777 \
  -v "$INSTDIR:/opt/hst:ro" -v "$CORPUS:/corpus:ro" -v "${HST_HARNESS_DIR:-$HERE}:/harness:ro" -v "$JOBS:/jobs.json:ro" \
  -e PYTHONDONTWRITEBYTECODE=1 "$IMAGE" /usr/bin/python3 -I ${HST_HARNESS_MAIN:-/harness/sandbox_run.py} /jobs.json \
  2>"$OUT.stderr" | grep --line-buffered '^@@R ' >"$OUT" || true
