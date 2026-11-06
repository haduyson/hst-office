#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# HST Office and the distribution's LibreOffice installed and running side by side.
#   check-coexistence.sh <hst-office.deb> [<out-dir>]
# On the host: runs itself in a disposable ubuntu:24.04 container (removed on exit) and copies the log
# to <out-dir> (default ./coexistence). Inside (HST_COEXIST_INNER=1) it installs libreoffice-writer/calc/
# impress (GTK3), then the HST .deb, and fails when
#   - dpkg reports or the two packages ship a common file;
#   - installing or removing HST changes the default application (xdg-mime, gio) of ODF/OOXML types;
#   - both suites cannot run at once under Xvfb as separate processes with their own windows, or
#     starting one hands its document to the other (the single-instance pipe);
#   - an HST launcher is not named vn.hasontech.hstoffice-<module>.desktop with that StartupWMClass,
#     an HST window does not carry that class, or a LibreOffice window carries one of HST's;
#   - HST's first start touches a LibreOffice/OpenOffice profile directory (strace);
#   - removing either package leaves the other unable to start.
# Exit 0 = every check passed, 1 = a check failed, 2 = setup error, 64 = usage.
set -Eeuo pipefail
IMAGE="${HST_COEXIST_IMAGE:-ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852}"

host_main() {
  if [ $# -lt 1 ] || [ $# -gt 2 ]; then sed -n "3,4p" "$0" >&2; exit 64; fi
  local deb out here name rc=0
  deb="$(realpath "$1")"; out="$(realpath -m "${2:-coexistence}")"
  [ -f "$deb" ] || { echo "no such package: $deb" >&2; exit 64; }
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  mkdir -p "$out"
  name="hst-coexist-$$"
  # shellcheck disable=SC2064  # expand now: the trap must remove this run's container only
  trap "docker rm -f '$name' >/dev/null 2>&1 || :" EXIT
  docker run --rm --name "$name" -e HST_COEXIST_INNER=1 \
    -v "$deb:/coexist/hst-office.deb:ro" -v "$here/check-coexistence.sh:/coexist/check.sh:ro" -v "$out:/coexist/out" \
    "$IMAGE" bash /coexist/check.sh /coexist/hst-office.deb /coexist/out || rc=$?
  echo "coexistence: exit $rc (log: $out/coexistence.log)"
  exit "$rc"
}

# ---------------------------------------------------------------- inside the container
USER_NAME=tester
HST_ID=vn.hasontech.hstoffice   # launcher, icon, WM_CLASS and Wayland app_id prefix (sysui/productlist.mk)
FAILS=0
TYPES=(application/vnd.oasis.opendocument.text application/vnd.oasis.opendocument.spreadsheet
       application/vnd.oasis.opendocument.presentation
       application/vnd.openxmlformats-officedocument.wordprocessingml.document
       application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
       application/vnd.openxmlformats-officedocument.presentationml.presentation)
LO_PKGS=(libreoffice-writer libreoffice-calc libreoffice-impress libreoffice-gtk3)

log() { printf '%s\n' "$*"; }
pass() { log "PASS $*"; }
fail() { log "FAIL $*"; FAILS=$((FAILS + 1)); }
as_user() { runuser -u "$USER_NAME" -- env HOME="/home/$USER_NAME" DISPLAY=:99 SAL_USE_VCLPLUGIN=gtk3 "$@"; }
apt_quiet() { DEBIAN_FRONTEND=noninteractive apt-get -o Dpkg::Use-Pty=0 -y -q "$@"; }

# Default application per type as xdg-mime (generic) and GLib/GNOME (gio) see it, one line per type.
defaults() {
  local t
  for t in "${TYPES[@]}"; do
    printf '%s xdg=%s gio=%s\n' "$t" "$(as_user xdg-mime query default "$t" 2>/dev/null)" \
      "$(as_user gio mime "$t" 2>/dev/null | sed -n 's/^Default application for .*: //p')"
  done
}

# Top-level windows: "<pid> <res_class>" for every mapped root child that has a WM_CLASS.
windows() {
  local id
  for id in $(xwininfo -display :99 -root -children 2>/dev/null | awk '/^ +0x/ {print $1}'); do
    local cls pid
    cls="$(xprop -display :99 -id "$id" WM_CLASS 2>/dev/null | sed -n 's/^WM_CLASS(STRING) = "[^"]*", "\(.*\)"$/\1/p')"
    pid="$(xprop -display :99 -id "$id" _NET_WM_PID 2>/dev/null | sed -n 's/^_NET_WM_PID(CARDINAL) = //p')"
    [ -n "$cls" ] && printf '%s %s\n' "${pid:-0}" "$cls"
  done
}

# wait_window <class> [<seconds>]: until a top-level window of that WM_CLASS exists; prints its pid.
wait_window() {
  local cls="$1" left="${2:-120}" line
  while [ "$left" -gt 0 ]; do
    line="$(windows | awk -v c="$cls" '$2 == c {print $1; exit}')"
    [ -n "$line" ] && { echo "$line"; return 0; }
    sleep 2; left=$((left - 2))
  done
  return 1
}

# Executable that owns the window pid (the gtk3 frame pid is soffice.bin); /proc/<pid>/exe is not
# readable across users without CAP_SYS_PTRACE, the command line is.
exe_of() { tr '\0' '\n' < "/proc/$1/cmdline" 2>/dev/null | head -1 || echo "?"; }

stop_offices() {
  pkill -u "$USER_NAME" -x soffice.bin 2>/dev/null || :
  local left=20
  while pgrep -u "$USER_NAME" -x soffice.bin >/dev/null && [ "$left" -gt 0 ]; do sleep 1; left=$((left - 1)); done
  pkill -KILL -u "$USER_NAME" -x soffice.bin 2>/dev/null || :
}

hst_launchers() { dpkg -L hst-office | grep -E '^/usr/share/applications/[^/]+\.desktop$'; }

check_files() {
  local lo_files hst_files common
  lo_files="$(mktemp)"; hst_files="$(mktemp)"
  dpkg-query -W -f='${Package}\n' 'libreoffice*' 'libuno*' 'ure*' 2>/dev/null | while read -r p; do dpkg -L "$p" 2>/dev/null; done \
    | while read -r f; do [ -d "$f" ] || echo "$f"; done | sort -u > "$lo_files"
  dpkg -L hst-office | while read -r f; do [ -d "$f" ] || echo "$f"; done | sort -u > "$hst_files"
  common="$(comm -12 "$lo_files" "$hst_files")"
  if [ -z "$common" ]; then pass "no file shipped by both LibreOffice and HST ($(wc -l < "$hst_files") HST files)"
  else fail "files shipped by both:"; echo "$common" | head -20; fi
  if grep -q 'trying to overwrite' /coexist/out/apt-hst.log; then fail "dpkg reported a file conflict"; else pass "dpkg reported no file conflict"; fi
  local f id cls bad=0
  for f in $(hst_launchers); do
    id="$(basename "$f" .desktop)"; cls="$(sed -n 's/^StartupWMClass=//p' "$f")"
    case "$id" in "$HST_ID"-*) ;; *) bad=1; fail "HST launcher $id is not named $HST_ID-<module>" ;; esac
    if [ -n "$cls" ] && [ "$cls" != "$id" ]; then bad=1; fail "HST launcher $id claims window class $cls"; fi
  done
  [ "$bad" -eq 0 ] && pass "HST launchers: $(hst_launchers | xargs -n1 basename | tr '\n' ' ')"
}

