# Blockers

| ID | Mô tả | Bằng chứng | Chặn | Owner | Điều kiện mở |
|---|---|---|---|---|---|
| LEG-01 | Header nguồn ONLYOFFICE: *“Pursuant to Section 7(b) … you must retain the original Product logo when distributing the program”* + Additional Terms 4 (no trademark license) | `LICENSES/upstream/*/LICENSE`, header `vendor/onlyoffice/plugins.js` | Fork/rebrand shell, installer HST (đường B) | Chủ dự án + tư vấn pháp lý | Ý kiến pháp lý bằng văn bản về phạm vi đổi tên/logo |
| LEG-02 | Trademark Policy ONLYOFFICE không trích được tự động (trang render JS) | `WebFetch` 2026-10-29 trả về trang không có nội dung policy | Mọi cách gọi tên dùng “ONLYOFFICE” ngoài mô tả tương thích | Chủ dự án | Người đọc, lưu bản PDF/text policy có ngày vào `LICENSES/` |
| LEG-03 | Duyệt phát hành công khai plugin/mẫu (đường A) | [LICENSE_AUDIT §4](LICENSE_AUDIT.md) | GitHub Release public của artifact | Chủ dự án | Ký duyệt checklist [RELEASE_CHECKLIST](RELEASE_CHECKLIST.md) |
| LEG-04 | Chưa audit license `desktop-sdk`, `dictionaries` (gitlink) và `3DPARTYLICENSE` binary | `upstream/upstream-lock.json` | Đường B | Kỹ thuật | Lưu LICENSE nguyên văn + review |
| LEG-05 | Hiệu lực hiện hành NĐ 30/2020/NĐ-CP năm 2026 chưa xác minh từ nguồn chính thức (Cổng chỉ có PDF ký 2020, không có trạng thái) | [VIETNAMESE_OFFICE_SPEC](VIETNAMESE_OFFICE_SPEC.md) | Gắn nhãn “đúng thể thức NĐ30” khi phát hành | Chủ dự án / pháp chế | Xác nhận trạng thái hiệu lực trên Cơ sở dữ liệu quốc gia về VBPL |
| QA-01 | Không có máy Windows/macOS và Microsoft Office hợp lệ | — | Hàng Win/mac/MS Office trong compatibility matrix | Chủ dự án | Cấp máy kiểm thử |
| OPS-01 | Chưa có runner ≥100 GB SSD cho full build | brief §9, build_tools | Workflow `desktop-*.yml` | Chủ dự án | Self-hosted/larger runner + quota |
| OPS-02 | Quota/billing GitHub Actions cho repo public chưa xác minh trên tài khoản; tài nguyên job chưa đo | brief §9 | Cam kết CI miễn phí | Kỹ thuật | Ghi số đo `measure-job.py` + trang billing tài khoản vào [CI](CI.md) |
| SIGN-01 | Chưa có chứng chỉ code signing Windows / Apple notarization | — | Installer | Chủ dự án | Có chứng chỉ, lưu trong GitHub Secrets |
