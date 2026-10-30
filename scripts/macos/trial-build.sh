#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# HST Office macOS build on a GitHub-hosted runner (see .github/workflows/desktop-macos.yml).
#   trial-build.sh --probe | --free-disk | --tools | --extract | --options | --patch | --configure | --fetch | --build | --collect | --verify
# Env: HST_ARCH (arm64|x86_64, must match the host), HST_REPO (checkout), HST_WORK (default
# $HOME/hst), HST_DL (pinned tarballs), HST_PYTHON (python3 with Pillow), HST_BUILD_DEADLINE
# (epoch seconds; --build stops make cleanly then and returns 0 with status budget-stop).
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
PS4='+ [${BASH_SOURCE##*/}:${LINENO}] '
set -x
ARCH="${HST_ARCH:?HST_ARCH must be arm64 or x86_64}"
REPO="${HST_REPO:?HST_REPO must point at the repository checkout}"
WORK="${HST_WORK:-$HOME/hst}"
SRC="$WORK/lo"; LOGS="$WORK/logs"; METRICS="$WORK/metrics"; DL="${HST_DL:-$WORK/dl}"
CONF="$REPO/build-config/macos-$ARCH.conf"
LO_VERSION=26.8.1.1
case "$ARCH" in arm64|x86_64) ;; *) echo "unsupported HST_ARCH $ARCH"; exit 64 ;; esac
PY="${HST_PYTHON:-$(command -v python3)}"
BREW="${HST_BREW:-$(command -v brew || true)}"
eval "$("$PY" "$REPO/scripts/write-hst-version.py" --env)"
export HST_VERSION HST_VERSION_MAJOR HST_VERSION_MINOR HST_VERSION_MICRO
mkdir -p "$LOGS" "$METRICS" "$WORK/bin"
# Minimal PATH: only the tools linked into $WORK/bin plus the base system. Keeps Homebrew's
# libraries, pkg-config and headers out of configure and the bundled external builds.
if [ -z "${HST_KEEP_PATH:-}" ]; then
  export PATH="$WORK/bin:/usr/bin:/bin:/usr/sbin:/sbin"
fi
unset PKG_CONFIG_PATH CPATH LIBRARY_PATH
export CCACHE_DIR="$WORK/ccache" CCACHE_BASEDIR="$WORK" CCACHE_MAXSIZE="${HST_CCACHE_MAXSIZE:-5G}"
export CCACHE_COMPRESS=1 CCACHE_SLOPPINESS="include_file_mtime,include_file_ctime,time_macros"
# Only gb_ variables of a tarball tree: no git submodules to fetch (see the Windows trial).
LO_MAKE=(make GIT_NEEDED_SUBMODULES=)

free_gib() { df -Pk "$WORK" | awk 'END { printf "%d", $4 / 1048576 }'; }

phase() { # phase <name> <command...>: run, time and record in phases.jsonl; propagate failure
  local name="$1" start rc=0 status; shift; start=$(date +%s)
  "$@" || rc=$?
  [ "$rc" -eq 0 ] || echo "FAILED phase $name: exit $rc" >&2
  status=ok; [ "$rc" -eq 0 ] || status="failed($rc)"
  [ "$rc" -ne 0 ] || [ "${BUDGET_STOPPED:-0}" -eq 0 ] || status=budget-stop
  printf '{"phase":"%s","seconds":%d,"status":"%s","free_gib":%s}\n' "$name" $(( $(date +%s) - start )) "$status" \
    "$(free_gib)" >> "$METRICS/phases.jsonl"
  return "$rc"
}

do_probe() { # runner facts for the evidence artifact: CPU, RAM, disk, OS, Xcode/SDK
  sw_vers; uname -a
  echo "cpu: $(sysctl -n machdep.cpu.brand_string) ncpu=$(sysctl -n hw.ncpu) perflevel0=$(sysctl -n hw.perflevel0.physicalcpu 2>/dev/null || echo n/a)"
  echo "ram_gib: $(( $(sysctl -n hw.memsize) / 1073741824 ))"
  echo "swap: $(sysctl -n vm.swapusage)"
  df -h / "$HOME"
  echo "free_gib_work: $(free_gib)"
  echo "xcode-select: $(xcode-select -p)"
  xcodebuild -version
  echo "sdk: $(xcrun --sdk macosx --show-sdk-version) $(xcrun --sdk macosx --show-sdk-path)"
  echo "clang: $(xcrun clang --version | head -1)"
  find /Applications -maxdepth 1 -name 'Xcode*' | sort
  if [ -n "$BREW" ]; then "$BREW" --version | head -1; else echo "brew: not found"; fi
}

