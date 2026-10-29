#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# HST Office Windows trial build, run inside Cygwin bash (see .github/workflows/desktop-windows.yml).
#   trial-build.sh --extract | --patch | --configure | --build
# Env: HST_WORK (Cygwin path, default /cygdrive/c/hst), HST_REPO (checkout), HST_BUILD_DEADLINE
# (epoch seconds; --build stops make cleanly then and returns 0 with status budget-stop).
set -euo pipefail
WORK="${HST_WORK:-/cygdrive/c/hst}"
REPO="${HST_REPO:?HST_REPO must point at the repository checkout}"
SRC="$WORK/lo"; LOGS="$WORK/logs"; METRICS="$WORK/metrics"; DL="$WORK/dl"
CONF="$REPO/build-config/windows-x86_64.conf"
mkdir -p "$LOGS" "$METRICS"
# Minimal PATH: Cygwin first, native make, NASM, Windows system. Avoids Strawberry perl / Git usr/bin shadowing.
export PATH="/usr/local/bin:/usr/bin:$WORK/bin:/cygdrive/c/Program Files/NASM:/cygdrive/c/Windows/system32:/cygdrive/c/Windows"
export HOME="$WORK/home"; mkdir -p "$HOME"

phase() { # phase <name> <command...>: run, time and record in phases.jsonl; propagate failure
  local name="$1" start rc=0 status; shift; start=$(date +%s)
  "$@" || rc=$?
  status=ok; [ "$rc" -eq 0 ] || status="failed($rc)"
  [ "$rc" -ne 0 ] || [ "${BUDGET_STOPPED:-0}" -eq 0 ] || status=budget-stop
  printf '{"phase":"%s","seconds":%d,"status":"%s","free_gib":%s}\n' "$name" $(( $(date +%s) - start )) "$status" \
    "$(df -BG --output=avail /cygdrive/c | tail -1 | tr -dc 0-9)" >> "$METRICS/phases.jsonl"
  return "$rc"
}

extract_one() { # extract_one <tarball> <dest>; strips the single top-level directory
  mkdir -p "$2"; tar -xf "$DL/$1" -C "$2" --strip-components=1
}

do_extract() {
  # errexit is suppressed inside phase(), so every step returns explicitly on failure.
  extract_one libreoffice-26.8.1.1.tar.xz "$SRC" || return 1
  rm -rf "$SRC/translations" "$SRC/dictionaries"
  extract_one libreoffice-translations-26.8.1.1.tar.xz "$SRC/translations" || return 1
  extract_one libreoffice-dictionaries-26.8.1.1.tar.xz "$SRC/dictionaries" || return 1
  test -f "$SRC/configure.ac" && test -d "$SRC/translations/source/vi" && ls "$SRC/dictionaries" | head -3
}

do_patch() {
  HST_LO_SRC="$SRC" bash "$REPO/scripts/apply-patches.sh"
}

options() { # configure options with the branding placeholder resolved
  grep -v '^\s*#' "$CONF" | sed '/^\s*$/d' | sed "s|@BRANDING@|$(cygpath -m "$WORK/branding")|"
}

do_configure() {
  test -f "$WORK/branding/staging-manifest.json" || { echo "branding not staged"; return 2; }
  # Every option must exist in the pinned configure.ac (same rule as build-linux.sh).
  options | while IFS= read -r opt; do
    base="${opt%%=*}"; base="${base#--}"; base="${base#with-}"; base="${base#without-}"; base="${base#enable-}"; base="${base#disable-}"
    case "$base" in host) continue ;; esac
    grep -qE "(AC_ARG_(WITH|ENABLE)|libo_FUZZ_ARG_(WITH|ENABLE))\($base," "$SRC/configure.ac" || { echo "unknown configure option: $opt"; exit 3; }
  done || return 3
  options > "$SRC/autogen.input"
  cat "$SRC/autogen.input"
  (cd "$SRC" && ./autogen.sh) 2>&1 | tee "$LOGS/configure.log"
  test "${PIPESTATUS[0]}" -eq 0
}

sample() { # one progress sample: steps compiled, free disk, memory used
  local steps free used
  steps=$(grep -c '^\[build ' "$LOGS/build.log" 2>/dev/null || true)
  free=$(df -BG --output=avail /cygdrive/c | tail -1 | tr -dc 0-9)
  used=$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{printf "%.1f",(t-a)/1048576}' /proc/meminfo)
  printf '{"t":%d,"steps":%s,"free_gib":%s,"mem_used_gib":%s}\n' "$(date +%s)" "${steps:-0}" "$free" "$used" >> "$METRICS/progress.jsonl"
}

do_build() {
  local deadline="${HST_BUILD_DEADLINE:?HST_BUILD_DEADLINE required}" pid rc=0
  BUDGET_STOPPED=0; : > "$LOGS/build.log"
  (cd "$SRC" && exec make) > "$LOGS/build.log" 2>&1 &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    sleep 60; sample
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "budget reached: stopping make cleanly" | tee -a "$LOGS/build.log"
      BUDGET_STOPPED=1
      kill -TERM "$pid" 2>/dev/null || true; sleep 20
      for exe in make.exe cl.exe link.exe; do /cygdrive/c/Windows/system32/taskkill.exe /F /T /IM "$exe" >/dev/null 2>&1 || true; done
      break
    fi
  done
  wait "$pid" || rc=$?
  sample
  if [ "$BUDGET_STOPPED" -eq 1 ]; then return 0; fi
  return "$rc"
}

case "${1:-}" in
  --extract) phase extract do_extract 2>&1 | tee "$LOGS/extract.log"; exit "${PIPESTATUS[0]}" ;;
  --patch) phase patch do_patch ;;
  --configure) phase configure do_configure ;;
  --build) phase build do_build ;;
  *) echo "usage: $0 --extract|--patch|--configure|--build"; exit 64 ;;
esac
