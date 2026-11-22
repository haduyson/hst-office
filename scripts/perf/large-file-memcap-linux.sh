#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# Open/save timings and peak memory of 50-200 MB files on Linux, each file in its own memory-capped cgroup.
#   large-file-memcap-linux.sh <program dir of an unpacked package> <fixtures dir> <out dir> <label> [files...]
# Runs scripts/perf/large-file-open.py --mode gui --save for every file (default: all in the fixtures dir) under its
# own Xvfb display :$LFO_DISPLAY (default 88; a display already in use stops the run), at nice 19, inside a transient
# systemd scope with MemoryMax=$LFO_MEMORY_MAX (default 8G) and no swap. After each file, the scope's memory.peak and
# its oom_kill count are appended to <out>/<label>-cgroup.jsonl; the harness's own JSON lines go to <out>/<label>.jsonl.
# The display is stopped on exit. LFO_REPEAT (default 1) and LFO_TIMEOUT (default 1800 s) go to the harness;
# LFO_SEED picks the profile seed, LFO_SAVE=0 times the open only.
set -Eeuo pipefail
program="$(cd "$1" && pwd)"; fixtures="$(cd "$2" && pwd)"; out="$(mkdir -p "$3" && cd "$3" && pwd)"; label="$4"
shift 4
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
display="${LFO_DISPLAY:-88}"
[ -e "/tmp/.X11-unix/X$display" ] && { echo "display :$display is in use" >&2; exit 2; }
Xvfb ":$display" -screen 0 1920x1080x24 -nolisten tcp >/dev/null 2>&1 &
xvfb=$!
trap 'kill "$xvfb" 2>/dev/null || true' EXIT
for _ in $(seq 50); do [ -e "/tmp/.X11-unix/X$display" ] && break; sleep 0.1; done
files=("$@")
[ ${#files[@]} -gt 0 ] || mapfile -t files < <(cd "$fixtures" && ls | grep -v '\.tmp$')
for name in "${files[@]}"; do
  unit="lfo-$label-$$-${name//[^A-Za-z0-9]/-}"
  rc=0
  DISPLAY=":$display" systemd-run --scope --quiet --unit "$unit" -p MemoryMax="${LFO_MEMORY_MAX:-8G}" \
    -p MemorySwapMax=0 -p CollectMode=inactive-or-failed --setenv=DISPLAY=":$display" \
    nice -n 19 python3 -I "$here/large-file-open.py" --soffice "$program/soffice" --python "$program/python" \
      --files "$fixtures" --only "$name" --out "$out" --label "$label" --mode gui $([ "${LFO_SAVE:-1}" = 1 ] && echo --save) --seed "${LFO_SEED:-default}" \
      --repeat "${LFO_REPEAT:-1}" --timeout "${LFO_TIMEOUT:-1800}" &
  pid=$!
  cg=""
  for _ in $(seq 100); do
    cg="$(sed -n 's/^0:://p' "/proc/$pid/cgroup" 2>/dev/null || true)"
    case "$cg" in *"$unit"*) break ;; esac; sleep 0.1
  done
  case "$cg" in *"$unit"*) ;; *) echo "no scope cgroup for $name" >&2; cg="/nonexistent" ;; esac
  peak=0; oom=0
  while kill -0 "$pid" 2>/dev/null; do  # memory.peak goes with the scope: sample it while it lives
    p="$(cat "/sys/fs/cgroup$cg/memory.peak" 2>/dev/null || echo 0)"; [ "$p" -gt "$peak" ] && peak="$p"
    o="$(sed -n 's/^oom_kill //p' "/sys/fs/cgroup$cg/memory.events" 2>/dev/null || echo 0)"; [ "${o:-0}" -gt "$oom" ] && oom="$o"
    sleep 1
  done
  wait "$pid" || rc=$?
  printf '{"label": "%s", "file": "%s", "cgroup_peak_mb": %d, "oom_kill": %d, "exit": %d}\n' \
    "$label" "$name" $((peak / 1000000)) "$oom" "$rc" | tee -a "$out/$label-cgroup.jsonl"
done
