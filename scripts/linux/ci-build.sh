#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# HST Office Linux .deb build on a GitHub-hosted runner (see .github/workflows/desktop-linux.yml).
#   ci-build.sh --deps | --extract | --patch | --configure | --fetch | --build | --package
# Env: HST_WORK (work dir, default /mnt/hst), HST_DL (pinned tarballs, default $HST_WORK/dl),
# HST_BUILD_DEADLINE (epoch seconds; --build stops make there and fails with status budget-stop),
# HST_MIN_FREE_GIB (default 3; --build stops make and fails below this much free disk),
# HST_SUDO (default sudo; empty when already root, e.g. in a local container check).
# Same steps as scripts/build-linux.sh, minus the local build user: the runner user is not root.
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="${HST_WORK:-/mnt/hst}"
SRC="$WORK/lo"; LOGS="$WORK/logs"; METRICS="$WORK/metrics"; DL="${HST_DL:-$WORK/dl}"
CONF="$REPO/build-config/linux-x86_64.conf"
SUDO="${HST_SUDO-sudo}"
LO_VER=26.8.1.1
# System tools only: hosted-runner tool caches (Python, Java, CMake) must not leak into
# configure, or --enable-python=system would link against a non-distribution Python.
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
# HST release version (/VERSION) for the generated header, installer list and make;
# HST make rules find the repository through HST_REPO_ROOT (the tree is not under it).
# (--deps installs the toolchain, so it runs before python3 is required.)
if [ "${1:-}" != --deps ]; then
  version_env="$(python3 "$REPO/scripts/write-hst-version.py" --env)"
  eval "$version_env"
  export HST_VERSION_MAJOR HST_VERSION_MINOR HST_VERSION_MICRO
fi
export HST_REPO_ROOT="$REPO"
# The sysui packaging rule otherwise looks for the HST icons two levels above the tree.
export HST_ICON_DIR="$REPO/assets/brand/icons"
mkdir -p "$LOGS" "$METRICS"
# Tarball tree: the lock-verified translations/dictionaries are merged by --extract,
# so `make get-submodules` must not re-download (unchecked) and re-unpack them.
LO_MAKE=(make GIT_NEEDED_SUBMODULES=)

phase() { # phase <name> <command...>: run, time and record in phases.jsonl; propagate failure
  local name="$1" start rc=0 status; shift; start=$(date +%s)
  "$@" || rc=$?
  [ "$rc" -eq 0 ] || echo "FAILED phase $name: exit $rc" >&2
  status=ok; [ "$rc" -eq 0 ] || status="failed($rc)"
  [ "${STOP_REASON:-}" = "" ] || status="$STOP_REASON"
  printf '{"phase":"%s","seconds":%d,"status":"%s","free_gib":%s}\n' "$name" $(( $(date +%s) - start )) "$status" \
    "$(df -BG --output=avail "$WORK" | tail -1 | tr -dc 0-9)" >> "$METRICS/phases.jsonl"
  return "$rc"
}

do_deps() {
  # LibreOffice build dependencies from the distribution's own source package (same as the
  # local build host, docs/UPSTREAM_BASELINE.md), plus Pillow for scripts/stage-branding.py and ninja (the bundled harfbuzz/meson build needs it).
  local sources=/etc/apt/sources.list.d/ubuntu.sources
  [ -f "$sources" ] || { echo "deps: $sources missing (expected Ubuntu 24.04 deb822 sources)"; return 1; }
  $SUDO sed -i 's/^Types: deb$/Types: deb deb-src/' "$sources" || return 1
  $SUDO apt-get update -qq || return 1
  $SUDO env DEBIAN_FRONTEND=noninteractive apt-get build-dep -y -qq libreoffice || return 1
  $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    python3 python3-pil zip unzip xz-utils patch fakeroot ninja-build curl ca-certificates || return 1
  gcc --version | head -1; python3 --version; make --version | head -1
}

extract_one() { # extract_one <tarball> <dest>; all three tarballs share one libreoffice-<ver>/ root
  mkdir -p "$2"; tar -xf "$DL/$1" -C "$2" --strip-components=1
}

