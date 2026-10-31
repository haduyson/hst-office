# USB Token setup: independent review, round 3

Review date: 2026-10-31. Branch: `codex/usb-token`. Reviewed HEAD: `22f29aefa587a1da767763af131cee2a0c2a3183` (`fix(signing): resolve bundled NSS and enabled token aliases`). Baseline: `0d2245b`, the round-2 report commit. Scope: the complete `0d2245b..22f29ae` diff, its production dependencies, all four round-2 findings, all seven round-1 scenarios, and fresh execution of the required suites.

**Verdict: FIX-THEN-SHIP — validation hold only. Product findings: 0 blocker, 0 major, 0 minor, 0 nit.** All four round-2 findings are fixed, all seven round-1 scenarios remain fixed, and no new product defect was found. Every executed test passes. However, the required unit discovery still skips one upstream-dependent test. The requested release rule requires every test to pass; a skipped test is not a demonstrated pass, so this report does not issue SHIP. Supply the missing upstream input and complete that validation before changing the verdict. No product-code fix is identified by this review.

Only this report is committed. Product code was not edited. `/opt/hst` remained mounted read-only. The baseline was exported with `git archive` into `/tmp/usb-review-3-evidence/before`, without changing the branch. Independent probes and GUI runs used uid 2000 (`codex`), private HOME/profile/database directories, and Xvfb `:99` / `:100`. The supplied unit and quality commands ran as root; native unit fixtures bypass their root guard, while the separate reviewer probes exercised the real guard as an ordinary user. NSS tools are `2:3.98-1ubuntu0.3`; SoftHSM is `2.6.1-2.2ubuntu3`. No dependencies or source files were downloaded.

## Findings by severity

| Severity | Open product findings |
| --- | ---: |
| Blocker | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

**Validation hold:** `test_shipped_dictionary_is_complete_after_merge` reports `LibreOffice tree not present`. Its required input is `upstream/libreoffice/dictionaries/vi/vi_VN.dic`; the skip is unchanged by this feature. Unit discovery exits successfully with **370 passed, 1 skipped**, not 371 demonstrated passes. CI also explicitly omits upstream-dependent preflight work as detailed below. This is an environment/coverage limitation, not a newly introduced defect or a failed assertion. The strict release gate remains unmet.

## Round-2 findings: before/after evidence

### R2-M1 — macOS NSS bundle lookup: fixed

Relevant HEAD locations: `usb_token_nss.py:98` (`macos_contents`), `:110` (`helper_python`), and `:124` (`nss_library`), under `extensions/hst-vietnamese-tools/python/hst_office/`.

The same reviewer script ran against the baseline and HEAD with six filesystem layouts: `HST.app` and `HST Office.app`, each using the framework root, `Versions/3.12`, or `Versions/Current` as the Python prefix. The office executable was under `Contents/MacOS`; NSS was under `Contents/Frameworks/libnss3.dylib`.

- **Before:** all **6/6** layouts raised `Không tìm thấy thư viện NSS của HST Office; chưa thay đổi kho chứng thư.` despite the library existing. This includes all four app/prefix combinations reported in round 2.
- **After:** all **6/6** resolved the correct NSS path and an executable Python helper, executed that helper, and completed production `register()` with status `added`. After explicit SQL initialization, independent `modutil -list` loaded SoftHSM in every resulting DB.

For this Linux experiment, the fixture's `.dylib` was a symlink to real system NSS, and its bundled Python path was a symlink to the real Linux interpreter. The worker, NSS loader, registration, and native listing were not mocked. Only the parent's platform/executable/prefix and PATH discovery were substituted. This proves lookup and worker transport with real NSS; **it does not prove Mach-O loading on macOS**.

The seven shipped bundle unit tests also pass. They cover executable/prefix discovery, a symlinked office launcher, missing framework helper aliases, Frameworks preference and MacOS fallback, missing-library refusal, rejection of a Linux `.so` substitute, and the paths sent to the worker. Local macOS probe scripts agree with the `Contents/MacOS` and `Contents/Frameworks` layout. Native macOS architecture, dyld, quarantine, and Rosetta behavior remain unexecuted platform coverage.

Evidence: `probes-before-complete.log`, `probes-head-complete.log`, and their `R2-M1-layout` JSON records; `usb-unit.log`.

### R2-m1 — enabled p11-kit alias disappears: fixed

Relevant HEAD location: `usb_token_detect.py:53`–`:73`. History is now tracked by canonical library identity and reconciled with the final configuration for each module filename.

