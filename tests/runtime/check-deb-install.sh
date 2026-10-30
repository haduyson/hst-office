#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Install-lifecycle test for the single HST Office .deb in a clean container:
# install -> package/metadata/coexistence checks -> convert a document as a normal
# user -> remove -> purge -> verify the user's documents and profile survive -> reinstall.
#   tests/runtime/check-deb-install.sh [deb-file] [out-dir]
# Environment:
#   IMAGE         container image (default ubuntu:24.04; debian:13 also supported)
#   INSTALL_MODE  apt (default; `apt-get install ./file.deb`, the path graphical installers
#                 use), pkcon (PackageKit `pkcon install-local`, what App Center and
#                 GNOME Software call) or upgrade (install a split set from OLD_SPLIT_DIR,
#                 as shipped before the single package, then install the .deb over it)
#   OLD_SPLIT_DIR directory of the old split .deb files (INSTALL_MODE=upgrade)
# Uses only a uniquely named, auto-removed container; never touches others.
# Needs network inside the container (apt resolves runtime library dependencies).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${IMAGE:-ubuntu:24.04}"
MODE="${INSTALL_MODE:-apt}"
DEB="${1:-}"
[ -n "$DEB" ] || DEB="$(find "$ROOT/dist/linux" -maxdepth 1 -name 'HSTOffice_*_Linux_x86-64.deb' -print -quit 2>/dev/null || true)"
[ -f "$DEB" ] || { echo "BLOCKED: no single .deb (pass the file, or build with scripts/build-linux.sh --package)"; exit 2; }
DEB="$(cd "$(dirname "$DEB")" && pwd)/$(basename "$DEB")"
OUT="${2:-$ROOT/tests/output/deb-install-${IMAGE//[:\/]/-}-$MODE}"
NAME="hst-deb-qa-$$"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
MOUNT_OLD=()
case "$MODE" in
  apt|pkcon) ;;
  upgrade)
    ls "${OLD_SPLIT_DIR:-/nonexistent}"/*.deb >/dev/null 2>&1 || { echo "BLOCKED: set OLD_SPLIT_DIR to the old split .deb files"; exit 2; }
    MOUNT_OLD=(-v "$(cd "$OLD_SPLIT_DIR" && pwd):/old:ro") ;;
  *) echo "unknown INSTALL_MODE: $MODE"; exit 64 ;;
esac

HSTV="$(python3 "$ROOT/scripts/write-hst-version.py" --print | cut -d. -f1,2)"
cat > "$OUT/inside.sh" <<'INSIDE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
step() { echo "STEP $1"; }
apt-get update -qq >/dev/null
step baseline
! dpkg-query -W -f='${Package}\n' | grep -E '^(libreoffice|libobasis)' \
  && echo "PASS no-preinstalled-office" || { echo "FAIL a LibreOffice package is preinstalled"; exit 9; }
install_deb() {
  case "$MODE" in
    pkcon)
      # PackageKit with its apt backend on a private system bus: what App Center / GNOME Software drive.
      apt-get install -y -qq packagekit dbus >/tmp/pk-setup.log 2>&1 || { tail -20 /tmp/pk-setup.log; return 10; }
      mkdir -p /run/dbus; rm -f /run/dbus/pid; dbus-daemon --system --fork
      pkcon -y install-local /pkg/hst.deb >/tmp/install.log 2>&1 || { tail -30 /tmp/install.log; return 10; } ;;
    *) apt-get install -y -qq /pkg/hst.deb >/tmp/install.log 2>&1 || { tail -30 /tmp/install.log; return 10; } ;;
  esac
}
if [ "$MODE" = upgrade ]; then
  step old-split-install; apt-get install -y -qq /old/*.deb >/tmp/old-install.log 2>&1 || { tail -30 /tmp/old-install.log; exit 40; }
  OLD_COUNT="$(dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' 'hst-office*' | grep -c '^ii ')"
  [ "$OLD_COUNT" -ge 30 ] && echo "PASS old-split-installed ($OLD_COUNT packages)" || { echo "FAIL old split set not installed ($OLD_COUNT)"; exit 41; }
  useradd -m tester
  su tester -c "mkdir -p ~/Documents && printf 'Văn bản kiểm thử HST Office\n' > ~/Documents/keep.txt && cd ~/Documents && hst-office --headless --convert-to odt keep.txt >/dev/null 2>&1 && test -s keep.odt" \
    && echo "PASS old-split-works" || { echo "FAIL old split install does not convert"; exit 42; }
  OLD_PROFILE="$(su tester -c 'find ~/.config -maxdepth 2 -type d | wc -l')"
fi
step install; install_deb || exit 10
[ "$(dpkg-query -W -f='${db:Status-Abbrev}' hst-office)" = "ii " ] && echo "PASS single-package-installed" || { echo "FAIL hst-office not installed"; exit 10; }
LEFT="$(dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' 'hst-office*' | grep '^ii ' | grep -v ' hst-office$' || true)"
echo "INFO config-files-only-records: $(dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' 'hst-office*' | grep -c '^rc ' || true)"
[ -z "$LEFT" ] && echo "PASS no-split-packages-left" || { echo "FAIL split packages remain:"; echo "$LEFT" | head; exit 43; }
if [ "$MODE" = upgrade ]; then
  [ "$(su tester -c 'find ~/.config -maxdepth 2 -type d | wc -l')" = "$OLD_PROFILE" ] && echo "PASS upgrade-profile-kept" || { echo "FAIL profile changed by upgrade"; exit 44; }
  su tester -c "test -s ~/Documents/keep.odt" && echo "PASS upgrade-documents-kept" || { echo "FAIL documents lost"; exit 44; }
fi
BIN="$(ls /opt/hst-office*/program/soffice 2>/dev/null | head -1)"
[ -n "$BIN" ] || { echo "FAIL soffice not found under /opt/hst-office*"; exit 11; }
echo "INFO binary $BIN"
PKGS="hst-office"
echo "INFO packages $PKGS"
echo "INFO package-count $(echo $PKGS | wc -w)"
step identity
! dpkg-query -W -f='${Package}\n' | grep -E '^(libreoffice|libobasis)' \
  && echo "PASS no-libreoffice-named-package" || { echo "FAIL libreoffice/libobasis package installed"; exit 20; }
