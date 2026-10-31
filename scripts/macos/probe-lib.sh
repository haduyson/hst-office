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

# close_welcome <pid> <log>: activate the process and press the welcome dialog's "Đóng" button through System
# Events (a shell-started app is not frontmost, so a bare Return would go to the Finder); Return as fallback.
# Harmless when no dialog is up. Needs no extra permission on GitHub-hosted macOS runners.
close_welcome() {
  osascript >"$2" 2>&1 <<OSA || echo "osascript exit $?" >>"$2"
tell application "System Events"
  set p to first process whose unix id is ${1:-0}
  set frontmost of p to true
  delay 0.5
  try
    click button "Đóng" of window 1 of p
  on error
    key code 36
  end try
end tell
OSA
}
