#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# HST Office Windows trial build, run inside Cygwin bash (see .github/workflows/desktop-windows.yml).
#   trial-build.sh --extract | --tools | --options | --patch | --configure | --build
# Env: HST_WORK (Cygwin path, default /cygdrive/d/hst), HST_REPO (checkout), HST_BUILD_DEADLINE
# (epoch seconds; --build stops make cleanly then and returns 0 with status budget-stop).
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
PS4='+ [${BASH_SOURCE##*/}:${LINENO}] '
set -x
CYGPATH="${HST_CYGPATH:-cygpath}"
WORK="${HST_WORK:-/cygdrive/d/hst}"
REPO="${HST_REPO:?HST_REPO must point at the repository checkout}"
SRC="$WORK/lo"; LOGS="$WORK/logs"; METRICS="$WORK/metrics"; DL="${HST_DL:-$WORK/dl}"
CONF="$REPO/build-config/windows-x86_64.conf"
# HST release version (/VERSION) for the generated header, installer list and make;
# the repository root in Windows form for HST rules inside the native make.
eval "$(python3 "$REPO/scripts/write-hst-version.py" --env)"
export HST_VERSION_MAJOR HST_VERSION_MINOR HST_VERSION_MICRO
HST_REPO_ROOT="$("$CYGPATH" -m "$REPO")"; export HST_REPO_ROOT
mkdir -p "$LOGS" "$METRICS"
# Minimal PATH: Cygwin first, native make, NASM, Windows system. Avoids Strawberry perl / Git usr/bin shadowing.
if [ -z "${HST_KEEP_PATH:-}" ]; then
  export PATH="$WORK/bin:/usr/local/bin:/usr/bin:/cygdrive/c/Program Files/NASM:/cygdrive/c/Windows/system32:/cygdrive/c/Windows"
fi
export HOME="$WORK/home"; mkdir -p "$HOME"
# The job starts from Git Bash, whose MSYSTEM/MSYS* variables leak into Cygwin.
# gbuild reads a non-empty MSYSTEM as "WSL helper build" and maps every path
# through wslpath, which breaks all source paths on a Cygwin build.
unset MSYSTEM MSYSTEM_PREFIX MSYSTEM_CHOST MSYSTEM_CARCH MINGW_PREFIX MINGW_CHOST MINGW_PACKAGE_PREFIX MSYS2_ARG_CONV_EXCL

phase() { # phase <name> <command...>: run, time and record in phases.jsonl; propagate failure
  local name="$1" start rc=0 status; shift; start=$(date +%s)
  "$@" || rc=$?
  [ "$rc" -eq 0 ] || echo "FAILED phase $name: exit $rc" >&2
  status=ok; [ "$rc" -eq 0 ] || status="failed($rc)"
  [ "$rc" -ne 0 ] || [ "${BUDGET_STOPPED:-0}" -eq 0 ] || status=budget-stop
  printf '{"phase":"%s","seconds":%d,"status":"%s","free_gib":%s}\n' "$name" $(( $(date +%s) - start )) "$status" \
    "$(df -BG --output=avail "$WORK" | tail -1 | tr -dc 0-9)" >> "$METRICS/phases.jsonl"
  return "$rc"
}

extract_one() { # extract_one <tarball> <dest>; all three tarballs share one top-level libreoffice-<ver>/ root
  mkdir -p "$2"; tar --force-local -xf "$DL/$1" -C "$2" --strip-components=1
}

do_extract() {
  # errexit is suppressed inside phase(), so every step returns explicitly on failure.
  echo "extract: main source"; extract_one libreoffice-26.8.1.1.tar.xz "$SRC" || return 1
  rm -rf "$SRC/translations" "$SRC/dictionaries"
  echo "extract: translations"; extract_one libreoffice-translations-26.8.1.1.tar.xz "$SRC" || return 1
  echo "extract: dictionaries"; extract_one libreoffice-dictionaries-26.8.1.1.tar.xz "$SRC" || return 1
  [ -f "$SRC/configure.ac" ] || { echo "extract: configure.ac missing"; return 1; }
  [ -d "$SRC/translations/source/vi" ] || { echo "extract: vi translations missing"; find "$SRC/translations" -maxdepth 1 | head; return 1; }
  # A tarball tree's `make get-submodules` re-downloads (unchecked) and re-unpacks
  # translations/dictionaries unless src/libreoffice-<module>-<ver>/ exists; its
  # unpack-sources then calls tar on a D:/ path, which Cygwin tar rejects. The
  # verified copies are already merged above, so mark them as unpacked.
  mkdir -p "$SRC/src/libreoffice-translations-26.8.1.1" "$SRC/src/libreoffice-dictionaries-26.8.1.1" || return 1
  echo "extract: ok"
}

do_tools() { # report tool versions so a missing prerequisite is visible before configure
  local tool bad=0
  for tool in make nasm perl python3 autoconf automake bison flex gperf patch tar zip unzip git curl; do
    if command -v "$tool" >/dev/null; then "$tool" --version 2>&1 | head -1 || true; else echo "MISSING tool: $tool"; bad=1; fi
  done
  command -v cl.exe >/dev/null && echo "cl.exe on PATH (configure still locates VS itself)" || echo "cl.exe not on PATH (expected; configure uses vswhere/registry)"
  return "$bad"
}

