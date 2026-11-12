#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Local incremental build of the HST Office Linux .deb, with the same steps as CI
# (.github/workflows/desktop-linux.yml + scripts/linux/ci-build.sh of the branch being built).
#
#   sudo scripts/linux/local-build.sh [options] <ref | worktree-path>
#     <ref>            branch, tag or sha of this repository (fetched from origin first;
#                      origin/<ref> wins over a local branch of the same name)
#     <worktree-path>  a checkout; its tracked + untracked (not ignored) files, uncommitted
#                      changes included, are built (output label gets "-dirty")
#   -j, --jobs N       make parallelism (default 12); lowered automatically on low memory
#   --reconfigure      run the configure phase even when nothing it depends on changed
#   --fresh            re-extract the pristine tarballs (full rebuild)
#   --no-package       stop after make (skip the single-.deb packaging)
#   --umount           only unmount the build chroot (after a crashed run) and exit
#
# Layout under HST_LOCAL_ROOT (default /data/hst-office-build):
#   chroot/    Ubuntu 22.04 root file system exported from the CI container image (same digest),
#              build dependencies installed by `ci-build.sh --deps` (clang from apt.llvm.org) + ccache
#   checkout/  plain copy of the repository being built (only changed files are rewritten)
#   src/       HST_WORK of ci-build.sh: lo/ (LibreOffice tree), dl/ (pinned tarballs), branding/,
#              pristine.git (index of the untouched tarball tree), installer/, metrics/
#   ccache/    CCACHE_DIR (max 20 GB)
#   external-tarballs/  hard links of src/lo/external/tarballs, kept across --fresh
#   logs/      <time>-<label>/ per run (wrapper.log, build.log, timings.tsv); ci/ phase logs
#   out/       <label>-<sha>/HSTOffice_<release>_Linux_x86-64.deb + SHA256SUMS
#
# Patch re-sync: every run resets the files the previous series touched to the pristine
# tarball state, applies the series exactly like CI (`ci-build.sh --patch`), and gives files
# whose content did not change their previous mtime back, so make rebuilds only what changed.
# Differences from CI, none of which changes what is compiled: a chroot instead of a docker
# container (keeps the 5+ GB toolchain off the root disk), ccache, -j N (default 12, max 16) instead
# of nproc, and resource caps for a shared server: make runs in a systemd scope (MemoryMax
# HST_LOCAL_MEMORY_MAX=24G, MemorySwapMax=0, CPUQuota HST_LOCAL_CPU_QUOTA=1600%) at nice 19 and
# idle I/O priority; MemAvailable below HST_LOCAL_MIN_MEM_GIB (6) or swap use grown by more than
# HST_LOCAL_SWAP_GROW_GIB (1) freezes it until HST_LOCAL_RESUME_MEM_GIB (8) GiB are available
# (repeated or swap pauses restart make with half the jobs, min 2; abort after
# HST_LOCAL_MEM_WAIT_MIN, default 30, minutes); only one heavy (>= 1 GiB) link runs at a time.
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR

SELF_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="${HST_LOCAL_ROOT:-/data/hst-office-build}"
CHROOT="$ROOT/chroot"; CHECKOUT="$ROOT/checkout"; STAGE="$ROOT/stage"
WORK="$ROOT/src"; SRC="$WORK/lo"; DL="$WORK/dl"; PRISTINE="$WORK/pristine.git"; SYNC="$WORK/sync"
EXT_CACHE="$ROOT/external-tarballs"; CCACHE="$ROOT/ccache"; OUT="$ROOT/out"; LOGROOT="$ROOT/logs"
TARBALL_CACHE="${HST_LOCAL_TARBALL_CACHE:-/home/office/upstream/cache/libreoffice}"
MIN_MEM_GIB="${HST_LOCAL_MIN_MEM_GIB:-6}"; RESUME_MEM_GIB="${HST_LOCAL_RESUME_MEM_GIB:-8}"
SWAP_GROW_GIB="${HST_LOCAL_SWAP_GROW_GIB:-1}"; MAX_JOBS=16
MEM_MAX="${HST_LOCAL_MEMORY_MAX:-24G}"; CPU_QUOTA="${HST_LOCAL_CPU_QUOTA:-1600%}"
MEM_WAIT_MIN="${HST_LOCAL_MEM_WAIT_MIN:-30}"; MIN_FREE_GIB="${HST_LOCAL_MIN_FREE_GIB:-5}"
JOBS=12; RECONFIGURE=0; FRESH=0; PACKAGE=1; TARGET=""; BUILD_PGID=""; MOUNTED=0

