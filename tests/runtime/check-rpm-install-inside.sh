#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Inside part of check-rpm-install.sh (runs as root in a throw-away Fedora/openSUSE/RHEL-family container).
set -uo pipefail
pass() { echo "PASS $*"; }
fail() { echo "FAIL $*"; }
step() { echo "STEP $*"; }
. /etc/os-release; echo "INFO os $PRETTY_NAME"
if command -v dnf >/dev/null; then
  PM=dnf; echo "INFO dnf $(dnf --version 2>/dev/null | head -1)"
  pm_install() { dnf install -y -q "$@"; }
  pm_remove() { dnf remove -y -q "$@"; }
  XVFB=xorg-x11-server-Xvfb
else
  PM=zypper; zypper -n refresh >/dev/null 2>&1
  pm_install() { zypper -n -q install --allow-unsigned-rpm "$@"; }
  pm_remove() { zypper -n -q remove "$@"; }
  XVFB=xorg-x11-server-Xvfb
fi
pm_install procps util-linux "$( [ $PM = dnf ] && echo shadow-utils || echo shadow)" findutils which >/dev/null 2>&1 || :
useradd -m tester 2>/dev/null || :
as_user() { su tester -s /bin/bash -c "$*"; }

if [ -n "${COEXIST:-}" ]; then
  step coexist-distro-libreoffice
  pm_install libreoffice-writer libreoffice-calc >/tmp/lo.log 2>&1 && pass "distro LibreOffice installed ($(rpm -q libreoffice-writer))" || { tail -5 /tmp/lo.log; fail "distro LibreOffice install"; }
fi

step install
if [ $PM = dnf ]; then
  # Unsigned local file: dnf (4 and 5) must accept it without --nogpgcheck (localpkg_gpgcheck is off by default).
  dnf install -y /pkg/hst.rpm >/tmp/install.log 2>&1; rc=$?
else
  # zypper refuses an unsigned file in non-interactive mode unless told (--allow-unsigned-rpm); record both.
  zypper -n install /pkg/hst.rpm >/tmp/zypper-plain.log 2>&1 && echo "INFO zypper accepts the unsigned rpm without a flag" \
    || echo "INFO zypper without --allow-unsigned-rpm: $(grep -iE 'signature|not signed|unsigned' /tmp/zypper-plain.log | head -1)"
  rpm -q hst-office >/dev/null 2>&1 || { zypper -n install --allow-unsigned-rpm /pkg/hst.rpm >/tmp/install.log 2>&1; }
  rc=$?
fi
grep -iE 'signature|gpg|not signed' /tmp/install.log | head -3 | sed 's/^/INFO install-log /'
rpm -q hst-office >/dev/null && pass "installed $(rpm -q hst-office) (exit $rc)" || { tail -30 /tmp/install.log; fail install; exit 10; }
rpm -qi hst-office | grep -E '^(Version|Release|Vendor|Signature)' | sed 's/^/INFO /'
[ "$(rpm -q --qf '%{VENDOR}' hst-office)" = "HASON TECH" ] && pass vendor || fail vendor
rpm -V hst-office >/tmp/verify.log 2>&1 && pass "rpm -V clean" || { head /tmp/verify.log; fail "rpm -V"; }

step identity
rpm -ql hst-office | grep -E '^/(usr|etc)/.*libreoffice' && fail "libreoffice-named system file" || pass "no libreoffice-named system file"
rpm -q --provides hst-office | grep -vE '^hst-office' && fail "unexpected provides" || pass "provides only hst-office"
if [ -n "${COEXIST:-}" ]; then
  [ -z "$(rpm -ql hst-office | sort | comm -12 - <(rpm -ql libreoffice-writer libreoffice-core 2>/dev/null | sort))" ] && pass "no shared file with distro LibreOffice" || fail "shared files"
fi

step desktop
for w in startcenter writer calc impress; do
  f=/usr/share/applications/vn.hasontech.hstoffice-$w.desktop
  [ -r "$f" ] && grep -q "^Icon=vn.hasontech.hstoffice-$w" "$f" || { fail "launcher $w"; continue; }
  [ -s /usr/share/icons/hicolor/48x48/apps/vn.hasontech.hstoffice-$w.png ] && pass "launcher+icon $w ($(sed -n 's/^Name=//p' "$f" | head -1))" || fail "icon $w"
done
grep -q 'vn\.hasontech\.hstoffice-writer' /usr/share/applications/mimeinfo.cache 2>/dev/null && pass "desktop database lists HST" || echo "INFO no mimeinfo.cache (desktop-file-utils absent)"
command -v hst-office >/dev/null && pass "hst-office on PATH" || fail "hst-office on PATH"
BIN=/opt/hst-office1.0/program/soffice
echo "INFO version $($BIN --version 2>/dev/null)"

step open-save-vietnamese
as_user "/opt/hst-office1.0/program/python /roundtrip.py /tmp/rt-tester hst-office" && pass "roundtrip as user" || fail "roundtrip"
as_user "mkdir -p ~/Documents && cp /tmp/rt-tester/vi.docx ~/Documents/keep.docx"

step gui
pm_install "$XVFB" >/tmp/xvfb.log 2>&1 || { tail -3 /tmp/xvfb.log; fail "install Xvfb"; }
(Xvfb :99 -screen 0 1280x800x24 >/dev/null 2>&1 &) ; sleep 3
as_user "DISPLAY=:99 hst-office --writer --norestore >/tmp/gui.log 2>&1 & sleep 25; pgrep -x soffice.bin >/dev/null && echo GUI-ALIVE; pkill -x soffice.bin; true" | grep -q GUI-ALIVE \
  && pass "GUI start under Xvfb (process stays up 25 s)" || { tail -5 /tmp/gui.log; fail "GUI start"; }
if [ -n "${COEXIST:-}" ]; then
  as_user "DISPLAY=:99 libreoffice --writer --norestore >/dev/null 2>&1 & sleep 15; DISPLAY=:99 hst-office --writer --norestore >/dev/null 2>&1 & sleep 25; pgrep -fc 'soffice.bin' ; pkill -f soffice.bin; true" >/tmp/both.log
  [ "$(head -1 /tmp/both.log)" -ge 2 ] 2>/dev/null && pass "both suites run at once (2 processes)" || fail "both suites at once ($(cat /tmp/both.log))"
fi

step reinstall
rpm -U --replacepkgs /pkg/hst.rpm >/tmp/upgrade.log 2>&1 && [ -x $BIN ] && pass "rpm -U --replacepkgs keeps the install" || { tail -5 /tmp/upgrade.log; fail "rpm -U"; }

step erase
pm_remove hst-office >/tmp/remove.log 2>&1 || { tail -5 /tmp/remove.log; fail remove; }
! rpm -q hst-office >/dev/null && [ ! -e /opt/hst-office1.0 ] && ! find /usr/share/applications -name '*hasontech*' | grep -q . && ! command -v hst-office >/dev/null \
  && pass "erase clean (/opt, launchers, PATH)" || fail "leftovers after erase"
! find /usr/share/icons/hicolor -name '*hasontech*' | grep -q . && pass "icons removed" || fail "icons left"
as_user "test -s ~/Documents/keep.docx" && pass "user documents kept" || fail "user documents lost"
if [ -n "${COEXIST:-}" ]; then
  as_user "cd /tmp && libreoffice --headless --convert-to pdf ~/Documents/keep.docx >/dev/null 2>&1 && test -s /tmp/keep.pdf" && pass "distro LibreOffice works after HST erase" || fail "distro LibreOffice after erase"
fi
pkill Xvfb || :
echo "DONE"
