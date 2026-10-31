# USB Token setup: independent review, round 2

Review date: 2026-10-31. Branch: `codex/usb-token`. Reviewed HEAD: `1213176b93aa284d51012a4a8057efc929dcc3c6`; baseline: `87e4abdef42cad61b8b5deeb768e46d98ef9c897`. Scope: the entire `87e4abd..1213176` diff, all seven production USB modules, the new tests/checker changes, and the affected help and core-selection integration.

**Verdict: FIX-THEN-SHIP. New findings: 0 blocker, 1 major, 3 minor, 0 nit.** All seven original failure scenarios are fixed in the before/after experiments below. The new macOS NSS locator misses the standard application layout; an enabled p11-kit alias can also disappear from detection. The required Linux tests are green, including actual SoftHSM signing in both modes.

Only this report is committed. No product code was edited. The original commit was checked out in a detached worktree at `/tmp/usb-review-2-before`. `/opt/hst` was mounted read-only throughout. Native runtime and independent registration probes used uid 2000 (`codex`), Xvfb `:99`, and private HOME/profile/SQL DB directories. The normal unit suite ran as root; its own native fixtures bypass their root guard, whereas the independent probes exercised the actual guard as an ordinary user. Installed NSS is 3.98 (`libnss3-tools 2:3.98-1ubuntu0.3`); SoftHSM is 2.6.1. The supplied test dependencies were available; only ripgrep needed installation.

## New major finding

### R2-M1. The macOS NSS locator cannot find NSS in the standard app bundle

**Location:** `extensions/hst-vietnamese-tools/python/hst_office/usb_token_nss.py:114`, called at `:133`.

The non-Linux search checks the executable's directory, `sys.base_prefix`, and `sys.base_prefix.parent / "Frameworks"`. For an app with its executable in `Contents/MacOS` and bundled Python under `Contents/Frameworks/LibreOfficePython.framework`, none is `Contents/Frameworks`, where the bundled `libnss3.dylib` resides. The last candidate instead becomes `Contents/Frameworks/Frameworks`, or a directory inside the Python framework when the prefix includes its version. Every candidate registration fails before the worker starts, including first-time creation of a module file, which the revised implementation still intends to support on macOS.