usage() { sed -n '4,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 64; }
die() { echo "local-build: $*" >&2; exit 1; }
log() { echo "[$(date '+%F %T')] $*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    -j|--jobs) JOBS="${2:-}"; shift 2 ;;
    -j[0-9]*) JOBS="${1#-j}"; shift ;;
    --reconfigure) RECONFIGURE=1; shift ;;
    --fresh) FRESH=1; shift ;;
    --no-package) PACKAGE=0; shift ;;
    --umount) TARGET=--umount; shift ;;
    -h|--help) usage ;;
    -*) die "unknown option $1" ;;
    *) [ -z "$TARGET" ] || die "only one ref or worktree"; TARGET="$1"; shift ;;
  esac
done
[ -n "$TARGET" ] || usage
if ! [[ "$JOBS" =~ ^[1-9][0-9]*$ ]]; then die "--jobs needs a positive number"; fi
if [ "$JOBS" -gt "$MAX_JOBS" ]; then echo "local-build: -j capped at $MAX_JOBS" >&2; JOBS=$MAX_JOBS; fi
[ "$(id -u)" -eq 0 ] || die "needs root (chroot and bind mounts)"
for tool in git rsync docker chroot mount flock python3 sha256sum systemd-run systemctl ionice; do
  command -v "$tool" >/dev/null || die "missing host tool: $tool"
done

mkdir -p "$ROOT" "$WORK" "$CCACHE" "$OUT" "$LOGROOT/ci" "$CHECKOUT"
exec 9>"$ROOT/.lock"
flock -n 9 || die "another local build holds $ROOT/.lock"

# ---------------------------------------------------------------- chroot and mounts
chroot_mounts() { awk -v p="$CHROOT/" 'index($5, p) == 1 {print $5}' /proc/self/mountinfo; }

umount_chroot() {
  local m
  # Deepest first; /sys is an rslave rbind, so nothing propagates back to the host.
  chroot_mounts | sort -r | while IFS= read -r m; do umount -R "$m" 2>/dev/null || umount -R -l "$m" || true; done
  MOUNTED=0
  [ -z "$(chroot_mounts)" ] || die "could not unmount: $(chroot_mounts | tr '\n' ' ')"
}

bind_at_same_path() { # bind_at_same_path <host dir>: visible at the same path in the chroot
  mkdir -p "$CHROOT$1"
  mountpoint -q "$CHROOT$1" || { mount --bind "$1" "$CHROOT$1"; mount --make-private "$CHROOT$1"; }
}

mount_chroot() {
  mountpoint -q "$CHROOT/proc" || mount -t proc proc "$CHROOT/proc"
  mountpoint -q "$CHROOT/sys" || { mount --rbind /sys "$CHROOT/sys"; mount --make-rslave "$CHROOT/sys"; }
  # Own minimal /dev (not a bind of the host's): device permissions stay standard whatever the host has.
  if ! mountpoint -q "$CHROOT/dev"; then
    local d=$CHROOT/dev
    mount -t tmpfs -o mode=755,size=16m,nosuid tmpfs "$d"; mount --make-private "$d"
    mknod -m 666 "$d/null" c 1 3; mknod -m 666 "$d/zero" c 1 5; mknod -m 666 "$d/full" c 1 7
    mknod -m 666 "$d/random" c 1 8; mknod -m 666 "$d/urandom" c 1 9; mknod -m 666 "$d/tty" c 5 0
    ln -s /proc/self/fd "$d/fd"; ln -s fd/0 "$d/stdin"; ln -s fd/1 "$d/stdout"; ln -s fd/2 "$d/stderr"
    mkdir -m 755 "$d/pts"; mkdir -m 1777 "$d/shm"
    mount -t devpts -o newinstance,ptmxmode=0666,mode=620 devpts "$d/pts"; ln -s pts/ptmx "$d/ptmx"
    mount -t tmpfs -o mode=1777,size=2g,nosuid,nodev tmpfs "$d/shm"
  fi
  bind_at_same_path "$WORK"; bind_at_same_path "$CCACHE"; bind_at_same_path "$CHECKOUT"
  bind_at_same_path "$LOGROOT"
  cp -L /etc/resolv.conf "$CHROOT/etc/resolv.conf"
  MOUNTED=1
}

