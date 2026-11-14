#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Local incremental build of the HST Office Linux .deb, with the same steps as CI
# (.github/workflows/desktop-linux.yml + scripts/linux/ci-build.sh of the branch being built), in one of the
# parallel build slots under HST_BUILD_ROOT (default /data/hst-build). Agents normally go through the queue
# (scripts/build-queue.sh, docs/BUILD_MATRIX.md); this script is what the queue runs.
#
#   sudo scripts/linux/local-build.sh [options] <ref | worktree-path>
#     <ref>            branch, tag or sha of this repository (fetched from origin first;
#                      origin/<ref> wins over a local branch of the same name)
#     <worktree-path>  a checkout; its tracked + untracked (not ignored) files, uncommitted
#                      changes included, are built (output label gets "-dirty")
#   --slot N|auto      build slot (default auto: the first idle slot the admission controller accepts)
#   -j, --jobs N       upper limit for make parallelism (default 20); the admission controller
#                      (scripts/linux/build-slots.py) decides the real -j from the other running slots
#   --modules a,b,...  test-only partial build: `make <module>.build` (or a make target containing "." or "_")
#                      instead of a full make, then a patch overlay of the changed instdir files instead of a .deb
#   --test "T1 T2 ..."  after the (incremental, unpackaged) build, run these test targets one by one with
#                      `make <target>` in the slot chroot (CppunitTest_*, PythonTest_*, <module>.check/.unitcheck/
#                      .slowcheck/.subsequentcheck); pass/fail per target in <out>/test-results.json, logs in
#                      <out>/test-logs/; failing tests do not fail the run (comma or space separated)
#   --label NAME       output label (default: the branch name)
#   --out DIR          output directory (default $HST_BUILD_ROOT/out/<label>-<sha>)
#   --reconfigure      run the configure phase even when nothing it depends on changed
#   --fresh            re-extract the pristine tarballs (full rebuild)
#   --no-package       stop after make (skip the single-.deb packaging)
#   --umount           only unmount the slot's chroot (after a crashed run) and exit (needs --slot N)
#
# Layout under HST_BUILD_ROOT:
#   chroot/    base root file system of the CI container image (same digest), build deps from
#              `ci-build.sh --deps` + ccache, rpm, file; read-only for builds (overlayfs lower layer of every slot)
#   ccache/    shared CCACHE_DIR (max HST_CCACHE_MAX, default 30G)   external-tarballs/  hard-link cache
#   out/       <label>-<sha>/ outputs of direct runs: .deb, plus .rpm and .AppImage for refs whose ci-build.sh
#              has --rpm-appimage                                  locks/  admission state (build-slots.py), chroot lock
#   slots/<N>/ one build tree each: root/ (overlay of chroot/ + chroot-upper/), checkout/, src/ (HST_WORK:
#              lo/, dl/, pristine.git, installer/), logs/<time>-<label>/ (wrapper.log, build.log, timings.tsv,
#              memory.tsv), .lock
# Inside every slot's chroot the tree is mounted at the same canonical paths (/data/hst-office-build/src,
# checkout, ccache, logs: where slot 1 was first built). LibreOffice build trees are not relocatable, so this
# keeps a tree valid when it is copied to another slot and lets all slots share ccache hits.
#
# Patch re-sync: every run resets the files the previous series touched to the pristine
# tarball state, applies the series exactly like CI (`ci-build.sh --patch`), and gives files
# whose content did not change their previous mtime back, so make rebuilds only what changed.
# Differences from CI, none of which changes what is compiled: a chroot instead of a docker
# container, ccache, -j from the admission controller instead of nproc, and resource caps for a shared
# server: make runs in a systemd scope (MemoryMax = the slot budget, MemoryHigh 90 % of it, MemorySwapMax=0,
# CPUQuota = jobs x 100 %) at nice 19 and idle I/O priority. The controller's global guard tells the most
# recently admitted slot to freeze when MemAvailable < 6 GiB or swap use grew by > 1 GiB; a slot thaws at
# HST_LOCAL_RESUME_MEM_GIB (8) GiB, and a repeated or swap pause restarts its make with half the jobs (min 2;
# abort after HST_LOCAL_MEM_WAIT_MIN, default 30, minutes); only one heavy (>= 1 GiB) link per slot at a time.
# The whole script is one { } group: bash parses it completely before running it, so updating this file (the
# queue dispatcher's checkout) never changes a build that is already running.
# shellcheck disable=SC2317 # shellcheck's reachability analysis gives up inside the group (false "unreachable")
{
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR

SELF_REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd -P)"   # real deploy dir, not a symlink
SLOTS_PY=(python3 -I "$SELF_REPO/scripts/linux/build-slots.py")
BUILD_ROOT="${HST_BUILD_ROOT:-/data/hst-build}"
BASE="$BUILD_ROOT/chroot"; CCACHE="$BUILD_ROOT/ccache"; EXT_CACHE="$BUILD_ROOT/external-tarballs"
# Canonical paths inside every slot chroot (see the header).
C_ROOT=/data/hst-office-build; C_WORK="$C_ROOT/src"; C_SRC="$C_WORK/lo"; C_CHECKOUT="$C_ROOT/checkout"
C_CCACHE="$C_ROOT/ccache"; C_LOGROOT="$C_ROOT/logs"
TARBALL_CACHE="${HST_LOCAL_TARBALL_CACHE:-/home/office/upstream/cache/libreoffice}"
RESUME_MEM_GIB="${HST_LOCAL_RESUME_MEM_GIB:-8}"; MAX_JOBS=20
MEM_WAIT_MIN="${HST_LOCAL_MEM_WAIT_MIN:-30}"; MIN_FREE_GIB="${HST_LOCAL_MIN_FREE_GIB:-5}"
CCACHE_MAX="${HST_CCACHE_MAX:-30G}"
# Optional systemd slice for the make scopes (a remote build host caps all its builds together in hst-build.slice).
SLICE="${HST_LOCAL_SLICE:-}"
[ -z "$SLICE" ] || [[ "$SLICE" =~ ^[A-Za-z0-9_-]+\.slice$ ]] || { echo "local-build: bad HST_LOCAL_SLICE" >&2; exit 64; }
JOBS=$MAX_JOBS; RECONFIGURE=0; FRESH=0; PACKAGE=1; TARGET=""; BUILD_PGID=""; MOUNTED=0; ADMITTED=0; BASE_MOUNTED=0
SLOT=auto; MODULES=""; TESTS=""; LABEL_OPT=""; OUT_OPT=""; UMOUNT_ONLY=0

