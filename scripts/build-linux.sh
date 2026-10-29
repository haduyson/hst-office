#!/usr/bin/env bash
# Build HST Office (LibreOffice 26.8.1.1 + HST patches/branding) on Linux x86_64.
#   scripts/build-linux.sh --preflight | --configure | --build | --package
# Runs upstream commands as the unprivileged build user $HST_BUILD_USER
# (default hstbuild) inside upstream/libreoffice; logs go to build/logs/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/upstream/libreoffice"
CONF="$ROOT/build-config/linux-x86_64.conf"
LOGS="$ROOT/build/logs"
BUILD_USER="${HST_BUILD_USER:-hstbuild}"
export CCACHE_DIR="$ROOT/upstream/ccache"
mkdir -p "$LOGS"

as_builder() {
  # Log the exact upstream command, then run it as the build user in the source tree.
  echo "+ (cd $SRC && $*)" | tee -a "$LOGS/commands.log"
  runuser -u "$BUILD_USER" -- env CCACHE_DIR="$CCACHE_DIR" HOME="$ROOT/build/home-$BUILD_USER" \
    bash -c "cd '$SRC' && $*"
}

preflight() {
  [ -f "$SRC/configure.ac" ] || { echo "missing source tree $SRC (run scripts/fetch-libreoffice.py)"; exit 2; }
  [ -f "$CONF" ] || { echo "missing $CONF"; exit 2; }
  id "$BUILD_USER" >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin "$BUILD_USER"
  mkdir -p "$CCACHE_DIR" "$ROOT/build/home-$BUILD_USER"
  chown -R "$BUILD_USER" "$SRC" "$CCACHE_DIR" "$ROOT/build/home-$BUILD_USER"
  # Every option in the conf file must exist in the pinned configure.ac.
  grep -v '^\s*#' "$CONF" | sed '/^\s*$/d' | while IFS= read -r opt; do
    name="${opt%%=*}"; name="${name#--}"; base="${name#with-}"; base="${base#without-}"; base="${base#enable-}"; base="${base#disable-}"
    grep -qE "(AC_ARG_(WITH|ENABLE)|libo_FUZZ_ARG_(WITH|ENABLE))\($base," "$SRC/configure.ac" || { echo "unknown configure option: $opt"; exit 3; }
  done
  [ -f "$ROOT/build/branding-staging/staging-manifest.json" ] || { echo "run scripts/stage-branding.py first"; exit 2; }
  echo "free: $(df -h --output=avail "$ROOT" | tail -1) ; cpus: $(nproc) ; mem: $(free -g | awk '/Mem/{print $7}') GiB available"
  echo "preflight ok"
}

configure() {
  grep -v '^\s*#' "$CONF" | sed '/^\s*$/d' > "$SRC/autogen.input"
  chown "$BUILD_USER" "$SRC/autogen.input"
  as_builder "ccache --max-size=4G >/dev/null && ./autogen.sh" 2>&1 | tee "$LOGS/configure.log"
}

build() {
  as_builder "make build" 2>&1 | tee "$LOGS/build.log" | grep -E '^\[|error|Error' | tail -5
  test -x "$SRC/instdir/program/soffice" || { echo "build did not produce instdir/program/soffice"; exit 1; }
}

package() {
  # Upstream installer target honouring --with-package-format=deb.
  as_builder "make" 2>&1 | tee "$LOGS/package.log" | tail -5
  find "$SRC/workdir/installation" -name '*.deb' | head -50
}

case "${1:-}" in
  --preflight) preflight ;;
  --configure) preflight; configure ;;
  --build) build ;;
  --package) package ;;
  *) echo "usage: $0 --preflight|--configure|--build|--package"; exit 64 ;;
esac