cleanup() {
  local rc=$?
  if [ -n "$BUILD_PGID" ]; then log "stopping make ($SCOPE.scope)"; stop_make; fi
  [ "$MOUNTED" -eq 0 ] || umount_chroot || true
  rm -rf "$STAGE"
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

if [ "$TARGET" = --umount ]; then umount_chroot; log "chroot unmounted"; exit 0; fi

# in_chroot <dir> <cmd...>: run in the build chroot with the same environment docker exec gives CI
in_chroot() {
  local dir="$1"; shift
  # shellcheck disable=SC2016 # expanded by the inner shell
  nice -n 19 ionice -c3 chroot "$CHROOT" /usr/bin/env -i HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin \
    HST_IN_CONTAINER=1 HST_SUDO= HST_WORK="$WORK" HST_DL="$DL" HST_CLANG="$CLANG" CCACHE_DIR="$CCACHE" \
    /bin/bash -c 'cd "$0" && exec "$@"' "$dir" "$@"
}
ci() { in_chroot "$CHECKOUT" bash "$CHECKOUT/scripts/linux/ci-build.sh" "$@"; }

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
  LABEL="${LABEL//\//_}"
  # Content compare (-c, no -t): unchanged files keep their mtime, so HST make rules stay up to date.
  rsync -rlpc --delete "$STAGE/" "$CHECKOUT/"
  rm -rf "$STAGE"
  local wf="$CHECKOUT/.github/workflows/desktop-linux.yml"
  IMAGE="$(sed -n 's/^ *HST_CONTAINER: *//p' "$wf" | head -1)"
  CLANG="$(sed -n "s/^ *HST_CLANG: *'\{0,1\}\([0-9]*\)'\{0,1\}.*/\1/p" "$wf" | head -1)"
  [ -n "$IMAGE" ] || die "HST_CONTAINER not found in $wf"
}

# ---------------------------------------------------------------- toolchain
ensure_chroot() { # root file system of the CI container image (same digest), kept on $ROOT
  [ "$(cat "$CHROOT/.hst-image" 2>/dev/null)" = "$IMAGE" ] && return 0
  [ -z "$(chroot_mounts)" ] || die "chroot still mounted; run with --umount first"
  log "creating chroot from $IMAGE"
  local had_image=0 cid
  docker image inspect "$IMAGE" >/dev/null 2>&1 && had_image=1
  [ "$had_image" -eq 1 ] || docker pull -q "$IMAGE" >/dev/null
  rm -rf "$CHROOT"; mkdir -p "$CHROOT"
  cid="$(docker create "$IMAGE" true)"
  docker export "$cid" | tar -xf - -C "$CHROOT"
  docker rm "$cid" >/dev/null
  [ "$had_image" -eq 1 ] || docker rmi "$IMAGE" >/dev/null || true # keep the root disk clean
  printf '%s\n' "$IMAGE" > "$CHROOT/.hst-image"
}

