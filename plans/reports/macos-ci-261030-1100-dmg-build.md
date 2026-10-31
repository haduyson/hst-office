# macOS CI: unsigned HST Office dmg on GitHub-hosted runners

Date 2026-10-30. Workflow `.github/workflows/desktop-macos.yml` (inputs `mode=preflight|full`), matrix
arm64 `macos-15` and x86_64 `macos-15-intel`, plus an optional `sign` job.

## Result

- **arm64: green.** Run 41026070593 built, packaged and verified `HSTOffice_1.0.0_macOS_arm64.dmg`. The
  artifact is `hst-office-macos-arm64-dmg-41026070593`.
- **x86_64: does not fit in one 6 h job.** It reached 71 % of the compile steps in 305 min. A budget stop
  saves ccache, so it resumes in the next `full` run on the same commit. Expect 2, possibly 3, chained runs.
- Preflight green on both arches: run 41004543396.

## Runner probe (measured)

| | arm64 `macos-15` | x86_64 `macos-15-intel` |
|---|---|---|
| CPU / RAM | Apple M1 (Virtual), 3 vCPU / 7 GiB | i7-8700B, 4 vCPU / 14 GiB |
| OS / Xcode / SDK | macOS 15.7.9, Xcode 16.4, SDK 15.5 | same |
| Free disk | 41 GiB, 98 GiB after removing unused Xcodes, Android and dotnet (190–340 s) | 107 GiB (no cleanup needed) |

## Runs

| Run | Mode | Result / fix |
|---|---|---|
| 41001405876 | preflight | `msgfmt` missing → link gettext |
| 41002656088 | preflight | configure needs `ninja` (harfbuzz) → brew ninja; meson uses its internal copy |
| 41003854419 | preflight | Intel: `msguniq` missing → link it (cancelled) |
| 41004543396 | preflight | **green both** (about 9–11 min) |
| 41005620641 | full | HST make rule used `$(SRCDIR)/../..` → export `HST_REPO_ROOT` |
| 41006981059 | full | liblangtag needs `pkg-config` → brew pkgconf with an empty `PKG_CONFIG_LIBDIR`, plus `libtoolize` (cancelled) |
| 41009123489 | full | configure rejects a "bogus" pkg-config → `--enable-bogus-pkg-config` (safe: the search path is empty) (cancelled) |
| 41009863968 | full | arm64 compile complete (8607 s), but dmg packaging failed on the space in "HST Office". Fixed by new `hst-packaging-macos-dmg.patch` plus merging the vi language pack. Intel cancelled at 8390 steps. |
| 41026070593 | full | **arm64 success**; Intel budget stop at 12 677 steps |

## Timings (run 41026070593, seconds)

| phase | arm64 | x86_64 |
|---|---|---|
| probe / free-disk / tools | 4 / 341 / 8 | 7 / 0 / 9 |
| extract / patch / configure / fetch | 96 / 31 / 44 / 205 | 147 / 108 / 81 / 235 |
| build (make) | 9934 ok (17 830 steps) | 18 339 budget-stop (12 677 steps, last `dbaccess/...`) |
| collect (+ dmgbuild) / verify | 50 / 1 | failed (no dmg) |
| job total | 3 h 01 min | about 5 h 20 min |

- Peaks: arm64 used at most 4.7 GiB RAM, no swap, and never dropped below 82 GiB free. x86_64 used at most
  8.0 GiB RAM, no swap, and never dropped below 91 GiB free.
- Projected x86_64 compile time is about 430–590 min, so it needs two or more jobs. On the arm64 time
  profile Intel runs 3.3x slower.
- ccache hit rates were 3.6 % (run 4) and 11 % (arm64 run 5). Commits between runs changed
  `officecfg/.../Common.xcs` (document tabs patch), and its generated headers are included almost everywhere.
  Hits are expected to be high on an unchanged tree.
- Cache sizes: arm64 1.05 GiB, x86_64 350 MiB.

## Artifact (arm64)

- `hst-office-macos-arm64-dmg-41026070593`: `HSTOffice_1.0.0_macOS_arm64.dmg`, 279 610 011 bytes, sha256
  `4993ab2cd3ff1b3a582762f2a1ece53bf49715ae72034cd70baea632b65b9bbf`. Downloaded here and
  `sha256sum -c SHA256SUMS` returned OK. The upstream main dmg was 282.7 MB and the vi language pack 1.0 MB.