do_free_disk() { # drop unused toolchains from the ephemeral runner image (not the selected Xcode)
  local before keep x
  before=$(free_gib)
  # Removing toolchains takes minutes (7 on Intel); skip when the image already has room.
  if [ "$before" -ge "${HST_MIN_FREE_GIB:-80}" ]; then echo "free disk: ${before} GiB, nothing removed"; return 0; fi
  keep="$(xcode-select -p)"; keep="$(cd "${keep%/Contents/Developer}" && pwd -P)"
  for x in /Applications/Xcode*.app; do
    [ -L "$x" ] && continue
    [ "$(cd "$x" && pwd -P)" = "$keep" ] && continue
    echo "removing $x"; sudo rm -rf "$x" || return 1
  done
  sudo rm -rf "$HOME/Library/Android" /usr/local/share/dotnet "$HOME/.dotnet" || return 1
  echo "free disk: ${before} GiB -> $(free_gib) GiB (kept $keep)"
}

BREW_TOOLS=(autoconf automake bison gperf nasm gpatch make ccache gettext ninja)

do_brew() { # install the build tools; retried because the Homebrew CDN has transient failures
  local attempt
  for attempt in 1 2 3; do
    HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1 \
      "$BREW" install --quiet "${BREW_TOOLS[@]}" && return 0
    echo "brew install attempt $attempt failed"; sleep $(( attempt * 30 ))
  done
  return 1
}

link_tool() { # link_tool <name-in-bin> <absolute target>
  [ -x "$2" ] || { echo "MISSING tool: $2"; return 1; }
  ln -sf "$2" "$WORK/bin/$1"
}

do_tools() { # link the Homebrew tools configure needs, then report versions
  [ "$(uname -s)" = Darwin ] || { echo "requires macOS"; return 1; }
  [ "$(uname -m)" = "$ARCH" ] || { echo "host is $(uname -m), expected native $ARCH"; return 1; }
  [ -n "$BREW" ] || { echo "MISSING brew"; return 1; }
  do_brew || return 1
  local bad=0 tool prefix
  prefix="$("$BREW" --prefix)"
  # No meson: configure then uses its internal copy with the build python (Homebrew meson needs Homebrew python).
  for tool in autoconf autoheader autom4te autoreconf aclocal automake gperf nasm ccache ninja; do
    link_tool "$tool" "$prefix/bin/$tool" || bad=1
  done
  link_tool bison "$("$BREW" --prefix bison)/bin/bison" || bad=1  # system bison 2.3 is too old
  link_tool make "$("$BREW" --prefix make)/bin/gmake" || bad=1    # configure needs GNU make >= 4.2
  link_tool patch "$("$BREW" --prefix gpatch)/bin/gpatch" || bad=1  # Apple patch is rejected
  link_tool msgfmt "$("$BREW" --prefix gettext)/bin/msgfmt" || bad=1  # scripts/l10n checks .po files
  link_tool python3 "$PY" || bad=1
  for tool in make bison gperf nasm patch autoconf automake ccache ninja msgfmt flex perl python3; do
    if command -v "$tool" >/dev/null; then echo "$tool: $(command -v "$tool") $("$tool" --version 2>&1 | head -1)"; else echo "MISSING tool: $tool"; bad=1; fi
  done
  for tool in xcodebuild xcrun clang hdiutil iconutil plutil zip unzip curl; do
    command -v "$tool" >/dev/null || { echo "MISSING tool: $tool"; bad=1; }
  done
  xcodebuild -version
  echo "macOS SDK $(xcrun --sdk macosx --show-sdk-version) at $(xcrun --sdk macosx --show-sdk-path)"
  return "$bad"
}

extract_one() { # extract_one <tarball> <dest>; all three tarballs share one top-level libreoffice-<ver>/ root
  mkdir -p "$2"; tar -xf "$DL/$1" -C "$2" --strip-components=1
}