The independent fixture installs real SoftHSM behind the catalog path `/usr/lib/libcastle.so.1.0.0` and a symlink alias, with a pre-existing NSS roots module. It exercises both registration modes and two enabled policies: vendor path → user alias, and vendor path → administrator replacement → user restoration.

- **Before:** all **4/4** enabled-policy/mode combinations detect zero candidates; registration returns no rows and the DB remains unchanged.
- **After:** all **4/4** detect one candidate and return `added`. Native NSS loads both the original roots module and the new token module. The original module-file prefix and the SQL-file hashes are preserved.
- Final explicit disable and empty overrides still exclude the canonical library in **4/4** additional policy/mode combinations on each revision. No DB bytes change. The shipped tests also cover trust/restricted entries, catalog aliases, restoration after intermediate disable/empty entries, and an independent exclusion winning over an enabled alias.

Evidence: the eight `R2-m1/*` records per revision in the independent probe logs and result JSON; the new real-NSS alias test and four detection regressions in `usb-unit.log`.

### R2-m2 — macOS help omits permanent refusal: fixed

Relevant HEAD location: `extensions/hst-vietnamese-tools/help/ky-so-usb-token.html:70`–`:89`.

**Before:** the help did not describe existing-file refusal and said manual setup was needed only for unsupported driver paths. Its manual commands could target the shared/browser store. **After:** the Vietnamese help explicitly describes existing `pkcs11.txt` refusal, browser profiles, second-driver additions, and why retry/restart does not remove the restriction. It warns against deleting or renaming the old file, describes selecting a separate empty store, and confines manual commands to a new separate directory with an explicit preservation-guarantee limitation.

On both revisions, the independent Darwin-branch transaction probe refuses an existing real NSS module file twice and preserves every tracked file hash. A separate empty directory accepts its first module; a second addition is refused without changing it. Native NSS subsequently loads the first module. This verifies that the revised documentation describes the implemented restriction.

The separate-empty-store workflow was also exercised through actual UNO/HST on Linux in both modes: an empty absolute configured directory is selected before NSS initializes; setup adds the module and requests restart; after restart/PDF initialization the same store is selected and the module loads. The existing Firefox store remains byte-identical. This validates core selection and the alternative's sequencing, not native macOS UI/runtime behavior.

Evidence: `help-before-after.json`; the `R2-m2-existing` and `R2-m2-empty` records in both independent probe runs; `runtime-empty-selection.log` and `/tmp/usb-review-3-runtime/empty-selection/results.json`.

### R2-m3 — oversized native test module: fixed without losing tests

**Before:** `test_usb_token_nss_real.py` has **308 newline characters / 309 lines by the checker convention**. **After**, using `text.count("\n") + 1`:

| Module under `tests/unit/` | Lines |
| --- | ---: |
| `usb_token_nss_fixtures.py` | 51 |
| `test_usb_token_nss_real.py` | 124 |
| `test_usb_token_nss_preservation.py` | 111 |
| `test_usb_token_nss_concurrency.py` | 104 |

AST comparison finds **all 16 original test methods retained**, with no removals: 15 bodies are identical and the existing macOS-refusal test is strengthened to check repeat refusal. All five extracted fixture/helper method bodies are identical. Two new native tests bring the total to **18**, all executed successfully. Every USB test/helper module is at most **172 lines**. The packaged extension has **53 Python modules**, maximum **199 lines**; changed detection/NSS modules are **102/163**.

Evidence: `static-audit.json`, the AST comparison output, `usb-unit.log`, and the successful extension checker.

## Round-1 scenarios reconfirmed against real NSS

The reviewer script runs unchanged against both the round-2 baseline and HEAD. Each destructive/preservation probe uses its own real SQL DB, system NSS roots and/or SoftHSM, native listing, and SHA-256 snapshots of `pkcs11.txt`, `cert9.db`, `key4.db`, and `secmod.db` presence. These checks do not reuse historical results. M2 additionally uses actual HST/UNO and its cached NSS selection.

