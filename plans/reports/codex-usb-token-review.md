# USB Token setup: independent review of 87e4abd

Review date: 2026-10-31. Reviewed commit: `87e4abdef42cad61b8b5deeb768e46d98ef9c897` (`feat(signing): add USB token setup for Linux and macOS`), branch `codex/usb-token`.

**Verdict: FIX-THEN-SHIP. Findings: 2 blocker, 3 major, 2 minor, 0 nit.** Existing module preservation fails in real NSS tests, including deterministic deletion of unrelated registrations. Fix the registration backend and add the regression cases below before shipping.

I read the complete commit, the implementation report, the affected extension/menu/dialog/localization/build/checker code, all four new unit-test files, the runtime harness and signing helpers, and `patches/libreoffice/hst-digital-signature.patch`. No product code was modified. `/opt/hst` was kept unchanged. Runtime and adversarial tests used uid 2000 (`codex`), private HOME/profile/database directories and Xvfb `:99`. Source/package retrieval described below was review research; the setup implementation itself contains no network requests.

## Blocker

### B1. The modutil route deletes existing modules from a valid CRLF module database

**Location:** `extensions/hst-vietnamese-tools/python/hst_office/usb_token_nss.py:124` (also `:120`).

The Python parser accepts CRLF, but the file is then handed unchanged to the system `modutil`. With this container's NSS 3.98, registration succeeds while deleting the previous internal-module record and an unrelated, working external-module record. There is no backup or preservation check.

**Reproduced:** create a SQL DB with `certutil`, register `/usr/lib/x86_64-linux-gnu/libnssckbi.so` as `Existing token`, convert `pkcs11.txt` from LF to CRLF, and verify that `modutil -list` still lists it. Call `register()` to add the real SoftHSM2 library. The returned status is `added`; the entire resulting file is just the new library/name stanza. The same experiment with LF preserves both old records. The combined spaces/CRLF experiment also loses the existing comment. Evidence: `/tmp/usb-review-evidence/crlf-roots.log` and `/tmp/usb-review-evidence/adversarial-verified.log`.

