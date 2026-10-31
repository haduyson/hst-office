# Ký số bằng USB Token (PKCS#11) — HST Office v1.0.0-beta.3

Date: 2026-10-31 · Scope: verify + fix digital signing for Vietnamese CA USB tokens (VNPT-CA, Viettel-CA, BKAV-CA, FPT-CA, MISA, EasyCA…).

## Verdict

Signing works on Linux with a token **after the fixes below**. beta.2 as shipped could not sign anything with a token once the user had exported any PDF in the same session (common flow: "Xuất PDF rồi ký"). Three defects fixed in a new core patch; Vietnamese help page added; repeatable SoftHSM2 test added. Windows/macOS: code + package review only (no device).

## Defects found and fixed

| # | Defect (evidence) | Fix |
|---|---|---|
| 1 | **Token/certificates invisible after a PDF export** (Linux, macOS). `comphelper` hash/crypto calls `NSS_NoDB_Init()` on first use (every PDF export hashes the document ID); the signing code's later `NSS_InitReadWrite(profile)` is then a no-op, so the token module in the NSS DB is never loaded: empty "Lựa chọn chứng chỉ", no PIN prompt, signed-PDF export fails (`Io Write Code:16`). Repro on beta.2: `plain` → PIN prompt; `export-first` → `personal: []` (probe2). | `comphelper/source/misc/hash.cxx`, `crypto/Crypto_NSS.cxx`: initialise NSS through the `NSSInitializer` UNO service (same profile DB as signing); `NSS_NoDB_Init` only without component context. Not on Windows (CryptoAPI). Alternatives tried and rejected with evidence: loading profile into running NoDB NSS (token visible, but `PK11_GetCertFromPrivateKey` fails); `NSS_Shutdown`+reinit (SEC_ERROR_BUSY inside soffice, then re-init fails -8018 → nothing works). |
| 2 | **Misleading PIN prompt**: "Tập tin “nssdb” được bảo vệ bằng mật khẩu." (token label `TOKEN: /path` parsed as URL by uui → last path segment). Wrong PIN said "Mật khẩu không đúng. Không thể mở tài liệu này." | NSS callback names the request `pkcs11:token=<name>` (RFC 7512 form); uui shows title "Nhập mã PIN", text "Nhập mã PIN của thiết bị ký số (USB Token hoặc thẻ thông minh) “<token>”.", label "Mã PIN:", wrong PIN: "Mã PIN không đúng. Hãy nhập lại. Thiết bị có thể tự khóa nếu nhập sai nhiều lần." (4 new strings + vi translations in the patch). |
| 3 | **Linux NSS DB discovery** missed Snap Firefox (Ubuntu default), Flatpak Firefox/Thunderbird; without a Mozilla profile HST used a throw-away temp DB, so a token registered with `modutil` could never be found without manual Options setup. | `MNSFolders.cxx`: Snap/Flatpak profile roots. `nssinitializer.cxx`: fall back to `~/.pki/nssdb` (shared per-user NSS DB) when it exists, before the temp DB. Linux only. |

Patch: `patches/libreoffice/hst-digital-signature.patch` (9 files: comphelper ×2, connectivity, xmlsecurity ×2, uui ×3, `translations/source/vi/uui/messages.po`), appended to `series`; `scripts/apply-patches.sh --check` → applied. Built incrementally as hstbuild (`Library_merged`, `AllLangMoTarget_uui`, mozbootstrap); links cleanly.

Translation overrides (7 rows, `l10n/vi-overrides.jsonl`, validated with `check-translations.py --strict`, keys exist): "tài liều macro" typo, "Xem chứng..." truncated, Serial Number "Số sản xuất"→"Số sê-ri", Subject "Chủ đề"→"Chủ thể", Subject Algorithm, Public Key "Khoá công"→"Khóa công khai", menu "Ký PDF Hiện có..."→"Ký tệp PDF có sẵn...". Applied by the normal build (apply-overrides.py); not rebuilt locally.

## Results — Linux (Docker Ubuntu 24.04, SoftHSM2 token "HST-TEST-TOKEN", RSA-2048, user CN "Nguyễn Văn Thử", test CA trusted in NSS DB set via Options CertDir, TZ Asia/Ho_Chi_Minh)