do_extract() {
  echo "extract: main source"; extract_one "libreoffice-$LO_VERSION.tar.xz" "$SRC" || return 1
  rm -rf "$SRC/translations" "$SRC/dictionaries"
  echo "extract: translations"; extract_one "libreoffice-translations-$LO_VERSION.tar.xz" "$SRC" || return 1
  echo "extract: dictionaries"; extract_one "libreoffice-dictionaries-$LO_VERSION.tar.xz" "$SRC" || return 1
  [ -f "$SRC/configure.ac" ] || { echo "extract: configure.ac missing"; return 1; }
  [ -d "$SRC/translations/source/vi" ] || { echo "extract: vi translations missing"; return 1; }
  echo "extract: ok"
}

do_patch() {
  HST_LO_SRC="$SRC" bash "$REPO/scripts/apply-patches.sh" || return 1
  # Same Vietnamese overlay + overrides as the Linux and Windows builds (both idempotent).
  "$PY" -B "$REPO/scripts/l10n/merge-vi.py" --apply --tree "$SRC" || return 1
  "$PY" -B "$REPO/scripts/l10n/apply-overrides.py" --tree "$SRC" || return 1
  # Dock/Finder icon (main.icns) from the HST artwork instead of the LibreOffice icon.
  "$PY" -I "$REPO/scripts/macos/stage-app-icon.py" --tree "$SRC" || return 1
}

options() { # configure options with the branding placeholder resolved
  grep -v '^[[:space:]]*#' "$CONF" | grep -v '^[[:space:]]*$' | sed "s|@BRANDING@|$WORK/branding|"
}

do_options() { # validate every option against the pinned configure.ac, then write autogen.input
  local opt base
  while IFS= read -r opt; do
    base="${opt%%=*}"; base="${base#--}"; base="${base#with-}"; base="${base#without-}"; base="${base#enable-}"; base="${base#disable-}"
    grep -qE "(AC_ARG_(WITH|ENABLE)|libo_FUZZ_ARG_(WITH|ENABLE))\($base," "$SRC/configure.ac" || { echo "unknown configure option: $opt"; return 3; }
  done < <(options)
  options > "$SRC/autogen.input" || return 1
  cat "$SRC/autogen.input"
}

fill_version() { # fill_version <file>: HST release version into the configure-generated product list
  perl -pi -e "s/\@HST_VERSION_MAJOR\@/$HST_VERSION_MAJOR/g; s/\@HST_VERSION_MINOR\@/$HST_VERSION_MINOR/g; s/\@HST_VERSION_MICRO\@/$HST_VERSION_MICRO/g" "$1" || return 1
  if grep -q '@HST_VERSION' "$1"; then echo "configure: HST version placeholders left in $1"; return 1; fi
}

do_configure() {
  test -f "$WORK/branding/staging-manifest.json" || { echo "branding not staged"; return 2; }
  do_options || return $?
  (cd "$SRC" && ./autogen.sh) 2>&1 | tee "$LOGS/configure.log"
  test "${PIPESTATUS[0]}" -eq 0 || return 1
  # Same HST version wiring as scripts/build-linux.sh prepare_version.
  "$PY" "$REPO/scripts/write-hst-version.py" --header "$SRC/include/hst_version.h" || return 1
  fill_version "$SRC/instsetoo_native/util/openoffice.lst" || return 1
  # Finder "Get Info" shows CFBundleShortVersionString: the HST release, not the engine version.
  local plist="$SRC/sysui/desktop/macosx/Info.plist"
  plutil -replace CFBundleShortVersionString -string "$HST_VERSION" "$plist" || return 1
  plutil -replace CFBundleVersion -string "$HST_VERSION" "$plist" || return 1
  plutil -lint "$plist" || return 1
  grep -q 'vn.hasontech.hstoffice' "$plist" || { echo "configure: bundle identifier not in Info.plist"; return 1; }
  grep -E '^export (ENABLE_RELEASE_BUILD|MACOSX_BUNDLE_IDENTIFIER|MACOSX_DEPLOYMENT_TARGET|MACOSX_SDK_VERSION|PRODUCTNAME|CCACHE|PARALLELISM)=' "$SRC/config_host.mk" || true
}

