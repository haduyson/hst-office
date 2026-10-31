# USB Token setup — beta.5

Date: 2026-10-31. Linux container, real HST Office at `/opt/hst` (LibreOffice core 26.8.1.1), Xvfb `:99`, uid 2000 and separate test HOME/profile directories. The installed application was kept read-only. No push was performed.

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
