#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Decide whether macOS installers may come from a later commit than the release commit.
#   git diff --name-only <release commit> <macos commit> | macos-commit-paths.sh
# Reads changed paths on stdin. Succeeds when every path is outside what the Windows and Linux
# installers are built from, so those installers are still exactly what that later commit would
# build. Otherwise prints the offending paths and fails. Allowed:
#   scripts/macos/**                     macOS packaging only (affects only the macOS installer)
#   .github/workflows/**, scripts/check-workflows.py   CI definitions and their checker
#   scripts/release/**                   release tooling (runs after the builds)
#   docs/**, plans/**, tests/**          documentation, plans, reports, tests
#   website/**                           product website (not built into any installer)
set -euo pipefail
allowed='^(scripts/macos/|scripts/release/|\.github/workflows/|docs/|plans/|tests/|website/|scripts/check-workflows\.py$)'
bad="$(grep -vE "$allowed")" || [ $? -eq 1 ]  # grep exits 1 when every path is allowed
if [ -n "$bad" ]; then
  printf 'changes outside macOS packaging, CI and docs:\n%s\n' "$bad" >&2
  exit 1
fi