| Finding | Fresh HEAD observation | Result |
| --- | --- | --- |
| **B1 — CRLF deletion** | Both modes refuse before mutation. Native listing retains the existing roots module; all tracked hashes remain identical. | PASS: safe refusal |
| **B2 — prefix deletion** | Both modes add SoftHSM beside `Feitian ePass2003 old`; native listing loads both. Entire original prefix, mode `0640`, and SQL hashes survive. Repeat registration is `existing` and byte-identical. Native unit tests also retain exact/quoted-name and library-prefix coverage. | PASS |
| **M1 — concurrent update loss** | A real `modutil` writer launched at the final append boundary waits for the transaction and exits 0 afterward; both registrations load. The native unit suite also passes already-initialized NSS writer, SQL-lock refusal, and late native rename cases. Only scheduling is controlled; the competing writer and locks are real. | PASS |
| **M2 — wrong selected DB** | Both modes pass absolute configured, `sql:` configured with Firefox present, missing configured directory, literal tilde, and fallback/restart cases: **10 cases / 34 checks**. Setup agrees with core before initialization, after PDF export, and after restart; ignored/missing stores remain untouched. | PASS |
| **M3 — corrupt driver false success** | Both modes reject a text driver on both attempts and preserve all tracked hashes. Native tests additionally reject an already-registered broken module, wrong ELF architecture and missing dependency. | PASS |
| **m1 — English permission failure** | Real uid-2000 DBs with directory mode `0500` return `Không có quyền ghi kho chứng thư. Hãy chọn kho thuộc tài khoản đang sử dụng.` in both modes, with no English exception or errno; hashes remain unchanged. Production action/result tests also pass. | PASS |
| **m2 — excluded catalog driver** | Native regression and independent final-disable/empty-alias probes detect no candidates, add nothing, and preserve the DB. Enabled aliases now work without undoing explicit exclusions. | PASS |

Example B1 evidence: HEAD modutil fixture `pkcs11.txt` SHA-256 is `1f64c50b4963fed84a24a27811010d4f68b7b55e3432d463a8e647748becf550` before and after; the no-tools fixture is `aa8a0912c67912f394ed881140255d18644d50268185ada39c08675259ab5a0f` before and after. Hashes are compared within each fixture, not across independently created DBs.

## Diff review and regression assessment

The diff changes two production Python modules, Vietnamese help, the implementation report, and six test/helper files. I found no new defect requiring a code change.

- The bundle locator resolves enclosing application directories and chooses bundled NSS before fallback locations. Helper selection still passes an argument array to the existing subprocess path. The worker's architecture check and load validation remain intact; no failed load is converted to success.
- p11-kit exclusions are reconciled within each final override chain. Explicit exclusions remain canonical and apply when catalog and p11-kit candidates are merged. Both successful enablement and continued exclusion were verified with real libraries.
- The NSS transaction, worker, database selector, and UI action are unchanged by this diff. Existing native tests retain their independent assertions; backup, rollback, SQL locks, append lease, and no-clobber new-file tests still execute.
- The help alternative preserves the old store and acknowledges the first-driver-only restriction. Its selection/restart sequence was exercised with real HST.
- No new production network access, elevation, PIN/login request, private-key operation, or shell invocation was introduced.

No claim is made about every possible power-loss/lease-expiry interleaving, physical proprietary tokens, native macOS, or Windows runtime. The Linux no-tools mode is exercised with both NSS CLI tools disabled inside setup; it is not a replacement for native macOS acceptance.

## Exact execution counts

All results below are fresh runs on `22f29ae`. Subsets and repeated runs are identified to avoid double counting.

| Command/check | Exact result |
| --- | --- |
| `python3 -m unittest discover -s tests/unit -v` | **371 run: 370 passed, 0 failures, 0 errors, 1 skipped** |
| USB-specific unit discovery | **81/81 passed**, 0 failures/errors/skips; subset of the 371, separately rerun |
| Native NSS tests within USB subset | **18/18 passed**, 0 skipped |
| macOS layout unit tests within USB subset | **7/7 passed**, Linux filesystem/transport fixtures |
| Required runtime `--mode both`: modutil | **9/9 checks passed**, 0 skipped |
| Required runtime `--mode both`: pkcs11 | **10/10 checks passed**, 0 skipped |
| Additional runtime `--mode both --cold` | modutil **9/9**, pkcs11 **10/10**, 0 skipped |
| SoftHSM signing: required run | **2/2 valid signed ODTs**, **20/20 reference digests**, 0 unchecked references |
| SoftHSM signing: required + cold runs | **4/4 valid signed ODTs**, **40/40 reference digests**, 0 unchecked references |
| `check-usb-token-review.py --mode both` | **10/10 cases, 34/34 checks passed**, 0 skipped |
| Independent empty-store UNO workflow | **2/2 cases passed**, one per mode |
| Independent before/after probes | **25 cases per revision**; baseline reproduces round-2 defects, HEAD satisfies all assertions |
| `bash scripts/ci-quality.sh` | **44 commands executed, 44 passed, 0 failed** |
| Unittest invocations inside quality | **32 invocations, 398 tests: 397 passed, 0 failures/errors, 1 skipped**; includes unit/brand tests and overlaps the counts above |
| `python3 scripts/check-extensions.py --self-test` | **18/18 passed** |
| `python3 scripts/build-extensions.py --verify-reproducible` | **2 identical builds**, SHA-256 `19da5d73fb207363055572df6f6319f7988d3821235cfdfa28ffdcb811d2df1e` |
| Standalone DMG background check; `git diff --check` | Both passed |

