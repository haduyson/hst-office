#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Deploy a commit of the build infrastructure for the local build queue (scripts/build-queue.sh).
#   sudo scripts/linux/build-infra-deploy.sh <commit|branch>   checkout + atomic switch + dispatcher restart + prune
#   sudo scripts/linux/build-infra-deploy.sh --prune           only remove versions no process uses any more
# Every version is its own detached worktree $ROOT/infra-<sha12>; $ROOT/infra-current is a symlink swapped with an
# atomic rename. The dispatcher and local-build.sh resolve their real directory when they start, so a running job
# keeps the version it started with; new jobs use the new one after the dispatcher restart. A version is removed
# only when no process has it in its command line or working directory.
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
ROOT="${HST_BUILD_ROOT:-/data/hst-build}"
REPO="${HST_INFRA_REPO:-/home/office}"
CURRENT="$ROOT/infra-current"
die() { echo "build-infra-deploy: $*" >&2; exit 1; }
log() { echo "[$(date '+%F %T')] $*"; }
[ "$(id -u)" -eq 0 ] || die "needs root"

in_use() { # in_use <dir>: a process runs from <dir> (command line or working directory)
  local p
  for p in /proc/[0-9]*; do   # processes come and go during the scan: a vanished one is skipped
    { tr '\0' ' ' < "$p/cmdline" | grep -qF "$1/"; } 2>/dev/null && return 0
    case "$(readlink "$p/cwd" 2>/dev/null || true)" in "$1"|"$1"/*) return 0 ;; esac
  done
  return 1
}

prune() {
  local cur d
  cur="$(readlink -f "$CURRENT" 2>/dev/null || true)"
  for d in "$ROOT"/infra-[0-9a-f]* "$ROOT/infra"; do
    if [ ! -d "$d" ] || [ -L "$d" ]; then continue; fi
    [ "$d" != "$cur" ] || continue
    if in_use "$d"; then log "keeping $d (still in use)"; continue; fi
    git -C "$REPO" worktree remove --force "$d"
    log "removed $d"
  done
}

[ $# -eq 1 ] || die "usage: build-infra-deploy.sh <commit|branch> | --prune"
if [ "$1" = --prune ]; then prune; exit 0; fi
git -C "$REPO" fetch -q origin || log "warning: git fetch failed, using local refs"
sha="$(git -C "$REPO" rev-parse -q --verify "origin/$1^{commit}" || git -C "$REPO" rev-parse -q --verify "$1^{commit}")" \
  || die "unknown commit $1"
dir="$ROOT/infra-${sha:0:12}"
[ -d "$dir" ] || git -C "$REPO" worktree add -q --detach "$dir" "$sha"
bash -n "$dir/scripts/linux/local-build.sh"
python3 -I -m py_compile "$dir/scripts/build-queue.py" "$dir/scripts/build-queue-dispatcher.py" "$dir/scripts/linux/build-slots.py"
ln -sfn "${dir##*/}" "$CURRENT.new"
mv -T "$CURRENT.new" "$CURRENT"   # rename(2): atomic
log "infra-current -> ${dir##*/}"
if systemctl is-enabled -q hst-build-queue 2>/dev/null; then
  systemctl restart hst-build-queue   # KillMode=process: running builds are not touched
  log "dispatcher restarted"
fi
prune