do_patch() {
  HST_LO_SRC="$SRC" bash "$REPO/scripts/apply-patches.sh" || return 1
  # Same Vietnamese overlay + overrides as scripts/build-linux.sh (both idempotent).
  python3 -B "$REPO/scripts/l10n/merge-vi.py" --apply --tree "$SRC" || return 1
  python3 -B "$REPO/scripts/l10n/apply-overrides.py" --tree "$SRC" || return 1
}

options() { # configure options with the branding placeholder resolved
  grep -v '^\s*#' "$CONF" | sed '/^\s*$/d' | sed "s|@BRANDING@|$("$CYGPATH" -m "$WORK/branding")|"
}

do_options() { # validate every option against the pinned configure.ac, then write autogen.input
  options | while IFS= read -r opt; do
    base="${opt%%=*}"; base="${base#--}"; base="${base#with-}"; base="${base#without-}"; base="${base#enable-}"; base="${base#disable-}"
    case "$base" in host) continue ;; esac
    grep -qE "(AC_ARG_(WITH|ENABLE)|libo_FUZZ_ARG_(WITH|ENABLE))\($base," "$SRC/configure.ac" || { echo "unknown configure option: $opt"; exit 3; }
  done || return 3
  options > "$SRC/autogen.input" || return 1
  cat "$SRC/autogen.input"
}

do_configure() {
  test -f "$WORK/branding/staging-manifest.json" || { echo "branding not staged"; return 2; }
  do_options || return $?
  (cd "$SRC" && ./autogen.sh) 2>&1 | tee "$LOGS/configure.log"
  test "${PIPESTATUS[0]}" -eq 0 || return 1
  # Same HST version wiring as scripts/build-linux.sh prepare_version.
  python3 "$REPO/scripts/write-hst-version.py" --header "$SRC/include/hst_version.h" || return 1
  sed -i -e "s/@HST_VERSION_MAJOR@/$HST_VERSION_MAJOR/g" -e "s/@HST_VERSION_MINOR@/$HST_VERSION_MINOR/g" \
    -e "s/@HST_VERSION_MICRO@/$HST_VERSION_MICRO/g" "$SRC/instsetoo_native/util/openoffice.lst" || return 1
  if grep -q '@HST_VERSION' "$SRC/instsetoo_native/util/openoffice.lst"; then echo "configure: HST version placeholders left"; return 1; fi
}

do_fetch() { # download every external tarball (sha256-checked by gbuild) so preflight covers make's fetch stage
  # get-submodules re-fetches the core source tarballs without a checksum unless
  # they are already in TARFILE_LOCATION; reuse the copies verified against the lock.
  mkdir -p "$SRC/external/tarballs" || return 1
  cp -n "$DL"/libreoffice-translations-26.8.1.1.tar.xz "$DL"/libreoffice-dictionaries-26.8.1.1.tar.xz \
    "$SRC/external/tarballs/" || return 1
  (cd "$SRC" && make fetch) 2>&1 | tee "$LOGS/fetch.log"
  local rc=${PIPESTATUS[0]}
  [ "$rc" -eq 0 ] || return "$rc"
  # `make showmodules` parses all of gbuild, running its path helpers; a wrong
  # environment shows up here as failed helper processes before any compiler runs.
  (cd "$SRC" && make showmodules) 2>&1 | tee -a "$LOGS/fetch.log"
  rc=${PIPESTATUS[0]}
  if grep -qE 'process_begin: CreateProcess|wslpath|Bad file descriptor' "$LOGS/fetch.log"; then
    echo "fetch: gbuild path helpers failed (environment leak?)"; return 1
  fi
  # HST rules read the repository through HST_REPO_ROOT (native make path form).
  [ -f "$HST_REPO_ROOT/scripts/build-extensions.py" ] || { echo "fetch: HST_REPO_ROOT unusable: $HST_REPO_ROOT"; return 1; }
  # Any re-download of the core source tarballs means the tree layout is wrong.
  if grep -q 'Saving to: .*libreoffice-\(translations\|dictionaries\)-' "$LOGS/fetch.log"; then
    echo "fetch: make tried to re-download translations/dictionaries tarballs"; return 1
  fi
  return "$rc"
}

sample() { # one progress sample: steps compiled, free disk, memory used
  local steps free used
  steps=$(grep -c '^\[build ' "$LOGS/build.log" 2>/dev/null || true)
  free=$(df -BG --output=avail "$WORK" | tail -1 | tr -dc 0-9)
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
  --tools) phase tools do_tools ;;
  --options) phase options do_options ;;
  --patch) phase patch do_patch ;;
  --configure) phase configure do_configure ;;
  --fetch) phase fetch do_fetch ;;
  --build) phase build do_build ;;
  *) echo "usage: $0 --extract|--tools|--options|--patch|--configure|--fetch|--build"; exit 64 ;;
esac
