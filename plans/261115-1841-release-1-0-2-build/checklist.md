# Dựng và phát hành HST Office 1.0.2: danh sách kiểm tra

Giờ Asia/Saigon. Nhánh chuẩn bị: `release/1.0.2-prep` (VERSION/release.json 1.0.2, banner tích hợp = feed 2026-11-14T09:13:27Z,
ghi chú `docs/releases/v1.0.2.md`, bản nháp feed `docs/releases/v1.0.2-update-draft/`). Không dùng token USB trên máy test.

## 0. Chốt commit phát hành (integrator)

- [ ] `feat/ribbon-g10-menus` đã vào `rc/1.0.2-batch5` và train của nó đạt cả Linux và Windows.
- [ ] Merge `release/1.0.2-prep` vào `rc/1.0.2-batch5` (không đụng tệp ribbon, merge sạch). Ghi lại commit R.
- [ ] Ở R: `bash /data/hst-agents/scratch-keep/fresh-apply2.sh <wt> <outdir riêng>` = 0; `bash scripts/ci-quality.sh` 0 lỗi
      (gồm unit test, `check-workflows.py`, `check-authored-lines.py`); `python3 scripts/check-extensions.py --require-banner-key`.
- [ ] `python3 scripts/write-hst-version.py --release` in `1.0.2`; `--build` in `10000`.

## 1. Dựng Windows và Linux qua build-queue (không build tay, không build trên dev server)

- [ ] Linux (VM103): `bash /home/wt-build-infra/scripts/build-queue.sh submit --platform linux --ref <R hoặc rc/1.0.2-batch5> --integrator`, rồi `... wait <id>`.
      Thu `.deb`, `.rpm`, `.AppImage`; tên đúng `HSTOffice_1.0.2_Linux_x86-64.{deb,rpm,AppImage}`; `pin <id> --reason release-1.0.2`.
- [ ] Windows (slot hst3/hst4/hst5): `... submit --platform windows --ref <R> --integrator`, `wait`, `pin`. Tệp `HSTOffice_1.0.2_Win_x86-64_en-US_vi.msi`.
- [ ] Windows: `scripts/check-msi-upgrade.py --msi <msi>` và `scripts/check-msi-no-cli.py --msi <msi>` không lỗi; ProductVersion `1.0.2.10000`.
- [ ] Linux: `dpkg-deb -f <deb> Version` = `1:1.0.2-1`; `rpm -qp --qf '%{VERSION}-%{RELEASE}' <rpm>` = `1.0.2-1`;
      `scripts/check-branding.py --install-root <instdir> --release 1.0.2`.

## 2. macOS: ký và notarize trên main (r1: main phải có dmg đã ký)

- [ ] Đưa R lên `main` (chủ dự án/integrator). Chỉ `main` vào được môi trường `macos-signing`.
- [ ] `gh workflow run desktop-macos.yml --ref main -f mode=full`; đợi xanh cả arm64 và x86_64, job ký + notarize + staple thành công.
- [ ] Nếu phải sửa riêng macOS sau R: chỉ đường dẫn macOS (`scripts/release/macos-commit-paths.sh`), commit kế tiếp trên main.
- [ ] Tải artifact dmg đã ký, `spctl -a -vv -t install` (Mac thật) và `xcrun stapler validate`; `CFBundleShortVersionString` 1.0.2, `CFBundleVersion` 10000.

## 3. Smoke test (theo khóa console; synthetic docs; C:\hst-test hoặc D:\hst-test, có .hst-owner)

- [ ] HST5 (192.168.1.125), HST3, HST1: lấy `C:\hst-test\console-lock.txt` khi trống, trả bằng xóa tệp của mình; không gửi phím mù.
  - Cài 1.0.1 → cài đè 1.0.2: không lỗi 1304/1935/1937; một mục HST Office trong Cài đặt ▸ Ứng dụng; About = 1.0.2.
  - Văn bản có bảng tính + trình chiếu nhúng: lưu `.odt` và `.docx`, mở lại, đối tượng còn nội dung, không tự đóng.
  - Dải lệnh/QAT/mẹo phím (Alt, Alt+2, F10), nút ▾ mới; Tệp tin ▸ In xem trước và in ra PDF; LAMBDA/MAP nhập Ctrl+Shift+Enter.
  - Mở tệp lớn mẫu (docx nhiều ghi chú, xlsx 10 MB); tắt máy giả lập (đăng xuất) với tài liệu đang sửa → mở lại có khôi phục.
  - Banner hiện bộ 7 banner; HST5 thêm 150% (set_scale, trả 100 trước khi nhả khóa).
- [ ] VM103 / container: cài `.deb` (Ubuntu 24.04 sạch, nâng cấp từ 1.0.1), `tests/runtime/check-rpm-install.sh`, `tests/runtime/check-appimage.sh`;
      kiểm tra dưới Xvfb ở nice 19 trên dev server chỉ với gói đã dựng.

## 4. Chủ sở hữu tự thử

- [ ] macOS M2: cài dmg đã ký từ `/Applications`, mở lần đầu (Gatekeeper), Cập nhật ngay từ 1.0.1, dải lệnh/phím tắt Cmd.
- [ ] Ký PDF bằng token USB thật (VNPT-CA) trên máy của chủ sở hữu, kể cả PDF có mật khẩu. Agent không chạm token.
- [ ] Duyệt ghi chú phát hành và quyết định phát hành.

## 5. Nguồn cập nhật và website (sau khi đủ 6 tệp)

- [ ] Gom 6 tệp vào một thư mục, `sha256sum` → `SHA256SUMS`.
- [ ] `python3 scripts/release/fill-update-manifest-hashes.py --draft docs/releases/v1.0.2-update-draft --assets-dir <dir> --out <out>`
      (dừng nếu thiếu tệp, sai tên, hoặc kết quả khác bản nháp ngoài sha256/size). Đổi `date` trong bản nháp nếu ngày phát hành khác 2026-11-15.
- [ ] Ký `<out>/site/latest-3.json`, `latest-2.json`, `latest.json` bằng `sign-update-manifest.py`, rồi `--verify`.
- [ ] Gửi remote-5f: tag, tên tệp, kích thước, SHA256SUMS, feed đã ký; danh sách sửa website ở báo cáo
      `plans/reports/fullstack-developer-261115-1845-release-102-prep.md` (mục Website). Feed đăng sau cùng.
- [ ] Sau deploy: HEAD các `/tai/*` (kể cả `/tai/linux-rpm`, `/tai/linux-appimage`), `--verify` feed tải về, 1.0.1 báo có 1.0.2.
- [ ] Tag `v1.0.2` ở R; README dòng "Bản chính thức" đổi thành 1.0.2; `docs/BUILD_MATRIX.md` bảng lõi giữ 26.8.1.1.