The [NSS module-store implementation](https://raw.githubusercontent.com/nss-dev/nss/master/lib/util/utilmod.c) has different newline handling in its reader and deletion writer. Passing a file that the Python reader accepts to that writer is insufficient to guarantee preservation.

**Suggested fix:** immediately refuse CRLF/mixed-newline files before invoking an affected `modutil`, with a Vietnamese explanation and no mutation. Implement any eventual conversion/registration through a protected transaction that preserves unrelated records; do not normalize the live file speculatively. Add a real-NSS regression checking every old module and its configuration after registration. The current CRLF tests exercise only the Python writer; the modutil unit test mocks out the writer entirely.

### B2. Exact-name collision handling does not protect against NSS's prefix deletion

**Location:** `extensions/hst-vietnamese-tools/python/hst_office/usb_token_nss.py:56` and `:124`.

`addition()` avoids equal module names only. The NSS deletion operation used during module addition can match a prefix of an existing unquoted name/library. Thus adding a distinct name can remove an unrelated registration, even with ordinary LF line endings.

**Reproduced:** register a valid existing module named `Feitian ePass2003 old`; then use the production `register()` to add SoftHSM2 as `Feitian ePass2003`. It returns `added`, but both the old name and its library disappear from `pkcs11.txt`. Evidence: `/tmp/usb-review-evidence/prefix.log`. This is not a duplicate-library case: the old module is libnssckbi and the new one is SoftHSM2.

**Suggested fix:** account for the native writer's matching behavior. Choose names that cannot prefix-match any existing name, and refuse/defer the modutil route for conflicting raw library prefixes. Prefer an audited registration operation with an explicit invariant that all unrelated records survive. Add real-NSS tests for exact collisions, prefix collisions, quoted/unquoted existing records and library-prefix collisions; checking the argv of a mocked failing subprocess does not establish preservation.

## Major

### M1. The fallback's final change check still permits lost updates

**Location:** `extensions/hst-vietnamese-tools/python/hst_office/usb_token_nss.py:80`–`:83`; lock at `:109`–`:111`.

The read/compare and `os.replace()` are separate operations. NSS, Firefox, Thunderbird and ordinary `modutil` do not acquire `.hst-usb-token.lock`. A writer that commits after the comparison is silently overwritten by the replacement. Atomic replacement prevents a partial file; it does not make this read-modify-write transaction atomic.

**Reproduced:** while `register()` holds its normal HST lock, a scheduling hook immediately before the real `os.replace()` runs an actual `modutil -add` for a second valid module. That command succeeds and its stanza is present. The fallback then replaces the file, loses the second module, and returns `added`. Only the interleaving was controlled; the competing writer and database were real. Evidence: `/tmp/usb-review-evidence/adversarial-verified.log`, case `concurrent real modutil before replace`.

Separately, I initialized NSS in a running `/opt/hst` soffice against the very DB being modified. `/proc/<pid>/fd` confirmed open `cert9.db` and `key4.db` descriptors. Setup proceeded and correctly requested a restart. This ordinary idle-open case passed; it does not exercise simultaneous writes or establish an exclusive database lock. Evidence: `/tmp/usb-review-evidence/office-adversarial.log`, `open-db`.

**Suggested fix:** do not claim safe concurrent editing using an HST-only lock. Defer direct module-file mutation until exclusive access can actually be established, including the owning browser/profile and other HST processes; otherwise fail without mutation. Use a registration mechanism whose concurrency contract is understood and tested. Keep a recoverable original and verify preservation without blindly restoring over somebody else's later update. Add an interleaving test at the final compare/replace boundary. `tests/unit/test_usb_token_nss.py:78` changes the file before calling the writer, so it cannot catch this race.

### M2. Configured-path normalization can register into a DB that core never selects

**Location:** `extensions/hst-vietnamese-tools/python/hst_office/usb_token_db.py:37`–`:53`; `extensions/hst-vietnamese-tools/python/hst_office/usb_token.py:31`–`:39`.

The selector gives any configured `CertDir` priority over core's `NSSPath`, strips `sql:` and expands `~`. Core tests the configured filesystem path itself and can reject it, falling back to a browser profile. The helper neither persists a corrected configured path nor always accounts for a path already cached before NSS initialization.

**Reproduced in the installed application:** set `CertDir` to `sql:/absolute/existing-db` and provide a valid Firefox profile. Before setup, core reports the Firefox DB and `IsNSSinitialized=False`. Setup reports successful registration into `existing-db` and gives the normal signing instruction. After PDF export, core still uses Firefox; after a full restart, it still uses Firefox. This is a persistent wrong-DB success. Evidence: `/tmp/usb-review-evidence/office-adversarial.log`, `sql-prefixed-configured`.

A stale configured directory also diverges: with NSS tools available, setup creates that directory and reports success while core uses the Firefox path it cached earlier in the session. Without the tools, setup writes the registration and then raises its “Chưa tạo được kho chứng thư” error because initialization occurs in the other DB. Evidence: `/tmp/usb-review-evidence/office-stale-with-tools.log` and `office-adversarial.log`.

**Suggested fix:** align accepted `CertDir` syntax and existence rules with core. Treat `NSSPath` as authoritative unless deliberately switching it. If repairing/creating a configured path, persist the accepted absolute filesystem path and explicitly require a restart whenever core has selected a different path, including before `IsNSSinitialized` becomes true. Verify the effective core path before reporting readiness. Test with actual UNO configuration and Firefox present; the current unit tests assume the helper's desired precedence instead of checking core.

### M3. No-tools setup reports unusable libraries as successfully registered forever

**Location:** `extensions/hst-vietnamese-tools/python/hst_office/usb_token_detect.py:73`; `extensions/hst-vietnamese-tools/python/hst_office/usb_token_nss.py:125`–`:127`; `extensions/hst-vietnamese-tools/python/hst_office/usb_token.py:53`–`:57`.

Detection only proves that a readable regular file exists. The fallback appends its path and returns `added`; subsequent invocations return `existing` solely from the text record. There is no load, architecture, dependency or macOS quarantine assessment. Because neither row is an error, the architecture/retry guidance is not displayed.

**Reproduced:** a plain-text file named like a driver returns `added`, then `existing`; independent `modutil -list` reports that module as **Not loaded**, with no slots. Evidence: `/tmp/usb-review-evidence/adversarial-verified.log`, `invalid driver without tools`. This proves the false-success mechanism on Linux. The corresponding macOS architecture/quarantine failures were assessed from code, not executed on a Mac.

**Suggested fix:** distinguish “configuration written, driver not yet verified” from a usable loaded module. Validate loadability in an isolated helper compatible with the HST process architecture, without logging in or requesting a PIN, or verify on next startup and retain a pending state until then. Report incompatible architecture, missing dependencies and OS-blocked loading in Vietnamese. Do not remove quarantine or alter Gatekeeper policy. A driver matching the machine's architecture can still mismatch an HST process running under Rosetta. Add incompatible/corrupt-library cases and native macOS validation before claiming that fallback setup is complete.

## Minor

### m1. Ordinary failures expose English exception text

**Location:** `extensions/hst-vietnamese-tools/python/hst_office/usb_token.py:72`; `extensions/hst-vietnamese-tools/python/hst_office/usb_token_nss.py:129`.

The Vietnamese wrapper interpolates arbitrary Python/OS exception text. On a user-owned NSS directory with mode `0500`, the actual result is `Chưa hoàn tất thiết lập USB Token: [Errno 13] Permission denied: '.../.hst-usb-token.lock'`. Lock contention and malformed INI errors have the same untranslated-message problem. No Python traceback was shown in this reproduction, and the read-only DB was unchanged.

**Suggested fix:** map expected permission, lock, configuration, I/O and timeout failures to Vietnamese messages with safe path details. Use a Vietnamese generic failure for unexpected exceptions rather than displaying `str(exc)`. Test real English OS exceptions; the existing action test injects a Vietnamese exception and therefore cannot verify this requirement.

### m2. Catalog detection overrides an explicit p11-kit exclusion

**Location:** `extensions/hst-vietnamese-tools/python/hst_office/usb_token_detect.py:62`–`:69` (filter at `:49`).

The p11-kit reader honors `disable-in`, but the catalog has already added the same file. A user config with `module: /usr/lib/libcastle.so.1.0.0` and `disable-in: soffice.bin` still results in that library being detected and registered through its catalog entry. This can reintroduce a module explicitly disabled for compatibility reasons. Global p11-kit `user-config` policy is also not read. The [p11-kit configuration reference](https://p11-glue.github.io/p11-glue/p11-kit/manual/pkcs11-conf.html) defines these controls; they are not a security boundary.

**Suggested fix:** resolve effective p11-kit configuration and canonical-path exclusions before merging catalog candidates, including the global configuration policy. Add a fixture where the excluded path is a real catalog candidate. Existing p11-kit override tests use uncatalogued `/old.so` and `/new.so`, so they miss this interaction. Evidence: `/tmp/usb-review-evidence/adversarial-verified.log`, `p11-kit disabled catalog driver`.

## Rerun results

The initial container lacked dependencies. The exact initial unit command ran **312 tests: 310 passed, 1 import error, 1 skipped** because PyYAML was missing. The initial runtime invocation failed importing `cryptography` before any mode/check ran. Initial quality was **40 commands, 9 failures**, caused by missing PyYAML, Pillow and shellcheck. I installed the test prerequisites in the container, rebuilt the extension from the reviewed tree, and reran. These environment failures are not attributed to this commit.

| Check after prerequisites | Exact result |
| --- | --- |
| `python3 -m unittest discover -s tests/unit` | **336 run; 335 passed, 0 failures, 0 errors, 1 skipped** |
| USB-specific unit discovery | **46 run; 46 passed, 0 failures/errors/skips**; included in the 336 above |
| Runtime `--mode both`: modutil | **9/9 checks passed** |
| Runtime `--mode both`: pkcs11, both tools disabled inside extension | **10/10 checks passed** |
| Additional runtime `--mode pkcs11 --cold` | **10/10 checks passed** |
| Independent ODT signature verification | **3/3 documents valid; 10/10 reference digests each; 0 unchecked references** |
| `bash scripts/ci-quality.sh` | **40 commands executed, 0 failures** |
| `python3 scripts/check-extensions.py --self-test` | **17/17 passed** |
| Reproducible extension build | **2 identical builds**, SHA-256 `f6efe6e6160c014d3b3dcae866bdc026da3637bc5dc9293494c5b91f84f0e7a5` |
| Packaged Python size | **50 modules, maximum 199 lines** by checker convention; new modules 74/98/76/133 |
| Standalone DMG background check; `git diff --check` | Both passed |

The unit skip is `test_shipped_dictionary_is_complete_after_merge` because the upstream tree is absent. Quality explicitly skips the Windows pinned-tarball simulation, macOS option/patch/icon checks, and the DMG background guard. The latter guard skips under its pipeline despite available dependencies; the standalone `python3 -I scripts/macos/make-dmg-background.py --check` passed. There were no runtime skips after prerequisite installation. Physical tokens, native macOS and Windows runtime remain untested.

Runtime commands, using already-running Xvfb:

```sh
runuser -u codex -- env HOME=/tmp/usb-review-home python3 \
  tests/runtime/check-usb-token-setup.py --instdir /opt/hst \
  --workdir /tmp/usb-review-runtime/ready --display :99 --port 2183
runuser -u codex -- env HOME=/tmp/usb-review-home python3 \
  tests/runtime/check-usb-token-setup.py --instdir /opt/hst \
  --workdir /tmp/usb-review-runtime/cold --display :99 --port 2183 \
  --mode pkcs11 --cold
```

Logs and review-only scripts are under `/tmp/usb-review-evidence`; runtime result JSON is under the two work directories above. They are not part of the commit. The custom probes are exploratory cases, not an additional formal test-suite pass count.

## Adversarial coverage and safety observations

| Case | Observed result |
| --- | --- |
| `/Applications/VNPT-CA Token Manager.app/...`-shaped path containing spaces | Works through both backends; real NSS loads SoftHSM2. Native runtime also signs successfully using a spaced path. |
| Quotes, backslashes and `=` in library filenames | Eight fresh-DB probes, four per backend: each loads the real SoftHSM2 module and returns `existing` on repeat. See `quote-check.log`. |
| Run twice / aliases | Runtime verifies byte-identical second invocation and symlink deduplication. |
| Other modules, comments and CRLF | Fallback preserves the original byte prefix and mode `0640`. LF/modutil baseline preserves ordinary unrelated records. CRLF/modutil and prefix-name collision fail as B1/B2. |
| New file permissions | Existing unit test verifies `0600`; directory creation requests `0700`; no executable script is written by setup. |
| No driver installed | Isolated empty catalog/p11-kit search returns no modules, displays guidance and does not create the selected DB. |
| Read-only NSS directory | Tested as uid 2000, mode `0500`: fails without changing DB bytes. English error is m1. |
| Running soffice with same DB open | Open cert/key descriptors confirmed; registration returns and requests restart. No assertion that an idle SQLite connection holds a permanent exclusive lock. The simultaneous writer reproduction separately fails as M1. |
| Legacy `secmod.db` / DBM | Created a real DBM fixture with certutil. `user_database()` rejects it; SHA-256 snapshots of `cert8.db`, `key3.db`, `secmod.db` remain identical. No DBM migration was observed. |
| Root execution | Actual uid-0 call to the ownership guard rejects before creating the target directory. Production contains no sudo/elevation request. |
| DB selection | Shared `~/.pki/nssdb` is exercised by the runtime; explicit ordinary absolute path, Snap Firefox and Flatpak Thunderbird agree with actual core. All Linux/macOS root lists have unit coverage. Configured-path divergence is M2. |
| Windows | Menu remains visible and returns the Vietnamese “Không cần thiết lập NSS trên Windows” message. NSS/fcntl imports are deferred into setup, which this branch does not call. Unit coverage passes; no Windows executable was run. |

The setup code has no PIN entry, credential arguments, login operation, key export or secret logger. `run_tool()` uses argument arrays with no shell and discards stdout/stderr/stdin. It creates an empty-password **internal NSS DB**, not a token PIN. Registering/loading vendor modules necessarily executes vendor code; arbitrary vendor behavior is outside what this Python audit can establish.

Writes made explicitly by setup are the selected user's NSS directory/files, its empty HST lock file and temporary module file, plus **the user's HST `CertDir` preference** on fallback. Thus “only the NSS DB” is not literally the full write scope. The preference change is documented in the implementation report. The registration bugs above can affect a shared browser database. No system driver installation, permission elevation, quarantine removal or direct network access occurs in the feature.

The runtime PKI deliberately creates disposable CA/private-key material and fixed test PINs. `signature_pki.py` writes a test `ca.key`, temporary user key files (removed after importing into SoftHSM), and the SoftHSM token store. Its pre-existing `describe()` can write a test PIN file; this USB runtime does not call it. These are test fixtures, not production user-secret handling, and none is committed.

The new menu and normal result strings are Vietnamese in both locale catalogs; `run()` explicitly loads Vietnamese and the native dialog helper uses Vietnamese buttons. The signing instruction corresponds to the File ribbon's digital-signature action; the help also documents the nested classic-menu route. The ordinary permission failure violates the all-Vietnamese requirement (m1). No user traceback was observed. The runtime inspects text through UNO and dispatches the command directly; it does not prove every menu placement or native platform layout.

The tests provide real end-to-end signing evidence, but do not prove the preservation claims. In particular, parsing output with the same parser that produced it is insufficient evidence of NSS compatibility; the separate real-NSS probes above establish the common quoting cases. `test_catalog_requires_evidence_and_no_invented_ca_names` checks for a URL string and empty lists, not that a source supports a path. The checker rejects a direct network import and stale catalog data, but its regex is not a general sandbox for subprocess behavior. Inspection found only the intended local NSS commands.

## Catalog provenance audit

There are **20 entries: 11 with paths, 9 explicitly empty; 27 path patterns**. I checked every entry below. A conventional search directory is a candidate, not evidence that a vendor installer places its library there. Empty paths are an explicit detection gap, not invented support.

| Catalog entry (line in `data/hst/pkcs11-modules.json`) | Evidence and limits |
| --- | --- |
| VNPT-CA / macOS, 22 | Independently downloaded Apple Silicon package `31122025145306.pkg` from the [official download page](https://vnpt-ca.vn/download-page). Package version 1.0.1 installs the app under `/Applications`; payload contains the exact `Contents/Resources/libvnptca_p11_v8.dylib`. Its postinstall copies it to `/usr/local/lib/libvnptca_p11_v8.dylib`. Both catalog paths are real. The inspected library is a fat Mach-O with x86_64 and arm64 slices. Installer/scripts were not executed. |
| Feitian / Linux, 32 | The [referenced application's module mapping](https://github.com/PeculiarVentures/webcrypto-local/blob/master/packages/cards/lib/card.json) contains `/usr/lib/libcastle.so.1.0.0`. `/usr/lib/x86_64-linux-gnu` and `/usr/local/lib` are explicitly conventional guesses of location, not verified installer destinations. |
| Feitian / macOS, 43 | The same mapping and [CertDigital's installation instructions](https://www.certdigital.ro/wp-content/uploads/2025/02/Instructiuni-pentru-instalare-dispozitive-Criptografice-CertDigital-v3.pdf) support `libcastle.1.0.0.dylib` under `/usr/local/lib`. The shipped `libcastle*.dylib` is broader than that exact evidence. No proprietary load test. |
| Thales SafeNet / Linux, 52 | The referenced mapping contains `/usr/lib/libeTPkcs11.so`. The other three directories are conventional candidates; no Linux vendor package was inspected. |
| Thales SafeNet / macOS, 64 | The mapping contains `/usr/local/lib/libeTPkcs11.dylib`. [DigiCert's instructions](https://knowledge.digicert.com/solution/safenet-hardware-token-not-detected-in-adobe-reader-on-mac-os) describe that directory with `LibeTPkcs11.dylib` capitalization. Verify against an installed package on a case-sensitive volume before claiming exhaustive detection. |
| Bit4id / Linux, 73 | The [vendor manual](https://cdn.bit4id.com/es/middleware/Linux/Linux.html) explicitly lists `/usr/lib/bit4id/libbit4xpki.so` and `/usr/share/bit4id/libbit4xpki.so`. The two other prefixes are conventional candidates. |
| Bit4id / macOS, 85 | The referenced application mapping contains `/System/Library/bit4id/libbit4xpki.dylib`. That establishes a historical integration path, not current macOS installer compatibility. `/usr/local/lib/libbit4xpki.dylib` is a conventional candidate without a verified current package. |
| OpenSC / Linux, 95 | [OpenSC documents its PKCS#11 module](https://github.com/OpenSC/OpenSC/wiki/Using-OpenSC); this container actually has the two x86_64 paths, resolving to the installed module. Other entries are distro-layout candidates. File presence does not prove that a particular CA-customized token works. |
| OpenSC / macOS, 108 | [OpenSC's own instructions](https://github.com/OpenSC/OpenSC/wiki/macOS-Quick-Start) give `/Library/OpenSC/lib/opensc-pkcs11.so` and copies in `/usr/local/lib`. `/opt/homebrew/lib` is a Homebrew-prefix candidate rather than evidence from the inspected vendor package. |
| MISA / macOS, 119 | [MISA's PDF-signing instructions](https://helpesign.misa.vn/knowledge-base/ky-file-pdf-tren-macbook/) give the exact `/usr/local/lib/misaca_csp11_v2.dylib` path. The separate installation guide is not proof of arm64 compatibility; no package/load test was performed. |
| EasyCA / macOS, 128 | Independently downloaded `Update_260605.zip` linked from [EasyCA's page](https://easyca.vn/tai-ve/). The DMG contains `Easyca_csp11_v1.pkg`; `PKCS11.pkg/Payload` contains `easyca_csp11_v1.dylib` and `PackageInfo` specifies `/usr/local/lib`. The inspected dylib has x86_64 and arm64 slices. No installer, archive Python script or dylib was executed. |
| Viettel-CA / Linux, 137 | Empty. No Linux PKCS#11 filename established. |
| Viettel-CA / macOS, 144 | Empty. The [official page](https://viettel-ca.vn/tai-ve/viettel-ca-download) does link a Mac Token Manager V6 archive; a filename/install path was not verified. |
| BKAV-CA / Linux, 151 | Empty. The [official download page](https://bkavca.vn/tai-ve) supplies no verified Linux library path for this catalog. |
| BKAV-CA / macOS, 158 | Empty. No macOS PKCS#11 path established from that page. |
| FPT-CA / Linux, 165 | Empty. The cited CA site was inaccessible through the review browser; no independent library evidence obtained. |
| FPT-CA / macOS, 172 | Empty, with the same evidence limitation. |
| VNPT-CA / Linux, 179 | Empty. The verified macOS package does not establish a Linux filename. |
| MISA / Linux, 186 | Empty. The cited macOS installation guide does not establish a Linux filename. |
| EasyCA / Linux, 193 | Empty. The verified macOS package does not establish a Linux filename. |

Downloaded evidence SHA-256:

- VNPT `31122025145306.pkg`: `f9761bfdec8c120c0274b6094d431474928d8066361cf57558f764b799691beb`.
- EasyCA `Update_260605.zip`: `c442fd10f9c6b6a0bfdbf592393330b2f44b3a8d2fc018dd162b54de50de8d7a`.

The VNPT bundle path is substantiated, not invented. The catalog appropriately leaves unknown CA filenames empty, but its conventional-directory candidates and historical third-party mappings must remain labeled as candidates. I did not validate macOS code signatures, notarization, Gatekeeper behavior or actual driver loading. Those are still native acceptance checks, and universal architecture alone does not settle them.

## Release decision

**FIX-THEN-SHIP.** Require fixes for B1/B2 and M1–M3, Vietnamese error handling, and the p11-kit exclusion regression before release. Retain the passing SoftHSM signing tests and add real-NSS preservation and configured-path regression cases. The current **335 passing unit tests, 19/19 required runtime checks and 40/40 quality commands** do not cover the demonstrated loss of existing registrations.
