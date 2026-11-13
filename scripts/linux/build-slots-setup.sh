#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# One-time setup of the parallel local Linux build slots used by scripts/linux/local-build.sh --slot N.
#   sudo scripts/linux/build-slots-setup.sh migrate     the single-tree layout /data/hst-office-build becomes
#                                                       slot 1 (moves only, no copy, build state kept)
#   sudo scripts/linux/build-slots-setup.sh clone N     slot N as a copy of slot 1's warm tree (slot 1 must be idle)
#   sudo scripts/linux/build-slots-setup.sh plan        how many slots fit on the disk (no change)
# A slot clone copies slot 1's lo/ tree (the tree is valid in any slot because every slot chroot mounts it at the
# same canonical path); the pinned tarballs, external tarballs and pristine.git are hard links (never rewritten in
# place: git and the download steps write new files and rename them). A clone is refused unless /data keeps
# HST_MIN_FREE_GIB (15) GiB plus the ccache growth up to its max plus HST_OUT_RESERVE_GIB (5) for outputs free.
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
BUILD_ROOT="${HST_BUILD_ROOT:-/data/hst-build}"
OLD=/data/hst-office-build
MIN_FREE_GIB="${HST_MIN_FREE_GIB:-15}"; OUT_RESERVE_GIB="${HST_OUT_RESERVE_GIB:-5}"
CCACHE_MAX_GIB="${HST_CCACHE_MAX_GIB:-30}"
die() { echo "build-slots-setup: $*" >&2; exit 1; }
log() { echo "[$(date '+%F %T')] $*"; }
[ "$(id -u)" -eq 0 ] || die "needs root"

gib_of() { du -sB1G "$@" 2>/dev/null | awk '{s += $1} END {print s + 0}'; }
free_gib() { df -BG --output=avail "$BUILD_ROOT" | tail -1 | tr -dc 0-9; }
slot_need_gib() { # space a clone of slot 1 takes: lo/ without the hard-linked external tarballs, plus checkout
  local s1="$BUILD_ROOT/slots/1"
  du -sB1G --exclude="$s1/src/lo/external/tarballs" "$s1/src/lo" | awk '{print $1 + 1}'
}
reserve_gib() { # free space that must remain after a clone
  local cc; cc=$(gib_of "$BUILD_ROOT/ccache")
  echo $(( MIN_FREE_GIB + OUT_RESERVE_GIB + (CCACHE_MAX_GIB > cc ? CCACHE_MAX_GIB - cc : 0) ))
}

migrate() {
  if [ ! -d "$OLD/chroot" ]; then die "$OLD/chroot missing (already migrated?)"; fi
  [ ! -e "$BUILD_ROOT/slots/1" ] || die "$BUILD_ROOT/slots/1 already exists"
  exec 9>>"$OLD/.lock"
  flock -n 9 || die "a local build still holds $OLD/.lock; wait for it to finish"
  if awk -v p="$OLD/chroot/" 'index($5, p) == 1 {f = 1} END {exit !f}' /proc/self/mountinfo; then
    die "$OLD/chroot still has mounts; run the old local-build.sh --umount first"
  fi
  mkdir -p "$BUILD_ROOT/slots" "$BUILD_ROOT/locks"
  for d in chroot ccache external-tarballs out; do
    [ ! -e "$BUILD_ROOT/$d" ] || die "$BUILD_ROOT/$d already exists"
    [ -d "$OLD/$d" ] || die "missing $OLD/$d"
  done
  for d in chroot ccache external-tarballs out; do mv "$OLD/$d" "$BUILD_ROOT/$d"; done
  rm -rf "$OLD/stage"
  # Compatibility directory, swapped in right after the move: other tools read headers from $OLD/src/lo on the
  # host, so src points at slot 1; ccache is a plain file so an older local-build.sh (default root $OLD) fails at
  # its `mkdir -p` instead of starting a second tree.
  local compat="$OLD.compat"
  rm -rf "$compat"; mkdir -p "$compat"
  ln -s "$BUILD_ROOT/slots/1/src" "$compat/src"
  printf 'moved to %s (slot 1 = %s/slots/1); see docs/BUILD_MATRIX.md\n' "$BUILD_ROOT" "$BUILD_ROOT" | tee "$compat/ccache" > "$compat/README"
  mv "$OLD" "$BUILD_ROOT/slots/1" && mv "$compat" "$OLD"
  sed -i "s/^max_size = .*/max_size = ${CCACHE_MAX_GIB}G/" "$BUILD_ROOT/ccache/ccache.conf" 2>/dev/null \
    || echo "max_size = ${CCACHE_MAX_GIB}G" > "$BUILD_ROOT/ccache/ccache.conf"
  log "migrated: $BUILD_ROOT/slots/1 (tree), chroot/ ccache/ external-tarballs/ out/ shared; ccache max ${CCACHE_MAX_GIB}G"
}

clone() {
  local n="$1" s1="$BUILD_ROOT/slots/1" dst tmp need free reserve f
  [[ "$n" =~ ^[2-9]$ ]] || die "clone needs a slot number 2-9"
  dst="$BUILD_ROOT/slots/$n"; tmp="$dst.tmp"
  [ -d "$s1/src/lo" ] || die "slot 1 missing (run migrate first)"
  [ ! -e "$dst" ] || die "slot $n already exists"
  need=$(slot_need_gib); free=$(free_gib); reserve=$(reserve_gib)
  log "slot $n needs ~${need} GiB; /data free ${free} GiB; must keep ${reserve} GiB free"
  [ $(( free - need )) -ge "$reserve" ] || die "not enough disk for slot $n ($free - $need < $reserve GiB)"
  exec 9>>"$s1/.lock"
  flock -n 9 || die "slot 1 is building; clone when it is idle"
  rm -rf "$tmp"; mkdir -p "$tmp/src" "$tmp/logs/ci"
  cp -a "$s1/checkout" "$tmp/checkout"
  cp -al "$s1/src/dl" "$s1/src/pristine.git" "$tmp/src/"
  for f in "$s1/src/"* "$s1/src/".[!.]*; do
    case "${f##*/}" in lo|dl|pristine.git|installer|'.[!.]*') ;; *) cp -a "$f" "$tmp/src/" ;; esac
  done
  mkdir -p "$tmp/src/lo/external"
  cp -al "$s1/src/lo/external/tarballs" "$tmp/src/lo/external/tarballs"
  rsync -aH --exclude=/external/tarballs/ "$s1/src/lo/" "$tmp/src/lo/"
  mv "$tmp" "$dst"
  log "slot $n ready: $dst ($(gib_of "$dst") GiB apparent incl. hard links); /data free $(free_gib) GiB"
}

plan() {
  local need free reserve
  need=$(slot_need_gib); free=$(free_gib); reserve=$(reserve_gib)
  echo "per extra slot ~${need} GiB; /data free ${free} GiB; reserve ${reserve} GiB" \
    "(min free ${MIN_FREE_GIB} + outputs ${OUT_RESERVE_GIB} + ccache growth to ${CCACHE_MAX_GIB}G)"
  echo "extra slots that fit now: $(( (free - reserve) / need ))"
}

case "${1:-}" in
  migrate) migrate ;;
  clone) clone "${2:-}" ;;
  plan) plan ;;
  *) sed -n '3,6p' "$0" | sed 's/^# \{0,1\}//'; exit 64 ;;
esac
