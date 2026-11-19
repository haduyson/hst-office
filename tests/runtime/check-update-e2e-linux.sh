#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# "Cập nhật ngay" end to end in a real, installed HST Office, in an auto-removed container (Xvfb, user "tester"):
# install the OLD package, start it with a document, dispatch org.hst.office.update:Install on the document
# (update-e2e-drive.py + update_e2e_macro.py), then check that the office quit, the NEW package is installed and an
# office came back by itself. pkexec is a sudo shim (containers have no polkit agent); everything else is real.
#   tests/runtime/check-update-e2e-linux.sh deb|rpm|appimage <old> <new> [options for update-e2e-drive.py]
# Without --installer in the options, the published signed manifest is read and <new> must be the package it names
# (placed in the update cache, so nothing is downloaded). With --installer, give <new> again: any test build.
# --code /ext runs this checkout's updater code in the old office; EXPECT_REOPEN=1 also checks that the relaunched office
# reopened the document. Report and logs: $OUT (default ./update-e2e-out).
set -euo pipefail
pass() { echo "PASS $*"; }
fail() { echo "FAIL $*"; }

inside() {
  set +e
  local kind="$KIND" home=/home/tester cache=/home/tester/.cache/hst-office/update
  case "$kind" in
    deb)
      export DEBIAN_FRONTEND=noninteractive; apt-get update -qq >/dev/null
      apt-get install -y -qq --no-install-recommends xvfb x11-utils procps sudo ca-certificates >/dev/null
      apt-get install -y -qq /pkg/old.deb >/tmp/old.log 2>&1 || { tail -5 /tmp/old.log; fail "old install"; return; }
      version() { dpkg-query -W -f '${Version}' hst-office 2>/dev/null; } ;;
    rpm)
      dnf install -y -q xorg-x11-server-Xvfb xwininfo procps-ng sudo /pkg/old.rpm >/tmp/old.log 2>&1 || { tail -5 /tmp/old.log; fail "old install"; return; }
      version() { rpm -q --qf '%{VERSION}-%{RELEASE}' hst-office 2>/dev/null; } ;;
    appimage)
      export DEBIAN_FRONTEND=noninteractive; apt-get update -qq >/dev/null
      apt-get install -y -qq --no-install-recommends libgtk-3-0 libnss3 libcups2 libgstreamer-plugins-base1.0-0 libxinerama1 \
        libsm6 libx11-xcb1 libgssapi-krb5-2 xvfb x11-utils procps fuse3 sudo ca-certificates >/dev/null
      version() { sha256sum < /home/tester/Apps/HST.AppImage | cut -c1-16; } ;;
  esac
  useradd -m tester
  # Fedora: sudo's PAM account step refuses a user without a usable shadow entry, even with NOPASSWD
  pwconv >/dev/null 2>&1 || :; usermod -p '' tester >/dev/null 2>&1 || :
  printf 'tester ALL=(root) NOPASSWD: ALL\n' >/etc/sudoers.d/tester
  printf '#!/bin/sh\nexec sudo -n "$@"\n' >/usr/local/bin/pkexec; chmod 755 /usr/local/bin/pkexec
  local soffice=/opt/hst-office1.0/program/soffice python=/opt/hst-office1.0/program/python new_name
  new_name="$(basename "$NEW_NAME")"
  if [ "$kind" = appimage ]; then
    mkdir -p "$home/Apps"; install -m 755 /pkg/old.AppImage "$home/Apps/HST.AppImage"
    cache="$home/Apps/.hst-office-update"
    su tester -c "cd /tmp && $home/Apps/HST.AppImage --appimage-extract >/dev/null 2>&1"
    python=/tmp/squashfs-root/opt/hst-office1.0/program/python; soffice="$home/Apps/HST.AppImage"
  fi
  mkdir -p "$cache"; cp "/pkg/new.$EXT_NAME" "$cache/$new_name"; chown -R tester "$home"
  local before; before="$(version)"; pass "old installed: $before"
  (Xvfb :99 -screen 0 1280x800x24 >/dev/null 2>&1 &); sleep 2
  printf '{\\rtf1\\ansi HST update probe\\par}\n' >/tmp/probe.rtf; chmod 644 /tmp/probe.rtf; mkdir -p /out; chown tester /out
  local extra=() arg
  for arg in "${DRIVE_ARGS[@]}"; do [ "$arg" = NEW ] && arg="$cache/$new_name"; extra+=("$arg"); done
  su tester -c "$(printf '%q ' env DISPLAY=:99 HOME="$home" HST_APPIMAGE_NO_INTEGRATION=1 "$python" /drive/update-e2e-drive.py --soffice "$soffice" \
    --profile /tmp/probe-profile --document /tmp/probe.rtf --out /out/report.json "${extra[@]}")" >/out/drive.log 2>&1
  local rc=$?
  cp "$cache/update.log" /out/ 2>/dev/null || cp /home/tester/.cache/hst-office/update/update.log /out/ 2>/dev/null || :
  sed 's/^/LOG /' /out/update.log 2>/dev/null | grep -v -E 'Unpacking|Selecting|Preparing|Setting up|Processing' | tail -15
  python3 -c 'import json,sys; r=json.load(open("/out/report.json")); print("EVENTS", [e["event"] for e in r["events"]]); print("QUIT", r["office_quit_after_s"], "RELAUNCHED", r["relaunched_pids"])' 2>/dev/null \
    || grep -v '^ ' /out/drive.log | tail -5
  local after; after="$(version)"
  grep -q '"office_quit_after_s": [0-9]' /out/report.json 2>/dev/null && pass "office quit" || fail "office did not quit"
  [ "$after" != "$before" ] || [ -n "${SAME_VERSION_OK:-}" ] && pass "now $after" || fail "still $after"
  [ "$rc" = 0 ] && pass "an office came back after the update" || fail "no office came back (driver exit $rc)"
  if [ -f /out/report.json ]; then
    for pid in $(python3 -c 'import json; print(*json.load(open("/out/report.json"))["relaunched_pids"])' 2>/dev/null); do
      echo "RELAUNCHED $pid: $(tr '\0' ' ' </proc/"$pid"/cmdline 2>/dev/null)"
    done
  fi
  [ ! -e "$cache/update-result.json" ] && pass "no failure record" || fail "failure recorded: $(cat "$cache/update-result.json")"
  if [ -n "${EXPECT_REOPEN:-}" ]; then  # releases with update_resume reopen the document in the relaunched office
    for _ in $(seq 1 30); do LC_ALL=C.UTF-8 DISPLAY=:99 xwininfo -root -tree 2>/dev/null | grep -q 'probe.rtf' && break; sleep 3; done
    LC_ALL=C.UTF-8 DISPLAY=:99 xwininfo -root -tree 2>/dev/null | grep -q 'probe.rtf' && pass "document reopened after the update" || fail "document not reopened"
    [ ! -e /home/tester/.cache/hst-office/update/update-pending.json ] && pass "pending record consumed" || fail "pending record left"
  fi
  pkill -u tester soffice.bin || :; pkill Xvfb || :
}

