# Release checklist — HST Office

Một bản phát hành chỉ được đánh dấu sẵn sàng khi **mọi mục bắt buộc** có bằng chứng (link log/evidence). Không có chứng chỉ thì không ghi "signed/verified".

## A. Nguồn & giấy phép

- [ ] Phiên bản: sửa [`VERSION`](../VERSION) (`MAJOR.MINOR.MICRO`) và mã đầy đủ trong [`data/hst/release.json`](../data/hst/release.json), build lại; About và `soffice --version` hiển thị đúng mã bản phát hành (không nêu tên LibreOffice; "Sao chép thông tin phiên bản" có dòng Engine), tên tệp tải `HSTOffice_<release>_*`, phiên bản MSI/deb/dmg ([BUILD_MATRIX](BUILD_MATRIX.md#phiên-bản-hiển-thị-theo-hệ-điều-hành)) và tên gói/`/opt/hst-office<MAJOR>.<MINOR>` khớp. Không đổi phiên bản lõi LibreOffice.

- [ ] `upstream/libreoffice-lock.json` khớp tarball đã build (SHA-256 + chữ ký GPG "Good signature").
- [ ] `scripts/apply-patches.sh --check` sạch; mỗi patch có header lý do + giấy phép file gốc (MPL-2.0).
- [ ] Source tương ứng công bố: tag git của repo HST + tarball upstream + `patches/`.
- [ ] `license.xml`/`NOTICE` upstream và `NOTICE.md`/`THIRD_PARTY_NOTICES.md` có trong gói cài.
- [ ] LEG-03, LEG-06, LEG-07 đã được chủ dự án/tư vấn ký duyệt ([BLOCKERS](BLOCKERS.md)).

## B. Thương hiệu

- [ ] `scripts/check-branding.py --install-root <instdir>` không còn chuỗi "LibreOffice/Document Foundation" ngoài allowlist pháp lý.
- [ ] Ảnh chụp: splash, Start Center, About (có "derived from LibreOffice"), launcher, icon 3 module.

## C. Chức năng (Linux x86_64)

- [ ] Writer/Sheets/Slides: tạo, mở, sửa, lưu, mở lại DOCX/XLSX/PPTX và ODT/ODS/ODP; xuất PDF.
- [ ] Tabbed UI mặc định, A4, Times New Roman; giao diện tiếng Việt khi `LANG=vi_VN.UTF-8` (`tests/runtime/check-defaults.py`).
- [ ] Extension tiếng Việt: NĐ30, chuyển mã, định dạng VND/ngày, CSV — `tests/runtime/check-extensions.py`.
- [ ] Mọi mẫu: `tests/runtime/check-templates.py` PASS cả round-trip lưu/in.
- [ ] Không kết nối mạng khi dùng (chạy trong network namespace) ngoài kiểm tra cập nhật tới `office.hasontech.vn` ([UPDATE_CHECK](UPDATE_CHECK.md)) và báo cáo lỗi chỉ khi người dùng bấm Gửi ([PRIVACY](PRIVACY.md)), và không có telemetry.
- [ ] `data/hst/release.json` đúng mã bản phát hành; manifest cập nhật đã sửa, ký (`scripts/release/sign-update-manifest.py`) và tải lên sau khi tệp cài đặt đã công bố.
- [ ] Độ trễ menu chuột phải Linux trong ngưỡng ([CONTEXT_MENU_PERFORMANCE](CONTEXT_MENU_PERFORMANCE.md)).

## D. Đóng gói

- [ ] `.deb` cài trên container Ubuntu 24.04 sạch; gỡ/purge/nâng cấp **không xoá tài liệu người dùng** và không đụng profile khác.
- [ ] SHA-256 cho mọi artifact, changelog, danh sách OS/arch đã kiểm thử.

## E. Nền tảng khác (BLOCKED tới khi có máy)

- [ ] Windows x64 `.msi` (OPS-01, SIGN-01, QA-01).
- [ ] macOS arm64 `.dmg` + notarization (OPS-01, SIGN-01, MAC-01) — kèm số đo độ trễ chuột phải trước/sau trên Mac thật.

## Đưa bản phát hành lên office.hasontech.vn (mọi phiên bản từ beta 4.1)

- [ ] Phát hành trên GitHub (tag `v<release>`, tạo release bằng tài khoản chủ dự án rồi chạy `release.yml` với `append=true` cho từng nền tảng).
- [ ] Nền tảng nào build xong thì gửi ngay cho phiên quản lý website: tag, tên tệp, kích thước, SHA256. Website tải tệp về `tai/<release>/`, kiểm tra `sha256sum -c`, rồi chuyển `/tai/windows|linux|macos-arm|macos-intel` và `/tai/sha256`.
- [ ] Khi đủ cả ba hệ điều hành: tạo và ký `update/latest.json` + `update/latest-2.json` (`generate-update-manifest.py`, `sign-update-manifest.py`), gửi kèm; website cập nhật nhãn phiên bản, `/diem-moi/`, dòng hỗ trợ, đồng bộ hướng dẫn (`sync-help.py --ref v<release>`) và đăng manifest — một lần.
- [ ] Kiểm tra lại: 4 link `/tai/*` trả đúng tệp từ office.hasontech.vn, manifest báo đúng phiên bản.