do_fetch() { # download every external tarball (sha256-checked by gbuild) so preflight covers make's fetch stage
  mkdir -p "$SRC/external/tarballs" || return 1
  cp -n "$DL/libreoffice-translations-$LO_VERSION.tar.xz" "$DL/libreoffice-dictionaries-$LO_VERSION.tar.xz" \
    "$SRC/external/tarballs/" || return 1
  (cd "$SRC" && "${LO_MAKE[@]}" fetch) 2>&1 | tee "$LOGS/fetch.log"
  local rc=${PIPESTATUS[0]}
  [ "$rc" -eq 0 ] || return "$rc"
  if grep -q 'Saving to: .*libreoffice-\(translations\|dictionaries\)-' "$LOGS/fetch.log"; then
    echo "fetch: make tried to re-download translations/dictionaries tarballs"; return 1
  fi
  (cd "$SRC" && "${LO_MAKE[@]}" showmodules) > "$LOGS/showmodules.log" 2>&1
}

sample() { # one progress sample: steps compiled, free disk, memory used, swap used
  local steps page mem_total pages used swap
  steps=$(grep -c '^\[build ' "$LOGS/build.log" 2>/dev/null || true)
  page=$(sysctl -n hw.pagesize); mem_total=$(sysctl -n hw.memsize)
  # used = total - (free + inactive + speculative + purgeable) pages
  pages=$(vm_stat | awk -F: '/Pages (free|inactive|speculative|purgeable)/ { gsub(/[ .]/, "", $2); s += $2 } END { print s + 0 }')
  used=$(awk -v t="$mem_total" -v p="$pages" -v ps="$page" 'BEGIN { printf "%.1f", (t - p * ps) / 1073741824 }')
  swap=$(sysctl -n vm.swapusage | awk '{ for (i = 1; i <= NF; i++) if ($i == "used") { v = $(i + 2); sub(/M$/, "", v); printf "%.1f", v / 1024 } }')
  printf '{"t":%d,"steps":%s,"free_gib":%s,"mem_used_gib":%s,"swap_used_gib":%s}\n' "$(date +%s)" "${steps:-0}" "$(free_gib)" \
    "$used" "${swap:-0}" >> "$METRICS/progress.jsonl"
}

do_build() {
  local deadline="${HST_BUILD_DEADLINE:?HST_BUILD_DEADLINE required}" pid rc=0
  BUDGET_STOPPED=0; : > "$LOGS/build.log"
  ccache -z || return 1
  (cd "$SRC" && exec "${LO_MAKE[@]}") > "$LOGS/build.log" 2>&1 &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    sleep 60; sample
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "budget reached: stopping make cleanly" | tee -a "$LOGS/build.log"
      BUDGET_STOPPED=1
      kill -TERM "$pid" 2>/dev/null || true; sleep 20
      pkill -TERM -f "$SRC" 2>/dev/null || true  # compilers and tools of this build tree only
      break
    fi
  done
  wait "$pid" || rc=$?
  sample
  ccache -s > "$LOGS/ccache-stats.txt" 2>&1 || true
  if [ "$BUDGET_STOPPED" -eq 1 ]; then return 0; fi
  return "$rc"
}

dmg_name() { printf 'HSTOffice_%s_macOS_%s.dmg' "$HST_VERSION" "$ARCH"; }

do_collect() { # the single HST Office dmg -> $WORK/dmg with SHA256SUMS; signing inputs -> evidence
  local inst="$SRC/workdir/installation/HSTOffice/dmg/install" out="$WORK/dmg" kit="$WORK/artifacts/signing-kit"
  if find "$SRC/workdir/installation" -maxdepth 4 -name '*_witherror' | grep -q .; then
    echo "collect: installer reported errors"; return 1
  fi
  local found=()
  while IFS= read -r f; do found+=("$f"); done < <(find "$inst" -name '*.dmg' -not -iname '*languagepack*' -not -iname '*helppack*')
  [ "${#found[@]}" -eq 1 ] || { echo "collect: expected one dmg under $inst, found ${#found[@]}: ${found[*]-}"; return 1; }
  rm -rf "$out"; mkdir -p "$out"
  cp "${found[0]}" "$out/$(dmg_name)" || return 1
  (cd "$out" && shasum -a 256 "$(dmg_name)" > SHA256SUMS) || return 1
  cat "$out/SHA256SUMS"
  # Upstream's signing script and the entitlement files generated by this configure, so the
  # gated signing job signs exactly like an upstream --enable-macosx-code-signing build.
  rm -rf "$kit"; mkdir -p "$kit/build/sysui/desktop/macosx" "$kit/src/sysui/desktop/macosx"
  cp "$SRC/solenv/bin/macosx-codesign-app-bundle" "$kit/" || return 1
  cp "$SRC/hardened_runtime.xcent" "$kit/build/" || return 1
  cp "$SRC/sysui/desktop/macosx/LaunchConstraint.plist" "$kit/build/sysui/desktop/macosx/" || return 1
  cp "$SRC/sysui/desktop/macosx/quicklookappex.entitlements" "$kit/src/sysui/desktop/macosx/" || return 1
}

