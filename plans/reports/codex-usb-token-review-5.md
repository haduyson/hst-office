# USB Token setup: independent review, round 5

Review date: 2026-10-31. Branch: `codex/usb-token`. Reviewed commit: `d0bfc6f5a96009efdae72abf7b78df1c5ff39e77` (`fix(usb-token): isolate migrated stores and honor environment pins`). Before revision: `2f3d183`. Scope: the complete 13-file diff, production dependencies, all four earlier reports, and fresh unit, native NSS, real HST/UNO, SoftHSM signing and quality execution.

**Verdict: SHIP. Open findings: 0 blocker, 0 major, 0 minor, 0 nit.** R4-M1 and R4-M2 are fixed in the before/after experiments below. No new product regression was found. Required suites pass; the one known upstream-dictionary unit skip is non-blocking under this review's explicit instructions.

Only this report is committed. No product or supplied test code was modified. `/opt/hst` stayed mounted read-only. The baseline was exported with `git archive` into `/tmp/usb-review-5-before`; both OXTs were built from their respective trees. Native probes and runtime checks ran as uid 2000 (`codex`) with disposable HOME, profiles and token stores. Full unit discovery and quality ran as root, followed by the entire USB subset as uid 2000. NSS tools: `2:3.98-1ubuntu0.3`; SoftHSM: `2.6.1-2.2ubuntu3`. No dependencies were downloaded.

## Findings by severity

| Severity | Open findings |
| --- | ---: |
| Blocker | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

## R4-M1: internal parameters bound to the old database — fixed

Relevant locations under `extensions/hst-vietnamese-tools/python/hst_office/`: `usb_token_binding.py:63`, `:89`; `usb_token_store.py:101`–`:103`.

The same reviewer-authored `core-compare.py` ran against the rebuilt baseline and reviewed OXTs. Each case creates a real SQL Firefox store with internal, Builtin Roots and another vendor record. The quoted case changes only the outer quoting of the internal `parameters=` value. HST loads that source successfully before setup. The script records CertDir, NSSPath, actual `/proc/<soffice-pid>/fd` SQL paths, dialogs and source manifests, fully restarts HST, then imports a disposable sentinel certificate using native `certutil -A -d sql:<new-store>`.

| Case, each in modutil and pkcs11 modes | Before: `2f3d183` | After: `d0bfc6f` |
| --- | --- | --- |
| Quoted internal parameters | Setup claims migration success. After restart NSSPath names the new store, but both open SQL descriptors point into the old Firefox store. An import addressed to the new store appears in the old store and changes its SQL hashes. **2/2 historical failures reproduced.** | Both descriptors point exclusively to the new store's `cert9.db` and `key4.db`. The sentinel appears only in the new store. Complete old manifests remain equal, including file bytes, modes and uid. Repeat setup after restart reports existing registration without another restart instruction. **2/2 fixed.** |
| Ordinary unquoted internal parameters | Both source-preserving control cases work. | Both controls still work, including exact SQL paths and isolated imports. **2/2 passed.** |

Concrete modutil evidence, relative to each case's `office/home`:

```text
before-modutil-quoted, after restart:
  NSSPath: Library/Application Support/HST Office/nssdb
  open SQL: .mozilla/firefox/default/{cert9.db,key4.db}
  sentinel listed in old/new stores: true / true

after-modutil-quoted, after restart:
  NSSPath: Library/Application Support/HST Office/nssdb
  open SQL: Library/Application Support/HST Office/nssdb/{cert9.db,key4.db}
  sentinel listed in old/new stores: false / true
```

The baseline source `cert9.db` changes from `e6e6ef70e28faeca5218504070dd14f8edf72b52131291523906a23a9c8ebfe0` to `3cedf9866589de197d7be969de2cd97ae1fbcc04b5f8b7cfcda04a5cae4d5b31` after the import. The reviewed fixture's source stays `e6e6ef70e28faeca5218504070dd14f8edf72b52131291523906a23a9c8ebfe0` before and after. Its `key4.db` stays `b855221e5629a3c58016875b971edcf624252bbec7b3e5ece481dd4c9b8f7d22`. These are comparisons within each fixture; setup itself leaves the baseline source unchanged until later use/import.