do_extract() {
  # errexit is suppressed inside phase(), so every step returns explicitly on failure.
  rm -rf "$SRC" || return 1
  echo "extract: main source"; extract_one "libreoffice-$LO_VER.tar.xz" "$SRC" || return 1
  rm -rf "$SRC/translations" "$SRC/dictionaries"
  echo "extract: translations"; extract_one "libreoffice-translations-$LO_VER.tar.xz" "$SRC" || return 1
  echo "extract: dictionaries"; extract_one "libreoffice-dictionaries-$LO_VER.tar.xz" "$SRC" || return 1
  [ -f "$SRC/configure.ac" ] || { echo "extract: configure.ac missing"; return 1; }
  [ -d "$SRC/translations/source/vi" ] || { echo "extract: vi translations missing"; return 1; }
  echo "extract: ok"
}

do_patch() {
  HST_LO_SRC="$SRC" bash "$REPO/scripts/apply-patches.sh" || return 1
  # Same Vietnamese overlay + overrides as scripts/build-linux.sh (both idempotent).
  python3 -B "$REPO/scripts/l10n/merge-vi.py" --apply --tree "$SRC" || return 1
  python3 -B "$REPO/scripts/l10n/apply-overrides.py" --tree "$SRC" || return 1
  # HST icons in place of LibreOffice-shaped ones (same step as scripts/build-linux.sh).
  python3 -B "$REPO/scripts/brand/apply-icon-overrides.py" --tree "$SRC" || return 1
}

options() { # linux-x86_64.conf with this runner's branding dir and CPU count
  grep -v '^\s*#' "$CONF" | sed '/^\s*$/d' \
    | sed -e "s|^--with-branding=.*|--with-branding=$WORK/branding|" -e "s|^--with-parallelism=.*|--with-parallelism=$(nproc)|"
}

