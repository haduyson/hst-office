#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# End-to-end "Cập nhật ngay" install step for .rpm and AppImage installs, in an auto-removed container:
# install the OLD package, detect the install kind with update_linux_install.py (bundled python), build the real
# helper (update_helper_cmd.build_helper), run it once the "office" pid is gone and check that the NEW package is in
# place and started again. pkexec is a pass-through shim (containers have no polkit agent); the rest is real
# (dnf or zypper, the rename over the AppImage, the relaunch under Xvfb).
#   tests/runtime/check-linux-package-update.sh rpm <old.rpm> <new.rpm> [image, default fedora:42]
#   tests/runtime/check-linux-package-update.sh appimage <old.AppImage> <new.AppImage> [image, default ubuntu:24.04]
# The new package must differ from the old one (e.g. repacked from a .deb renamed to a higher release id).
# EXPECT_SIGNED=1 (rpm): the new package is GPG-signed and the old one ships RPM-GPG-KEY-hasontech; the helper must
# import that key and install without --allow-unsigned-rpm.
set -euo pipefail
pass() { echo "PASS $*"; }
fail() { echo "FAIL $*"; }

helper() { # helper <python> <kind> <installer> <target>: write the real helper script, print its argv (one per line)
  PYTHONPATH=/ext "$1" - "$2" "$3" "$4" <<'PY'
import hashlib, subprocess, sys
from hst_office import update_helper_cmd as cmd, update_launch as launch
kind, installer, target = sys.argv[1:4]
dead = subprocess.Popen(["true"]); dead.wait()
sha = hashlib.sha256(open(installer, "rb").read()).hexdigest()
h = cmd.build_helper("Linux", pid=dead.pid, installer=installer, soffice=target, log="/tmp/upd/update.log", sha256=sha,
                     linux_kind=kind, release_from="1.0.1", release_to="9.9.9")
print("\n".join(cmd.argv(h, launch.write_helper(h, "/tmp/upd"))))
PY
}

inside_rpm() {
  if command -v dnf >/dev/null; then PM="dnf install -y -q"; else zypper -n -q refresh >/dev/null; PM="zypper -n -q install --allow-unsigned-rpm"; fi
  $PM procps-ng >/dev/null 2>&1 || $PM procps >/dev/null 2>&1 || :
  $PM /pkg/old.$EXT_NAME >/tmp/old.log 2>&1 && pass "old installed: $(rpm -q hst-office)" || { tail -5 /tmp/old.log; fail "old install"; return; }
  PY=/opt/hst-office1.0/program/python
  kind="$(PYTHONPATH=/ext $PY -c 'from hst_office import update_linux_install as li; print(li.detect("/opt/hst-office1.0/program", {}))')"
  [ "$kind" = rpm ] && pass "install kind detected: rpm" || fail "install kind: $kind"
  printf '#!/bin/sh\nexec "$@"\n' > /usr/local/bin/pkexec; chmod 755 /usr/local/bin/pkexec
  cp /pkg/new.$EXT_NAME /tmp/upd-new.rpm; mkdir -p /tmp/upd
  mapfile -t argv < <(helper "$PY" rpm /tmp/upd-new.rpm /opt/hst-office1.0/program/soffice)
  "${argv[@]}"; rc=$?
  sed 's/^/LOG /' /tmp/upd/update.log | grep -v 'Unpacking\|Installing  \|Verifying\|Running\|^LOG  ' | tail -12
  [ "$rc" = 0 ] && grep -qE 'Installing with (dnf|zypper)' /tmp/upd/update.log && pass "helper installed with $(grep -oE 'Installing with \w+' /tmp/upd/update.log)" || fail "helper exit $rc"
  [ "$(rpm -q --qf '%{VERSION}' hst-office)" = "$(rpm -qp --qf '%{VERSION}' /pkg/new.$EXT_NAME)" ] && pass "now $(rpm -q hst-office)" || fail "version after update: $(rpm -q hst-office)"
  [ ! -e /tmp/upd-new.rpm ] && pass "installer deleted after success" || fail "installer left"
  grep -q 'Relaunching HST Office' /tmp/upd/update.log && pass "relaunch attempted" || fail "no relaunch"
  [ ! -e /tmp/upd/update-result.json ] && pass "no failure record" || fail "failure recorded: $(cat /tmp/upd/update-result.json)"
  if [ -n "${EXPECT_SIGNED:-}" ]; then  # a signed update over an install that ships the key
    grep -q 'Signed package: importing' /tmp/upd/update.log && ! grep -q 'allow-unsigned' /tmp/upd/update.log \
      && rpm -q gpg-pubkey >/dev/null && pass "signed update: key imported, no --allow-unsigned-rpm" || fail "signed update path"
  fi
}

