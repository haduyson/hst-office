# USB Token setup — beta.5

Date: 2026-10-31. Linux container, real HST Office at `/opt/hst` (LibreOffice core 26.8.1.1), Xvfb `:99`, uid 2000 and separate test HOME/profile directories. The installed application was kept read-only. No push was performed.

The original delivery and validation below describe `87e4abd`. The **Review fixes** section records the revised safety contract and the current validation results; its limitations supersede the original registration/restart claims.

## Delivered

- **HST ▸ Thiết lập USB Token…**, always Vietnamese, in Writer/Sheets/Slides and the Start Center. Windows displays that NSS setup is unnecessary. One result dialog lists the detected libraries, registration status, database and next step; existing Vietnamese dialog helpers supply the button.
- A packaged, evidence-annotated catalog at `data/hst/pkcs11-modules.json`: VNPT-CA macOS first, Feitian ePass2003, SafeNet eToken, Bit4id, OpenSC, MISA macOS and EasyCA macOS. Linux also reads p11-kit module registrations in vendor/admin/user configuration directories. File discovery does not open tokens. Canonical paths deduplicate symlink aliases.
- NSS selection through UNO `CertDir` and `NSSInitializer.NSSPath`, respecting `MOZILLA_CERTIFICATE_FOLDER`. The fallback selector mirrors Thunderbird → Firefox → SeaMonkey, including Snap/Flatpak, profile defaults and macOS roots. A new shared database is explicitly selected through CertDir: the existing core patch automatically discovers `~/.pki/nssdb` only on Linux.
- Registration uses `modutil -add … -libfile … -dbdir sql:… -force` when available. Otherwise it appends NSS text records with correct quoting, preserving existing bytes, comments, unrelated modules and permissions. It handles name collisions, repeated runs and symlink aliases, uses a lock and atomic replacement, and detects intervening file changes. It refuses root execution, another user's database, symlinked database files and legacy DBM-only databases instead of migrating them.
- No driver download, installation or bundled driver. No token PIN/key access or logging by setup; subprocesses have no shell, credential arguments, stdin or captured vendor output. Only the user's NSS database and the corresponding user certificate-path preference are changed.
- Help now leads with menu steps, includes VNPT-CA Token Manager on macOS, and retains manual NSS commands under an advanced fallback. BACKLOG marks the work done for beta.5.

## Restart and empty database behavior

NSS caches its database and modules after the first cryptographic operation, including PDF export. The command checks `NSSInitializer.IsNSSinitialized`, retains the pending-restart indication across repeated commands, and does not shut down or reload a running NSS instance. Both runtime modes deliberately export PDF before setup and verify the Vietnamese restart instruction; after restarting, repeating setup no longer asks for another restart.

Without CLI tools and before NSS initialization, the HST core initializer creates `cert9.db`/`key4.db` with an empty internal password. When NSS already owns a different database, the helper creates the target directory and module file and selects it through CertDir; the core completes database creation on first use after restarting. Both paths were tested. The extra cold-start scenario verifies that no restart is requested when NSS can load the new registration on its first use.

## Driver evidence and gaps