OWNED="$(dpkg -L $PKGS | sort -u)"
! echo "$OWNED" | grep -E '^/(usr|etc|var)/.*(libreoffice|libobasis)' \
  && echo "PASS no-libreoffice-named-system-file" || { echo "FAIL libreoffice-named file outside /opt"; exit 21; }
echo "$OWNED" | grep -qE '^/opt/libreoffice' && { echo "FAIL /opt/libreoffice* owned"; exit 22; } || echo "PASS install-root-hst-only"
CONF="$(dpkg-query -W -f='${Conflicts}${Replaces}${Provides}\n' $PKGS | tr ',' '\n' | sed 's/ *(.*//;s/^ *//' | grep -E 'libreoffice|libobasis|openoffice' | grep -v '^hst-' || true)"
[ -z "$CONF" ] && echo "PASS no-conflicts-with-libreoffice" || { echo "FAIL conflicts/replaces/provides: $CONF"; exit 23; }
dpkg-query -W -f='${Package} ${Version} ${Maintainer}\n' hst-office | sed 's/^/INFO maintainer /'
step desktop
DESK="$(echo "$OWNED" | grep -E '^/usr/share/applications/.*\.desktop$')"
ICONS="$(echo "$OWNED" | grep -cE '^/usr/share/icons/hicolor/.*/apps/hst-office@HSTV_RE@-(writer|calc|impress)\.png$')"
echo "INFO desktop-files $(echo "$DESK" | wc -l) app-icon-files $ICONS"
[ "$ICONS" -ge 9 ] && echo "PASS app-icons-installed" || { echo "FAIL app icons missing ($ICONS)"; exit 24; }
for want in "Name=HST Writer" "Name=HST Sheets" "Name=HST Slides" "Name=HST Office"; do
  grep -lq "^$want\$" $DESK 2>/dev/null && echo "PASS launcher '$want'" || { echo "FAIL launcher '$want' missing"; exit 25; }
done
for w in writer calc impress; do
  grep -q "^Icon=hst-office@HSTV@-$w\$" /usr/share/applications/hst-office@HSTV@-$w.desktop || { echo "FAIL icon name $w"; exit 26; }
  cmp -s /usr/share/icons/hicolor/48x48/apps/hst-office@HSTV@-$w.png /usr/share/icons/hicolor/48x48/apps/hst-office@HSTV@-writer.png && [ "$w" != writer ] && { echo "FAIL $w icon identical to writer"; exit 26; }