The native binding tests additionally execute **28 migration/import combinations**: two modes × two outer forms × seven inner forms. They exercise nonempty certificate/key prefixes, reset destination prefixes, preserve supported policy and the complete NSS slot line, and retain an external module's parameters containing the old directory verbatim. **Seven escaped-source-path cases** and **70 unsupported-policy/form refusals** also pass. These are subcases within three unittest methods, not extra tests added to the full-suite count.

Independent reviewer probes add **8/8 private migration/path cases** with source directories actually `0500` and module files `0400`, covering spaces, quotes, backslashes and equals in each mode. They initialize/import into the destination and compare complete old snapshots. All pass. The original recovery copy remains byte-exact even though the destination's internal binding correctly changes.

Evidence: `/tmp/usb-review-5-evidence/core-compare.py`, `core-compare.log`, `usb-unit-unprivileged.log`, `native-probes.py`, `native/results.json`; `/tmp/usb-review-5-runtime/core-compare/{before,after}-{modutil,pkcs11}-{quoted,unquoted}/result.json`.

## R4-M2: MOZILLA_CERTIFICATE_FOLDER pin — fixed

Relevant locations: `usb_token_store.py:80`–`:85`, `usb_token.py:22`–`:24`, `usb_token_db.py:73`–`:89`; Vietnamese help at `help/ky-so-usb-token.html:72`.

The independent core matrix starts HST with the variable inherited from its launch environment, first under forced Darwin, then under normal Linux with a real open reader on `pkcs11.txt` preventing the lease. It repeats setup before and after a complete restart. The Linux case has no platform override.

| Observation | Before: `2f3d183` | After: `d0bfc6f` |
| --- | --- | --- |
| Forced Darwin and normal Linux reader conflict, both modes | Creates and selects an unused private store. After restart NSSPath and SQL descriptors still point to the pinned old store; repeat setup falsely reports existing registration in the unused store. **4/4 historical failures reproduced.** | Refuses in Vietnamese on both attempts and after restart. CertDir is unchanged; no private directory is allocated; every old file's bytes, mode and uid remain unchanged. The message names the variable, explains safe Linux registration, and instructs removing the launch override and restarting if necessary. **4/4 fixed.** |
| Safe Linux registration into the pinned store, both modes | Control covered by reviewed tests. | The supplied real-HST binding runner registers into the pinned store, loads it after restart and reports the existing registration correctly. **2/2 passed.** |

For the independent `after-modutil-pinned-linux-reader` fixture, CertDir remains unset before setup, after setup and after restart; the old `cert9.db` and `key4.db` remain the only open SQL files. Both dialogs say `MOZILLA_CERTIFICATE_FOLDER đang cố định kho chứng thư; chưa thay đổi tệp hay chọn kho mới.` The variable is not silently unset.

The unit tests also verify that an unused marked CertDir cannot mask the pinned path, even when that marked path is in the pending-restart set; a marked store without a pending switch cannot override core; and a pinned missing Darwin directory is not created. Ordinary repeat-before-restart still selects the pending destination and preserves the restart requirement.

Evidence: the four `pinned-*` mode/policy cases per revision in `core-compare.log` and their JSON; `/tmp/usb-review-5-runtime/bindings/results.json`; `test_usb_token_pinned` and `test_usb_token_action` output in `usb-unit-unprivileged.log`.

## Diff and preservation audit

The change is confined to internal binding interpretation, pin-aware selection, non-creating ownership preflight, help and regression tests. The Linux lease/SQL-lock transaction and disposable driver-validation worker are unchanged.