- Inspection was done on the runner by the `--verify` step (mounted with `hdiutil`), because 7-Zip could not
  be installed locally:
  - volume `HST Office` holds `HST Office.app`, `Applications`, `.background.tiff`, `.VolumeIcon.icns` and `.DS_Store`;
  - `CFBundleName=HST Office`, `CFBundleIdentifier=vn.hasontech.hstoffice`, version 1.0.0, `LSMinimumSystemVersion=11.0.0`;
  - `soffice` is arm64;
  - `Resources/resource/vi` holds 32 `.mo` catalogs, and `vi.lproj` is present;
  - `NSHumanReadableCopyright` is exactly the HST line, with no "All rights reserved";
  - `main.icns`, `oasis-text.icns` and `generic-spreadsheet.icns` are byte-identical to the HST build output.
    I extracted them to PNG (evidence `macos-build-arm64-41026070593`) and checked them visually: they are
    the HST Tile icons.

## What changed

- `scripts/macos/trial-build.sh` runs the phases probe, free-disk, tools, extract, patch, configure, fetch,
  build, collect and verify.
  - It uses a minimal PATH: only the needed Homebrew tools are symlinked into `~/hst/bin`.
  - Configs are `build-config/macos-{arm64,x86_64}.conf`, with no `--host` and no `--with-package-version`.
    The version comes from `/VERSION`, as in `openoffice.lst` and the `CFBundle*Version` keys.
- `scripts/macos/{summarize-build.py,preflight-local.sh}` added. `preflight-local.sh` runs inside `ci-quality.sh`.
  `fetch-sources.py` is reused from `scripts/windows/` without editing it.
- Branding:
  - `stage-macos-icons.py` replaces the app iconset and all 26 document iconsets from the HST masters:
    Writer, Sheets, Slides, Draw, Math and Base each get their own module, extensions get HST Office.
    `scripts/brand/apply-icon-overrides.py` is applied too.
  - Per-module `branding/macos/hst-*.icns` files are not needed: Info.plist references the `oasis-*`/`generic-*`
    icns that are built from these iconsets, from the same generator PNGs.
- dmg:
  - `build-dmg.sh` and `dmg-settings.py` (dmgbuild 1.6.7, pinned) build the image: HST background 550x442 plus
    @2x (`make-dmg-background.py`, Vietnamese text "Kéo HST Office vào thư mục Applications…"), HST volume
    icon, icon positions, volume name "HST Office".
  - There is no SLA/licence dialog: upstream's Rez/unflatten path is inert as well.
  - Upstream ships only en-US in the main macOS installer, so the vi language pack is merged into the app the
    same way its installer would, and the bundle is renamed `HST Office.app`.
- `patches/libreoffice/hst-packaging-macos-dmg.patch` (appended to `series`) quotes the hdiutil paths and uses
  the PRODUCTNAME_WITHOUT_SPACES bundle name for language packs. It touches only the macOS dmg branch of
  `simplepackage.pm`; deb, msi and archive packaging are unchanged.
- `scripts/check-workflows.py` and its tests:
  - The macOS stub rules were replaced, `BLOCKER` was removed, and new pins were verified via `gh api`:
    `actions/cache/{restore,save}` 0057852 (v4.3.0) and `actions/download-artifact` d3f86a1 (v4.3.0).
  - Secrets and environments are allowed only in the `sign` job, at the `gate` step or in gated steps.
  - A job-level `if` is allowed only on `sign` (full mode).
- Signing (optional):
  - The `sign` job runs in environment `macos-signing` and skips cleanly without secrets.
  - It uses a temporary keychain, deleted with `if: always()`.
  - It signs with upstream `solenv/bin/macosx-codesign-app-bundle` plus the configure-generated
    `hardened_runtime.xcent` and launch constraint. That is what `--enable-macosx-code-signing` runs, kept out
    of the build job so no secrets enter it.
  - It then rebuilds the dmg, signs it, runs `notarytool --wait`, staples, and checks with `spctl` and
    `codesign --verify --deep --strict`.
  - Not exercised yet: no secrets are configured.
- `docs/CI.md` has a macOS section with the secret names, the Gatekeeper workaround and the measurements.

## Gatekeeper (unsigned)

The dmg is unsigned. Gatekeeper reports "HST Office is damaged" on Apple Silicon (linker ad-hoc signature, no
Developer ID) or "unidentified developer" on Intel. To open it, a tester:

1. drags the app to Applications;
2. right-clicks it and chooses Open (on macOS 15: System Settings → Privacy & Security → Open Anyway), or runs
   `xattr -dr com.apple.quarantine "/Applications/HST Office.app"`.

Shipping to users requires the `sign` job with secrets.

## Recommendation for x86_64

1. Simplest: after the final commit, run `desktop-macos.yml mode=full` twice. The first run warms the Intel
   ccache (the arm64 leg is already green); the second finishes Intel. The release needs both arm64 and
   x86_64 artifacts from a successful run on that commit.
2. Better: cross-compile x86_64 on the arm64 runner (`--host=x86_64-apple-macos`, Rosetta for build tools),
   which is likely about 3–3.5 h. Untested.