do_options() { # validate every option against the pinned configure.ac, then write autogen.input
  options | while IFS= read -r opt; do
    base="${opt%%=*}"; base="${base#--}"; base="${base#with-}"; base="${base#without-}"; base="${base#enable-}"; base="${base#disable-}"
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

do_fetch() { # download every external tarball (sha256-checked by gbuild) before the timed build
  mkdir -p "$SRC/external/tarballs" || return 1
  cp -n "$DL/libreoffice-translations-$LO_VER.tar.xz" "$DL/libreoffice-dictionaries-$LO_VER.tar.xz" \
    "$SRC/external/tarballs/" || return 1
  (cd "$SRC" && "${LO_MAKE[@]}" fetch) 2>&1 | tee "$LOGS/fetch.log"
  local rc=${PIPESTATUS[0]}
  [ "$rc" -eq 0 ] || return "$rc"
  [ -f "$HST_REPO_ROOT/scripts/build-extensions.py" ] || { echo "fetch: HST_REPO_ROOT unusable: $HST_REPO_ROOT"; return 1; }
  if grep -q 'Saving to: .*libreoffice-\(translations\|dictionaries\)-' "$LOGS/fetch.log"; then
    echo "fetch: make tried to re-download translations/dictionaries tarballs"; return 1
  fi
}

free_gib() { df -BG --output=avail "$WORK" | tail -1 | tr -dc 0-9; }

sample() { # one progress sample: steps compiled, free disk, memory and swap used
  local steps
  steps=$(grep -c '^\[build ' "$LOGS/build.log" 2>/dev/null || true)
  printf '{"t":%d,"steps":%s,"free_gib":%s,"mem_used_gib":%s,"swap_used_gib":%s}\n' "$(date +%s)" "${steps:-0}" "$(free_gib)" \
    "$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{printf "%.1f",(t-a)/1048576}' /proc/meminfo)" \
    "$(awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{printf "%.1f",(t-f)/1048576}' /proc/meminfo)" >> "$METRICS/progress.jsonl"
}

do_build() {
  local deadline="${HST_BUILD_DEADLINE:?HST_BUILD_DEADLINE required}" min_free="${HST_MIN_FREE_GIB:-3}" pid rc=0
  STOP_REASON=""; : > "$LOGS/build.log"
  # Plain `make` = build incl. instsetoo_native, which writes the .deb sets (--with-package-format=deb).
  (cd "$SRC" && exec setsid "${LO_MAKE[@]}") > "$LOGS/build.log" 2>&1 &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    sleep 30; sample
    if [ "$(date +%s)" -ge "$deadline" ]; then STOP_REASON=budget-stop
    elif [ "$(free_gib)" -lt "$min_free" ]; then STOP_REASON=disk-stop
    fi
    if [ -n "$STOP_REASON" ]; then
      echo "$STOP_REASON: stopping make" | tee -a "$LOGS/build.log"
      kill -TERM -- "-$pid" 2>/dev/null || true; sleep 20; kill -KILL -- "-$pid" 2>/dev/null || true
      break
    fi
  done
  wait "$pid" || rc=$?
  sample
  [ -z "$STOP_REASON" ] || return 1
  [ "$rc" -eq 0 ] || { tail -60 "$LOGS/build.log"; return "$rc"; }
  test -x "$SRC/instdir/program/soffice" || { echo "build did not produce instdir/program/soffice"; return 1; }
}

do_package() { # HSTOffice_<ver>_Linux_x86-64_deb.tar.gz (folder of .deb + inner SHA256SUMS) + outer SHA256SUMS
  local inst="$SRC/workdir/installation" out="$WORK/installer" ver name d n
  ver="$(python3 "$REPO/scripts/write-hst-version.py" --print)" || return 1
  name="HSTOffice_${ver}_Linux_x86-64_deb"
  # An installer run that logged errors leaves "<name>_deb_witherror": never ship that.
  if find "$inst" -maxdepth 4 -name '*_witherror' | grep -q .; then
    echo "package: installer reported errors:"; find "$inst" -maxdepth 4 -name '*_witherror'; return 1
  fi
  rm -rf "$out" "$WORK/pkg"; mkdir -p "$out" "$WORK/pkg/$name" || return 1
  for d in HSTOffice HSTOffice_languagepack; do
    [ -d "$inst/$d/deb/install" ] || { echo "package: missing $inst/$d/deb/install"; return 1; }
    find "$inst/$d/deb/install" -path '*/DEBS/*.deb' -exec cp -p {} "$WORK/pkg/$name/" \; || return 1
  done
  n=$(find "$WORK/pkg/$name" -name '*.deb' | wc -l)
  [ "$n" -gt 0 ] || { echo "package: no .deb produced"; return 1; }
  (cd "$WORK/pkg/$name" && sha256sum -- *.deb > SHA256SUMS) || return 1
  tar -C "$WORK/pkg" -czf "$out/$name.tar.gz" "$name" || return 1
  (cd "$out" && sha256sum -- "$name.tar.gz" > SHA256SUMS) || return 1
  echo "package: $n .deb, $(du -sm "$WORK/pkg/$name" | cut -f1) MiB unpacked -> $out/$name.tar.gz ($(du -m "$out/$name.tar.gz" | cut -f1) MiB)"
  cat "$out/SHA256SUMS"
}

case "${1:-}" in
  --deps) phase deps do_deps 2>&1 | tee "$LOGS/deps.log"; exit "${PIPESTATUS[0]}" ;;
  --extract) phase extract do_extract 2>&1 | tee "$LOGS/extract.log"; exit "${PIPESTATUS[0]}" ;;
  --patch) phase patch do_patch 2>&1 | tee "$LOGS/patch.log"; exit "${PIPESTATUS[0]}" ;;
  --options) do_options ;;
  --configure) phase configure do_configure ;;
  --fetch) phase fetch do_fetch ;;
  --build) phase build do_build ;;
  --package) phase package do_package 2>&1 | tee "$LOGS/package.log"; exit "${PIPESTATUS[0]}" ;;
  *) echo "usage: $0 --deps|--extract|--patch|--options|--configure|--fetch|--build|--package"; exit 64 ;;
esac
