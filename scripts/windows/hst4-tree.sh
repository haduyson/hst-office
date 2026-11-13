#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Patched-tree update for local Windows builds (scripts/windows/hst4-build.ps1), run inside Cygwin bash.
#   hst4-tree.sh [--clean] [--verify]
# Env: HST_ROOT (Cygwin path of the build root), HST_REPO, HST_DL (as for trial-build.sh).
#
# Produces in $ROOT/lo exactly what a fresh `trial-build.sh --extract` + `--patch` of this checkout gives, but
# only rewrites files whose content differs, so make rebuilds just what changed:
#   pristine/<key>/lo  the extracted tarballs, cached; key = tarball sha256s + trial-build.sh (the extract steps)
#   stage/lo           pristine + the last patch run; .hst-manifest lists the paths that run changed
# A run resets the manifest paths (and created/deleted directories) in stage to pristine, re-applies the
# patches, lists what the patch steps changed (ctime newer than their start, created/deleted files and
# directories) and copies the union of the old and new lists into lo. Without a usable stage (first run, new key, --clean) stage is rebuilt from pristine and
# lo is updated by a full content comparison. --verify checks the result against a fresh extract+patch.
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
ROOT="${HST_ROOT:?HST_ROOT must point at the build root}"
REPO="${HST_REPO:?HST_REPO must point at the repository checkout}"
CLEAN=0; VERIFY=0
for arg in "$@"; do
  case "$arg" in --clean) CLEAN=1 ;; --verify) VERIFY=1 ;; *) echo "usage: $0 [--clean] [--verify]"; exit 64 ;; esac
done
TRIAL=(bash -o igncr "$REPO/scripts/windows/trial-build.sh")
STAGE="$ROOT/stage"; LO="$ROOT/lo"
export LC_ALL=C

key="$( { grep -o '"sha256": *"[0-9a-f]*"' "$REPO/upstream/libreoffice-lock.json"; cat "$REPO/scripts/windows/trial-build.sh"; } | sha256sum | cut -c1-16)"
PRISTINE="$ROOT/pristine/$key"
log() { echo "[tree $(date +%T)] $*"; }

ensure_pristine() {
  if [ ! -f "$PRISTINE/files.txt" ]; then
    log "extracting pristine $key"
    rm -rf "$ROOT/pristine"; mkdir -p "$ROOT/pristine"
    HST_WORK="$PRISTINE.tmp" "${TRIAL[@]}" --extract
    (cd "$PRISTINE.tmp/lo" && find . -type f -printf '%P\n' | sort) > "$PRISTINE.tmp/files.txt"
    mv "$PRISTINE.tmp" "$PRISTINE"
  else log "pristine $key cached"; fi
  [ -f "$PRISTINE/dirs.txt" ] || (cd "$PRISTINE/lo" && find . -mindepth 1 -type d -printf '%P\n' | sort) > "$PRISTINE/dirs.txt"
}

patch_stage() { # re-apply every patch step on stage/lo; record what they changed in manifest.new / dirs.new
  local t0
  sleep 1; t0="$(date +%s.%N)"
  HST_WORK="$STAGE" "${TRIAL[@]}" --patch
  # One walk: ctime (NTFS ChangeTime) catches every write, including copies that keep the old mtime.
  (cd "$STAGE/lo" && find . -mindepth 1 \( -type f -o -type d \) -printf '%y\t%C@\t%P\n') > "$STAGE/walk.tsv"
  awk -F'\t' '$1 == "f" { print $3 }' "$STAGE/walk.tsv" | sort > "$STAGE/files.txt"
  awk -F'\t' '$1 == "d" { print $3 }' "$STAGE/walk.tsv" | sort > "$STAGE/dirs.txt"
  {
    awk -F'\t' -v t0="$t0" '$1 == "f" && $2 >= t0 { print $3 }' "$STAGE/walk.tsv"
    comm -23 "$PRISTINE/files.txt" "$STAGE/files.txt"   # deleted by the patch steps
    comm -13 "$PRISTINE/files.txt" "$STAGE/files.txt"   # created by the patch steps
  } | sort -u > "$STAGE/manifest.new"
  # Directories matter too: a step may skip work when its target directory already exists.
  { comm -13 "$PRISTINE/dirs.txt" "$STAGE/dirs.txt" | sed 's/^/+\t/'
    comm -23 "$PRISTINE/dirs.txt" "$STAGE/dirs.txt" | sed 's/^/-\t/'; } > "$STAGE/dirs.new"
  rm -f "$STAGE/walk.tsv"
  log "patch steps changed $(wc -l < "$STAGE/manifest.new") files, $(wc -l < "$STAGE/dirs.new") directories"
}

rm_paths() { # rm_paths <dir>: delete the relative file paths read from stdin (batched: a fork per file is slow on Cygwin)
  (cd "$1" && xargs -d '\n' -r rm -f --)
}

dirs_of() { # dirs_of <+|-> <dirs file>: created (+) or deleted (-) directories, sorted
  awk -F'\t' -v k="$1" '$1 == k { print $2 }' "$2" | sort
}

