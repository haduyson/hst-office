# Kiểm tra phiên bản mới

HST Office tự biết khi có bản mới và báo cho người dùng kèm liên kết tải. Chỉ khi người dùng bấm "Cập nhật ngay" mới tải và (sau khi hỏi lại) cài: xem [UPDATE_INSTALL.md](UPDATE_INSTALL.md).

## Cách hoạt động

- **Manifest:** `https://office.hasontech.vn/update/latest.json` + chữ ký tách rời `latest.json.sig`
  (nguồn: [website/office.hasontech.vn/update/](../website/office.hasontech.vn/update/latest.json)). Không dùng URL GitHub hay LibreOffice.
- **Định dạng (`schema: 1`):** `channels.stable` và `channels.beta`, mỗi kênh là `null` hoặc
  `{version, date (YYYY-MM-DD), notes, downloads{windows, macos-arm, macos-intel, linux}, critical}`.
  Mọi liên kết phải là `https://` thuộc `hasontech.vn`; tải về dùng các chuyển hướng cố định `/tai/*` của trang.
  `critical: true` bỏ qua lựa chọn "Bỏ qua phiên bản này".
- **Chữ ký:** Ed25519 trên **đúng từng byte** của `latest.json`, base64 một dòng trong `latest.json.sig`.
  Ứng dụng kiểm bằng khóa công khai gắn trong extension (`update_logic.PUBLIC_KEY`), cài đặt Ed25519 thuần Python
  theo RFC 8032 (`hst_office/ed25519.py`, kiểm bằng các vector RFC 8032 mục 7.1). Manifest thiếu chữ ký, sai chữ ký
  hoặc sai định dạng bị bỏ qua im lặng (chỉ ghi log `HST update check: ...` ra stderr).
  - Khóa công khai: `d0f221c93fa61b12b57815046e3bce720006fb4b0b2ce57e67bed7c250a6c1e7`
  - Dấu vân tay: `sha256:2c4e3541c65e6990fd8d59dd54c89d8ded7752740c4b4eddbd833f647519fc36`
- **Phiên bản đang cài:** [data/hst/release.json](../data/hst/release.json) (`release`, ví dụ `1.0.0-beta.2`) là nguồn
  duy nhất của mã bản phát hành; phần `MAJOR.MINOR.MICRO` phải trùng `/VERSION` (build và unit test kiểm tra).
  `/VERSION` và `scripts/write-hst-version.py` giữ nguyên ý nghĩa (phiên bản sản phẩm, engine vẫn 26.8.1.1).
  `scripts/build-extensions.py` đóng tệp này vào extension thành `data/release.json`; mọi bản build (Linux, Windows,
  macOS) dựng extension qua quy tắc make gọi script đó, và tệp nằm trong `data/hst/` nên thay đổi kéo theo build lại `.oxt`.
- **Kênh:** bản có hậu tố pre-release (`-beta.N`) theo kênh beta: được báo bản beta **hoặc** stable mới hơn.
  Bản stable chỉ được báo bản stable. So sánh theo SemVer 2.0: `1.0.0-beta.2 < 1.0.0-beta.10 < 1.0.0 < 1.0.1`.
- **Khi khởi động** (job `onFirstVisibleTask`): chỉ khi `AutoCheck` bật và lần thử trước đã quá 24 giờ. Thời điểm
  thử được ghi trước khi gọi mạng; luồng nền tải tối đa 64 KiB mỗi tệp, timeout 5 giây, HTTPS tới
  `office.hasontech.vn`, chỉ theo chuyển hướng cùng nguồn. Ngoại tuyến hay lỗi: không hiện gì.
  Proxy: theo Công cụ ▸ Tùy chọn ▸ Internet ▸ Proxy (không dùng / thủ công HTTPS / theo hệ thống).
- **Thông báo:** thanh thông tin (infobar) trên Văn bản/Bảng tính/Trình chiếu: "Đã có HST Office X — bản mới."
  với [Tải về] [Xem điểm mới] [Bỏ qua phiên bản này]. Nếu lúc đó chỉ có Start Center, thông báo hiện ở tài liệu
  đầu tiên được mở. Liên kết mở bằng trình duyệt hệ thống.
