# SPDX-License-Identifier: AGPL-3.0-only
# shellcheck shell=bash
# Shared helper for the macOS probe scripts (sourced by ribbon-probe.sh).

# init_profile <app> <profile>: create the profile the way the first start does. A fresh profile makes soffice
# ask for one restart (exit code 81); repeat until it exits cleanly so later GUI starts keep the registry edits.
init_profile() {
  local rc=0
  for _ in 1 2 3; do
    rc=0
    "$1/Contents/MacOS/soffice" --headless --norestore --terminate_after_init "-env:UserInstallation=file://$2" >/dev/null 2>&1 || rc=$?
    [ "$rc" -eq 0 ] && return 0
  done
  echo "profile init did not finish cleanly (last exit $rc)" >&2
  return 0
}
