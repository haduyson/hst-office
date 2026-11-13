#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Test-only module build for local Windows builds (scripts/windows/hst4-build.ps1 -Modules), run in Cygwin bash:
#   hst4-make-targets.sh <make target>...
# Env: HST_WORK, HST_REPO (Cygwin paths, as for trial-build.sh), MAKEFLAGS=PARALLELISM=N.
# Uses the same environment as trial-build.sh --build (keep the block below in sync with its header), builds the
# UNO API headers in their own invocation first (docs/SHARED_BUILD_SLOTS.md), then the given targets.
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
[ "$#" -gt 0 ] || { echo "usage: $0 <make target>..."; exit 64; }
WORK="${HST_WORK:?}"; REPO="${HST_REPO:?}"; SRC="$WORK/lo"; LOGS="$WORK/logs"
# --- same as trial-build.sh
eval "$(python3 "$REPO/scripts/write-hst-version.py" --env)"
export HST_VERSION_MAJOR HST_VERSION_MINOR HST_VERSION_MICRO HST_RELEASE HST_VERSION_BUILD
HST_REPO_ROOT="$(cygpath -m "$REPO")"; export HST_REPO_ROOT
export PATH="$WORK/bin:/usr/local/bin:/usr/bin:/cygdrive/c/Program Files/NASM:/cygdrive/c/Windows/system32:/cygdrive/c/Windows"
export HOME="$WORK/home"; mkdir -p "$HOME" "$LOGS"
unset MSYSTEM MSYSTEM_PREFIX MSYSTEM_CHOST MSYSTEM_CARCH MINGW_PREFIX MINGW_CHOST MINGW_PACKAGE_PREFIX MSYS2_ARG_CONV_EXCL
# ---
cd "$SRC"
{ make GIT_NEEDED_SUBMODULES= udkapi.build offapi.build oovbaapi.build && make GIT_NEEDED_SUBMODULES= "$@"; } \
  > "$LOGS/build.log" 2>&1 || { tail -60 "$LOGS/build.log"; exit 1; }
tail -5 "$LOGS/build.log"