- **Menu:** HST ▸ Kiểm tra cập nhật…, tab Phần mở rộng của giao diện ribbon, và Trợ giúp ▸ Kiểm tra cập nhật HST Office…
  kiểm tra ngay (không phụ thuộc `AutoCheck`) và báo: đã mới nhất / có bản mới / không kiểm tra được.
- Mọi chữ hiển thị là tiếng Việt ở mọi ngôn ngữ giao diện (nội dung hệ thống, theo chính sách sản phẩm).

Mã: `extensions/hst-vietnamese-tools/python/hst_office/update_*.py`. Chỉ `update_fetch.py` được phép dùng
`urllib`/`ssl`/`http` (`scripts/check-extensions.py` kiểm tra; socket/process vẫn bị cấm).

## Cài đặt và khóa tập trung

Từ beta.4 cài đặt nằm trong lõi, nút `/org.openoffice.Office.HSTUpdate` (`AutoCheck`, `ManualCheck`,
`CheckIntervalHours`, `AllowInstall`, `Channel`, cùng trạng thái người dùng `LastCheck`, `SkippedVersion`). Mã đọc
cài đặt: `update_config.py` (chép một lần giá trị cũ từ `/org.hasontech.hstoffice.UpdateCheck` của `update.xcs`, vẫn
tôn trọng gói chính sách cũ). Người dùng đổi bằng Công cụ ▸ Tùy chọn ▸ Nâng cao ▸ Trình soạn cấu hình chuyên gia
(tìm `HSTUpdate`).

Quản trị viên khóa cho cả máy bằng tệp `.xcd` (Linux), registry chính sách (Windows) hoặc hồ sơ cấu hình (macOS):
xem [UPDATE_ADMIN](UPDATE_ADMIN.md).

## Khóa ký

- Khóa riêng (seed 32 byte, hex) nằm **ngoài kho mã**: `/root/.config/hst-office/update-signing-ed25519.key`
  trên máy build, quyền 600. Không in, không commit, không đưa vào log. `.gitignore` chặn `*.key`, `*.seed`,
  `update-signing-*`.
- Nên sao lưu khóa ở nơi an toàn và về sau đưa vào GitHub secret (ví dụ `HST_UPDATE_SIGNING_KEY`) để workflow
  phát hành tự ký; khi đó ghi secret ra tệp tạm quyền 600 và trỏ `HST_UPDATE_SIGNING_KEY_FILE` tới tệp đó.
- Mất khóa: tạo cặp khóa mới, thay `PUBLIC_KEY`, phát hành bản mới. Các bản đã cài với khóa cũ sẽ không còn
  nhận thông báo, nên phải giữ khóa cẩn thận.

## Phát hành một bản cập nhật

1. Sửa `website/office.hasontech.vn/update/latest.json` (phiên bản, ngày, `notes`, `downloads`); khi có bản
   chính thức, điền `channels.stable`. Đồng thời cập nhật `.htaccess`/`config.js` để `/tai/*` trỏ đúng bản mới
   (xem [README của trang](../website/office.hasontech.vn/README.md)) và ghi chú phát hành trong [docs/releases](releases/).
2. Ký: `python3 scripts/release/sign-update-manifest.py` (ghi `latest.json.sig`, tự kiểm lại bằng khóa công khai).
   Kiểm không cần khóa: `python3 scripts/release/sign-update-manifest.py --verify`.
3. Commit cả hai tệp, rồi tải **cả hai** lên `/domains/office.hasontech.vn/public_html/update/` (user `hasontech`),
   ngay sau khi các tệp cài đặt của bản mới đã có trên trang phát hành (workflow [release.yml](../.github/workflows/release.yml)).
   Máy chủ trả `application/json` / `text/plain`, `Cache-Control: public, max-age=300` (đã có trong `.htaccess`);
   không cần CORS vì ứng dụng không phải trình duyệt.

## Kiểm thử

- Unit: `tests/unit/test_update_ed25519.py`, `test_update_check.py`, `test_update_job.py` (chạy trong `scripts/ci-quality.sh`).
- Runtime: `python3 tests/runtime/check-update-notify.py` dựng gói thử (`build-extensions.py --update-test-mode`) và trỏ
  `HST_UPDATE_TEST_URL` tới máy chủ HTTP cục bộ 127.0.0.1. Biến này chỉ có tác dụng với gói thử;
  `check-extensions.py` từ chối gói có dấu thử nên bản phát hành không bao giờ chấp nhận nó.