| Area | Fresh result |
| --- | --- |
| Binding parser | Source spans restrict rewriting to internal binding values. Destination `configdir` is explicitly SQL; cert/key prefixes are empty; `secmod` is local. Outer quoting makes the destination binding effective in the actual core tests. Other parameter text, external records, comments and NSS slot policy survive. |
| Fail-closed parsing | **24/24 independent refusal cases** pass: duplicate bindings/policy/parameter lines, malformed inner/outer quotes, unknown keys/flags, update/nested-token bindings, read-only policy, oversized values and NUL, in both modes. No destination allocation or source mutation. The UI receives Vietnamese errors. |
| Supported policy | **4/4 additional native cases** retain and load `passwordRequired`, `forceOpen`, `optimizeSpace`, and their combination. Password-required stores reject empty passwords and initialize with a disposable nonempty password; the source remains unchanged. |
| Publication and failure behavior | Existing no-clobber link, multi-driver single publication, source-change check and pre-publication fsync tests pass. Five independent short-write, partial-write, append-fsync, backup-copy and rollback-failure probes pass. Successful rollback restores exact snapshots; failed rollback retains the original recovery copy and names it in the error. |
| Ownership and reuse | Eight path/ownership tests pass as uid 2000. Actual root and foreign-owner probes both refuse. Existing names and symlink targets are skipped; marked empty current stores alone are reusable. Private directory/marker/file modes remain `0700`/`0600`/`0600`. |
| Test retention | AST comparison retains all **102** earlier USB test methods; eight were added, giving **110**. The old runtime prefix assertion necessarily changes because the internal line must change. Its helper ignores parameter lines generally; the dedicated native binding test supplies the stricter external-parameter preservation assertion. No old scenario was removed. |
| Size and packaging | **55 packaged Python modules**, maximum **199 lines** using `text.count("\n") + 1`. Changed production modules: action **77**, binding **119**, DB **105**, store **126**. All changed USB tests/harnesses are at most **178**. Two builds are identical. |
| UI/help and authority | Vietnamese dialogs explain success, restart, refusal and recovery. Help now documents persistent pins and unsupported policies. No production PIN/login, signing, key extraction, network client, elevation or shell invocation was added. |

The existing limits remain: source snapshot checks are not a permanent freeze against later writers; same-uid path replacement is not comprehensively prevented; directory fsync and power-loss recovery are not implemented. These are unchanged scope limits, not newly observed failures. Private migration does not copy imported certificates or local SQL keys, as disclosed in help.

## Earlier-round scenarios rerun

All results below are fresh on the reviewed tree. Historical results are not substituted for current execution.

| Earlier scenario | Round-5 evidence and disposition |
| --- | --- |
| R1 B1: CRLF/mixed newline module loss | Native unit and independent two-mode CRLF fixtures refuse without changing old bytes. Existing modules remain listed. **PASS.** |
| R1 B2: exact/prefix/quoted-name and library-prefix deletion | Native preservation tests plus independent two-mode prefix fixtures retain original records, mode `0640`, SQL hashes and usable modules; repeat is byte-identical. **PASS.** |
| R1 M1: concurrent writer loss | Actual modutil and already-initialized NSS writers wait and both registrations survive; exclusive SQL-lock refusal and late native rename preservation pass. Linux no-lease migration preserves the source. **PASS.** |
| R1 M2: configured/core path disagreement | Complete per-mode actual-UNO suites pass absolute, `sql:`, missing, literal-tilde and fallback/restart cases: **10 cases / 34 checks**. **PASS.** |
| R1 M3: invalid driver false success | Corrupt libraries fail on repeated attempts in both modes without mutation. Existing broken registration, wrong architecture and missing dependency tests pass. Mixed private results publish only valid modules; invalid-only setup selects no store. **PASS.** |
| R1 m1: English exception leakage | Actual uid-2000 permission failures in both modes are Vietnamese without errno/English OS text; action/error tests pass. **PASS.** |
| R1 m2 / R2 m1: p11-kit exclusions and enabled aliases | Eight independent policy/mode cases cover alias enablement, vendor/admin/user restoration, explicit disable and empty override; native listing and preservation pass. Global, trust, restricted and cross-alias exclusions pass unit coverage. **PASS.** |
| R2 M1: bundle NSS/helper lookup | Seven unit methods plus **6/6 independent bundle/helper/native-NSS cases** pass for both app names and framework/version/Current prefixes. **PASS within Linux fixture limits.** |
| R2 m2: macOS workflow/help | The low-level existing-file append refusal remains safe. Automatic private-store first/second additions, multiple-driver publication, numbered stores and idempotence pass. The real empty-configured-store alternative passes both modes and leaves the browser store intact. Help reflects current behavior. **PASS.** |
| R2 m3: oversized tests | All earlier native methods retained; all changed modules meet the bound. **PASS.** |
| R3 validation hold | Dictionary test still skips because its upstream input is absent. Explicitly non-blocking in this round; no product defect. |
| R4 M1/M2 | Before/after and shipped core regressions above establish the fixes. **PASS.** |
| Other earlier scenarios | Spaces/quotes/backslashes/equals, symlink deduplication, comments, file permissions, no-driver guidance without DB creation, root/foreign/symlink/legacy guards, real DBM preservation, current-store reuse, read-only source migration and recovery all rerun. **PASS.** |
| Profile selection and open office | Actual Snap Firefox and Flatpak Thunderbird selection pass both modes, through restart, exact SQL paths and native module listing. Warm signing and core comparison exercise an office with its source SQL files open. **PASS.** |
| Windows and platform coverage | Vietnamese Windows early-return test passes without NSS setup. No Windows executable or native macOS was run. Catalog data is unchanged; detection behavior is re-executed, while historical vendor-package research is not presented as fresh hardware validation. |