check_defaults() { # check_defaults <label> <expected file>
  local now; now="$(defaults)"
  if [ "$now" = "$(cat "$2")" ]; then pass "$1: default applications unchanged"
  else fail "$1: default applications changed"; diff "$2" <(echo "$now") || :; fi
}

# run_both: LibreOffice first, then HST, then one more document for each; every window of one
# suite must belong to its own process and carry its own class.
run_both() {
  local lo_pid hst_pid lo_calc hst_calc
  as_user libreoffice --norestore --nologo --writer >/coexist/out/lo-writer.log 2>&1 &
  lo_pid="$(wait_window libreoffice-writer 180)" || { fail "LibreOffice Writer window did not appear"; return; }
  pass "LibreOffice Writer runs: pid $lo_pid $(exe_of "$lo_pid")"
  as_user hst-office --norestore --nologo --writer >/coexist/out/hst-writer.log 2>&1 &
  hst_pid="$(wait_window "$HST_ID-writer" 180)" || {
    fail "HST Writer window ($HST_ID-writer) did not appear while LibreOffice runs; windows: $(windows | tr '\n' ';')"; return; }
  if [ "$hst_pid" != "$lo_pid" ] && exe_of "$hst_pid" | grep -q '^/opt/hst-office'; then
    pass "HST Writer runs in its own process: pid $hst_pid $(exe_of "$hst_pid")"
  else fail "HST Writer window belongs to pid $hst_pid ($(exe_of "$hst_pid")), LibreOffice is $lo_pid"; fi
  # A second request to each suite must reach that suite's running process (its own pipe).
  as_user libreoffice --calc >/coexist/out/lo-calc.log 2>&1 || :
  as_user hst-office --calc >/coexist/out/hst-calc.log 2>&1 || :
  lo_calc="$(wait_window libreoffice-calc 120)" || lo_calc=none
  hst_calc="$(wait_window "$HST_ID-calc" 120)" || hst_calc=none
  if [ "$lo_calc" = "$lo_pid" ]; then pass "libreoffice --calc went to the running LibreOffice ($lo_pid)"
  else fail "libreoffice --calc window pid $lo_calc, LibreOffice is $lo_pid"; fi
  if [ "$hst_calc" = "$hst_pid" ]; then pass "hst-office --calc went to the running HST Office ($hst_pid)"
  else fail "hst-office --calc window pid $hst_calc, HST Office is $hst_pid"; fi
  local pid cls bad=0
  while read -r pid cls; do
    if [ "$pid" = "$hst_pid" ] && case "$cls" in libreoffice*|LibreOffice*) true ;; *) false ;; esac; then bad=1; fail "HST window with class $cls"; fi
    if [ "$pid" = "$lo_pid" ] && case "$cls" in hst*|HST*|vn.hasontech*) true ;; *) false ;; esac; then bad=1; fail "LibreOffice window with class $cls"; fi
  done < <(windows)
  [ "$bad" -eq 0 ] && pass "window classes: $(windows | sort -u | tr '\n' ';')"
  stop_offices
}

