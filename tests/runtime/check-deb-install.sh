#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Install-lifecycle test for HST Office .deb packages in a clean Ubuntu 24.04
# container: install -> package/metadata/coexistence checks -> convert a document
# as a normal user -> remove -> purge -> verify the user's documents and profile
# survive -> reinstall.
#   tests/runtime/check-deb-install.sh [deb-dir] [out-dir]
# Uses only a uniquely named, auto-removed container; never touches others.
# Needs network inside the container (apt resolves runtime library dependencies).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEBS="$(cd "${1:-$ROOT/dist/linux}" && pwd)"
OUT="${2:-$ROOT/tests/output/deb-install}"
NAME="hst-deb-qa-$$"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
ls "$DEBS"/*.deb >/dev/null 2>&1 || { echo "BLOCKED: no .deb files in $DEBS"; exit 2; }

HSTV="$(python3 "$ROOT/scripts/write-hst-version.py" --print | cut -d. -f1,2)"
cat > "$OUT/inside.sh" <<'INSIDE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
step() { echo "STEP $1"; }
apt-get update -qq >/dev/null
step baseline
! dpkg-query -W -f='${Package}\n' | grep -E '^(libreoffice|libobasis)' \
  && echo "PASS no-preinstalled-office" || { echo "FAIL a LibreOffice package is preinstalled"; exit 9; }
step install; apt-get install -y -qq /debs/*.deb >/tmp/install.log 2>&1 || { tail -30 /tmp/install.log; exit 10; }
BIN="$(ls /opt/hst-office*/program/soffice 2>/dev/null | head -1)"
[ -n "$BIN" ] || { echo "FAIL soffice not found under /opt/hst-office*"; exit 11; }
echo "INFO binary $BIN"
PKGS="$(dpkg-query -W -f='${Package}\n' | grep -E '^hst-office' | tr '\n' ' ')"
echo "INFO packages $PKGS"
echo "INFO package-count $(echo $PKGS | wc -w)"
step identity
! dpkg-query -W -f='${Package}\n' | grep -E '^(libreoffice|libobasis)' \
  && echo "PASS no-libreoffice-named-package" || { echo "FAIL libreoffice/libobasis package installed"; exit 20; }
OWNED="$(dpkg -L $PKGS | sort -u)"
! echo "$OWNED" | grep -E '^/(usr|etc|var)/.*(libreoffice|libobasis)' \
  && echo "PASS no-libreoffice-named-system-file" || { echo "FAIL libreoffice-named file outside /opt"; exit 21; }
echo "$OWNED" | grep -qE '^/opt/libreoffice' && { echo "FAIL /opt/libreoffice* owned"; exit 22; } || echo "PASS install-root-hst-only"
CONF="$(dpkg-query -W -f='${Conflicts}${Replaces}${Provides}\n' $PKGS | tr ',' '\n' | sed 's/ *(.*//;s/^ *//' | grep -E 'libreoffice|libobasis|openoffice' || true)"
[ -z "$CONF" ] && echo "PASS no-conflicts-with-libreoffice" || { echo "FAIL conflicts/replaces/provides: $CONF"; exit 23; }
dpkg-query -W -f='${Package} ${Maintainer}\n' hst-office@HSTV@ | sed 's/^/INFO maintainer /'
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
useradd -m tester
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
step remove; apt-get remove -y -qq $PKGS >/dev/null
step purge
# Removed local packages are unknown to apt, so purge the dpkg records directly.
dpkg --purge $PKGS >/tmp/purge.log 2>&1 || { tail -5 /tmp/purge.log; echo "FAIL purge"; exit 18; }
[ -z "$(dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' 'hst-office*' 2>/dev/null | grep -v '^un ' || true)" ] \
  && echo "PASS purged-no-dpkg-records" || { echo "FAIL dpkg records remain"; exit 19; }
su tester -c "test -s ~/Documents/keep.txt && test -s ~/Documents/keep.odt && test -s ~/Documents/keep.docx" \
  && echo "PASS user-documents-kept" || { echo "FAIL user documents removed"; exit 13; }
[ "$(su tester -c 'find ~/.config -maxdepth 2 -type d | wc -l')" = "$PROFILE_COUNT" ] \
  && echo "PASS user-profile-kept" || { echo "FAIL user profile changed by purge"; exit 14; }
test ! -e "$BIN" && echo "PASS binaries-removed" || { echo "FAIL binaries left after purge"; exit 15; }
! ls /opt | grep -q hst-office && ! ls /usr/share/applications | grep -q hst-office && ! command -v hst-office >/dev/null \
  && echo "PASS no-leftover-files" || { echo "FAIL leftovers after purge"; ls /opt /usr/share/applications | grep hst || true; exit 16; }
step reinstall; apt-get install -y -qq /debs/*.deb >/dev/null 2>&1 && "$BIN" --version >/dev/null && echo "PASS reinstall"
su tester -c "cd ~/Documents && hst-office --headless --convert-to pdf keep.odt >/dev/null 2>&1 && test -s keep.pdf" && echo "PASS convert-after-reinstall" || { echo "FAIL convert after reinstall"; exit 17; }
INSIDE
sed -i -e "s/@HSTV_RE@/${HSTV//./\\.}/g" -e "s/@HSTV@/$HSTV/g" "$OUT/inside.sh"

docker run --rm --name "$NAME" -v "$DEBS:/debs:ro" -v "$OUT/inside.sh:/inside.sh:ro" ubuntu:24.04 \
  bash /inside.sh 2>&1 | tee "$OUT/install-lifecycle.log"
status=${PIPESTATUS[0]}
grep -q '^FAIL' "$OUT/install-lifecycle.log" && status=1
echo "result: $([ "$status" = 0 ] && echo PASS || echo FAIL) (log: $OUT/install-lifecycle.log)"
exit "$status"
