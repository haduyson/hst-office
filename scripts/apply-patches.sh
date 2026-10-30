#!/usr/bin/env bash
# Apply patches/libreoffice/series to the LibreOffice tree (idempotent).
#   scripts/apply-patches.sh [--check]
# The applied state is found on a scratch copy of the touched files by reverse-applying the
# series from the last patch backwards, so patches that edit the same lines are handled. The
# applied patches must form a prefix of the series; the rest are dry-run in order on the scratch
# copy before anything in the tree is modified (--check stops there).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${HST_LO_SRC:-$ROOT/upstream/libreoffice}"
DIR="$ROOT/patches/libreoffice"
CHECK_ONLY="${1:-}"

names=()
while IFS= read -r name; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  names+=("$name")
done < "$DIR/series"

scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
copy_touched() { # fresh scratch copy of every file the series touches (missing files stay absent)
  rm -rf "$scratch/tree" && mkdir -p "$scratch/tree"
  local n f
  for n in "${names[@]}"; do
    sed -n 's|^+++ b/\([^[:space:]]*\).*|\1|p; s|^--- a/\([^[:space:]]*\).*|\1|p' "$DIR/$n"
  done | sort -u | while IFS= read -r f; do
    if [ -e "$SRC/$f" ]; then mkdir -p "$scratch/tree/$(dirname "$f")"; cp -p "$SRC/$f" "$scratch/tree/$f"; fi
  done
}

# Applied prefix: unwind from the end; skip the not-yet-applied tail, then every earlier patch
# must reverse-apply in turn.
copy_touched
applied=0 seen_applied=0
for (( i=${#names[@]}-1; i>=0; i-- )); do
  if patch -d "$scratch/tree" -p1 -R -s -f --no-backup-if-mismatch < "$DIR/${names[$i]}" >/dev/null 2>&1; then
    seen_applied=1
    [ "$applied" -eq 0 ] && applied=$((i + 1))
  elif [ "$seen_applied" -eq 1 ]; then
    echo "inconsistent tree: ${names[$i]} is not applied but a later patch is"; exit 1
  fi
done
for (( i=0; i<applied; i++ )); do echo "already applied: ${names[$i]}"; done

# Remaining patches: dry-run in order on a scratch copy of the current tree.
copy_touched
for (( i=applied; i<${#names[@]}; i++ )); do
  patch -d "$scratch/tree" -p1 -s -f --no-backup-if-mismatch < "$DIR/${names[$i]}" >/dev/null \
    || { echo "does not apply: ${names[$i]}"; exit 1; }
  [[ "$CHECK_ONLY" == "--check" ]] && echo "applies cleanly: ${names[$i]}"
done
[[ "$CHECK_ONLY" == "--check" ]] && exit 0

for (( i=applied; i<${#names[@]}; i++ )); do
  patch -d "$SRC" -p1 -s -f --no-backup-if-mismatch < "$DIR/${names[$i]}"
  echo "applied: ${names[$i]}"
done
