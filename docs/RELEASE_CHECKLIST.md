# Release checklist — HST Office

Một bản phát hành chỉ được đánh dấu sẵn sàng khi **mọi mục bắt buộc** có bằng chứng (link log/evidence). Không có chứng chỉ thì không ghi "signed/verified".

## A. Nguồn & giấy phép

- [ ] Phiên bản: sửa [`VERSION`](../VERSION) (`MAJOR.MINOR.MICRO`) và mã đầy đủ trong [`data/hst/release.json`](../data/hst/release.json), build lại; About và `soffice --version` hiển thị đúng mã bản phát hành (không nêu tên LibreOffice; "Sao chép thông tin phiên bản", ReadMe và báo cáo lỗi không có phiên bản lõi; `scripts/check-branding.py --release`), tên tệp tải `HSTOffice_<release>_*`, phiên bản MSI/deb/dmg ([BUILD_MATRIX](BUILD_MATRIX.md#phiên-bản-hiển-thị-theo-hệ-điều-hành)) và tên gói/`/opt/hst-office<MAJOR>.<MINOR>` khớp. Không đổi phiên bản lõi LibreOffice.

- [ ] `upstream/libreoffice-lock.json` khớp tarball đã build (SHA-256 + chữ ký GPG "Good signature").
- [ ] `scripts/apply-patches.sh --check` sạch; mỗi patch có header lý do + giấy phép file gốc (MPL-2.0).
- [ ] Source tương ứng công bố: tag git của repo HST + tarball upstream + `patches/`.
- [ ] `license.xml`/`NOTICE` upstream và `NOTICE.md`/`THIRD_PARTY_NOTICES.md` có trong gói cài.
- [ ] LEG-03, LEG-06, LEG-07 đã được chủ dự án/tư vấn ký duyệt ([BLOCKERS](BLOCKERS.md)).

## B. Thương hiệu

- [ ] `scripts/check-branding.py --install-root <instdir>` không còn tên nguồn gốc ngoài [ngoại lệ giấy phép, bản quyền và khai báo DTD](../branding/brand-audit-allowlist.json); nội dung giao diện vẫn phải báo lỗi.
- [ ] Ảnh chụp: splash, Start Center, About (có "derived from LibreOffice"), launcher, icon 3 module.

## C. Chức năng (Linux x86_64)

- [ ] Writer/Sheets/Slides: tạo, mở, sửa, lưu, mở lại DOCX/XLSX/PPTX và ODT/ODS/ODP; xuất PDF.
- [ ] Tabbed UI mặc định, A4, Times New Roman; giao diện tiếng Việt khi `LANG=vi_VN.UTF-8` (`tests/runtime/check-defaults.py`).
- [ ] Extension tiếng Việt: NĐ30, chuyển mã, định dạng VND/ngày, CSV — `tests/runtime/check-extensions.py`.
- [ ] Mọi mẫu: `tests/runtime/check-templates.py` PASS cả round-trip lưu/in.
- [ ] Không kết nối mạng khi dùng (chạy trong network namespace) ngoài kiểm tra cập nhật tới `office.hasontech.vn` ([UPDATE_CHECK](UPDATE_CHECK.md)) báo cáo lỗi chỉ khi người dùng bấm Gửi ([PRIVACY](PRIVACY.md)), feed banner và báo cáo lượt hiển thị banner mỗi ngày một lần tới `system.hasontech.vn` ([BANNERS](BANNERS.md)); không có telemetry nào khác.
- [ ] `data/hst/release.json` đúng mã bản phát hành; manifest cập nhật đã sửa, ký (`scripts/release/sign-update-manifest.py`) và tải lên sau khi tệp cài đặt đã công bố.
- [ ] Độ trễ menu chuột phải Linux trong ngưỡng ([CONTEXT_MENU_PERFORMANCE](CONTEXT_MENU_PERFORMANCE.md)).

## D. Đóng gói

- [ ] `.deb` cài trên container Ubuntu 24.04 sạch; gỡ/purge/nâng cấp **không xoá tài liệu người dùng** và không đụng profile khác.
- [ ] SHA-256 cho mọi artifact, changelog, danh sách OS/arch đã kiểm thử.

## E. Nền tảng khác (BLOCKED tới khi có máy)

- [ ] Windows x64 `.msi` (OPS-01, SIGN-01, QA-01).
- [ ] Windows smoke: `uninstall-beta4-then-install` đạt (gỡ beta.4 rồi cài: đủ tệp, khóa riêng, mở được). `upgrade-from-beta4` chỉ ghi nhận; nếu phiên bản tệp thực thi còn thấp hơn bản trước thì ghi chú phát hành phải yêu cầu gỡ bản cũ trước khi cài, và bản Windows không có trong nguồn cập nhật cho các bản đó.
- [ ] Windows: `scripts/check-msi-upgrade.py --msi <tệp>` không lỗi (UpgradeCode riêng, không component nào còn GUID của beta 1–4); không phiên bản tệp khóa nào giảm so với bản trước, nếu buộc phải giảm thì đổi `COMPONENTGUIDSEED` ([BUILD_MATRIX](BUILD_MATRIX.md#mã-msi-trên-windows-upgradecode)).
- [ ] Windows: `scripts/check-msi-no-cli.py --msi <tệp>` không lỗi (không tệp `cli_*`, không dòng `MsiAssembly`: không ghi gì vào GAC) và kịch bản smoke `upgrade-from-1.0.1` đạt (nâng cấp từ 1.0.1 không để lại assembly `cli_*` trong GAC, macro VBA vẫn chạy).
- [ ] macOS arm64 `.dmg` + notarization (OPS-01, SIGN-01, MAC-01) — kèm số đo độ trễ chuột phải trước/sau trên Mac thật.

## Đưa bản phát hành lên office.hasontech.vn (mọi phiên bản từ beta 4.1)

- [ ] Phát hành trên GitHub (tag `v<release>`, tạo release bằng tài khoản chủ dự án rồi chạy `release.yml` với `append=true` cho từng nền tảng).
- [ ] Nền tảng nào build xong thì gửi ngay cho phiên quản lý website: tag, tên tệp, kích thước, SHA256. Website tải tệp về `tai/<release>/`, kiểm tra `sha256sum -c`, rồi chuyển `/tai/windows|linux|macos-arm|macos-intel` và `/tai/sha256`.
- [ ] Khi đủ cả ba hệ điều hành: tạo và ký `update/latest.json` + `update/latest-2.json` (`generate-update-manifest.py`, `sign-update-manifest.py`), gửi kèm; website cập nhật nhãn phiên bản, `/diem-moi/`, dòng hỗ trợ, đồng bộ hướng dẫn (`sync-help.py --ref v<release>`) và đăng manifest — một lần.
- [ ] Kiểm tra lại: 4 link `/tai/*` trả đúng tệp từ office.hasontech.vn, manifest báo đúng phiên bản.

### Chỉ phát hành tệp trên office.hasontech.vn, không đưa link GitHub cho người dùng

- [ ] Tạo bản phát hành **nháp** trước: `release.yml` với `draft=true` và các run id đã kiểm thử (bản nháp không công khai, chưa có tag).
- [ ] Tải tệp từ bản nháp: `gh release download v<release> -D <thư mục>` (nhanh hơn tải artifact), rồi `sha256sum -c SHA256SUMS` và đối chiếu từng mã với artifact của run đã kiểm thử.
- [ ] Đưa tệp lên hosting: `tai/<release>/` cùng `tai/SHA256SUMS`, chuyển `/tai/<nền tảng>`, rồi kiểm tra bằng HEAD (không GET) từng link.
- [ ] Mọi chỗ người dùng thấy (trang tải về, `/diem-moi/`, ghi chú phát hành, `installers[].url` của nguồn cập nhật) chỉ trỏ tới `https://office.hasontech.vn/tai/...`, không bao giờ tới github.com.
- [ ] Khi bộ cài Windows không cài đè được bản cũ: nguồn cập nhật **không** có `installers.windows` và `downloads.windows` trỏ tới `https://office.hasontech.vn/#tai-ve`, để bản cũ trên Windows chỉ báo có bản mới, không chạy bộ cài.