usage() { sed -n '7,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 64; }
die() { echo "local-build: $*" >&2; exit 1; }
log() { echo "[$(date '+%F %T')] $*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    -j|--jobs) JOBS="${2:-}"; shift 2 ;;
    -j[0-9]*) JOBS="${1#-j}"; shift ;;
    --slot) SLOT="${2:-}"; shift 2 ;;
    --modules) MODULES="${2:-}"; shift 2 ;;
    --test) TESTS="${2:-}"; shift 2 ;;
    --label) LABEL_OPT="${2:-}"; shift 2 ;;
    --out) OUT_OPT="${2:-}"; shift 2 ;;
    --reconfigure) RECONFIGURE=1; shift ;;
    --fresh) FRESH=1; shift ;;
    --no-package) PACKAGE=0; shift ;;
    --umount) UMOUNT_ONLY=1; shift ;;
    -h|--help) usage ;;
    -*) die "unknown option $1" ;;
    *) [ -z "$TARGET" ] || die "only one ref or worktree"; TARGET="$1"; shift ;;
  esac
done
[ -n "$TARGET" ] || [ "$UMOUNT_ONLY" -eq 1 ] || usage
if ! [[ "$JOBS" =~ ^[1-9][0-9]*$ ]]; then die "--jobs needs a positive number"; fi
if [ "$JOBS" -gt "$MAX_JOBS" ]; then echo "local-build: -j capped at $MAX_JOBS" >&2; JOBS=$MAX_JOBS; fi
[[ "$SLOT" =~ ^(auto|[1-9][0-9]?)$ ]] || die "--slot needs a slot number or auto"
[ -z "$LABEL_OPT" ] || [[ "$LABEL_OPT" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$ ]] || die "--label: letters, digits, . _ - only"
[ -z "$OUT_OPT" ] || [[ "$OUT_OPT" = /* ]] || die "--out needs an absolute path"
MAKE_TARGETS=()
if [ -n "$MODULES" ]; then
  IFS=, read -r -a mods <<< "$MODULES"
  for m in "${mods[@]}"; do
    [[ "$m" =~ ^[A-Za-z0-9][A-Za-z0-9_.+-]*$ ]] || die "--modules: bad module or target '$m'"
    # A bare module name builds just that module (`sc.build`); names with "." or "_" are make targets as is
    # (Library_merged, sc.check, ...).
    if [[ "$m" == *[._]* ]]; then MAKE_TARGETS+=("$m"); else MAKE_TARGETS+=("$m.build"); fi
  done
  [ "${#MAKE_TARGETS[@]}" -gt 0 ] || die "--modules needs at least one module"
  PACKAGE=0
fi
TEST_TARGETS=()
if [ -n "$TESTS" ]; then
  read -r -a TEST_TARGETS <<< "${TESTS//,/ }"
  for t in "${TEST_TARGETS[@]}"; do
    [[ "$t" =~ ^((CppunitTest|PythonTest)_[A-Za-z0-9_]+|[a-z0-9_]+\.(check|unitcheck|slowcheck|subsequentcheck))$ ]] \
      || die "--test: '$t' is not a CppunitTest_*/PythonTest_* or <module>.check-style target"
  done
  [ "${#TEST_TARGETS[@]}" -gt 0 ] || die "--test needs at least one target"
  PACKAGE=0
fi
MAKE_KIND=full; [ -z "$MODULES" ] || MAKE_KIND=modules
[ "$(id -u)" -eq 0 ] || die "needs root (chroot and mounts)"
for tool in git rsync chroot mount flock python3 sha256sum systemd-run systemctl ionice; do   # docker: update_base
  command -v "$tool" >/dev/null || die "missing host tool: $tool"
done
if [ ! -d "$BASE" ] || [ ! -d "$BUILD_ROOT/slots" ]; then die "$BUILD_ROOT is not set up (scripts/linux/build-slots-setup.sh)"; fi

# ---------------------------------------------------------------- slot selection and lock
if [ "$SLOT" = auto ]; then
  [ "$UMOUNT_ONLY" -eq 0 ] || die "--umount needs --slot N"
  SLOT="$("${SLOTS_PY[@]}" free-slot --want "$JOBS")" || die "no idle admissible slot now (see: ${SLOTS_PY[*]} status)"
fi
ROOT="$BUILD_ROOT/slots/$SLOT"
[ -d "$ROOT/src" ] || die "slot $SLOT does not exist under $BUILD_ROOT/slots"
CHROOT="$ROOT/root"; UPPER="$ROOT/chroot-upper"; OVLWORK="$ROOT/chroot-work"
CHECKOUT="$ROOT/checkout"; STAGE="$ROOT/stage"; LOGROOT="$ROOT/logs"
WORK="$ROOT/src"; SRC="$WORK/lo"; DL="$WORK/dl"; PRISTINE="$WORK/pristine.git"; SYNC="$WORK/sync"
OUT="$BUILD_ROOT/out"
mkdir -p "$WORK" "$CCACHE" "$OUT" "$LOGROOT/ci" "$CHECKOUT" "$BUILD_ROOT/locks"
exec 9>"$ROOT/.lock"
flock -n 9 || die "slot $SLOT is busy (another local build holds $ROOT/.lock)"
# Base chroot: builds hold it shared while their overlay is mounted; only a deps update takes it exclusively.
exec 8>"$BUILD_ROOT/locks/chroot.lock"

# ---------------------------------------------------------------- chroot and mounts
mounts_under() { awk -v p="$1/" 'index($5, p) == 1 {print $5}' /proc/self/mountinfo; }

umount_tree() { # umount_tree <dir>: everything mounted below <dir>, deepest first, then <dir> itself
  local m
  mounts_under "$1" | sort -r | while IFS= read -r m; do umount -R "$m" 2>/dev/null || umount -R -l "$m" || true; done
  if mountpoint -q "$1"; then umount "$1" 2>/dev/null || umount -l "$1" || true; fi
  if [ -n "$(mounts_under "$1")" ] || mountpoint -q "$1"; then die "could not unmount $1: $(mounts_under "$1" | tr '\n' ' ')"; fi
}
umount_chroot() { umount_tree "$CHROOT"; MOUNTED=0; }

bind_at() { # bind_at <root> <host dir> <path inside the root>
  mkdir -p "$1$3"
  mountpoint -q "$1$3" || { mount --bind "$2" "$1$3"; mount --make-private "$1$3"; }
}

mount_system() { # mount_system <root>: proc, sys and an own minimal /dev
  local r="$1"
  mountpoint -q "$r/proc" || mount -t proc proc "$r/proc"
  mountpoint -q "$r/sys" || { mount --rbind /sys "$r/sys"; mount --make-rslave "$r/sys"; }
  # Own minimal /dev (not a bind of the host's): device permissions stay standard whatever the host has.
  if ! mountpoint -q "$r/dev"; then
    local d=$r/dev
    mount -t tmpfs -o mode=755,size=16m,nosuid tmpfs "$d"; mount --make-private "$d"
    mknod -m 666 "$d/null" c 1 3; mknod -m 666 "$d/zero" c 1 5; mknod -m 666 "$d/full" c 1 7
    mknod -m 666 "$d/random" c 1 8; mknod -m 666 "$d/urandom" c 1 9; mknod -m 666 "$d/tty" c 5 0
    ln -s /proc/self/fd "$d/fd"; ln -s fd/0 "$d/stdin"; ln -s fd/1 "$d/stdout"; ln -s fd/2 "$d/stderr"
    mkdir -m 755 "$d/pts"; mkdir -m 1777 "$d/shm"
    mount -t devpts -o newinstance,ptmxmode=0666,mode=620 devpts "$d/pts"; ln -s pts/ptmx "$d/ptmx"
    mount -t tmpfs -o mode=1777,size=2g,nosuid,nodev tmpfs "$d/shm"
  fi
  bind_at "$r" "$WORK" "$C_WORK"; bind_at "$r" "$CCACHE" "$C_CCACHE"; bind_at "$r" "$CHECKOUT" "$C_CHECKOUT"
  bind_at "$r" "$LOGROOT" "$C_LOGROOT"
}

base_marker() { cat "$BASE/.hst-image" "$BASE/.hst-deps" 2>/dev/null | sha256sum | cut -c1-16; }

mount_chroot() { # the slot's overlay of the base chroot (writes go to chroot-upper/, reset when the base changes)
  if ! mountpoint -q "$CHROOT"; then
    if [ "$(cat "$ROOT/.chroot-base" 2>/dev/null)" != "$(base_marker)" ]; then rm -rf "$UPPER" "$OVLWORK"; fi
    mkdir -p "$CHROOT" "$UPPER" "$OVLWORK"
    mount -t overlay overlay -o "lowerdir=$BASE,upperdir=$UPPER,workdir=$OVLWORK" "$CHROOT"
    mount --make-private "$CHROOT"
    base_marker > "$ROOT/.chroot-base"
  fi
  MOUNTED=1
  mount_system "$CHROOT"
  cp -L /etc/resolv.conf "$CHROOT/etc/resolv.conf"
}

cleanup() {
  local rc=$?
  if [ -n "$BUILD_PGID" ]; then log "stopping make ($SCOPE.scope)"; stop_make; fi
  [ "$ADMITTED" -eq 0 ] || "${SLOTS_PY[@]}" release --slot "$SLOT" || true
  [ "$MOUNTED" -eq 0 ] || umount_chroot || true
  if [ -n "$(mounts_under "$BASE")" ] && [ "$BASE_MOUNTED" -eq 1 ]; then umount_tree "$BASE" || true; fi
  rm -rf "$STAGE"
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

if [ "$UMOUNT_ONLY" -eq 1 ]; then umount_chroot; log "slot $SLOT chroot unmounted"; exit 0; fi

# in_chroot <dir> <cmd...>: run in the slot chroot with the same environment docker exec gives CI
in_chroot() {
  local dir="$1"; shift
  # shellcheck disable=SC2016 # expanded by the inner shell
  nice -n 19 ionice -c3 chroot "${IN_ROOT:-$CHROOT}" /usr/bin/env -i HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin \
    HST_IN_CONTAINER=1 HST_SUDO= HST_WORK="$C_WORK" HST_DL="$C_WORK/dl" HST_CLANG="$CLANG" CCACHE_DIR="$C_CCACHE" \
    /bin/bash -c 'cd "$0" && exec "$@"' "$dir" "$@"
}
ci() { in_chroot "$C_CHECKOUT" bash "$C_CHECKOUT/scripts/linux/ci-build.sh" "$@"; }

# ---------------------------------------------------------------- timings
RUN_ID="$(date +%Y%m%d-%H%M%S)"
timed() { # timed <phase> <command...>; not under `||`, so errexit stays active inside the phase
  local name="$1" start; shift; start=$(date +%s)
  log "phase $name: start"
  "$@"
  printf '%s\t%d\n' "$name" $(( $(date +%s) - start )) >> "$RUN_LOGS/timings.tsv"
  log "phase $name: done in $(( $(date +%s) - start ))s"
}

# ---------------------------------------------------------------- source checkout
resolve_source() {
  rm -rf "$STAGE"; mkdir -p "$STAGE"
  if [ -d "$TARGET" ]; then
    local wt; wt="$(cd "$TARGET" && git rev-parse --show-toplevel)" || die "$TARGET is not a git checkout"
    SHA="$(git -C "$wt" rev-parse --short=10 HEAD)"
    LABEL="$(git -C "$wt" symbolic-ref -q --short HEAD || basename "$wt")"
    [ -z "$(git -C "$wt" status --porcelain)" ] || SHA="$SHA-dirty"
    (cd "$wt" && git ls-files -z -co --exclude-standard | tar --null --ignore-failed-read -T - -cf -) \
      | tar -xf - -C "$STAGE"
  else
    git -C "$SELF_REPO" fetch -q origin || log "warning: git fetch origin failed, using local refs"
    local full
    full="$(git -C "$SELF_REPO" rev-parse -q --verify "origin/$TARGET^{commit}" \
      || git -C "$SELF_REPO" rev-parse -q --verify "$TARGET^{commit}")" || die "unknown ref $TARGET"
    SHA="$(git -C "$SELF_REPO" rev-parse --short=10 "$full")"; LABEL="$TARGET"
    git -C "$SELF_REPO" archive "$full" | tar -xf - -C "$STAGE"
  fi
  [ -z "$LABEL_OPT" ] || LABEL="$LABEL_OPT"
  LABEL="${LABEL//\//_}"
  # Content compare (-c, no -t): unchanged files keep their mtime, so HST make rules stay up to date.
  rsync -rlpc --delete "$STAGE/" "$CHECKOUT/"
  rm -rf "$STAGE"
  local wf="$CHECKOUT/.github/workflows/desktop-linux.yml"
  IMAGE="$(sed -n 's/^ *HST_CONTAINER: *//p' "$wf" | head -1)"
  CLANG="$(sed -n "s/^ *HST_CLANG: *'\{0,1\}\([0-9]*\)'\{0,1\}.*/\1/p" "$wf" | head -1)"
  [ -n "$IMAGE" ] || die "HST_CONTAINER not found in $wf"
}

# ---------------------------------------------------------------- toolchain (base chroot, shared by all slots)
deps_want() {
  echo "clang=$CLANG $(sed -n '/^do_deps()/,/^}/p' "$CHECKOUT/scripts/linux/ci-build.sh" | sha256sum | cut -c1-16)"
}
base_current() { [ "$(cat "$BASE/.hst-image" 2>/dev/null)" = "$IMAGE" ] && [ "$(cat "$BASE/.hst-deps" 2>/dev/null)" = "$(deps_want)" ]; }

update_base() { # recreate/extend the base chroot; runs with the chroot lock held exclusively
  if grep -q " overlay .*lowerdir=${BASE}[,:]" /proc/self/mountinfo; then
    die "another slot still has an overlay of $BASE mounted (crashed run? local-build.sh --umount --slot N)"
  fi
  if [ "$(cat "$BASE/.hst-image" 2>/dev/null)" != "$IMAGE" ]; then
    [ -z "$(mounts_under "$BASE")" ] || die "base chroot still mounted"
    log "creating base chroot from $IMAGE"
    command -v docker >/dev/null || die "docker is needed to create the base chroot from $IMAGE (a remote build host gets a copy of the dev server's chroot instead)"
    local had_image=0 cid
    docker image inspect "$IMAGE" >/dev/null 2>&1 && had_image=1
    [ "$had_image" -eq 1 ] || docker pull -q "$IMAGE" >/dev/null
    rm -rf "$BASE"; mkdir -p "$BASE"
    cid="$(docker create "$IMAGE" true)"
    docker export "$cid" | tar -xf - -C "$BASE"
    docker rm "$cid" >/dev/null
    [ "$had_image" -eq 1 ] || docker rmi "$IMAGE" >/dev/null || true # keep the root disk clean
    printf '%s\n' "$IMAGE" > "$BASE/.hst-image"
  fi
  if [ "$(cat "$BASE/.hst-deps" 2>/dev/null)" != "$(deps_want)" ]; then
    BASE_MOUNTED=1; mount_system "$BASE"
    IN_ROOT="$BASE" ci --deps
    # rpm and file: what `ci-build.sh --rpm-appimage` needs (it installs them itself into a slot's overlay when the
    # base predates them; the base gets them the next time it is rebuilt).
    IN_ROOT="$BASE" in_chroot / env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends ccache rpm file
    deps_want > "$BASE/.hst-deps"
    umount_tree "$BASE"; BASE_MOUNTED=0
  fi
}

ensure_toolchain() {
  if ! base_current; then
    log "base chroot needs an update: waiting until no other slot uses it"
    flock -x 8
    base_current || update_base
  fi
  flock -s 8   # (downgrades an exclusive lock) held until exit
  base_current || die "base chroot changed under us; rerun"
}

# ---------------------------------------------------------------- pristine tree
pgit() { git --git-dir="$PRISTINE" --work-tree="$SRC" -c core.quotePath=false "$@"; }

ensure_tarballs() { # pinned tarballs in $DL: local cache copy, else download like CI; sha256 from the lock
  local lock="$CHECKOUT/upstream/libreoffice-lock.json" name sum missing=0
  mkdir -p "$DL"
  while read -r name sum; do
    if [ ! -f "$DL/$name" ] && [ -f "$TARBALL_CACHE/$name" ]; then cp "$TARBALL_CACHE/$name" "$DL/$name"; fi
    if [ -f "$DL/$name" ] && echo "$sum  $DL/$name" | sha256sum -c --quiet -; then continue; fi
    rm -f "$DL/$name"; missing=1
  done < <(python3 -I -c 'import json,sys; [print(t["name"], t["sha256"]) for t in json.load(open(sys.argv[1]))["tarballs"]]' "$lock")
  [ "$missing" -eq 0 ] || python3 -I "$CHECKOUT/scripts/windows/fetch-sources.py" --dest "$DL"
}

ensure_pristine() { # extract like CI once, then index the untouched tree (outside $SRC: no .git there,
  # or LibreOffice would treat it as a git build and rerun autogen.sh on its own)
  local want; want="$(sha256sum "$CHECKOUT/upstream/libreoffice-lock.json" | cut -c1-16)"
  [ "$FRESH" -eq 0 ] && [ "$(cat "$WORK/.pristine" 2>/dev/null)" = "$want" ] && return 0
  ensure_tarballs
  rm -rf "$PRISTINE" "$SYNC" "$WORK/.pristine"
  ci --extract
  # External tarballs (sha256-checked by make fetch) survive re-extraction as hard links.
  mkdir -p "$EXT_CACHE" "$SRC/external/tarballs"
  cp -rln "$EXT_CACHE/." "$SRC/external/tarballs/"
  git init -q --bare "$PRISTINE"
  pgit config core.bare false; pgit config gc.auto 0
  pgit add -A -f .
  pgit -c user.name=local-build -c user.email=local-build@localhost commit -q -m "pristine $want"
  printf '%s\n' "$want" > "$WORK/.pristine"
}

# ---------------------------------------------------------------- patch re-sync
untracked() { # files not in the tarball, without build output
  pgit -C "$SRC" ls-files -o -z --exclude=/workdir/ --exclude=/instdir/ --exclude=/external/tarballs/ \
    --exclude=/autom4te.cache/ | sort -z
}
touched() { # files the series changed or added
  { pgit -C "$SRC" diff --name-only -z; [ ! -f "$SYNC/added" ] || cat "$SYNC/added"; } | sort -zu
}
snapshot() { # "<sha1> <mtime> <path>" for every touched file that exists
  (cd "$SRC" && touched | while IFS= read -r -d '' f; do [ ! -f "$f" ] || printf '%s\0' "$f"; done) > "$SYNC/list"
  [ -s "$SYNC/list" ] || return 0
  # Both commands keep the input order, so the lines pair up.
  paste -d ' ' <(cd "$SRC" && xargs -0 sha1sum -- < "$SYNC/list" | sed 's/^\\//' | cut -c1-40) \
    <(cd "$SRC" && xargs -0 stat -c '%.9Y %n' -- < "$SYNC/list")
}

sync_patches() {
  mkdir -p "$SYNC"
  # A sync that failed half-way left no "added" list: rebuild it from that sync's baseline.
  if [ ! -f "$SYNC/added" ] && [ -f "$SYNC/untracked-before" ]; then
    untracked > "$SYNC/untracked-now"
    comm -z -13 "$SYNC/untracked-before" "$SYNC/untracked-now" > "$SYNC/added"
  fi
  snapshot > "$SYNC/before.txt"
  # Back to pristine: modified/deleted tracked files from the index, files the series added removed.
  pgit -C "$SRC" update-index -q --refresh >/dev/null || true
  pgit -C "$SRC" diff --name-only -z | xargs -0r git --git-dir="$PRISTINE" --work-tree="$SRC" -C "$SRC" checkout -f --
  if [ -f "$SYNC/added" ]; then
    # Remove the added files and the directories they leave empty (scripts glob for theme dirs).
    (cd "$SRC" && xargs -0r rm -f -- < "$SYNC/added" \
      && { xargs -0r dirname -z -- < "$SYNC/added" | sort -zu | xargs -0r rmdir -p --ignore-fail-on-non-empty -- 2>/dev/null || true; })
  fi
  rm -f "$SYNC/added"
  untracked > "$SYNC/untracked-before"
  ci --patch
  untracked > "$SYNC/untracked-after"
  comm -z -13 "$SYNC/untracked-before" "$SYNC/untracked-after" > "$SYNC/added"
  snapshot > "$SYNC/after.txt"
  # Same content as before the reset: restore the old mtime. Everything else counts as changed.
  awk 'function path() { p = $0; sub(/^[^ ]+ [^ ]+ /, "", p); return p }
       NR==FNR { old[path()] = $1 " " $2; next }
       { p = path(); split(old[p], o, " "); if ((p in old) && o[1] == $1) print o[2] " " p; else print "C " p; delete old[p] }
       END { for (p in old) print "C " p }' "$SYNC/before.txt" "$SYNC/after.txt" > "$SYNC/compare.txt"
  (cd "$SRC" && awk '$1 != "C" {print}' "$SYNC/compare.txt" | while read -r t p; do touch -m -d "@$t" -- "$p"; done)
  sed -n 's/^C //p' "$SYNC/compare.txt" | sort > "$SYNC/changed.txt"
  rm -f "$SYNC/untracked-before" "$SYNC/untracked-after" "$SYNC/untracked-now"
  log "patch sync: $(wc -l < "$SYNC/after.txt") files touched by the series ($(tr -cd '\0' < "$SYNC/added" | wc -c) added), $(wc -l < "$SYNC/changed.txt") changed since last run"
}

invalidate_translations() { # catalogues and the translated registry have no .po dependency (docs/SHARED_BUILD_SLOTS.md)
  local lang
  sed -n 's|^translations/source/\([^/]*\)/.*\.po$|\1|p' "$SYNC/changed.txt" | sort -u | while IFS= read -r lang; do
    log "translations changed for $lang: dropping its .mo catalogues and registry_$lang.xcd"
    rm -f "$SRC/workdir/MoTarget/"*"$lang.mo" "$SRC/workdir/XcdTarget/"*"$lang.xcd"
    rm -rf "$SRC/workdir/XcuResTarget/"*"/$lang"
  done
}

invalidate_stale_translations() { # also catches a .po synced by a run that never got to rebuild its catalogues
  local dir lang oldest
  for dir in "$SRC/translations/source"/*/; do
    lang="$(basename "$dir")"
    oldest="$(find "$SRC/workdir/MoTarget" -maxdepth 1 -name "*$lang.mo" -printf '%T@ %p\n' 2>/dev/null | sort -n | head -1 | cut -d' ' -f2-)"
    [ -n "$oldest" ] || continue
    find "$dir" -name '*.po' -newer "$oldest" -print -quit | grep -q . || continue
    log "translations of $lang are newer than its catalogues: dropping its .mo catalogues and registry_$lang.xcd"
    rm -f "$SRC/workdir/MoTarget/"*"$lang.mo" "$SRC/workdir/XcdTarget/"*"$lang.xcd"
    rm -rf "$SRC/workdir/XcuResTarget/"*"/$lang"
  done
}

check_translations() { # the built catalogues must match this ref's .po (scripts/l10n/check-mo-fresh.py)
  python3 -I "$SELF_REPO/scripts/l10n/check-mo-fresh.py" --tree "$SRC" --lang vi \
    || die "stale translation catalogues in instdir (see above); the package would ship old Vietnamese strings"
}

# ---------------------------------------------------------------- configure
needs_configure() {
  [ "$RECONFIGURE" -eq 1 ] && return 0
  [ -f "$SRC/config_host.mk" ] && [ -f "$WORK/autogen.input.last" ] || return 0
  # The inputs LibreOffice's own Makefile.in would rerun autogen.sh for (tarball builds never do).
  grep -qE '^(autogen\.sh|config_host(_lang)?\.mk\.in|Makefile\.in|instsetoo_native/util/openoffice\.lst\.in|configure\.ac|config_host/.*\.h\.in|download\.lst|m4/.*\.m4|distro-configs/.*)$' \
    "$SYNC/changed.txt" && return 0
  cmp -s "$SRC/autogen.input" "$WORK/autogen.input.last" || return 0
  in_chroot / python3 "$C_CHECKOUT/scripts/write-hst-version.py" --header "$C_WORK/sync/hst_version.h" >/dev/null
  cmp -s "$SYNC/hst_version.h" "$SRC/include/hst_version.h" || return 0
  return 1
}

configure_if_needed() {
  ci --options > /dev/null # autogen.input from linux-x86_64.conf exactly like CI (validated)
  if needs_configure; then
    timed configure ci --configure
    cp "$SRC/autogen.input" "$WORK/autogen.input.last"
    timed fetch ci --fetch
    cp -rln "$SRC/external/tarballs/." "$EXT_CACHE/"
  else
    log "configure: inputs unchanged, skipped"
  fi
}

# ---------------------------------------------------------------- build with resource guards
# make runs in a transient systemd scope (MemoryMax = slot budget, MemorySwapMax=0, CPUQuota = jobs x 100 %)
# at nice 19 / idle I/O, so the kernel caps it instead of OOM-killing other services. On top of that:
# - admission (build-slots.py): -j and the budget come from the controller; when the slots' fair share changes
#   (another slot starts or ends) make is restarted with the new -j;
# - memory: the controller's global guard tells the youngest running slot to freeze its scope; it thaws at
#   RESUME_MEM_GIB (a repeated or swap-triggered pause restarts make with half the jobs);
# - heavy links: only one linker using >= 1 GiB runs per slot at a time, the others are stopped until it ends.
mem_avail_gib() { awk '/MemAvailable/ {print int($2 / 1048576)}' /proc/meminfo; }
swap_used_mib() { awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo; }
free_gib() { df -BG --output=avail "$BUILD_ROOT" | tail -1 | tr -dc 0-9; }
scope_cg() { echo "/sys/fs/cgroup/${SLICE:-system.slice}/$SCOPE.scope"; }
budget_mib() { "${SLOTS_PY[@]}" budget --jobs "$1"; }

start_make() { # make like ci-build.sh --build (or the --modules targets), in a capped scope, own session
  local jobs="$1" max high
  SCOPE_N=$(( ${SCOPE_N:-0} + 1 )); SCOPE="hst-local-build-s$SLOT-$RUN_ID-$SCOPE_N"
  max=$(budget_mib "$jobs"); high=$(( max * 9 / 10 ))
  log "make -j$jobs ${MAKE_TARGETS[*]:-(full)} [$MAKE_KIND] in $SCOPE.scope (MemoryMax=${max}M MemoryHigh=${high}M" \
    "MemorySwapMax=0 CPUQuota=$(( jobs * 100 ))%, nice 19, idle I/O; MemAvailable $(mem_avail_gib) GiB," \
    "swap used $(swap_used_mib) MiB, /data free $(free_gib) GiB)"
  # shellcheck disable=SC2016 # expanded by the inner shell
  systemd-run --scope --quiet --unit="$SCOPE" ${SLICE:+--slice="$SLICE"} -p MemoryMax="${max}M" -p MemoryHigh="${high}M" \
    -p MemorySwapMax=0 -p CPUQuota="$(( jobs * 100 ))%" -- \
    setsid nice -n 19 ionice -c3 chroot "$CHROOT" /usr/bin/env -i HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin \
    CCACHE_DIR="$C_CCACHE" HST_REPO_ROOT="$C_CHECKOUT" HST_ICON_DIR="$C_CHECKOUT/assets/brand/icons" \
    /bin/bash -c 'echo 500 > /proc/self/oom_score_adj
      eval "$(python3 "$HST_REPO_ROOT/scripts/write-hst-version.py" --env)"
      export HST_VERSION_MAJOR HST_VERSION_MINOR HST_VERSION_MICRO
      cd "$0" || exit 1; jobs="$1"; kind="$2"; shift 2
      case "$kind" in
        full) exec make GIT_NEEDED_SUBMODULES= PARALLELISM="$jobs" ;;
        test) exec make GIT_NEEDED_SUBMODULES= PARALLELISM="$jobs" "$@" ;;
      esac
      # Module builds: the UNO API headers first, in their own invocation (docs/SHARED_BUILD_SLOTS.md).
      make GIT_NEEDED_SUBMODULES= PARALLELISM="$jobs" udkapi.build offapi.build oovbaapi.build || exit $?
      exec make GIT_NEEDED_SUBMODULES= PARALLELISM="$jobs" "$@"' "$C_SRC" "$jobs" "$MAKE_KIND" "${MAKE_TARGETS[@]}" \
    >> "$BUILD_LOG" 2>&1 &
  BUILD_PGID=$!; PAUSES=0
  "${SLOTS_PY[@]}" update --slot "$SLOT" --jobs "$jobs" --scope "$SCOPE" || true
}

freeze() { [ ! -w "$(scope_cg)/cgroup.freeze" ] || echo "$1" > "$(scope_cg)/cgroup.freeze"; }

stop_make() {
  [ -n "$BUILD_PGID" ] || return 0
  freeze 0; systemctl kill --signal=CONT "$SCOPE.scope" 2>/dev/null || true
  systemctl kill --signal=TERM "$SCOPE.scope" 2>/dev/null || kill -TERM -- "-$BUILD_PGID" 2>/dev/null || true
  local _; for _ in $(seq 30); do kill -0 "$BUILD_PGID" 2>/dev/null || break; sleep 1; done
  systemctl kill --signal=KILL "$SCOPE.scope" 2>/dev/null || kill -KILL -- "-$BUILD_PGID" 2>/dev/null || true
  wait "$BUILD_PGID" 2>/dev/null || true
  BUILD_PGID=""
}

throttle_links() { # keep at most one heavy (>= 1 GiB RSS) linker running in this slot
  local procs pid comm rss state running="" stopped=()
  procs="$(scope_cg)/cgroup.procs"
  [ -r "$procs" ] || return 0
  while read -r pid; do
    comm=$(cat "/proc/$pid/comm" 2>/dev/null) || continue
    case "$comm" in ld|ld.bfd|ld.gold|ld.lld|lld) ;; *) continue ;; esac
    # Processes come and go between reads: a vanished one is simply skipped.
    rss=$(awk '/VmRSS/ {print $2}' "/proc/$pid/status" 2>/dev/null) || continue
    [ "${rss:-0}" -ge 1048576 ] || continue
    state=$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null) || continue
    if [ "$state" = T ]; then stopped+=("$pid")
    elif [ -z "$running" ]; then running=$pid
    else kill -STOP "$pid" 2>/dev/null && log "link throttle: paused linker $pid (another heavy link is running)"; fi
  done < <(sort -n "$procs")
  if [ -z "$running" ] && [ "${#stopped[@]}" -gt 0 ]; then kill -CONT "${stopped[0]}" 2>/dev/null || true; fi
}

pause_for_memory() { # pause_for_memory <reason>; returns 0 to thaw, 1 to restart with fewer jobs
  local reason="$1" waited=0
  PAUSES=$(( PAUSES + 1 ))
  log "resource guard: $reason; freezing make (MemAvailable $(mem_avail_gib) GiB, swap used $(swap_used_mib) MiB)"
  freeze 1
  while [ "$(mem_avail_gib)" -lt "$RESUME_MEM_GIB" ]; do
    [ "$waited" -lt $(( MEM_WAIT_MIN * 60 )) ] || break
    sleep 15; waited=$(( waited + 15 ))
  done
  if [ "$(mem_avail_gib)" -ge "$RESUME_MEM_GIB" ] && [ "$PAUSES" -eq 1 ] && [[ "$reason" != swap* ]]; then
    log "resource guard: MemAvailable $(mem_avail_gib) GiB, thawing make"; freeze 0
    "${SLOTS_PY[@]}" update --slot "$SLOT" --frozen 0 || true
    return 0
  fi
  return 1
}

do_build() {
  local jobs="$JOBS" rc waited oom_retries=0 tick=0 action value
  : > "$BUILD_LOG"
  start_make "$jobs"
  while true; do
    if ! kill -0 "$BUILD_PGID" 2>/dev/null; then
      rc=0; wait "$BUILD_PGID" || rc=$?; BUILD_PGID=""
      [ "$rc" -ne 0 ] || break
      if tail -200 "$BUILD_LOG" | grep -qE 'Killed|Error 137|signal 9' && [ "$oom_retries" -lt 3 ] && [ "$jobs" -gt 2 ]; then
        oom_retries=$(( oom_retries + 1 )); jobs=$(( jobs / 2 )); [ "$jobs" -ge 2 ] || jobs=2
        "${SLOTS_PY[@]}" update --slot "$SLOT" --want "$jobs" || true
        log "make killed (scope memory cap?), retrying with -j$jobs"; sleep 30; start_make "$jobs"; continue
      fi
      tail -60 "$BUILD_LOG"; return "$rc"
    fi
    sleep 5; tick=$(( tick + 1 ))
    throttle_links || true
    printf '%s\t%s\t%s\t%s\t%s\n' "$(date +%s)" "$jobs" "$(mem_avail_gib)" "$(swap_used_mib)" "$(free_gib)" >> "$RUN_LOGS/memory.tsv"
    if [ "$(free_gib)" -lt "$MIN_FREE_GIB" ]; then stop_make; die "disk-stop: less than $MIN_FREE_GIB GiB free on $BUILD_ROOT"; fi
    [ $(( tick % 2 )) -eq 0 ] || continue   # the controller is asked every 10 s
    read -r action value < <("${SLOTS_PY[@]}" poll --slot "$SLOT" --jobs "$jobs" || echo "ok $jobs")
    if [ "$action" = ok ]; then
      # Shrink at once (keeps the total within the server budget); grow only when it is worth a restart.
      if [ "$value" -lt "$jobs" ] || [ "$value" -ge $(( jobs + 6 )) ]; then
        log "admission: share changed, restarting make with -j$value"
        jobs="$value"; stop_make; start_make "$jobs"
      fi
      continue
    fi
    pause_for_memory "$value" && continue
    stop_make
    [ "$jobs" -gt 2 ] || die "resource guard: still short of memory at -j2, aborting"
    jobs=$(( jobs / 2 )); [ "$jobs" -ge 2 ] || jobs=2
    "${SLOTS_PY[@]}" update --slot "$SLOT" --want "$jobs" || true
    waited=0
    while [ "$(mem_avail_gib)" -lt "$RESUME_MEM_GIB" ]; do
      [ "$waited" -lt $(( MEM_WAIT_MIN * 60 )) ] || die "resource guard: MemAvailable stayed below $RESUME_MEM_GIB GiB for $MEM_WAIT_MIN min, aborting"
      sleep 15; waited=$(( waited + 15 ))
    done
    "${SLOTS_PY[@]}" update --slot "$SLOT" --frozen 0 || true
    start_make "$jobs"
  done
  log "make done (final -j$jobs)"
  [ "$MAKE_KIND" = test ] || test -x "$SRC/instdir/program/soffice" || die "build did not produce instdir/program/soffice"
}

run_tests() { # each --test target in turn, same scope guards as the build; results never fail the run
  local t rc start
  mkdir -p "$TEST_OUT/test-logs"; : > "$RUN_LOGS/tests.tsv"
  MAKE_KIND="test"
  for t in "${TEST_TARGETS[@]}"; do
    MAKE_TARGETS=("$t"); BUILD_LOG="$RUN_LOGS/test-$t.log"; start=$(date +%s); rc=0
    log "test $t: start"
    do_build || rc=$?
    cp "$BUILD_LOG" "$TEST_OUT/test-logs/$t.log"
    printf '%s\t%s\t%s\n' "$t" "$rc" "$(( $(date +%s) - start ))" >> "$RUN_LOGS/tests.tsv"
    log "test $t: $([ "$rc" -eq 0 ] && echo PASS || echo "FAIL (make exit $rc)") in $(( $(date +%s) - start ))s"
  done
  python3 -I -c 'import json, sys
rows = [line.rstrip("\n").split("\t") for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
results = {t: {"result": "pass" if rc == "0" else "fail", "exit": int(rc), "seconds": int(sec),
               "log": "test-logs/" + t + ".log"} for t, rc, sec in rows}
json.dump({"ref": sys.argv[3], "sha": sys.argv[4], "results": results}, open(sys.argv[2], "w"), indent=1, sort_keys=True)
' "$RUN_LOGS/tests.tsv" "$TEST_OUT/test-results.json" "$LABEL" "$SHA"
  log "tests: $(grep -c $'\t0\t' "$RUN_LOGS/tests.tsv" || true) of ${#TEST_TARGETS[@]} passed"
}

admit() { # wait for the admission controller; it decides -j
  local granted kind=full
  [ -z "$MODULES" ] || kind=modules
  log "admission: asking for slot $SLOT (up to -j$JOBS)"
  granted="$("${SLOTS_PY[@]}" acquire --slot "$SLOT" --pid "$$" --want "$JOBS" --kind "$kind")"
  ADMITTED=1
  JOBS="${granted%% *}"
  log "admission: slot $SLOT admitted with -j$JOBS, memory budget ${granted#* } GiB"
}

supports_rpm_appimage() { # supports_rpm_appimage <ci-build.sh>: the built ref can repack its .deb as .rpm + .AppImage
  grep -q -- '--rpm-appimage)' "$1"
}

copy_packages() { # copy_packages <installer dir> <dest>: SHA256SUMS and exactly the packages it lists (.deb, .rpm, .AppImage)
  local name
  cp -p "$1/SHA256SUMS" "$2/" || return 1
  while read -r _ name; do
    name="${name#\*}"
    case "$name" in *.deb|*.rpm|*.AppImage) cp -p "$1/$name" "$2/" || return 1 ;; *) echo "unexpected package $name" >&2; return 1 ;; esac
  done < "$1/SHA256SUMS"
  (cd "$2" && sha256sum -c --quiet SHA256SUMS)
}

do_package() {
  ci --package
  # Refs from 1.0.2 on also ship .rpm and .AppImage repacked from the .deb (no rebuild); older refs keep the .deb only.
  if supports_rpm_appimage "$CHECKOUT/scripts/linux/ci-build.sh"; then
    ci --rpm-appimage
  else
    log "package: this ref's ci-build.sh has no --rpm-appimage, .deb only"
  fi
  rm -rf "$DEST"; mkdir -p "$DEST"
  copy_packages "$WORK/installer" "$DEST"
  log "package: $(cd "$DEST" && du -h -- *.deb *.rpm *.AppImage 2>/dev/null | tr '\t\n' ' ')"
}

do_overlay() { # test-only patch overlay: the instdir files the module build rewrote (docs/BUILD_MATRIX.md)
  local name ov n
  name="HSTOffice-overlay-$LABEL-$SHA-${MODULES//,/+}"
  ov="$STAGE/$name"
  rm -rf "$STAGE" "$DEST"; mkdir -p "$ov/files" "$DEST"
  (cd "$SRC/instdir" && find . -path ./sdk -prune -o -type f -newer "$ROOT/.build-start" -printf '%P\n' | sort) > "$ov/FILES"
  n=$(wc -l < "$ov/FILES")
  [ "$n" -gt 0 ] || log "overlay: the module build changed no instdir file"
  (cd "$SRC/instdir" && tar -cf - -T "$ov/FILES") | tar -xf - -C "$ov/files"
  (cd "$ov/files" && xargs -r -d '\n' sha256sum -- < "$ov/FILES") > "$ov/SHA256SUMS"
  cp "$SELF_REPO/scripts/overlay/apply-build-overlay.sh" "$ov/"
  {
    echo "HST Office patch overlay - TEST ONLY. Never ship it or install it on user machines."
    echo "ref: $LABEL @ $SHA; modules: $MODULES; built $(date '+%F %T %z') in local slot $SLOT"
    echo "Apply onto an extracted reference .deb of the same base:"
    echo "  dpkg-deb -x HSTOffice_*.deb ref/ && ./apply-build-overlay.sh ref/"
    echo "$n files: list in FILES, checksums in SHA256SUMS."
  } > "$ov/README.txt"
  tar -C "$STAGE" -czf "$DEST/$name.tar.gz" "$name"
  (cd "$DEST" && sha256sum "$name.tar.gz" > SHA256SUMS)
  rm -rf "$STAGE"
  log "overlay: $DEST/$name.tar.gz ($n files)"
}

# ---------------------------------------------------------------- main
resolve_source
RUN_LOGS="$LOGROOT/$RUN_ID-$LABEL"; mkdir -p "$RUN_LOGS"; BUILD_LOG="$RUN_LOGS/build.log"
DEST="$OUT/$LABEL-$SHA"; [ -z "$MODULES" ] || DEST="$DEST-modules-${MODULES//,/+}"; [ -z "$TESTS" ] || DEST="$DEST-tests"
[ -z "$OUT_OPT" ] || DEST="$OUT_OPT"
exec > >(tee -a "$RUN_LOGS/wrapper.log") 2>&1
log "slot $SLOT: building $LABEL @ $SHA, up to -j$JOBS${MODULES:+, modules $MODULES}${TESTS:+, tests $TESTS}, logs in $RUN_LOGS"
[ -L "$WORK/logs" ] || { rm -rf "$WORK/logs"; ln -s "$C_LOGROOT/ci" "$WORK/logs"; }
total_start=$(date +%s)
timed toolchain ensure_toolchain
mount_chroot
in_chroot / ccache --max-size="$CCACHE_MAX" >/dev/null
timed branding /usr/bin/python3 -I "$CHECKOUT/scripts/stage-branding.py" --out "$ROOT/branding-stage"
rsync -rlpc --delete "$ROOT/branding-stage/" "$WORK/branding/"; rm -rf "$ROOT/branding-stage"
timed extract ensure_pristine
timed patch sync_patches
invalidate_translations
invalidate_stale_translations
configure_if_needed
if [ -n "$MODULES" ] && [ ! -x "$SRC/instdir/program/soffice" ]; then
  die "slot $SLOT has no complete build yet; --modules needs one full build in the slot first"
fi
admit
touch "$ROOT/.build-start"
timed build do_build
TEST_OUT="$RUN_LOGS/test-out"
[ "${#TEST_TARGETS[@]}" -eq 0 ] || timed tests run_tests
# Packaging/overlay are light: free the memory reservation and jobs for other slots now.
"${SLOTS_PY[@]}" release --slot "$SLOT" || true; ADMITTED=0
if [ -n "$MODULES" ]; then timed overlay do_overlay
elif [ "$PACKAGE" -eq 1 ]; then timed translations check_translations; timed package do_package; fi
if [ "${#TEST_TARGETS[@]}" -gt 0 ]; then   # after overlay/package, which recreate $DEST
  mkdir -p "$DEST"; cp -r "$TEST_OUT/." "$DEST/"
  log "tests: results in $DEST/test-results.json"
fi
in_chroot / ccache -s | sed -n '/[Hh]its\|[Mm]isses\|[Cc]ache size/p' || true
log "total $(( $(date +%s) - total_start ))s; timings in $RUN_LOGS/timings.tsv"
log "output: $DEST"
exit "$?"
}
