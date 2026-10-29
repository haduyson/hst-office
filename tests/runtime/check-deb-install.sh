#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Install-lifecycle test for HST Office .deb packages in a clean Ubuntu 24.04
# container: install -> convert a document as a normal user -> remove -> purge
# -> verify the user's documents and profile survive -> reinstall.
#   tests/runtime/check-deb-install.sh [deb-dir] [out-dir]
# Uses only a uniquely named, auto-removed container; never touches others.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEBS="$(cd "${1:-$ROOT/dist/linux}" && pwd)"
OUT="${2:-$ROOT/tests/output/deb-install}"
NAME="hst-deb-qa-$$"
mkdir -p "$OUT"
ls "$DEBS"/*.deb >/dev/null 2>&1 || { echo "BLOCKED: no .deb files in $DEBS"; exit 2; }

cat > "$OUT/inside.sh" <<'INSIDE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
step() { echo "STEP $1"; }
apt-get update -qq >/dev/null
step install; apt-get install -y -qq /debs/*.deb >/tmp/install.log 2>&1 || { tail -30 /tmp/install.log; exit 10; }
BIN="$(ls /opt/*/program/soffice 2>/dev/null | head -1)"
[ -n "$BIN" ] || { echo "FAIL soffice not found under /opt"; exit 11; }
echo "INFO binary $BIN"
"$BIN" --version | sed 's/^/INFO version /'
useradd -m tester
su tester -c "mkdir -p ~/Documents && printf 'Văn bản kiểm thử HST Office\n' > ~/Documents/keep.txt"
step convert
su tester -c "cd ~/Documents && '$BIN' --headless --convert-to odt keep.txt >/dev/null 2>&1 && '$BIN' --headless --convert-to docx keep.odt >/dev/null 2>&1"
su tester -c "test -s ~/Documents/keep.odt && test -s ~/Documents/keep.docx" && echo "PASS convert" || { echo "FAIL convert"; exit 12; }
PROFILE_COUNT="$(su tester -c 'find ~/.config -maxdepth 2 -type d | wc -l')"
PKGS="$(dpkg-query -W -f='${Package}\n' | grep -E '^(hst|hstoffice)' | tr '\n' ' ')"
echo "INFO packages $PKGS"
step remove; apt-get remove -y -qq $PKGS >/dev/null
step purge; apt-get purge -y -qq $PKGS >/dev/null
su tester -c "test -s ~/Documents/keep.txt && test -s ~/Documents/keep.odt && test -s ~/Documents/keep.docx" \
  && echo "PASS user-documents-kept" || { echo "FAIL user documents removed"; exit 13; }
[ "$(su tester -c 'find ~/.config -maxdepth 2 -type d | wc -l')" = "$PROFILE_COUNT" ] \
  && echo "PASS user-profile-kept" || { echo "FAIL user profile changed by purge"; exit 14; }
test ! -e "$BIN" && echo "PASS binaries-removed" || { echo "FAIL binaries left after purge"; exit 15; }
step reinstall; apt-get install -y -qq /debs/*.deb >/dev/null 2>&1 && "$BIN" --version >/dev/null && echo "PASS reinstall"
INSIDE

docker run --rm --name "$NAME" -v "$DEBS:/debs:ro" -v "$OUT/inside.sh:/inside.sh:ro" ubuntu:24.04 \
  bash /inside.sh 2>&1 | tee "$OUT/install-lifecycle.log"
status=${PIPESTATUS[0]}
grep -q '^FAIL' "$OUT/install-lifecycle.log" && status=1
echo "result: $([ "$status" = 0 ] && echo PASS || echo FAIL) (log: $OUT/install-lifecycle.log)"
exit "$status"