3. Alternatives:
   - a larger Intel runner (`macos-15-large`, 12 vCPU, paid per minute, roughly $0.08–0.12/min, price not
     verified);
   - a self-hosted Mac.

## Unresolved questions

- Does the controller's single final run need the Intel dmg? If so, run `full` twice on the final commit, or
  approve the cross-compile experiment.
- The signing path is untested until the owner adds the 7 secrets and creates the `macos-signing` environment
  (with optional reviewers).
- The default UI language follows macOS. Vietnamese appears only when Vietnamese is a preferred macOS
  language; owner intent says menus follow the OS, so this is OK.
- The app was not launched (no GUI on the runner): the GUI and first-start check remain for QA on a real Mac.

## Update 2026-10-31: beta.2 "HST Office is damaged" on Apple Silicon

- **Root cause (proved by CI on the released beta.2 arm64 dmg).** Probe runs 41161683389 and 41161906665
  used `.github/workflows/macos-signature-probe.yml` on macOS 15.8.2 arm64, dmg sha256 `02514d73…0295`.
  - The shipped `HST Office.app` and `Contents/MacOS/soffice` are only linker-signed
    (`flags=0x20002(adhoc,linker-signed)`, `Info.plist=not bound`, `Sealed Resources=none`).
  - `codesign --verify --deep --strict`, `spctl --assess` and `syspolicy_check` all fail with "code has no
    resources but signature indicates they must be present". `LibreOfficePython.framework` fails the same way.
  - Cause: an upstream release build without a signing identity never signs the bundle, and HST then edits it
    (vi language pack, icons, Info.plist). With quarantine set, macOS reports this as "damaged".
- **Fix (9de2f56).** `scripts/macos/adhoc-sign.sh` signs inside-out like `macosx-codesign-app-bundle`:
  254 Mach-O files, then 5 nested bundles (Python.framework per version, QuickLook appex, Spotlight
  mdimporter), then the app with identifier `vn.hasontech.hstoffice`.
  - It has no hardened runtime and no entitlements; `sign-notarize.sh` re-signs everything with `--force`
    for Developer ID.
  - `trial-build.sh --collect` runs it after the last bundle change, before `build-dmg.sh`. The build fails
    if `codesign --verify --deep --strict` fails.
  - `--verify` re-checks the mounted dmg (hard gate) and records `spctl` output.
- **Verified on the beta.2 bundle after re-sign:**
  - `codesign --verify --deep --strict`: "valid on disk / satisfies its Designated Requirement".
  - `spctl --assess --type execute -vv`: "rejected" (exit 3, unnotarized), the same with a simulated Safari
    quarantine flag.
  - `syspolicy_check distribution`: only "Notary Ticket Missing" plus a generic XProtect distribution note;
    the codesign error is gone.
  - Headless conversion `soffice --headless --convert-to pdf` works (exit 0, 13 872-byte PDF).
- **Docs:** `docs/CI.md` and `docs/releases/v1.0.0-beta.3.md` ("Cài đặt" macOS) now give the macOS 15 steps
  Xong → Cài đặt hệ thống ▸ Quyền riêng tư & Bảo mật ▸ Vẫn mở, plus the `xattr -dr com.apple.quarantine`
  fallback.
- **Not run:** no full `desktop-macos` build was started. The beta.3 builds will exercise the new gate.

## Update 2026-10-31: Developer ID signing and notarization proven

- **Probe 41164931911.**
  - Signing passed: 254 Mach-O files, all timestamped Developer ID with hardened runtime.
  - The entitlements are apple-events, allow-jit, disable-executable-page-protection,
    disable-library-validation and addressbook, with no get-task-allow.
  - `notarytool` returned HTTP 401.
  - Fixed in 801dc97: no `--team-id` with API-key auth, a key self-check (`notarytool history`) right after
    import, the key accepted as PEM or base64, and empty results parsed safely.
- **Probe 41165430268 (green).** On the beta.2 arm64 app with the ad-hoc fix:
  - notarization is `Accepted` (submission f272ba96-d66f-4160-86bc-35f8ee20573e);
  - staple and validate pass;
  - `spctl -a -t open --context context:primary-signature` on the dmg gives accepted, Notarized Developer ID;
  - the app inside passes `codesign --verify --deep --strict`, and `spctl -a -t exec` gives accepted,
    Notarized Developer ID;
  - the temporary keychain was deleted.
- **Artifact:** `macos-signing-probe-arm64-dmg-signed-41165430268` (3 days), dmg sha256 `4a501bb8…7cd20`.
- **Other signing fixes (0749c6d):**
  - The launch constraint is filled with the real team id at signing time (an unsigned configure leaves it
    empty).
  - Every Mach-O is pre-signed before upstream's pass.
  - Signing happens under a space-free bundle name, because upstream's script leaves paths unquoted.
  - Every Mach-O is checked for a timestamped Developer ID signature before submission.