- VNPT-CA: the owner's inspection of the official Token Manager 1.0.1 packages established `libvnptca_p11_v8.dylib`, including the application-bundle candidate. The [official download page](https://vnpt-ca.vn/download-page) publishes Intel and Apple Silicon packages. The owner reported that OpenSC could not read their VNPT-initialized Feitian ePass2003Auto; the helper prioritizes the VNPT library.
- MISA: [official PDF-signing instructions](https://helpesign.misa.vn/knowledge-base/ky-file-pdf-tren-macbook/) specify `/usr/local/lib/misaca_csp11_v2.dylib`.
- EasyCA: inspected the archive linked by the [official download page](https://easyca.vn/tai-ve/) without executing it. `Update_260605.zip` → `EASYCA_installer.dmg` → `Easyca_csp11_v1.pkg` → `PKCS11.pkg/Payload` contains `easyca_csp11_v1.dylib`; `PackageInfo` installs it under `/usr/local/lib`.
- Viettel: the [official page](https://viettel-ca.vn/tai-ve/viettel-ca-download) lists Token Manager V6 for macOS but links an external archive; research did not establish the installed PKCS#11 filename. BKAV's [official download](https://bkavca.vn/tai-ve) did not establish a Linux/macOS filename. FPT's official CA site did not provide a retrievable native-library manifest in this environment. These entries deliberately have empty path lists, with source notes; no filename or compatibility was invented. The same limitation applies to CA-specific Linux names for VNPT/MISA/EasyCA. Documented vendor libraries and Linux p11-kit registrations may still detect their installed driver.
- The remaining vendor paths have source notes in the catalog; registration discovery follows the [p11-kit configuration rules](https://p11-glue.github.io/p11-glue/p11-kit/manual/pkcs11-conf.html). No third-party downloads are performed by setup.

## Validation

| Check | Result |
|---|---|
| New USB-token unit tests | **46 passed**, 0 failures, 0 skips |
| `python3 -m unittest discover -s tests/unit` | **336 run: 335 passed, 1 skipped**, 0 failures/errors |
| Runtime with modutil | **9/9 checks passed** |
| Runtime with both modutil/certutil disabled in extension | **10/10 checks passed** |
| Additional no-tools runtime before NSS initialization (`--cold`) | **10/10 checks passed** |
| ODT signatures, all 3 runtime scenarios | HST `OK`; independent signature value and CA issuer valid; **10/10 reference digests per document**, 0 unchecked references |
| Extension reproducibility | Identical SHA-256 on two builds |
| `check-extensions.py --self-test` | **17/17 passed**, including rejection of networking in USB setup and stale catalog data |
| Extension module size | Every packaged Python module ≤199 lines; new production modules ≤133 lines |
| `scripts/ci-quality.sh` | **40 commands executed, 0 failures** |
| `git diff --check` | Passed |

The runtime harness reuses `signature_pki.py`, creates the test CA/user certificate in SoftHSM2 without pre-registering its module, and symlinks it into a fake Feitian library path under a directory containing spaces. A second vendor alias points to the same library. It invokes the actual extension command in an English office UI, reads the Vietnamese result from the native dialog, repeats setup to check byte-for-byte idempotence, restarts HST, lists the certificate through `XSecurityEnvironment.getPersonalCertificates()` with a test PIN, signs ODT through the real signature dialogs, reopens it, and independently verifies its XML signature. The no-tools mode creates its SQL database using the application itself, not certutil. The harness redirects the bundled-extension bootstrap directory to a private copy of the built OXT because installing another same-version copy with unopkg conflicts with the installed bundled UNO implementations; the executable remains `/opt/hst/program/soffice`.

Commands (run runtime checks as an unprivileged user with a separate HOME and Xvfb already running):

```sh
python3 scripts/build-extensions.py --verify-reproducible
python3 -m unittest discover -s tests/unit
python3 tests/runtime/check-usb-token-setup.py --instdir /opt/hst --workdir /tmp/usb-runtime-11 --display :99
python3 tests/runtime/check-usb-token-setup.py --instdir /opt/hst --workdir /tmp/usb-runtime-cold --display :99 --mode pkcs11 --cold
python3 scripts/check-extensions.py --self-test
bash scripts/ci-quality.sh
python3 -I scripts/macos/make-dmg-background.py --check
```

Runtime evidence is in `/tmp/usb-runtime-11/results.json` and `/tmp/usb-runtime-cold/results.json`, with native-dialog screenshots under each `office/setup-shots` and signing screenshots under `shots`. Sanitized results/logs/screenshots are copied to `tests/output/usb-token-setup/` (ignored); temporary PKI/key files are not copied or committed.

## Skipped checks and unverified platforms

- `test_shipped_dictionary_is_complete_after_merge`: skipped because `upstream/libreoffice` is absent.
- Windows preflight: pinned-tarball build simulation (extract/options/patch, MSI strings/artwork/icon/copyright checks) skipped because `upstream/cache/libreoffice` tarballs are absent.
- macOS preflight: configure-option validation for arm64/x86_64, patch applicability and app/document icon staging skipped because `upstream/libreoffice` is absent.
- The macOS preflight font/Pillow guard printed `SKIP dmg background: needs Pillow and fonts-liberation` despite these dependencies being installed (its `fc-list | grep -q` guard runs under pipefail). The actual check was separately run with `python3 -I scripts/macos/make-dmg-background.py --check` and **passed**.
- Real VNPT/Viettel/BKAV/FPT/MISA/EasyCA tokens, proprietary driver loading and architecture compatibility, macOS GUI/bundled NSS execution, and Windows runtime were not available. Linux SoftHSM proves the registration/signing flow and real NSS text-file handling; it does not prove compatibility with those physical tokens. Vendor certificate-chain installation remains the user's existing CA workflow.


## Review fixes

2026-10-31. Addressed all **2 blockers, 3 majors and 2 minors**. No network access, elevation, push, or changes to `/opt/hst` were used. All native tests use disposable SQL databases; office runtime tests use uid 2000, separate HOME/profile directories and Xvfb `:99`.

| Finding | Fix | Regression evidence |
|---|---|---|
| **B1 — CRLF deletion** | Reject CRLF/mixed newlines and unknown module-file syntax before mutation. Never pass the live DB to `modutil`; it operates only on an isolated SQL probe DB. | `test_crlf_refused_without_mutation_both_methods` creates a real certutil DB, adds a working NSS roots module, converts its file to CRLF, confirms native NSS still lists it, and checks refusal plus unchanged DB bytes for both methods. |
| **B2 — prefix deletion** | Generate `HST <label> <canonical-path hash>` names, check both prefix directions, and refuse unresolved collisions. Both methods publish only an additional quoted stanza; native deletion/rewrite code never sees existing registrations. | `test_prefix_and_exact_names_preserved_both_methods` covers exact/prefix and quoted names, checks every original byte and mode, and independently lists both loaded modules with modutil. `test_library_prefix_preserves_unrelated_registration` covers raw library-path prefixes. `test_unresolvable_name_prefix_refused` checks safe refusal. |
| **M1 — lost concurrent update** | Remove compare/replace entirely. Existing files require a Linux kernel write lease; NSS opens wait even when its process was already initialized. Hold real SQLite exclusive locks while making opaque recovery copies. Keep SQL source descriptors open until lock release so ordinary file closing cannot silently drop POSIX locks. Append in place, verify inode identity, and undo only our appended tail on failure. Create absent files using atomic, non-replacing `link()`. Refuse unavailable locks and unsupported platforms for existing files. | `test_final_boundary_keeps_real_competing_modutil_update` reproduces the original final-boundary race with real modutil. `test_already_initialized_native_writer_waits_for_module_lease` uses an initialized native NSS process. Both registrations survive. `test_late_native_rename_is_detected_without_restoring_over_competitor` checks that a late competing native DB replacement is retained. SQL-lock, unsupported-lock and partial-write rollback tests check unchanged originals. |
| **M2 — different DB from core** | Treat `NSSInitializer.NSSPath` as authoritative before and after NSS initialization. Do not expand shell paths or strip `sql:` from configured CertDir. Accept configured filesystem paths only when absolute and existing. Do not create stale configured paths. Leave new live SQL initialization to core after restart, including cold setup; persist fallback CertDir only following successful registration. | `check-usb-token-review.py` uses actual UNO configuration with Firefox present: absolute, `sql:`-prefixed and missing configured paths follow the actual core selection through setup, PDF export and restart. Literal `~` paths exposed by this core are refused unchanged. Two additional fallback cases prove registration, repeat behavior, core SQL creation after restart and independent NSS loading. **10 cases / 34 checks**, both methods. |
| **M3 — unusable library reported registered** | Every candidate, including an existing text registration, must load through `SECMOD_LoadUserModule` in a disposable process using the office's NSS library. Verify process architecture and pointer width. Treat unloaded modules, crashes and helper failures as errors; retain no new registration. Neither method logs in or requests credentials. | `test_corrupt_library_fails_every_time_both_methods`, `test_existing_unloadable_record_is_not_reported_registered`, `test_wrong_architecture_is_failed_without_registration` and `test_missing_dependency_is_failed_without_registration` use real NSS and check unchanged SQL/module files. Native modutil independently confirms the old broken-record fixture is not loaded. |
| **m1 — English exceptions** | Only authored `SetupError` messages may reach the UI verbatim. Map permission, lock, configuration and I/O exceptions to Vietnamese; use a Vietnamese generic message for unexpected failures. Do not offer the signing next step when every registration failed. | `test_real_permission_failure_is_vietnamese_and_preserves_db` runs against a mode-0500 SQL DB as an unprivileged user. Action tests inject real English permission text and an unexpected English exception and verify neither leaks into the Vietnamese dialog. |
| **m2 — excluded catalog module** | Resolve p11-kit global `user-config` policy and effective vendor/admin/user registrations before merging catalog candidates. Canonical exclusions apply to catalog paths and all aliases, including an empty user override. | `test_catalog_exclusion_prevents_registration_in_real_db` uses a real catalog path linked to SoftHSM and a real SQL DB. Detection/registration leave it unchanged. Additional tests cover canonical aliases, global `none`/`only`, and empty overrides. |

### Transaction and platform limits

Before changing the module file, setup backs up each present `pkcs11.txt`, `secmod.db`, `cert9.db` and `key4.db` into a private `.hst-token-backup-*` directory (directory 0700, copies 0600). Copies are flushed before publication. The live certificate/key databases are never written by setup, and existing module bytes and permissions are retained. Recoverable append failures restore the original length while exclusion is still held. A failed rollback retains the recovery copy and reports its location in Vietnamese; setup never restores over a competing replacement. Legacy secmod/DBM databases are refused before mutation. Successful additions retain their recovery copies.

The modutil method now uses certutil/modutil only inside its disposable verification database. The no-tools method uses native NSS loading directly. Both share the same add-only publisher. No active office NSS instance is shut down or reinitialized by setup. An empty live DB requires a restart for core to initialize SQL; the cold runtime expectations were updated to enforce this behavior. The certificate/PIN/signature and independent-verification assertions in the existing signing harness remain intact.

Kernel leases are a Linux capability, not a portable advisory-lock claim. Existing module files are refused on macOS and filesystems without this capability; new module-file creation can proceed atomically when a compatible helper and NSS library are available. Native macOS architecture/quarantine behavior and physical tokens remain untested. This is intentionally a narrower, safe contract than the original implementation's macOS claim. No quarantine policy is changed.

### Before/after proof and current counts

Exported `87e4abd` locally with `git archive` and ran seven selected finding regressions against that implementation: **all seven failed** (12 failed assertions including subtests, plus one permission-error subprocess failure). The original final-boundary test ran a real competing modutil before the original replace. A rebuilt original OXT also fails the new actual-UNO `sql:` case by reporting registration into the configured directory while core selects Firefox. Baseline files and logs are under `/tmp/hst-usb-before`, `/tmp/usb-before.log` and `/tmp/usb-selection-before.log`; no baseline code was changed in the repository.

| Current check | Actual result |
|---|---|
| USB-specific unit discovery | **68 passed**, 0 failures/errors/skips; includes **16 real-NSS regression tests** |
| Required `python3 -m unittest discover -s tests/unit` | **334 run: 332 passed, 1 import error, 1 skipped**, 0 assertion failures. The error is missing PyYAML; the skip is the absent upstream dictionary tree. |
| New real-HST review runtime | **34/34 checks passed in 10 cases**, both registration methods; configured-path selection, safe refusal, restart and independent NSS loading |
| Required `check-usb-token-setup.py --mode both`; also each method separately | **Blocked before mode execution** by missing `cryptography`; `lxml` is also absent. **0 new signing checks executed, 2 modes blocked**. The original 19/19 signing result above is historical and is not a result for these fixes. |
| Required `bash scripts/ci-quality.sh` | **41 commands: 32 passed, 9 failed** due to missing PyYAML, Pillow and shellcheck. No dependencies were downloaded under the no-network rule. |
| Extension checker self-test | **18/18 passed**, including network rejection in the new native probe module |
| Reproducible extension build | **2 identical builds**; SHA-256 `7a00eabb1a571b00b89c717fe2284e907abd1db2dfa35926811b221359743fb3` |
| Packaged Python size / whitespace | Every module within the 199-line limit; `git diff --check` passed |

Current logs: `/tmp/usb-unit-final.log`, `/tmp/usb-all-unit-final.log`, `/tmp/usb-quality-final.log`, `/tmp/usb-signing.log`, `/tmp/usb-signing-modutil.log`, `/tmp/usb-signing-pkcs11.log`. Native review results: `/tmp/usb-fix-runtime/review-final/results.json`. Earlier equivalent selection/fallback runs are in `/tmp/usb-fix-runtime/selection-final/results.json` and `/tmp/usb-fix-runtime/fallback-final/results.json`.

The fixes and focused regressions pass, but **full release validation is not green** in this offline container. Rerun the exact full unit, both-method signing and quality commands in an environment with PyYAML, Pillow, shellcheck, cryptography and lxml already available. No signing success or native macOS acceptance is claimed for this revision.


## Round-2 fixes

2026-10-31. Addressed all **1 major and 3 minor** findings in the second independent review. The counts below supersede the earlier environment-blocked validation in “Review fixes”. Production still preserves existing module bytes and names, uses the same private backup/rollback transaction, and displays Vietnamese errors. No production PIN/login/key operation was added. No external network, sudo, push, or write to the read-only `/opt/hst` installation was used; GUI tests ran as uid 2000 with private HOME/profile/SQL directories and Xvfb `:99`.

| Finding | Fix | Test / verification |
|---|---|---|
| **R2-M1 — macOS NSS bundle locator** | Resolve the enclosing `.app/Contents` from the executable or Python prefix, including symlinks and nested framework/version directories. Prefer `Contents/Frameworks/libnss3.dylib`, with `Contents/MacOS/libnss3.dylib` as a fallback. Resolve bundled `LibreOfficePython.framework/bin/python3` and versioned helpers before the PATH fallback. | **7 bundle tests** in `test_usb_token_macos.py`: `HST.app` and `HST Office.app`, framework-root/version/Current prefixes, external Python, symlinked office launcher, missing helper aliases, library precedence and safe missing-library refusal. The standard layout test covers **6 app/prefix combinations** and executes the fixture helper in each. A worker-transport fixture verifies the actual resolved NSS and helper paths passed by `register()`. These are filesystem/transport tests on Linux, not Mach-O execution. |
| **R2-m1 — enabled p11-kit alias excluded** | Track canonical library identities per configuration name and reconcile each complete vendor/admin/user override chain with its effective final configuration. Same-library aliases and restored vendor paths stay enabled; displaced paths and explicit disable/empty/trust/restricted configurations remain excluded, including catalog aliases. | **4 detection regressions** cover enabled alias replacement, restoration after intermediate replacement/disable/empty entries, final exclusions, and an independent explicit exclusion winning over an enabled alias. `test_enabled_alias_override_registers_real_driver_both_methods` additionally detects the SoftHSM alias and registers it through both methods, independently lists both loaded modules with native NSS, and checks preservation of existing bytes and SQL files. |
| **R2-m2 — permanent macOS refusal absent from help** | The shipped Vietnamese macOS help now explains refusal to add to an existing `pkcs11.txt`, including browser profiles and a second driver. It states that retry/restart cannot remove this restriction, forbids deleting/renaming the existing file as a workaround, and gives steps for selecting a separate empty store while preserving the old one. Manual NSS instructions now target a new separate directory and explicitly lack the backend's preservation/recovery guarantees. | Extended `test_unsupported_exclusive_lock_refuses_existing_file` verifies repeat refusal and unchanged native SQL/module snapshots. New `test_macos_new_file_creation_then_second_driver_refusal` checks atomic first creation, private permissions, second-driver refusal, and independent native NSS loading after SQL initialization. Help structure/link checks pass in the full unit/quality suites; the restriction and alternative were also reviewed against the transaction and core-selection code. |
| **R2-m3 — oversized native-NSS test module** | Extract `usb_token_nss_fixtures.py`; split native validation/policy, preservation/recovery, and concurrency tests into three focused modules. | **All 16 original native tests retained**, checked by method-name comparison and executed; **18 native tests now pass** including the two new regressions. By the checker convention (`newline count + 1`), fixture/validation/preservation/concurrency modules are **51 / 124 / 111 / 104 lines**. Every USB test/helper module is at most **172 lines**. |

### macOS layout evidence and limits

Inspected local `scripts/macos/startup-probe.sh`, `spell-probe.sh`, `probe-lib.sh` and `signature-probe.sh`: the office executable is `Contents/MacOS/soffice`, and native libraries/frameworks are under `Contents/Frameworks`. `trial-build.sh` fills the generated `instsetoo_native/util/openoffice.lst` and `sysui/desktop/macosx/Info.plist` before packaging. The local `hst-packaging.patch` contains the instsetoo HST product/include list (PackageSet/GeneratedPackage/Package/ExtensionPackage); the `hst-copyright.patch` sysui plist hunk retains executable `soffice`. The local postprocess patch hunks concern registry generation, not a different library location. The round-2 review records `libnss3.dylib` and `LibreOfficePython.framework` from upstream NSS packaging/Python bootstrap sources; those exact filenames are used by the fixtures.

The complete upstream `instsetoo_native`/`postprocess` packaging lists and `sysui` source tree, reviewer `/tmp` source copies, and a native macOS artifact are **absent in this container**. They were searched for but could not be independently reread without network access. No files were downloaded. Native macOS loading, architecture/quarantine acceptance and a macOS fresh-store GUI smoke test remain unverified; successful Linux layout fixtures and no-tools signing are not presented as macOS runtime acceptance. Existing macOS module files continue to be refused safely.

### Commands and results for these fixes

```sh
python3 -m unittest discover -s tests/unit
python3 scripts/build-extensions.py --verify-reproducible
runuser -u codex -- env HOME=/tmp/usb-round2-home python3 tests/runtime/check-usb-token-setup.py --instdir /opt/hst --workdir /tmp/usb-round2-runtime --display :99 --mode both
bash scripts/ci-quality.sh
python3 scripts/check-extensions.py --self-test
python3 -I scripts/macos/make-dmg-background.py --check
```

| Check | Actual result |
|---|---|
| Required `python3 -m unittest discover -s tests/unit` | **371 run: 370 passed, 0 failures, 0 errors, 1 skipped** |
| USB subset (also executed by quality) | **81/81 passed**, 0 failures/errors/skips, including **18/18 real-NSS tests** |
| Required runtime, `--mode both`: modutil | **9/9 checks passed**, 0 skipped |
| Required runtime, `--mode both`: pkcs11 (both NSS CLI tools disabled in setup) | **10/10 checks passed**, 0 skipped |
| Actual SoftHSM signing | **2/2 signed ODTs** reopened with HST signature state `OK`; independent signature and issuer verification valid, **10/10 reference digests each**, **20/20 total**, 0 unchecked references. Certificate listing, test PIN dialogs and UI signing all executed. Test credentials remain confined to the existing harness. |
| Required `bash scripts/ci-quality.sh` | **44 commands executed, 44 passed, 0 failed**; its **32 unittest invocations run 398 tests**, with the same one upstream skip |
| Extension checker self-tests | **18/18 passed** |
| Reproducible OXT build | **2 identical builds**, SHA-256 `19da5d73fb207363055572df6f6319f7988d3821235cfdfa28ffdcb811d2df1e` |
| Packaged Python bound | **53 modules**, maximum **199 lines**; modified detection/NSS modules **102 / 163 lines** |
| Standalone DMG background check; `git diff --check` | Passed |

The sole unit skip is the unchanged `test_shipped_dictionary_is_complete_after_merge` because the upstream tree is absent. Windows preflight skips its pinned-tarball simulation, and macOS preflight skips upstream configure/patch/icon checks for the same missing inputs. Its existing font/Pillow guard also reports a DMG-background skip; the separate exact background check above passed. **No runtime/signing check was skipped, no dependency was downloaded, and no failing check was waived.**

Logs are `/tmp/usb-round2-{unit,build,runtime,quality,extension-check,dmg}.log`; native runtime results are `/tmp/usb-round2-runtime/results.json`. Copies of those logs and the result JSON are in ignored `tests/output/usb-token-setup/round2/`; PKI/key files were not copied or committed. `/opt/hst` remained mounted read-only. The transaction/worker implementation is unchanged by these fixes, and all earlier preservation, backup, rollback, concurrency and invalid-library regressions passed.
