#!/usr/bin/env bash
# Apply patches/libreoffice/series to the LibreOffice tree (idempotent).
#   scripts/apply-patches.sh [--check]
# A patch already applied (reverse-applies cleanly) is skipped; any other
# failure stops before modifying the tree (each patch is dry-run first).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${HST_LO_SRC:-$ROOT/upstream/libreoffice}"
DIR="$ROOT/patches/libreoffice"
CHECK_ONLY="${1:-}"

while IFS= read -r name; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  patch_file="$DIR/$name"
  if patch -d "$SRC" -p1 -R --dry-run -s -f < "$patch_file" >/dev/null 2>&1; then
    echo "already applied: $name"; continue
  fi
  patch -d "$SRC" -p1 --dry-run -s -f < "$patch_file" || { echo "does not apply: $name"; exit 1; }
  if [[ "$CHECK_ONLY" == "--check" ]]; then echo "applies cleanly: $name"; continue; fi
  patch -d "$SRC" -p1 -s -f --no-backup-if-mismatch < "$patch_file"
  echo "applied: $name"
done < "$DIR/series"