# start_alone <command> <class> <label>: the suite starts and shows its window with the other removed.
start_alone() {
  as_user "$1" --norestore --nologo --writer >"/coexist/out/$3.log" 2>&1 &
  local pid
  if pid="$(wait_window "$2" 180)"; then pass "$3: $1 starts (pid $pid)"; else fail "$3: $1 did not show a $2 window"; fi
  stop_offices
}

inner_main() {
  local deb="$1"
  export DEBIAN_FRONTEND=noninteractive
  log "== setup (image $(sed -n "s/^PRETTY_NAME=//p" /etc/os-release))"
  apt_quiet update >/dev/null
  apt_quiet install --no-install-recommends xvfb x11-utils xdg-utils libglib2.0-bin desktop-file-utils \
    shared-mime-info strace procps dbus-x11 >/coexist/out/apt-tools.log 2>&1 || { log "setup: tools"; return 2; }
  id "$USER_NAME" >/dev/null 2>&1 || useradd -m "$USER_NAME"
  apt_quiet install --no-install-recommends "${LO_PKGS[@]}" >/coexist/out/apt-lo.log 2>&1 || { log "setup: LibreOffice"; return 2; }
  log "LibreOffice: $(dpkg-query -W -f='${Version}' libreoffice-core)"
  defaults > /coexist/out/defaults-lo.txt; cat /coexist/out/defaults-lo.txt
  Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp >/coexist/out/xvfb.log 2>&1 &
  sleep 2

  log "== install HST Office next to LibreOffice"
  if apt_quiet install --no-install-recommends "$deb" >/coexist/out/apt-hst.log 2>&1; then pass "apt installs the HST .deb next to LibreOffice"
  else fail "apt could not install the HST .deb next to LibreOffice"; tail -20 /coexist/out/apt-hst.log; return 1; fi
  HST_ROOT="$(sed -n 's|^\(/opt/hst-office[0-9.]*\)/program/soffice$|\1|p' <<<"$(readlink -f /usr/bin/hst-office)")"
  [ -n "$HST_ROOT" ] || { log "setup: cannot find the HST install root"; return 2; }
  log "HST: $(dpkg-query -W -f='${Version}' hst-office) in $HST_ROOT"
  check_files
  check_defaults "after installing HST" /coexist/out/defaults-lo.txt

  log "== HST first start: LibreOffice/OpenOffice profiles are not read"
  # Profiles an upstream first start would migrate from (created as the user: ~/.config must stay theirs).
  as_user mkdir -p "/home/$USER_NAME/.config/libreoffice/3/user" "/home/$USER_NAME/.libreoffice/3/user"
  local trace=/tmp/hst-first-start.strace
  install -o "$USER_NAME" /dev/null "$trace"
  # A GUI first start: the profile migration of an upstream first start runs there, not headless.
  as_user strace -f -qq -e trace=%file -o "$trace" \
    hst-office --norestore --nologo --writer >/coexist/out/hst-first-start.log 2>&1 &
  local traced=$!
  wait_window "$HST_ID-writer" 180 >/dev/null || log "note: no $HST_ID-writer window during the traced first start"
  stop_offices
  wait "$traced" || :
  cp "$trace" /coexist/out/
  [ -s "$trace" ] || { log "setup: strace recorded nothing (see hst-first-start.log)"; return 2; }
  local touched
  touched="$(grep -oiE "/home/$USER_NAME/(\.config/)?\.?(libreoffice|openoffice|staroffice|starsuite)[^\"]*" "$trace" | sort -u || :)"
  if [ -z "$touched" ]; then pass "HST's first start does not touch ~/.config/libreoffice or other suites' profiles"
  else fail "HST's first start touches another suite's profile:"; echo "$touched" | head; fi
  if [ -d "/home/$USER_NAME/.config/hstoffice/4/user" ]; then pass "HST profile: ~/.config/hstoffice/4"; else fail "no HST profile in ~/.config/hstoffice/4"; fi

  log "== both running at once (Xvfb, GTK3)"
  run_both
  stop_offices   # also when run_both stopped early, so the next checks start each suite afresh
  if [ -d "/home/$USER_NAME/.config/libreoffice/4/user" ] && [ -d "/home/$USER_NAME/.config/hstoffice/4/user" ]; then
    pass "separate profiles: ~/.config/libreoffice/4 and ~/.config/hstoffice/4"
  else fail "expected both ~/.config/libreoffice/4 and ~/.config/hstoffice/4"; fi
  check_defaults "after running both" /coexist/out/defaults-lo.txt

  log "== remove HST: LibreOffice keeps working"
  apt_quiet purge hst-office >/coexist/out/apt-purge-hst.log 2>&1 || fail "apt purge hst-office"
  if [ ! -e "$HST_ROOT" ]; then pass "$HST_ROOT removed"; else fail "$HST_ROOT left behind"; fi
  check_defaults "after removing HST" /coexist/out/defaults-lo.txt
  start_alone libreoffice libreoffice-writer lo-after-hst-removal

  log "== reinstall HST, remove LibreOffice: HST keeps working"
  apt_quiet install --no-install-recommends "$deb" >/coexist/out/apt-hst2.log 2>&1 || fail "reinstall HST"
  apt_quiet purge "${LO_PKGS[@]}" libreoffice-core libreoffice-common >/coexist/out/apt-purge-lo.log 2>&1 || fail "apt purge LibreOffice"
  if dpkg -s hst-office >/dev/null 2>&1; then pass "hst-office still installed after LibreOffice removal"
  else fail "hst-office removed with LibreOffice"; fi
  start_alone hst-office "$HST_ID-writer" hst-after-lo-removal

  log "== result: $FAILS failed check(s)"
  [ "$FAILS" -eq 0 ]
}

if [ "${HST_COEXIST_INNER:-}" = 1 ]; then
  rc=0
  inner_main "$1" > >(tee /coexist/out/coexistence.log) 2>&1 || rc=$?
  pkill -x Xvfb 2>/dev/null || :
  sleep 1
  exit "$rc"
fi
host_main "$@"