do_verify() { # mount the dmg read-only and check product identity and Vietnamese resources
  # Checks run in a piped subshell: a failure is recorded as a "FAIL:" line in the report.
  local dmg mnt="$WORK/mnt" app plist bad=0 report="$WORK/artifacts/dmg-verify.txt"
  dmg="$WORK/dmg/$(dmg_name)"
  mkdir -p "$WORK/artifacts"
  rm -rf "$mnt"; mkdir -p "$mnt"
  hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" || return 1
  {
    echo "dmg: $(dmg_name) $(wc -c < "$dmg") bytes"
    echo "volume:"; ls -la "$mnt"
    app="$mnt/HST Office.app"; plist="$app/Contents/Info.plist"
    if [ -d "$app" ]; then echo "app: HST Office.app"; else echo "FAIL: HST Office.app missing"; bad=1; fi
    for key in CFBundleName CFBundleIdentifier CFBundleShortVersionString CFBundleVersion LSMinimumSystemVersion CFBundleIconFile; do
      echo "$key=$(/usr/libexec/PlistBuddy -c "Print :$key" "$plist" 2>&1)"
    done
    [ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$plist")" = vn.hasontech.hstoffice ] || { echo "FAIL: bundle id"; bad=1; }
    [ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleName' "$plist")" = "HST Office" ] || { echo "FAIL: bundle name"; bad=1; }
    echo "architectures: $(lipo -archs "$app/Contents/MacOS/soffice")"
    lipo -archs "$app/Contents/MacOS/soffice" | grep -qw "$ARCH" || { echo "FAIL: soffice is not $ARCH"; bad=1; }
    echo "vi resources:"; find "$app/Contents/Resources" -maxdepth 3 \( -path '*/resource/vi' -o -name 'vi.lproj' \) | head -20
    find "$app/Contents/Resources/resource/vi/LC_MESSAGES" -name '*.mo' 2>/dev/null | wc -l | sed 's/^ */vi .mo catalogs: /'
    find "$app/Contents/Resources" -path '*/resource/vi/LC_MESSAGES/*.mo' | grep -q . || { echo "FAIL: no Vietnamese UI catalogs"; bad=1; }
    echo "codesign (unsigned build, informational):"; codesign -dv "$app" 2>&1 | head -5 || true
    du -sh "$app"
  } 2>&1 | tee "$report"
  [ "${PIPESTATUS[0]}" -eq 0 ] || bad=1
  grep -q '^FAIL' "$report" && bad=1
  hdiutil detach "$mnt" || return 1
  return "$bad"
}

case "${1:-}" in
  --probe) phase probe do_probe 2>&1 | tee "$LOGS/runner-probe.txt"; exit "${PIPESTATUS[0]}" ;;
  --free-disk) phase free-disk do_free_disk 2>&1 | tee "$LOGS/free-disk.txt"; exit "${PIPESTATUS[0]}" ;;
  --tools) phase tools do_tools 2>&1 | tee "$LOGS/tools.log"; exit "${PIPESTATUS[0]}" ;;
  --extract) phase extract do_extract 2>&1 | tee "$LOGS/extract.log"; exit "${PIPESTATUS[0]}" ;;
  --options) phase options do_options ;;
  --patch) phase patch do_patch 2>&1 | tee "$LOGS/patch.log"; exit "${PIPESTATUS[0]}" ;;
  --configure) phase configure do_configure ;;
  --fetch) phase fetch do_fetch ;;
  --build) phase build do_build ;;
  --collect) phase collect do_collect ;;
  --verify) phase verify do_verify ;;
  *) echo "usage: $0 --probe|--free-disk|--tools|--extract|--options|--patch|--configure|--fetch|--build|--collect|--verify"; exit 64 ;;
esac