inside_appimage() {
  export DEBIAN_FRONTEND=noninteractive; apt-get update -qq >/dev/null
  apt-get install -y -qq --no-install-recommends libgtk-3-0 libnss3 libcups2 libgstreamer-plugins-base1.0-0 libxinerama1 libsm6 \
    libx11-xcb1 libgssapi-krb5-2 xvfb procps fuse3 >/dev/null 2>&1 || fail "packages"
  useradd -m tester; mkdir -p /home/tester/Apps/.hst-office-update
  install -m 755 /pkg/old.$EXT_NAME /home/tester/Apps/HST.AppImage
  cp /pkg/new.$EXT_NAME /home/tester/Apps/.hst-office-update/HSTOffice_9.9.9_Linux_x86-64.AppImage
  chown -R tester /home/tester/Apps
  su tester -s /bin/bash -c "cd /tmp && /home/tester/Apps/HST.AppImage --appimage-extract >/dev/null 2>&1"
  ROOTFS=/tmp/squashfs-root
  kind="$(su tester -s /bin/bash -c "APPIMAGE=/home/tester/Apps/HST.AppImage APPDIR=$ROOTFS PYTHONPATH=/ext $ROOTFS/opt/hst-office1.0/program/python -c 'from hst_office import update_linux_install as li; import os; print(li.detect(\"$ROOTFS/opt/hst-office1.0/program\", os.environ))'")"
  [ "$kind" = appimage ] && pass "install kind detected: appimage" || fail "install kind: $kind"
  (Xvfb :99 -screen 0 1280x800x24 >/dev/null 2>&1 &); sleep 2
  su tester -s /bin/bash -c "mkdir -p /tmp/upd; $(declare -f helper); helper $ROOTFS/opt/hst-office1.0/program/python appimage /home/tester/Apps/.hst-office-update/HSTOffice_9.9.9_Linux_x86-64.AppImage /home/tester/Apps/HST.AppImage > /tmp/argv"
  su tester -s /bin/bash -c 'mapfile -t argv < /tmp/argv; APPIMAGE=/stale APPDIR=/stale DISPLAY=:99 HST_APPIMAGE_NO_INTEGRATION=1 "${argv[@]}"'; rc=$?
  sed 's/^/LOG /' /tmp/upd/update.log | tail -8
  [ "$rc" = 0 ] && pass "helper exit 0" || fail "helper exit $rc"
  [ "$(sha256sum < /home/tester/Apps/HST.AppImage)" = "$(sha256sum < /pkg/new.$EXT_NAME)" ] && pass "AppImage replaced in place (same path, new content)" || fail "AppImage not replaced"
  [ -x /home/tester/Apps/HST.AppImage ] && [ ! -e /home/tester/Apps/.hst-office-update ] && pass "executable, hidden download directory removed" || fail "mode or leftovers"
  sleep 20
  pgrep -u tester -x soffice.bin >/dev/null && pass "new AppImage relaunched (soffice.bin running)" || fail "no relaunch"
  pkill -u tester soffice.bin || :; pkill Xvfb || :
}

if [ "${1:-}" = --inside ]; then
  if [ "$KIND" = rpm ]; then inside_rpm; else inside_appimage; fi
  echo DONE; exit 0
fi
KIND="${1:?kind}"; OLD="$(realpath "${2:?old}")"; NEW="$(realpath "${3:?new}")"
case "$KIND" in rpm) IMAGE="${4:-fedora:42}"; EXT_NAME=rpm ;; appimage) IMAGE="${4:-ubuntu:24.04}"; EXT_NAME=AppImage ;; *) echo "kind: rpm|appimage"; exit 64 ;; esac
EXT="$(cd "$(dirname "$0")/../../extensions/hst-vietnamese-tools/python" && pwd)"
NAME="hst-update-e2e-$$"
LOG="$(mktemp)"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || :; rm -f "$LOG"' EXIT
docker run --rm --name "$NAME" -e KIND="$KIND" -e EXT_NAME="$EXT_NAME" -e EXPECT_SIGNED="${EXPECT_SIGNED:-}" --device /dev/fuse --cap-add SYS_ADMIN --security-opt apparmor:unconfined \
  -v "$OLD:/pkg/old.$EXT_NAME:ro" -v "$NEW:/pkg/new.$EXT_NAME:ro" -v "$EXT:/ext:ro" -v "$(realpath "$0"):/self.sh:ro" "$IMAGE" bash /self.sh --inside 2>&1 | tee "$LOG"
status=${PIPESTATUS[0]}
grep -q '^FAIL' "$LOG" && status=1
echo "result: $([ "$status" = 0 ] && echo PASS || echo FAIL)"
exit "$status"
