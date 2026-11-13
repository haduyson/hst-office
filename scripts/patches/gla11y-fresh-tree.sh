#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Run the build's accessibility check (bin/gla11y with the parameters of solenv/gbuild/UIConfig.mk) on every UI
# module the patch series touches, before pushing: a .ui change that passes the unit tests can still stop the
# build there (unlabelled menu items, a labelled-by without its label-for, stale suppressions of a changed class).
#
# usage: scripts/patches/gla11y-fresh-tree.sh TREE TARBALL
#   TREE     a LibreOffice tree with the series applied (e.g. from the fresh-apply script); missing upstream files
#            of the checked modules (other .ui files, bin/gla11y, solenv/sanitizers) are taken from TARBALL
#   TARBALL  libreoffice-26.8.1.1.tar.xz
# Needs python3 with lxml. Exit status 1 when any module has a new fatal.
set -uo pipefail
TREE="$1"; TARBALL="$2"
[ -d "$TREE" ] && [ -f "$TARBALL" ] || { echo "usage: $0 TREE TARBALL" >&2; exit 2; }
TOP=$(tar -tJf "$TARBALL" 2>/dev/null | head -1 | cut -d/ -f1)
# UI module directory -> sanitizer name, as solenv/gbuild/UIConfig.mk pairs them
declare -A MODULES=(
  [sw/uiconfig/swriter/ui]=modules/swriter [sc/uiconfig/scalc/ui]=modules/scalc
  [sd/uiconfig/simpress/ui]=modules/simpress [sd/uiconfig/sdraw/ui]=modules/sdraw
  [svx/uiconfig/ui]=svx [sfx2/uiconfig/ui]=sfx [cui/uiconfig/ui]=cui [xmlsecurity/uiconfig/ui]=xmlsec
)
patterns=("$TOP/bin/gla11y" "$TOP/solenv/sanitizers/ui/*")
for dir in "${!MODULES[@]}"; do patterns+=("$TOP/$dir/*.ui"); done
tar -xJf "$TARBALL" -C "$TREE" --strip-components=1 --skip-old-files --wildcards "${patterns[@]}" 2>/dev/null
status=0
for dir in "${!MODULES[@]}"; do
  name=${MODULES[$dir]}
  files=("$TREE/$dir"/*.ui)
  [ -e "${files[0]}" ] || continue
  args=(-P "$TREE/")
  [ -f "$TREE/solenv/sanitizers/ui/$name.false" ] && args+=(-f "$TREE/solenv/sanitizers/ui/$name.false")
  [ -f "$TREE/solenv/sanitizers/ui/$name.suppr" ] && args+=(-s "$TREE/solenv/sanitizers/ui/$name.suppr")
  out=$(mktemp)
  (cd "$TREE" && python3 bin/gla11y "${args[@]}" \
    --widgets-suffixignored +ValueSet,HBox,VBox,ToolBox,Preview,PreviewWin,PreviewWindow,PrevWindow \
    --widgets-button +svtlo-ManagedMenuButton \
    --fatal-all --not-fatal-type duplicate-mnemonic --not-fatal-type labelled-by-and-mnemonic \
    --not-fatal-type orphan-label -o "$out" "${files[@]#$TREE/}") >/dev/null 2>&1
  rc=$?
  fatals=$(grep -c "FATAL" "$out")
  echo "$name: rc=$rc fatal=$fatals"
  grep "FATAL" "$out" | head -20
  [ "$rc" -eq 0 ] && [ "$fatals" -eq 0 ] || status=1
  rm -f "$out"
done
exit $status