ensure_deps() { # ci-build.sh --deps (re-run when its deps step or the clang version changes) + ccache
  local want
  want="clang=$CLANG $(sed -n '/^do_deps()/,/^}/p' "$CHECKOUT/scripts/linux/ci-build.sh" | sha256sum | cut -c1-16)"
  [ "$(cat "$CHROOT/.hst-deps" 2>/dev/null)" = "$want" ] && return 0
  ci --deps
  in_chroot / env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends ccache
  in_chroot / ccache --max-size=20G >/dev/null
  printf '%s\n' "$want" > "$CHROOT/.hst-deps"
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

# ---------------------------------------------------------------- configure
needs_configure() {
  [ "$RECONFIGURE" -eq 1 ] && return 0
  [ -f "$SRC/config_host.mk" ] && [ -f "$WORK/autogen.input.last" ] || return 0
  # The inputs LibreOffice's own Makefile.in would rerun autogen.sh for (tarball builds never do).
  grep -qE '^(autogen\.sh|config_host(_lang)?\.mk\.in|Makefile\.in|instsetoo_native/util/openoffice\.lst\.in|configure\.ac|config_host/.*\.h\.in|download\.lst|m4/.*\.m4|distro-configs/.*)$' \
    "$SYNC/changed.txt" && return 0
  cmp -s "$SRC/autogen.input" "$WORK/autogen.input.last" || return 0
  in_chroot / python3 "$CHECKOUT/scripts/write-hst-version.py" --header "$SYNC/hst_version.h" >/dev/null
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
# make runs in a transient systemd scope (MemoryMax, MemorySwapMax=0, CPUQuota) at nice 19 / idle
# I/O, so the kernel caps it instead of OOM-killing other services. On top of that:
# - memory: MemAvailable < MIN_MEM_GIB or swap use grown by > SWAP_GROW_GIB freezes the scope;
#   it thaws at RESUME_MEM_GIB (a repeated or swap-triggered pause restarts make with half the jobs);
# - heavy links: only one linker using >= 1 GiB runs at a time, the others are stopped until it ends.
mem_avail_gib() { awk '/MemAvailable/ {print int($2 / 1048576)}' /proc/meminfo; }
swap_used_mib() { awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo; }
free_gib() { df -BG --output=avail "$ROOT" | tail -1 | tr -dc 0-9; }
scope_cg() { echo "/sys/fs/cgroup/system.slice/$SCOPE.scope"; }

start_make() { # make like ci-build.sh --build, inside a capped scope, in its own session (pgid = pid)
  local jobs="$1"; SCOPE_N=$(( ${SCOPE_N:-0} + 1 )); SCOPE="hst-local-build-$RUN_ID-$SCOPE_N"
  log "make -j$jobs in $SCOPE.scope (MemoryMax=$MEM_MAX MemorySwapMax=0 CPUQuota=$CPU_QUOTA, nice 19, idle I/O;" \
    "MemAvailable $(mem_avail_gib) GiB, swap used $(swap_used_mib) MiB, /data free $(free_gib) GiB)"
  # shellcheck disable=SC2016 # expanded by the inner shell
  systemd-run --scope --quiet --unit="$SCOPE" -p MemoryMax="$MEM_MAX" -p MemorySwapMax=0 -p CPUQuota="$CPU_QUOTA" -- \
    setsid nice -n 19 ionice -c3 chroot "$CHROOT" /usr/bin/env -i HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin \
    CCACHE_DIR="$CCACHE" HST_REPO_ROOT="$CHECKOUT" HST_ICON_DIR="$CHECKOUT/assets/brand/icons" \
    /bin/bash -c 'echo 500 > /proc/self/oom_score_adj
      eval "$(python3 "$HST_REPO_ROOT/scripts/write-hst-version.py" --env)"
      export HST_VERSION_MAJOR HST_VERSION_MINOR HST_VERSION_MICRO
      cd "$0" && exec make GIT_NEEDED_SUBMODULES= PARALLELISM="$1"' "$SRC" "$jobs" >> "$RUN_LOGS/build.log" 2>&1 &
  BUILD_PGID=$!; SWAP_BASE=$(swap_used_mib); PAUSES=0
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

throttle_links() { # keep at most one heavy (>= 1 GiB RSS) linker running
  local procs pid comm rss state running="" stopped=()
  procs="$(scope_cg)/cgroup.procs"
  [ -r "$procs" ] || return 0
  while read -r pid; do
    comm=$(cat "/proc/$pid/comm" 2>/dev/null) || continue
    case "$comm" in ld|ld.bfd|ld.gold|ld.lld|lld) ;; *) continue ;; esac
    rss=$(awk '/VmRSS/ {print $2}' "/proc/$pid/status" 2>/dev/null); [ "${rss:-0}" -ge 1048576 ] || continue
    state=$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null)
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
    log "resource guard: MemAvailable $(mem_avail_gib) GiB, thawing make"; freeze 0; SWAP_BASE=$(swap_used_mib); return 0
  fi
  return 1
}