## Exact execution counts

Subsets, repeated runs and reviewer probes overlap; do not add them to unit discovery.

| Command/check | Exact result |
| --- | --- |
| `python3 -m unittest discover -s tests/unit -v` | **400 run: 399 passed, 0 failures, 0 errors, 1 skipped** |
| USB-specific discovery, separately as uid 2000 | **110/110 passed**, 0 failures/errors/skips; includes **36 methods using native NSS fixtures**, seven bundle methods and eight ownership/path methods |
| Normal signing runtime `--mode both` | modutil **9/9**, pkcs11 **10/10**; **19/19**, 0 skipped |
| Forced Darwin signing `--mode both --darwin` | modutil **12/12**, pkcs11 **13/13**; **25/25**, 0 skipped |
| Normal cold signing `--mode both --cold` | **9/9 + 10/10 = 19/19**, 0 skipped |
| Forced Darwin cold signing `--mode both --darwin --cold` | **12/12 + 13/13 = 25/25**, 0 skipped |
| Signing-runtime total | **88/88 checks**, eight completed mode/policy/initialization combinations |
| Actual SoftHSM signing | **8/8 ODTs valid; 80/80 reference digests; 0 unchecked references** |
| Original CertDir runtime, complete separate processes per mode | modutil **5/5 cases, 17/17 checks**; pkcs11 **5/5 cases, 17/17 checks**; total **10/10 cases, 34/34 checks** |
| New supplied binding/pin runtime `--mode both` | **10/10 cases, 44/44 checks**, 0 skipped |
| Independent before/after HST comparison | Before: **6/6 defect reproductions + 2/2 controls**, **52/52 expected-observation checks**. After: **8/8 cases, 52/52 checks**. Total **16 cases / 104 checks** |
| Independent extra HST cases | Snap, Flatpak, empty configured store and no driver, both modes: **8/8 cases, 30/30 checks** |
| Independent native historical probes | **36/36 cases**: eight preservation/validation, eight private paths, eight p11-kit policies, six bundle and six storage/DBM |
| Additional parser / policy / ownership probes | **24/24 refusals; 4/4 supported-policy cases; 2/2 actual root/foreign-owner guards** |
| `bash scripts/ci-quality.sh` | **48 commands executed, 48 passed, 0 failures** |
| Unittest invocations inside quality | **36 invocations; 427 tests: 426 passed, 1 skipped, 0 failures/errors** |
| Extension checker self-tests | **18/18 passed** |
| Reproducible extension build | **2 identical builds**, SHA-256 `dce1ee2ac42ff0efd1a641b1af4795fbf6f0511b3e0677b662322a4c4b0afc1d` |
| Standalone DMG background check; whitespace checks | Both passed |

Each signing run enumerates the actual SoftHSM certificate through XSecurityEnvironment, answers the disposable test PIN dialog, signs through the UI, reopens with HST signature state `OK`, and independently verifies the signature value, issuer and every reference digest. Both NSS CLI tools are disabled inside production setup in pkcs11 mode. No signing check was skipped or mocked.