reset_stage() { # stage/lo back to pristine for everything the previous run changed
  local prev="$STAGE/.hst-manifest"
  dirs_of - "$STAGE/.hst-dirs" | while IFS= read -r d; do mkdir -p "$STAGE/lo/$d"; done
  comm -12 "$prev" "$PRISTINE/files.txt" > "$STAGE/restore.txt"
  rsync -lI --files-from="$STAGE/restore.txt" "$PRISTINE/lo/" "$STAGE/lo/"
  comm -23 "$prev" "$PRISTINE/files.txt" | rm_paths "$STAGE/lo"
  dirs_of + "$STAGE/.hst-dirs" | while IFS= read -r d; do rm -rf "${STAGE:?}/lo/$d"; done
  log "reset $(wc -l < "$STAGE/restore.txt") files to pristine"
}

sync_lo() { # sync_lo <paths> <old dirs file|/dev/null>: copy paths from stage to lo by content, mirror deletions
  comm -12 "$1" "$STAGE/files.txt" > "$STAGE/copy.txt"
  rsync -lc --stats --files-from="$STAGE/copy.txt" "$STAGE/lo/" "$LO/" | grep -E 'files transferred|Number of files:' || true
  comm -23 "$1" "$STAGE/files.txt" | rm_paths "$LO"
  dirs_of + "$STAGE/dirs.new" | while IFS= read -r d; do mkdir -p "$LO/$d"; done
  dirs_of - "$STAGE/dirs.new" | while IFS= read -r d; do rm -rf "${LO:?}/$d"; done
  # Directories the previous patch run created that this one does not, or deleted that this one keeps.
  comm -23 <(dirs_of + "$2") <(dirs_of + "$STAGE/dirs.new") | while IFS= read -r d; do rm -rf "${LO:?}/$d"; done
  comm -23 <(dirs_of - "$2") <(dirs_of - "$STAGE/dirs.new") | while IFS= read -r d; do mkdir -p "$LO/$d"; done
}

ensure_pristine
if [ "$CLEAN" -eq 0 ] && [ -f "$STAGE/.hst-manifest" ] && [ -f "$STAGE/.hst-dirs" ] \
   && [ "$(cat "$STAGE/.hst-key" 2>/dev/null)" = "$key" ] && [ -f "$LO/configure.ac" ]; then
  log "incremental update"
  rm -f "$STAGE/.hst-key"   # stage is only trusted again once this run completes
  reset_stage
  patch_stage
  sort -u "$STAGE/.hst-manifest" "$STAGE/manifest.new" > "$STAGE/sync.txt"
  sync_lo "$STAGE/sync.txt" "$STAGE/.hst-dirs"
else
  log "full update (clean=$CLEAN)"
  rm -rf "$STAGE"; mkdir -p "$STAGE"
  cp -a "$PRISTINE/lo" "$STAGE/lo"
  patch_stage
  [ "$CLEAN" -eq 0 ] || rm -rf "$LO"
  if [ -f "$LO/configure.ac" ]; then
    # No --times: rewritten files get a new mtime so make sees them; unchanged files keep theirs.
    rsync -rlc --stats "$STAGE/lo/" "$LO/" | grep -E 'files transferred|Number of files:' || true
    sync_lo "$STAGE/manifest.new" /dev/null   # mirrors the patch steps' deletions
  else rm -rf "$LO"; cp -a "$STAGE/lo" "$LO"; fi
fi
mv "$STAGE/manifest.new" "$STAGE/.hst-manifest"
mv "$STAGE/dirs.new" "$STAGE/.hst-dirs"
echo "$key" > "$STAGE/.hst-key"
rm -f "$STAGE/restore.txt" "$STAGE/copy.txt" "$STAGE/sync.txt"

if [ "$VERIFY" -eq 1 ]; then
  log "verify: fresh extract + patch"
  mkdir -p "$ROOT/logs"
  rm -rf "$ROOT/verify"
  HST_WORK="$ROOT/verify" "${TRIAL[@]}" --extract
  HST_WORK="$ROOT/verify" "${TRIAL[@]}" --patch
  diff -rq --no-dereference "$ROOT/verify/lo" "$STAGE/lo" > "$ROOT/logs/verify-stage.txt" \
    || { log "verify FAILED: stage differs from a fresh tree (logs/verify-stage.txt)"; exit 1; }
  # lo also holds configure/build output; every source file must match, except what --configure rewrites
  # (autogen.sh regenerates configure and aclocal.m4; the HST version is written into openoffice.lst).
  rsync -rlcn --out-format='%n' "$ROOT/verify/lo/" "$LO/" | grep -v '/$' \
    | grep -vxF -e 'instsetoo_native/util/openoffice.lst' -e configure -e aclocal.m4 > "$ROOT/logs/verify-lo.txt" || true
  if [ -s "$ROOT/logs/verify-lo.txt" ]; then log "verify FAILED: lo differs from a fresh tree (logs/verify-lo.txt)"; exit 1; fi
  rm -rf "$ROOT/verify"
  log "verify ok: stage and lo equal a fresh extract+patch"
fi