do_build() {
  local jobs="$JOBS" rc waited oom_retries=0
  : > "$RUN_LOGS/build.log"
  start_make "$jobs"
  while true; do
    if ! kill -0 "$BUILD_PGID" 2>/dev/null; then
      rc=0; wait "$BUILD_PGID" || rc=$?; BUILD_PGID=""
      [ "$rc" -ne 0 ] || break
      if tail -200 "$RUN_LOGS/build.log" | grep -qE 'Killed|Error 137|signal 9' && [ "$oom_retries" -lt 3 ] && [ "$jobs" -gt 2 ]; then
        oom_retries=$(( oom_retries + 1 )); jobs=$(( jobs / 2 )); [ "$jobs" -ge 2 ] || jobs=2
        log "make killed (scope memory cap?), retrying with -j$jobs"; sleep 30; start_make "$jobs"; continue
      fi
      tail -60 "$RUN_LOGS/build.log"; return "$rc"
    fi
    sleep 5
    throttle_links
    printf '%s\t%s\t%s\t%s\t%s\n' "$(date +%s)" "$jobs" "$(mem_avail_gib)" "$(swap_used_mib)" "$(free_gib)" >> "$RUN_LOGS/memory.tsv"
    if [ "$(free_gib)" -lt "$MIN_FREE_GIB" ]; then stop_make; die "disk-stop: less than $MIN_FREE_GIB GiB free on $ROOT"; fi
    local reason=""
    if [ "$(mem_avail_gib)" -lt "$MIN_MEM_GIB" ]; then reason="MemAvailable below $MIN_MEM_GIB GiB"
    elif [ $(( $(swap_used_mib) - SWAP_BASE )) -gt $(( SWAP_GROW_GIB * 1024 )) ]; then reason="swap use grew by more than $SWAP_GROW_GIB GiB"
    fi
    [ -n "$reason" ] || continue
    pause_for_memory "$reason" && continue
    stop_make
    [ "$jobs" -gt 2 ] || die "resource guard: still short of memory at -j2, aborting"
    jobs=$(( jobs / 2 )); [ "$jobs" -ge 2 ] || jobs=2
    waited=0
    while [ "$(mem_avail_gib)" -lt "$RESUME_MEM_GIB" ]; do
      [ "$waited" -lt $(( MEM_WAIT_MIN * 60 )) ] || die "resource guard: MemAvailable stayed below $RESUME_MEM_GIB GiB for $MEM_WAIT_MIN min, aborting"
      sleep 15; waited=$(( waited + 15 ))
    done
    start_make "$jobs"
  done
  log "make done (final -j$jobs)"
  test -x "$SRC/instdir/program/soffice" || die "build did not produce instdir/program/soffice"
}

do_package() {
  ci --package
  local dest="$OUT/$LABEL-$SHA"
  rm -rf "$dest"; mkdir -p "$dest"
  cp -p "$WORK/installer/"*.deb "$WORK/installer/SHA256SUMS" "$dest/"
  (cd "$dest" && sha256sum -c --quiet SHA256SUMS)
  log "package: $(ls "$dest"/*.deb) ($(du -h "$dest"/*.deb | cut -f1))"
}

# ---------------------------------------------------------------- main
resolve_source
RUN_LOGS="$LOGROOT/$RUN_ID-$LABEL"; mkdir -p "$RUN_LOGS"
exec > >(tee -a "$RUN_LOGS/wrapper.log") 2>&1
log "building $LABEL @ $SHA, -j$JOBS, logs in $RUN_LOGS"
[ -L "$WORK/logs" ] || { rm -rf "$WORK/logs"; ln -s "$LOGROOT/ci" "$WORK/logs"; }
total_start=$(date +%s)
timed chroot ensure_chroot
mount_chroot
timed deps ensure_deps
timed branding /usr/bin/python3 -I "$CHECKOUT/scripts/stage-branding.py" --out "$ROOT/branding-stage"
rsync -rlpc --delete "$ROOT/branding-stage/" "$WORK/branding/"; rm -rf "$ROOT/branding-stage"
timed extract ensure_pristine
timed patch sync_patches
invalidate_translations
configure_if_needed
timed build do_build
[ "$PACKAGE" -eq 0 ] || timed package do_package
in_chroot / ccache -s | sed -n '/[Hh]its\|[Mm]isses\|[Cc]ache size/p' || true
log "total $(( $(date +%s) - total_start ))s; timings in $RUN_LOGS/timings.tsv"