The sole unit skip is `test_shipped_dictionary_is_complete_after_merge` (`LibreOffice tree not present`). Quality separately reports absent Windows pinned-tarball simulation and upstream macOS option/patch/icon inputs. Its existing DMG dependency guard prints a skip; the standalone exact DMG command passes. These omissions are disclosed and are unchanged by this diff.

An initial runtime launch completed zero checks because the short-lived shell had terminated Xvfb (`Can't open display: :99`), preventing profile creation. A persistent Xvfb session fixed the review environment; all four complete signing matrices then passed in fresh workdirs. An exploratory reviewer policy probe initially assumed `passwordRequired` should accept an empty password; NSS correctly rejected it. The corrected probe verifies that refusal, successful nonempty-password initialization and preserved source hashes. Neither correction changed product code or supplied test assertions. The earlier combined CertDir runner's PyUNO lifetime issue was avoided by executing each complete five-case mode in its own process; no missing case was counted as a pass.

## Reproduction and evidence

Evidence root: `/tmp/usb-review-5-evidence`. Runtime JSON, signed ODTs, PDFs and screenshots: `/tmp/usb-review-5-runtime`. The scripts and disposable PKI remain outside the commit.

```sh
python3 -m unittest discover -s tests/unit -v
runuser -u codex -- env HOME=/tmp/usb-review-5-home python3 \
  -m unittest discover -s tests/unit -p 'test_usb_token*.py' -v
bash scripts/ci-quality.sh
python3 scripts/build-extensions.py --verify-reproducible
python3 scripts/check-extensions.py --self-test
python3 -I scripts/macos/make-dmg-background.py --check

runuser -u codex -- env HOME=/tmp/usb-review-5-home python3 \
  tests/runtime/check-usb-token-setup.py --instdir /opt/hst \
  --oxt /tmp/usb-review-5-evidence/reviewed.oxt \
  --workdir /tmp/usb-review-5-runtime/linux-ready --display :99 --port 2483 --mode both
# Also --darwin, --cold, and --darwin --cold, using separate fresh workdirs.

runuser -u codex -- env HOME=/tmp/usb-review-5-home python3 \
  tests/runtime/check-usb-token-review.py --instdir /opt/hst \
  --oxt /tmp/usb-review-5-evidence/reviewed.oxt \
  --workdir /tmp/usb-review-5-runtime/selection-modutil --display :99 --port 2483 --mode modutil
# Repeat with --mode pkcs11 and a fresh selection-pkcs11 workdir.

runuser -u codex -- env HOME=/tmp/usb-review-5-home python3 \
  tests/runtime/check-usb-token-bindings.py --instdir /opt/hst \
  --oxt /tmp/usb-review-5-evidence/reviewed.oxt \
  --workdir /tmp/usb-review-5-runtime/bindings --display :99 --port 2483 --mode both
```

For independent comparison, run `core-compare.py --revision before|after --mode modutil|pkcs11 --case quoted|unquoted|pinned-darwin|pinned-linux-reader --workdir <fresh-root> --oxt <corresponding-oxt>` as uid 2000, with Xvfb `:100` and port 2484. Each invocation is a fresh Python process and includes its own full HST restart. Baseline OXT SHA-256: `3526a672ce16c6ab14f5c7a06ab1dbb281f4ea4867fd80385851de4416298eca`.

Key evidence files: `unit.log`, `usb-unit-unprivileged.log`, `quality.log`, `build.log`, `checker.log`, `dmg.log`, `static-audit.json`, `runtime-*.log`, `selection-*.log`, `bindings.log`, `core-compare.log`, `extra-core.log`, `native-probes.log`, `parser-refusals.log`, `policy-load-corrected.log`, `guards.json` and `runtime-summary.json`. Reviewer scripts are `core-compare.py`, `extra-core.py`, `native-probes.py`, `parser-refusals.py` and `policy-load.py`; their retained fixtures/results provide per-case evidence.

Native macOS/Mach-O, dyld/quarantine/Rosetta and proprietary physical tokens remain unavailable. Forced Darwin demonstrates the store policy, paths, real Linux NSS/core loading and signing; it does not establish native Mac hardware acceptance. Within the reviewed scope and explicit test gate, both major fixes are verified and the verdict is **SHIP**.