**Evidence:** filesystem fixtures containing `Contents/Frameworks/libnss3.dylib`, with the actual production `nss_library()` and only platform/executable/prefix values substituted, returned `Không tìm thấy thư viện NSS của HST Office; chưa thay đổi kho chứng thư.` in **4/4 cases**: app names `HST.app` and `HST Office.app`, each with a framework-root and version-directory Python prefix. The library file existed in every case. These are path-resolution reproductions on Linux, not native macOS loading tests. The layout is supported by the upstream [Python loader bootstrap](https://github.com/LibreOffice/core/blob/master/pyuno/CustomTarget_pyuno_pythonloader_ini.mk), [NSS packaging](https://github.com/LibreOffice/core/blob/master/external/nss/ExternalPackage_nss.mk), and [Darwin installation directories](https://github.com/LibreOffice/core/blob/master/configure.ac). Retrieved source copies are in `/tmp/usb-review-2-evidence/upstream`; the exact HST macOS artifact was not available.

**Fix suggestion:** resolve the running application's `Contents/Frameworks` through its bootstrap/bundle location or the already-loaded NSS library, rather than deriving it from Python's immediate parent. Exercise the bundled helper interpreter as well. Add app-layout fixtures with spaces and a native macOS fresh-DB smoke test before claiming that route works. This is separate from the intentional refusal to append to existing macOS module files.

## New minor findings

### R2-m1. A p11-kit override to an alias of the same driver excludes the enabled driver

**Location:** `extensions/hst-vietnamese-tools/python/hst_office/usb_token_detect.py:58`, with filtering at `:96`.

Any textual change of the `module` field adds the old canonical path to `excluded`, even when the replacement resolves to exactly the same library. The final enabled entry is subsequently filtered out. Exclusions also accumulate across superseded intermediate configurations instead of being reconciled with the final configuration.

**Reproduced against real NSS on both revisions:** vendor `token.module` specifies `/usr/lib/libcastle.so.1.0.0`; the user's same-named override specifies `/opt/token/active.so`, a symlink to that driver. There is no `disable-in`, `enable-in`, empty override, or trust exclusion. The driver is real SoftHSM. On `87e4abd`, detection returns one candidate, registration returns `added`, and native `modutil -list` shows it loaded. On HEAD, detection returns `[]`; registration changes nothing. The UI therefore follows its missing-driver branch despite an explicitly enabled, usable driver. Evidence: `policy-alias-before.log`, `policy-alias-head.log`, and `policy-alias.py` under `/tmp/usb-review-2-evidence`.

**Fix suggestion:** compare canonical identities before excluding an overridden path, and derive exclusions from the effective final configuration. Preserve explicit disable/empty-override precedence. Add regressions for same-library aliases and vendor → administrator → user overrides that restore an earlier library.

### R2-m2. The macOS help omits the new permanent refusal for existing module files

**Location:** new restriction at `extensions/hst-vietnamese-tools/python/hst_office/usb_token_transaction.py:45`; affected help at `extensions/hst-vietnamese-tools/help/ky-so-usb-token.html:63`, `:69`, and `:73`.

The implementation deliberately refuses every addition to an existing `pkcs11.txt` on macOS. Closing applications or restarting cannot make this path supported. This affects normal browser profiles and adding another driver to a database created by an earlier successful setup. The shipped help still describes the general macOS setup flow and says manual setup is needed only for unrecognized driver paths. The implementation report documents the narrowed contract, but users do not see that report.

**Evidence:** selecting the Darwin branch while operating on a real SQL fixture with an existing roots module refuses the addition and preserves all original bytes. See `extra-probes.log`, case `macos-existing-file`. The message itself is Vietnamese and accurately states the limitation; the help is the inconsistent part. This observation does not require a native macOS execution claim.

**Fix suggestion:** document the existing-file restriction and an actionable, preservation-safe alternative in the shipped Vietnamese help. Make clear that repeating setup or restarting cannot add another module on this route. Do not imply that arbitrary direct `modutil` rewrites have the preservation guarantees of the new backend.

### R2-m3. The new real-NSS test module exceeds the requested 199-line bound

**Location:** `tests/unit/test_usb_token_nss_real.py:200`.

`wc -l` reports **308 lines** in this new authored Python module. All shipped Python modules satisfy the bound, but the requested per-module limit is not met across the new code. The extension checker only measures files in the OXT, so its passing result does not cover this test file.

**Fix suggestion:** extract shared native-NSS fixtures and split preservation/concurrency and validation/error cases into modules of at most 199 lines. Retain all 16 native tests and their independent NSS assertions.

## Round-1 before/after verification

The reviewer-authored `reproduce.py` was run unchanged against the detached baseline and HEAD. Each case uses a fresh `certutil -N -d sql:<directory> --empty-password` database, real NSS roots and/or SoftHSM libraries, and independent `modutil -list` output. Snapshots record SHA-256 for `pkcs11.txt`, `cert9.db`, `key4.db`, and the presence/absence of `secmod.db`. No NSS command was mocked. Boundary scheduling and injected storage errors are identified separately below.

| Original finding | `87e4abd` observed result | HEAD observed result and disposition |
| --- | --- | --- |
| **B1: CRLF deletion** | Native listing confirms `Existing token` before setup. The modutil route returns `added`; the live file becomes only the new SoftHSM stanza, losing the internal and roots records. The old no-tools route preserves the CRLF prefix. | Both routes return a Vietnamese unsupported-newline error before mutation. All tracked file hashes remain identical, and native listing retains the existing module. **Fixed by safe refusal**, not normalization. Relevant code: `usb_token_nss.py:31`, `usb_token_worker.py:50`. |
| **B2: prefix deletion** | Register roots as `Feitian ePass2003 old`, then add SoftHSM as `Feitian ePass2003`. The modutil route returns `added` and removes the roots record. | Both routes return `added`; the entire original byte prefix and mode `0640` survive. Native NSS loads both roots and `HST Feitian ePass2003 f5c59ef723e5c14d`. SQL files remain unchanged. The suite additionally passes exact/quoted-name and raw-library-prefix cases. **Fixed.** Relevant code: `usb_token_nss.py:61`, `usb_token_worker.py:56`, `usb_token_transaction.py:112`. |
| **M1: lost concurrent update** | At the old final `os.replace` boundary, real `modutil` successfully adds `Concurrent roots`, which is present before replacement and missing afterward. A second reproduction calls full `register()` and independently confirms its HST flock is held; it still returns `added` after losing the native update. | At the new append boundary, real `modutil` waits, then completes after the transaction; native listing contains both registrations. The suite's separate already-initialized native NSS process also waits and preserves both records. **The demonstrated race is fixed.** Relevant code: `usb_token_transaction.py:26`, `:44`, `:85`. |
| **M2: wrong selected DB** | With real UNO `CertDir=sql:<existing-configured-db>` and Firefox present, setup registers in configured while core selects Firefox before setup, after PDF export, and after restart. Both modes reproduce it. For a missing ordinary configured directory, both create/register there while core still uses cached Firefox; the no-tools mode then reports the initialization failure. | Both modes register in core's Firefox DB; the existing ignored configured DB remains untouched, and the missing configured directory is not created. Core uses the same DB through PDF export and restart. Absolute configured paths, literal-tilde refusal and fallback/restart also pass. **Fixed.** Relevant code: `usb_token_db.py:48`, `usb_token.py:14`, `:31`. |
| **M3: unusable driver success** | A text file named `vendor.so` on the no-tools route returns `added`, then `existing`; independent NSS reports `Not loaded`. | Both attempts return a Vietnamese load error and preserve all DB hashes. Native tests also cover previously registered broken modules, wrong ELF architecture and missing dependencies. **Fixed for the demonstrated load failures.** Relevant code: `usb_token_worker.py:24`, `:52`. Native macOS architecture/quarantine acceptance remains untested. |
| **m1: English failures** | As uid 2000 with the real SQL directory mode `0500`, the action displays `[Errno 13] Permission denied: '.../.hst-usb-token.lock'`. | The action displays `Không có quyền ghi kho chứng thư. Hãy chọn kho thuộc tài khoản đang sử dụng.` and retry guidance; no English exception, errno, traceback, or signing-success instruction. DB hashes are unchanged on both revisions. **Fixed.** Relevant code: `usb_token_errors.py:14`, `usb_token.py:68`. |
| **m2: excluded catalog driver** | A catalog-path SoftHSM symlink plus `disable-in: soffice.bin` is still detected, registered and loaded by NSS. | Detection returns no candidates, registration adds nothing, and all DB hashes remain identical. Canonical alias exclusions, empty overrides and global policy cases also pass their existing tests. **Original case fixed**, with the distinct enabled-alias regression R2-m1 above. Relevant code: `usb_token_detect.py:38`, `:96`. |

For B1, the baseline's final module file is exactly:

```text
library=/usr/lib/softhsm/libsofthsm2.so
name=Feitian ePass2003

```

For the corresponding HEAD CRLF fixture, `pkcs11.txt` SHA-256 is `ad7aca7cf35cc82133d4814bcbfddc6e71f8e67cf7c4ca727bc74180727a3995` both before and after. These are separate fresh databases; hashes are compared within each experiment, not across revisions with different embedded paths.

The M1 full-register baseline evidence records `hst_lock_held=true`, `native_writer_returncode=0`, `present_before_replace=true`, and returned status `added`, followed by a native listing without `Concurrent roots`. HEAD's independent boundary experiment records the writer waiting and a final native listing with both names. The HEAD scheduling hook wraps the production transaction's `os.write`; it does not replace the native writer or its locking behavior.

For M2, the rebuilt original OXT was loaded into the real read-only `/opt/hst` using a private bundled-extension directory. The same independent UNO script runs both revisions, in both modes, for `sql:` and missing-directory cases. The branch's additional runtime harness covers **10 cases / 34 assertions** including absolute paths, tilde refusal and fallback. This verifies actual core behavior rather than assuming unit-test selector precedence.

## Required test results and exact counts

| Check on `1213176` | Result |
| --- | --- |
| `python3 -m unittest discover -s tests/unit` | **358 run: 357 passed, 0 failures, 0 errors, 1 skipped** |
| USB-specific unit discovery, separately rerun | **68 run: 68 passed, 0 failures/errors/skips**, including **16 real-NSS tests**; these are a subset of the 358 |
| `check-usb-token-setup.py --mode both`: modutil | **9/9 checks passed, 0 skipped** |
| Same required run: pkcs11, both NSS CLI tools disabled in setup | **10/10 checks passed, 0 skipped** |
| Additional `--mode both --cold`: modutil / pkcs11 | **9/9 + 10/10 passed, 0 skipped** |
| Actual SoftHSM signing across required and cold runs | **4/4 signed ODTs independently valid; 10/10 reference digests each; 0 unchecked references**. Each run lists the token certificate, exercises the test PIN dialog and UI signing, and reopens the signed document with HST signature state `OK`. |
| `check-usb-token-review.py --mode both` | **10/10 cases, 34/34 checks passed**, 0 skipped |
| `bash scripts/ci-quality.sh` | **41 commands executed, 41 passed, 0 failed**; its 29 unittest invocations run 385 tests including brand/checker tests, with the same one upstream skip |
| `python3 scripts/check-extensions.py --self-test` | **18/18 passed** |
| Reproducible OXT build | **2 identical builds**; SHA-256 `7a00eabb1a571b00b89c717fe2284e907abd1db2dfa35926811b221359743fb3` |
| Packaged Python size | **53 modules, maximum 199 lines** by checker convention (`text.count("\n") + 1`). USB modules: action 70, DB 104, detection 99, errors 26, NSS 142, transaction 149, worker 83. The unshipped test-file exception is R2-m3. |
| Standalone DMG background check; `git diff --check` | Both passed |

**No check failed because the host-only upstream tree was absent, and no branch failure was waived.** The one unit skip is `test_shipped_dictionary_is_complete_after_merge` (`LibreOffice tree not present`). Windows preflight explicitly skips the pinned-tarball simulation because `upstream/cache/libreoffice` is absent. macOS preflight explicitly skips configure-option/patch/icon checks because `/work/upstream/libreoffice` is absent. These check implementations are unchanged by `87e4abd..HEAD`.

macOS preflight also prints `SKIP dmg background: needs Pillow and fonts-liberation`; this is its existing dependency/font guard, not an upstream-tree failure. Running `python3 -I scripts/macos/make-dmg-background.py --check` separately returned 0. Runtime/signing checks were not skipped or replaced with historical round-1 results.

## Additional preservation, recovery and safety audit

| Probe or inspection | Result and limit |
| --- | --- |
| Successful append and recovery copies | Original module prefix and mode `0640` retained; `cert9.db` and `key4.db` hashes unchanged. Private backup directory is `0700`, copies are `0600`, owned by uid 2000, and match the originals byte-for-byte. Successful additions retain their backup. Repeat registration is byte-identical and does not create another backup. |
| Partial write returning a short count | Injected a real five-byte write before returning the short count. Original module bytes restored exactly; SQL hashes unchanged; incomplete backup directory removed. |
| Partial write followed by ENOSPC | Injected a real five-byte write and then an OS error. Exact same restoration result. |
| Fsync failure after append | Injected EIO at the post-append sync. Truncation and rollback sync restore the original snapshot. |
| Rollback itself fails | Injected partial append and a failing truncate. Original prefix remains, existing roots still load, and an exact recovery copy is retained. The raised Vietnamese error names its backup directory. No false claim that the live file was restored. |
| Backup creation/copy fails | Injected ENOSPC during copy. Live DB remains unchanged and partial backup is removed. |
| SQL locks, initialized native NSS, late replacement | The 16-test native suite passes lock refusal, an already-initialized NSS writer waiting, and a real native-generated replacement winning without HST restoring over it. Independent final-boundary tests also pass. |
| Missing module file | Uses non-replacing `link()` and mode `0600`; the two signing modes exercise new-file creation, repeat setup and core SQL initialization after restart. Existing files on unsupported lease platforms are deliberately refused. |
| macOS-shaped vendor path with spaces; quote, backslash and equals filenames | **8/8 independent real-NSS probes** pass: four path shapes in each mode, each `added` then `existing`, both modules loaded and original prefix preserved. These validate path transport/quoting on Linux, not Mach-O loading or the app-bundle locator. |
| Vietnamese messages | New authored errors and mapped permission/lock/configuration/I/O exceptions are Vietnamese. Actual result dialogs are Vietnamese even with the office UI seeded as English. Vendor output is discarded. The raw errors in direct fault-injection logs are below the UI mapping layer. |
| PIN/key operations | Production calls no token login, PIN API, key export, signing, or private-key parsing. Worker NSS initialization/module loading/shutdown is isolated from the running office. Empty-password `certutil -N` now targets only a disposable probe DB. The transaction **does copy the entire `key4.db` opaquely** as requested recovery data; that is a file copy, not token-key extraction. Retained copies can contain pre-existing NSS secrets and remain private. |
| Elevation/network | No production sudo/elevation request, direct network client, shell invocation or download was found. NSS subprocesses receive argument arrays and DEVNULL stdin/stdout/stderr. Driver initialization executes installed vendor code, whose internal behavior this audit cannot establish. Apt/source retrieval performed for review is separate from feature execution. |

These tests establish the recorded interleavings and recoverable write-error behavior. They do not prove resilience to every process kill, power loss, filesystem implementation or lease expiry. The worker has a 30-second subprocess deadline, Linux leases have a finite break interval, and directory fsync/crash-recovery replay are not implemented. No native macOS, Windows runtime or proprietary physical token was available. Safe refusal on unsupported existing-file platforms is preferable to weakening preservation, but it must be reflected in the supported user flow.

## Reproduction commands and evidence

All auxiliary scripts, logs and generated fixtures are outside the repository and are not committed. The original and HEAD OXT hashes are respectively `f6efe6e6160c014d3b3dcae866bdc026da3637bc5dc9293494c5b91f84f0e7a5` and `7a00eabb1a571b00b89c717fe2284e907abd1db2dfa35926811b221359743fb3`.

```sh
git worktree add --detach /tmp/usb-review-2-before 87e4abd
python3 -m unittest discover -s tests/unit
bash scripts/ci-quality.sh
python3 -m unittest discover -s tests/unit -p 'test_usb_token*.py' -v

runuser -u codex -- env HOME=/tmp/usb-review-2-home python3 \
  tests/runtime/check-usb-token-setup.py --instdir /opt/hst \
  --workdir /tmp/usb-review-2-runtime/signing --display :99 --port 2183 --mode both
# Repeat with --cold and --workdir /tmp/usb-review-2-runtime/signing-cold.
runuser -u codex -- env HOME=/tmp/usb-review-2-home python3 \
  tests/runtime/check-usb-token-review.py --instdir /opt/hst \
  --workdir /tmp/usb-review-2-runtime/selection-head --display :99 --port 2183 --mode both
```

Evidence under `/tmp/usb-review-2-evidence`:

- `unit.log`, `usb-unit.log`, `quality.log`, `runtime-signing.log`, `runtime-signing-cold.log`, `runtime-selection-head.log`: complete suite output.
- `reproduce.py`, `reproduce-before.log`, `reproduce-head.log`: B1/B2/M1/M3/m1/m2 before/after; per-case files, hashes and native listings are in `/tmp/usb-review-2-probes/{before,head}`.
- `old-register-race.py`, `register-race-before.log`: the original M1 race through full `register()`, with its HST lock verified held.
- `selection-before-after.py`, `runtime-selection-before.log`, `runtime-selection-head-independent.log`: same independent real-UNO M2 script against both built OXTs, both modes, both `sql:` and missing configured directories.
- `extra-probes.py`, `extra-probes.log`: five storage-error probes, eight real-NSS filename probes, four macOS locator fixtures and the existing-file refusal probe.
- `policy-alias.py`, `policy-alias-before.log`, `policy-alias-head.log`: new p11-kit alias regression, with native registration/listing.
- `build-before.log`, `build-reproducible.log`, `checker-self-test.log`, `dmg-background.log`: build and ancillary checks. Successful standalone DMG checking emits no output.

Runtime result JSON, signed documents and screenshots are retained under `/tmp/usb-review-2-runtime/{signing,signing-cold,selection-head,selection-before,selection-head-independent}`. Test PKI and fixed test PINs are disposable harness fixtures and are not part of the report commit.

The Linux preservation and signing regressions are resolved for the reproduced scenarios. Fix R2-M1 before releasing the advertised macOS setup flow, and address the enabled-alias regression, help mismatch and test-module bound. Retain the native preservation and SoftHSM tests when making those changes.