done
echo "PASS icon-names"
command -v hst-office >/dev/null && command -v hst-office@HSTV@ >/dev/null && echo "PASS commands-on-path ($(command -v hst-office))" || { echo "FAIL hst-office not on PATH"; exit 27; }
WEXEC="$(sed -n 's/^Exec=//p' /usr/share/applications/hst-office@HSTV@-writer.desktop | head -1)"
echo "INFO writer-exec $WEXEC"
case "$WEXEC" in hst-office@HSTV@\ --writer*) echo "PASS writer-exec-name" ;; *) echo "FAIL unexpected Exec $WEXEC"; exit 28 ;; esac
"$BIN" --version | sed -n 's/^\(.\+\)$/INFO version \1/p'
id tester >/dev/null 2>&1 || useradd -m tester
step bundled-extension
EXT="/opt/hst-office@HSTV@/share/extensions/hst-vietnamese-tools"
[ -f "$EXT/description.xml" ] && echo "PASS bundled-extension-files ($EXT/description.xml)" || { echo "FAIL $EXT/description.xml missing"; exit 30; }
UNOPKG="$(dirname "$BIN")/unopkg"
BUNDLED="$(su tester -c "$UNOPKG list --bundled 2>&1" || true)"
grep -q 'Identifier: vn\.hasontech' <<<"$BUNDLED" && echo "PASS unopkg-list-bundled ($(grep -o 'Identifier: vn\.hasontech[^ ]*' <<<"$BUNDLED" | head -1))" || { echo "FAIL unopkg list --bundled:"; echo "$BUNDLED" | tail -8; exit 31; }
step no-libreoffice-ui
# Installed Vietnamese UI strings must not name the upstream project (same allow-list as
# tests/runtime/check-no-libreoffice-ui.py: licence dialog, safe-mode zip file name).
python3 - "/opt/hst-office@HSTV@/program/resource/vi/LC_MESSAGES" <<'PY' || { echo "FAIL no-libreoffice-ui"; exit 32; }
import glob, gettext, re, sys
names = re.compile(r"libreoffice|document\s*foundation", re.I)
bad = []
for path in sorted(glob.glob(sys.argv[1] + "/*.mo")):
    for key, text in gettext.GNUTranslations(open(path, "rb"))._catalog.items():
        if not key or not isinstance(text, str) or not names.search(text):
            continue
        if str(key).startswith("licensedialog|") or "libreoffice-profile.zip" in text:
            continue
        bad.append((path.rsplit("/", 1)[-1], str(key)[:60]))
print("\n".join(map(str, bad)))
sys.exit(1 if bad else 0)
PY
echo "PASS no-libreoffice-ui"
su tester -c "mkdir -p ~/Documents && printf 'Văn bản kiểm thử HST Office\n' > ~/Documents/keep.txt"
step convert
# Launch through the PATH command that the .desktop Exec uses (headless equivalent).
su tester -c "cd ~/Documents && hst-office@HSTV@ --headless --convert-to odt keep.txt >/dev/null 2>&1 && hst-office --headless --convert-to docx keep.odt >/dev/null 2>&1"
su tester -c "test -s ~/Documents/keep.odt && test -s ~/Documents/keep.docx" && echo "PASS convert" || { echo "FAIL convert"; exit 12; }
su tester -c "find ~/.config -maxdepth 1 -mindepth 1 -printf 'INFO profile-dir %f\n'"
PROFILE_COUNT="$(su tester -c 'find ~/.config -maxdepth 2 -type d | wc -l')"
step coexist-simulate
# Simulated (no changes): installing the distribution LibreOffice next to HST Office must not remove HST packages.
SIM="$(apt-get -s install libreoffice-writer 2>&1 || true)"
grep -E '^Remv .*hst-office' <<<"$SIM" && { echo "FAIL official LibreOffice would remove HST packages"; exit 29; } || echo "PASS coexist-no-hst-removal"
grep -q '^Inst libreoffice-writer' <<<"$SIM" && echo "PASS coexist-official-installable" || { echo "FAIL could not simulate libreoffice-writer install"; echo "$SIM" | tail -5; exit 29; }
grep -q 'hst-office' /usr/share/applications/mimeinfo.cache 2>/dev/null && echo "PASS desktop-database-has-hst" || echo "INFO desktop-database-has-no-hst (desktop-file-utils missing?)"
step remove
if [ "$MODE" = pkcon ]; then pkcon -y remove hst-office >/tmp/remove.log 2>&1 || { tail -20 /tmp/remove.log; echo "FAIL pkcon remove"; exit 45; }
else apt-get remove -y -qq $PKGS >/dev/null; fi
[ "$(dpkg-query -W -f='${db:Status-Abbrev}' hst-office)" = "rc " ] || [ "$(dpkg-query -W -f='${db:Status-Abbrev}' hst-office)" = "un " ] \
  && echo "PASS removed-no-config-leftover-state" || { echo "FAIL state after remove: $(dpkg-query -W -f='${db:Status-Abbrev}' hst-office)"; exit 46; }
