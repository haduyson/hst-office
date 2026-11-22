# Blockers

| ID | Mô tả | Chặn | Owner | Điều kiện mở |
|---|---|---|---|---|
| LEG-03 | Duyệt phát hành công khai `.deb` HST Office | GitHub Release public | Chủ dự án | Ký duyệt [RELEASE_CHECKLIST](RELEASE_CHECKLIST.md) |
| LEG-05 | Hiệu lực hiện hành NĐ 30/2020/NĐ-CP năm 2026 chưa xác minh từ nguồn chính thức | Nhãn "đúng thể thức NĐ30" khi phát hành | Chủ dự án / pháp chế | Xác nhận trên CSDL quốc gia về VBPL |
| LEG-06 | Từ 1.0.4 mã HST (file riêng, gồm file mới trong patch) theo giấy phép độc quyền `LicenseRef-HST-Proprietary`, phân phối cùng LibreOffice MPL-2.0 và các thành phần LGPL/GPL trong cùng gói cài (MPL-2.0 §3.3 "Larger Work"); Điều khoản sử dụng là **bản nháp** — cần luật sư duyệt ([LICENSE_AUDIT](LICENSE_AUDIT.md) §2.1) | Phát hành 1.0.4 | Chủ dự án + tư vấn | Ý kiến pháp lý về Điều khoản sử dụng và cách kết hợp với thành phần LGPL/GPL |
| LEG-07 | Chưa lưu nguyên văn trademark policy của TDF | Phát hành công khai | Kỹ thuật | Lưu bản policy có ngày vào `LICENSES/` và đối chiếu kết quả `check-branding` |
| MAC-01 | **Tạm gác (chủ dự án, 2026-10-29 14:29):** độ trễ chuột phải trên macOS không còn tái hiện; chỉ điều tra lại khi gặp trong quá trình sử dụng. Không áp patch theo phỏng đoán | Không chặn phát hành Linux | Chủ dự án | Khi trễ xuất hiện lại: chạy `sample` + bộ đo `scripts/perf` ([CONTEXT_MENU_PERFORMANCE](CONTEXT_MENU_PERFORMANCE.md)) rồi gửi kết quả |
| QA-01 | Không có máy Windows/macOS và Microsoft Office hợp lệ | Hàng Win/mac/MS Office trong compatibility matrix | Chủ dự án | Cấp máy kiểm thử |
| OPS-01 | Build Windows/macOS cần máy ≥100 GB SSD (runner GitHub miễn phí không đủ) | `desktop-windows.yml`, `desktop-macos.yml` | Chủ dự án | Self-hosted runner / máy build |
| OPS-02 | Quota/billing GitHub Actions chưa xác minh trên tài khoản | Cam kết CI miễn phí | Kỹ thuật | Ghi số đo + trang billing vào [CI](CI.md) |
| SIGN-01 | Chưa có chứng chỉ ký mã Windows / Apple notarization | Installer Windows/macOS | Chủ dự án | Chứng chỉ trong GitHub Secrets |

Blockers của đường ONLYOFFICE (LEG-01, LEG-02, LEG-04) đã đóng do đổi engine — xem lịch sử git.