if [ "${1:-}" = --inside ]; then
  shift; read -r -a DRIVE_ARGS <<<"${DRIVE:-}"
  command -v python3 >/dev/null || { if command -v dnf >/dev/null; then dnf install -y -q python3 >/dev/null; else apt-get update -qq >/dev/null && apt-get install -y -qq python3 >/dev/null; fi; }
  inside; echo DONE; exit 0
fi
KIND="${1:?kind}"; OLD="$(realpath "${2:?old}")"; NEW="$(realpath "${3:?new}")"; shift 3
case "$KIND" in deb) IMAGE=ubuntu:24.04; EXT_NAME=deb ;; rpm) IMAGE=fedora:42; EXT_NAME=rpm ;;
  appimage) IMAGE=ubuntu:24.04; EXT_NAME=AppImage ;; *) echo "kind: deb|rpm|appimage" >&2; exit 64 ;; esac
HERE="$(cd "$(dirname "$0")" && pwd)"; EXT="$(cd "$HERE/../../extensions/hst-vietnamese-tools/python" && pwd)"
OUT="${OUT:-$PWD/update-e2e-out}"; mkdir -p "$OUT"
NAME="hst-update-e2e-$$"; LOG="$OUT/console.log"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || :' EXIT
docker run --rm --name "$NAME" -e KIND="$KIND" -e EXT_NAME="$EXT_NAME" -e NEW_NAME="${NEW_NAME:-$(basename "$NEW")}" \
  -e DRIVE="$*" -e SAME_VERSION_OK="${SAME_VERSION_OK:-}" -e EXPECT_REOPEN="${EXPECT_REOPEN:-}" --device /dev/fuse --cap-add SYS_ADMIN --security-opt apparmor:unconfined \
  -v "$OLD:/pkg/old.$EXT_NAME:ro" -v "$NEW:/pkg/new.$EXT_NAME:ro" -v "$EXT:/ext:ro" -v "$HERE:/drive:ro" -v "$OUT:/out" \
  -v "$(realpath "$0"):/self.sh:ro" "$IMAGE" bash /self.sh --inside 2>&1 | tee "$LOG"
status=${PIPESTATUS[0]}
grep -q '^FAIL' "$LOG" && status=1
echo "result: $([ "$status" = 0 ] && echo PASS || echo FAIL)"
exit "$status"