Signing through the real UI (UITest-driven): Tập tin → Chữ ký số... → Ký tài liệu... → chọn chứng chỉ → Ký → PIN → Đóng. PDF export via filter (`SignPDF` + certificate, optional TSA). An unsigned PDF is exported **before** signing (regression check for #1).

| Format | beta.2 (shipped) | Fixed build: signed | HST verify (status bar / API) | Independent verify |
|---|---|---|---|---|
| ODT (XAdES) | FAIL – no cert listed | yes | OK | lxml/cryptography: SignatureValue ✔, refs 10/10, issuer ✔ |
| DOCX | FAIL | yes | PARTIAL_OK ¹ | SignatureValue ✔, 8/8 refs ✔, 2 `.rels` refs unchecked ² |
| ODS | FAIL | yes | OK | ✔ 10/10 |
| XLSX | FAIL | yes | PARTIAL_OK ¹ | ✔ 8/8 (+2 unchecked) |
| ODP | FAIL | yes | OK | ✔ 9/9 |
| PPTX | FAIL | yes | PARTIAL_OK ¹ | ✔ 9/9 (+5 unchecked) |
| Sign existing PDF (PAdES, ETSI.CAdES.detached) | FAIL | yes | OK / valid, cert status 0 | pdfsig: valid + trusted; pyHanko: VALID |
| Export signed PDF | FAIL (`Io Write 16`) | yes | valid | pdfsig ✔, pyHanko ✔ |
| Export signed PDF + TSA (timestamp.digicert.com) | FAIL | yes | valid | pdfsig ✔, pyHanko ✔ (TSA token sound) |
| Tampered ODT (content.xml edited after signing) | — | — | BROKEN (correct) | digest mismatch content.xml (correct) |
| PIN: wrong then right | no prompt at all | 2 prompts ("Mã PIN:"), warning box shown, then signed | | |
| PIN: cancel | prompt "Tập tin “nssdb”…" | prompt "Mã PIN:", cancel → list empty, file unsigned, no crash | | |

¹ HST reports OOXML signatures as valid-but-partial because `docProps/core.xml`, `docProps/app.xml`, `[Content_Types].xml` are not signed (upstream OOXML convention). Not a regression.
² The test's own OPC RelationshipTransform does not reproduce xmlsec byte-for-byte; those references are listed "unchecked" (HST validates them).

Evidence: `tests/output/digital-signature/{fixed,beta2}/` (results.json, run.log, screenshots: PIN prompt, wrong-PIN box, chooser with "Nguyễn Văn Thử", signed dialogs per format, opened documents). Run logs for the final test: scratch `e2e/final.log`.

## Build/package checks (task item 1)

- Linux build: `ENABLE_NSS`, `ENABLE_GPGMEPP`, `ENABLE_PDFIUM`, `ENABLE_CURL` = TRUE, `SYSTEM_NSS` (deb `requires` includes `libnss3`, `libnspr4` via hst-packaging-vendor.patch). Core deb ships `libxmlsecurity.so`, gpgme libs, `libpdfiumlo.so`, xmlsec `.ui` files; xsec_xmlsec merged into `libmergedlo`.
- Windows beta.2 MSI (msiinfo/msiextract): `xmlsecurity.dll`, `libxmlsec.dll`, `libxmlsec-mscng.dll` (CNG), `nss3/smime3/softokn3/freebl3/nssckbi/nssdbm3/nssutil3/nspr4/plc4/plds4/ssl3.dll`, `gpgmepp.dll`, `pdfiumlo.dll`; `services.rdb` registers SEInitializer, SecurityEnvironment, XMLSecurityContext, XMLSignature, DocumentDigitalSignatures, CertificateContainer, NSSInitializer, GPG SEInitializer.
- macOS arm64 dmg: `libnss3/smime3/softokn3/freebl3/nssckbi`, `libxmlsecurity`, gpgme, `libmergedlo` present.
- No HST patch/config disables signing. Commands present: Writer/Calc/Impress menubar (`.uno:SignaturesMenu`, `.uno:Signature`, `.uno:SignPDF`, Writer/Calc `.uno:InsertSignatureLine`, `.uno:ExportToPDF`) and Tabbed UI (File tab + ☰ menu `Signature`, `SignPDF`; Writer Insert `InsertSignatureLine`). hst-remove-donation only drops Donation/Feedback/GetInvolved.
- Vietnamese labels: "Chữ ~ký số...", "Chữ ký số", "Dòng ~chữ ký...", PDF tab "Chữ ký số", dialogs translated. Remaining inconsistency: certificate = "chứng chỉ" / "chứng nhận" / "chứng thư" (open glossary item 3; not changed). Missing accelerator on "Chữ ký số" submenu and some Options buttons (minor).

## Windows path review (task item 3)

- Signing uses `xmlsecurity/source/xmlsec/mscrypt` (CryptoAPI/CNG store) and svl `SVL_CRYPTO_MSCRYPTO` for PDF; HST patches touch none of it. My changes are NSS-side; comphelper change is `#if !defined(_WIN32)`; uui PIN wording only triggers on `pkcs11:token=` (never sent on Windows). Token PIN on Windows is asked by the CA driver/minidriver, not HST.
- Vietnamese CA tokens: after installing the CA's token driver (VNPT-CA, Viettel-CA, BKAV-CA, FPT-CA, EasyCA…), the certificate appears in the Windows Personal store (`certmgr.msc` → Personal → Certificates) and in HST's "Lựa chọn chứng chỉ" ("Trình quản lý chứng nhận Windows"). Documented in the help page.
- Not run on a Windows machine (no device) — unverified at runtime.

## UX gaps / help (task item 4)

- Help page `extensions/hst-vietnamese-tools/help/ky-so-usb-token.html` (Windows/Linux/macOS steps, sign document, export signed PDF, sign existing PDF, TSA, verify, troubleshooting) + link in `help/index.html` TOC only (other pages' sidebars not touched to avoid conflicts with the Codex UX agent). `tests/unit/test_user_guide.py` passes.
- Helper (not implemented, recommendation): a menu action or small CLI shipped in the .deb that detects common PKCS#11 libraries (`opensc-pkcs11.so`, `libeTPkcs11.so`, `libcastle.so.1.0.0`, `libbit4xpki.so`, `/usr/lib/pkcs11/*.so`, p11-kit modules) and registers them with `modutil` into the DB HST uses (`~/.pki/nssdb` or the Firefox profile). Needs `libnss3-tools`, packaging changes (owned by the single-.deb agent) and UI strings → larger than this task. With fix #3 the documented manual flow is 3 commands + restart.

## Other findings (not fixed)

- PDF date strings in UTC are written `D:…Z'` (non-conformant, ISO 32000-1 §7.9.4); pyHanko strict parser rejects such files. Only when the OS timezone is UTC; Vietnamese machines write `+07'00'`. Upstream issue, low priority.
- After a new signature HST asks "Bạn có muốn ghi nhớ chữ ký đó cho mỗi lần lưu không?" (upstream; fine).
- During this work another agent's in-progress `sfx2/appserv.cxx` briefly broke `Library_merged`; my first nssinitializer revision used `NSSUTIL_DoubleEscape` (nssutil3 not linked) and broke the relink — fixed within minutes by local escaping, later removed with that approach; relinked as hstbuild, `libmergedlo.so` present.

## Test

`tests/runtime/check-digital-signature.py` (+ `signature_pki.py`, `signature_verify.py`): SoftHSM2 token + CA + NSS DB, GUI signing of 7 formats, signed PDF export (+ `--tsa`), wrong/cancel PIN, tamper check, HST + independent verification; exit 77 if tools missing. Options `--late-pdf`, `--tabs` (default runs with document tabs off: with the in-progress tabs build, loads after a signed document sometimes returned no component — not investigated further, tabs agent's area). Example:
`docker run … hst-sig-test:local` then `python3 tests/runtime/check-digital-signature.py --instdir /opt/hst-office1.0 --workdir /work/x --display :93 --tsa http://timestamp.digicert.com`.

## Recommendations

1. Ship beta.3 with `hst-digital-signature.patch` (fix #1 is release-blocking for token users on Linux/macOS).
2. Test on a real Windows PC with a VNPT/Viettel token and on macOS with a token driver (NSS path).
3. Decide glossary term for Certificate ("chứng thư số" is the legal term in Vietnamese e-signature law); then unify xmlsec/cui strings.
4. Implement the token-registration helper as a packaged feature.
5. Consider a CI job running the SoftHSM2 test in Docker.

## Unresolved questions

- Real VN token drivers' PKCS#11 library names per CA (help lists common names as examples only).
- Whether the `.rels`-transform references can be verified by an external tool (xmlsec1 CLI cannot resolve OPC part URIs).

Status: DONE_WITH_CONCERNS
Summary: Token signing verified end to end on Linux (ODT/DOCX/ODS/XLSX/ODP/PPTX/PDF, PAdES + TSA) after fixing three defects (certs hidden after PDF export, misleading PIN prompt, NSS DB discovery); help page, overrides and SoftHSM2 test added.
Concerns/Blockers: Windows/macOS not runtime-tested; OOXML shows PARTIAL_OK (upstream convention); ci-quality has 1 failure from another agent's untracked report (broken evidence link), not from this work.