test ! -e /opt/hst-office1.0 && ! ls /usr/share/applications | grep -q hst-office && ! command -v hst-office >/dev/null && ! ls /usr/share/icons/hicolor/*/apps 2>/dev/null | grep -q hst-office \
  && echo "PASS remove-clean (/opt, launchers, icons, PATH)" || { echo "FAIL leftovers after remove"; ls /opt /usr/share/applications | grep hst || true; exit 47; }
! grep -q 'hst-office' /usr/share/applications/mimeinfo.cache 2>/dev/null && echo "PASS desktop-database-cleaned" || { echo "FAIL mimeinfo.cache still lists hst-office"; exit 48; }
step purge
# Removed local packages are unknown to apt, so purge the dpkg records directly.
dpkg --purge $(dpkg-query -W -f='${Package}\n' 'hst-office*' 2>/dev/null || true) >/tmp/purge.log 2>&1 || { tail -5 /tmp/purge.log; echo "FAIL purge"; exit 18; }
[ -z "$(dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' 'hst-office*' 2>/dev/null | grep -v '^un ' || true)" ] \
  && echo "PASS purged-no-dpkg-records" || { echo "FAIL dpkg records remain"; exit 19; }
su tester -c "test -s ~/Documents/keep.txt && test -s ~/Documents/keep.odt && test -s ~/Documents/keep.docx" \
  && echo "PASS user-documents-kept" || { echo "FAIL user documents removed"; exit 13; }
[ "$(su tester -c 'find ~/.config -maxdepth 2 -type d | wc -l')" = "$PROFILE_COUNT" ] \
  && echo "PASS user-profile-kept" || { echo "FAIL user profile changed by purge"; exit 14; }
test ! -e "$BIN" && echo "PASS binaries-removed" || { echo "FAIL binaries left after purge"; exit 15; }
! ls /opt | grep -q hst-office && ! ls /usr/share/applications | grep -q hst-office && ! command -v hst-office >/dev/null \
  && echo "PASS no-leftover-files" || { echo "FAIL leftovers after purge"; ls /opt /usr/share/applications | grep hst || true; exit 16; }
step reinstall; apt-get install -y -qq /pkg/hst.deb >/dev/null 2>&1 && "$BIN" --version >/dev/null && echo "PASS reinstall"
su tester -c "cd ~/Documents && hst-office --headless --convert-to pdf keep.odt >/dev/null 2>&1 && test -s keep.pdf" && echo "PASS convert-after-reinstall" || { echo "FAIL convert after reinstall"; exit 17; }
INSIDE
sed -i -e "s/@HSTV_RE@/${HSTV//./\\.}/g" -e "s/@HSTV@/$HSTV/g" "$OUT/inside.sh"

docker run --rm --name "$NAME" -e MODE="$MODE" -v "$DEB:/pkg/hst.deb:ro" "${MOUNT_OLD[@]}" -v "$OUT/inside.sh:/inside.sh:ro" "$IMAGE" \
  bash /inside.sh 2>&1 | tee "$OUT/install-lifecycle.log"
status=${PIPESTATUS[0]}
grep -q '^FAIL' "$OUT/install-lifecycle.log" && status=1
echo "result: $([ "$status" = 0 ] && echo PASS || echo FAIL) (log: $OUT/install-lifecycle.log)"
exit "$status"