Each signing run lists the real SoftHSM certificate through XSecurityEnvironment, exercises the harness PIN dialog, signs through the UI, reopens with HST signature state `OK`, and independently verifies the signature value, issuer and all ten reference digests. No runtime or signing check was skipped.

The sole unit skip is the upstream-dictionary test described above. Quality explicitly skips the Windows pinned-tarball simulation and macOS configure-option/patch/icon checks because their upstream inputs are absent. The existing macOS preflight guard also prints `SKIP dmg background: needs Pillow and fonts-liberation`; the separately executed `python3 -I scripts/macos/make-dmg-background.py --check` passes. Successful command exits do not establish execution of these omitted checks.

The reviewer-authored harness initially needed two corrections: initialize the new SQL store before asking independent `modutil` to list it, and import the UNO bridge before importing `com.sun.star`. Corrected complete probes and the workflow rerun are the results counted above. No product code or supplied test assertion was altered to obtain a pass.

## Reproduction and evidence

Evidence root: `/tmp/usb-review-3-evidence`. Runtime artifacts, JSON, signed ODTs and screenshots: `/tmp/usb-review-3-runtime`. Independent SQL fixtures and per-case result JSON: `/tmp/usb-review-3-probes/{before-complete,head-complete}`. These paths are container-local and are not committed.

```sh
python3 -m unittest discover -s tests/unit -v
python3 -m unittest discover -s tests/unit -p 'test_usb_token*.py' -v
bash scripts/ci-quality.sh
python3 scripts/build-extensions.py --verify-reproducible
python3 scripts/check-extensions.py --self-test
python3 -I scripts/macos/make-dmg-background.py --check

runuser -u codex -- env HOME=/tmp/usb-review-3-home python3 \
  tests/runtime/check-usb-token-setup.py --instdir /opt/hst \
  --workdir /tmp/usb-review-3-runtime/signing --display :99 --port 2183 --mode both
runuser -u codex -- env HOME=/tmp/usb-review-3-home python3 \
  tests/runtime/check-usb-token-setup.py --instdir /opt/hst \
  --workdir /tmp/usb-review-3-runtime/signing-cold --display :100 --port 2184 --mode both --cold
runuser -u codex -- env HOME=/tmp/usb-review-3-home python3 \
  tests/runtime/check-usb-token-review.py --instdir /opt/hst \
  --workdir /tmp/usb-review-3-runtime/selection --display :99 --port 2183 --mode both
```

The work directories must be fresh when repeating runtime commands. Xvfb was started separately. The OXT was built from HEAD before the runtime runs and loaded through the harness's private bundled-extension directory, leaving `/opt/hst` unchanged.

Key evidence files:

- `unit.log`, `usb-unit.log`, `quality.log`: full suite output and exact skip/count records.
- `runtime-signing.log`, `runtime-signing-cold.log`, `runtime-selection.log`, `runtime-summary.json`: fresh required/cold/selection results.
- `probes.py`, `probes-before-complete.log`, `probes-head-complete.log`: identical independent probe script applied to the exported baseline and HEAD. Invoke it with the repository/export path and a fresh output directory, as uid 2000.
- `empty-selection.py`, `runtime-empty-selection.log`: real UNO check of the new help alternative in both modes.
- `static-audit.json`, `help-before-after.json`: method retention, line counts, quality totals, and documentation evidence.
- `build.log`, `build-reproducible.log`, `checker.log`, `dmg.log`: packaging and ancillary checks. Successful standalone DMG checking emits no output.

Release action: complete the skipped upstream-dependent validation in an environment containing the real source inputs, preserving the passing USB/NSS/signing results. The four round-2 fixes and the seven round-1 protections require no further product change based on this review.
