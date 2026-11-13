#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Inside part of check-appimage.sh (root in a throw-away container; the AppImage runs as user "tester").
set -uo pipefail
pass() { echo "PASS $*"; }
fail() { echo "FAIL $*"; }
step() { echo "STEP $*"; }
. /etc/os-release; echo "INFO os $PRETTY_NAME"
# Libraries the office links against (what a desktop installation has anyway), Xvfb, tools; never libfuse2.
case "$ID" in
  ubuntu|debian)
    export DEBIAN_FRONTEND=noninteractive; apt-get update -qq >/dev/null
    PKGS="libgtk-3-0 libnss3 libcups2 libgstreamer-plugins-base1.0-0 libxinerama1 libsm6 libx11-xcb1 libgssapi-krb5-2 xvfb procps desktop-file-utils shared-mime-info"
    add() { apt-get install -y -qq --no-install-recommends "$@" >/tmp/pkg.log 2>&1; } ;;
  fedora)
    PKGS="gtk3 nss cups-libs gstreamer1-plugins-base libXinerama libSM krb5-libs xorg-x11-server-Xvfb procps-ng desktop-file-utils shared-mime-info shadow-utils util-linux"
    add() { dnf install -y -q "$@" >/tmp/pkg.log 2>&1; } ;;
  arch)
    pacman -Sy --noconfirm >/dev/null 2>&1
    PKGS="gtk3 nss libcups gst-plugins-base-libs libxinerama libsm krb5 xorg-server-xvfb procps-ng desktop-file-utils shared-mime-info"
    add() { pacman -S --noconfirm --needed "$@" >/tmp/pkg.log 2>&1; } ;;
  *) echo "FAIL unsupported image $ID"; exit 2 ;;
esac
add $PKGS || { tail -5 /tmp/pkg.log; fail "install runtime libraries"; }
useradd -m tester 2>/dev/null || :
as_user() { su tester -s /bin/bash -c "$*"; }
install -d -o tester /home/tester/Apps
install -m 755 -o tester /pkg/HSTOffice.AppImage /home/tester/Apps/HSTOffice.AppImage
A=/home/tester/Apps/HSTOffice.AppImage
ldconfig -p | grep -q 'libfuse\.so\.2' && fail "libfuse2 present in the image" || pass "no libfuse2 on this machine"
echo "INFO glibc $(ldd --version 2>&1 | head -1)"

step no-fuse
if command -v fusermount >/dev/null || command -v fusermount3 >/dev/null; then
  echo "INFO fusermount already present in the image"
else
  as_user "$A --version" >/tmp/nofuse.log 2>&1
  if grep -qi 'fuse' /tmp/nofuse.log; then pass "without FUSE: the runtime explains it ($(grep -i fuse /tmp/nofuse.log | head -1 | cut -c1-90))"
  else head -5 /tmp/nofuse.log; fail "no FUSE message"; fi
fi
as_user "HST_APPIMAGE_NO_INTEGRATION=1 $A --appimage-extract-and-run --version" 2>/dev/null | grep -q '^HST Office' \
  && pass "--appimage-extract-and-run works without FUSE" || fail "--appimage-extract-and-run"

step fuse3-only
case "$ID" in ubuntu|debian) add fuse3 ;; fedora) add fuse3 ;; arch) add fuse3 ;; esac || fail "install fuse3"
ldconfig -p | grep -q 'libfuse\.so\.2' && fail "fuse3 pulled libfuse2" || pass "fuse3 installed, still no libfuse2"
V="$(as_user "HST_APPIMAGE_NO_INTEGRATION=1 $A --version" 2>&1)"
grep -q '^HST Office' <<<"$V" && pass "mounted start via FUSE 3 ($V)" || { echo "$V" | head -3; fail "FUSE start"; }

step integration
as_user "$A --version" >/dev/null 2>&1
D=/home/tester/.local/share
for w in startcenter writer calc impress; do
  f=$D/applications/vn.hasontech.hstoffice-$w.desktop
  grep -q "^Exec=\"$A\"" "$f" 2>/dev/null && pass "launcher $w points at the AppImage" || fail "launcher $w"
done
command -v desktop-file-validate >/dev/null && { desktop-file-validate $D/applications/vn.hasontech.hstoffice-*.desktop >/tmp/dfv.log 2>&1; grep -q error /tmp/dfv.log && { head -5 /tmp/dfv.log; fail "desktop-file-validate"; } || pass "desktop-file-validate"; }
[ -s $D/icons/hicolor/256x256/apps/vn.hasontech.hstoffice-writer.png ] && pass "icons" || fail icons
[ -s $D/mime/packages/vn.hasontech.hstoffice-appimage.xml ] && pass "MIME package" || fail "MIME package"
grep -q 'vn.hasontech.hstoffice-writer.desktop' $D/applications/mimeinfo.cache 2>/dev/null && pass "user desktop database maps types to HST Writer" || fail "mimeinfo.cache"
grep -q 'RemoveIntegration' $D/applications/vn.hasontech.hstoffice-startcenter.desktop && pass "removal action in the Start Center launcher" || fail "removal action"
as_user "mv $A /home/tester/Apps/HST.AppImage && /home/tester/Apps/HST.AppImage --version >/dev/null 2>&1"
grep -q '^Exec="/home/tester/Apps/HST.AppImage"' $D/applications/vn.hasontech.hstoffice-writer.desktop && pass "moved AppImage: launchers follow" || fail "moved AppImage"
A=/home/tester/Apps/HST.AppImage
as_user "$A --remove-desktop-integration"
if find $D -name 'vn.hasontech.*' | grep -q .; then fail "files left after removal"; else pass "removal deletes launchers and icons"; fi
as_user "$A --version >/dev/null 2>&1"
ls $D/applications/vn.hasontech.* >/dev/null 2>&1 && fail "re-integrated after removal" || pass "removal is remembered on the next start"
as_user "$A --install-desktop-integration" && [ -f $D/applications/vn.hasontech.hstoffice-writer.desktop ] && pass "--install-desktop-integration" || fail "--install-desktop-integration"

step open-save-vietnamese
as_user "cd /tmp && $A --appimage-extract >/dev/null 2>&1"
as_user "/tmp/squashfs-root/opt/hst-office1.0/program/python /roundtrip.py /tmp/rt $A" && pass "roundtrip through the AppImage" || fail roundtrip

step gui
(Xvfb :99 -screen 0 1280x800x24 >/dev/null 2>&1 &); sleep 3
as_user "DISPLAY=:99 $A --writer --norestore >/tmp/gui.log 2>&1 & sleep 25; pgrep -x soffice.bin >/dev/null && echo GUI-ALIVE; pkill -x soffice.bin; true" | grep -q GUI-ALIVE \
  && pass "GUI start under Xvfb" || { tail -5 /tmp/gui.log; fail "GUI start"; }
pkill Xvfb || :
echo DONE
