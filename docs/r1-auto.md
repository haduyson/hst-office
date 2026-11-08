# Checklist R1 tự động

Hai workflow `r1-auto-windows.yml` và `r1-auto-macos.yml` kiểm tra hiện vật của một
lần dựng đã hoàn tất thành công. Không thay extension hoặc ký lại ứng dụng.
Windows chạy hai máy sạch ở tỉ lệ 100% và 150%; macOS dùng runner arm64 và yêu cầu
chế độ màn hình thực 2×. Ảnh không được phóng to để thay thế HiDPI.

Mỗi lượt có `results.json`: `platform`, `run_id`, mã SHA-256 bộ cài, `display`,
`results`, `owner_review`. Mỗi phần tử kết quả có `item`, `status`, `detail`,
`screenshot`; chi tiết chứa số đo, nhãn cửa sổ và danh sách ảnh. Ảnh dùng đường dẫn
tương đối trong artifact. Kết quả được ghi trước khi chạy và sau từng mục, nên
lỗi chuẩn bị, crash hoặc timeout không biến thành thành công. `summary.md` và
`GITHUB_STEP_SUMMARY` có một dòng cho mỗi mục cùng phần chủ sở hữu duyệt.

| Mục | Kiểm tra | Script trong `tests/runtime/r1auto/` | Phạm vi |
|---|---|---|---|
| W1 | UI MSI, ô mặc định tích sẵn, mã cài đặt, dấu đăng ký; wrapper câu hỏi khởi động | `windows_install.py`, `delegated.py` | Tự động; chờ wrapper Windows |
| W2 | Giới thiệu chứa 1.0.0; wrapper không hỏi mặc định lần đầu | `documents.py`, `delegated.py` | Tự động; chờ wrapper Windows |
| W3 | UserChoice/ProgID/open command và mở `.docx` qua shell | `documents.py`, `default_session.py` | Tự động |
| W4 | Mở Writer, đóng, mở Sheets ba lượt trong cùng tiến trình | `documents.py` | Tự động |
| W5 | Nhập `quyet`, Tab, đọc loại đã chọn, popup và focus | `nd30.py` | Tự động |
| W6 | Gọi kiểm tra hover Windows của nhánh phụ trách | `delegated.py` | Tự động khi có wrapper |
| W7 | Nhập chữ có dấu, khung ký tự, ảnh 100%/150% | `nd30.py` | Một phần; duyệt nét chữ |
| W8 | Hình học nhóm ribbon, thứ tự thu nhỏ/gập, banner gọn | `ribbon_fit.py` | Tự động |
| W9 | Alt+Q, `bảng`, vị trí và dòng cuối danh sách | `ribbon.py` | Tự động |
| W10 | Rê qua ô kiểu, đọc kiểu và undo/redo trước/trong/sau, Ctrl+Z | `ribbon.py` | Tự động |
| W11 | Gọi kiểm tra trang tùy chọn Windows của nhánh phụ trách | `delegated.py` | Tự động khi có wrapper |
| W12 | PDF tổng hợp: dấu đỏ, độ mờ, lý do chữ ký, đường in và thumbnail gần đây | `pdf_checks.py` | Một phần; giấy in thật do chủ sở hữu duyệt |
| W13 | Đọc PDF trong Draw, đo độ mờ và chữ đen trên ảnh | `pdf_checks.py` | Tự động |
| W14 | Chứng thư phần mềm thử; PDF cấm ký, nút mật khẩu quyền, SHA-256 không đổi | `permission_check.py`, `software_certificate.py` | Một phần; token thật chỉ chủ sở hữu |
| W15 | Văn bản Đảng hai mặt, đo PDF lề trang lẻ/chẵn, ảnh xem trước in | `documents.py` | Tự động |
| M1 | Quarantine DMG, mở từ DMG, xác minh App Translocation, câu hỏi chuyển trước tiên | `mac_startup.py` | Tự động |
| M2 | Bấm Chuyển; ứng dụng tự mở từ Applications rồi hỏi mở tài liệu | `mac_startup.py` | Tự động |
| M3 | Đồng ý ở M2; LaunchServices và mở ba loại tệp qua Finder/shell | `documents.py`, `mac_access.py` | Tự động |
| M4 | Trang tùy chọn không trắng; đổi kiểu biểu tượng ngay; ảnh hai kiểu ở 2× | `appearance.py` | Độ sắc nét chỉ chủ sở hữu; lỗi trang vẫn FAIL |
| M5 | Chữ Ủy giữ đúng mã, khung ký tự trong ô và căn giữa | `nd30.py` | Một phần; duyệt hình chữ |
| M6 | Hover đổi dòng được chọn qua UNO; bấm đúng dòng phủ lên ô cơ quan | `nd30.py` | Tự động |
| M7 | Như W8–W10, phím tìm là Option+Cmd+K | `ribbon.py`, `ribbon_fit.py` | Tự động |
| M8 | Như W12–W13, cả trình xem, in, thumbnail và Draw | `pdf_checks.py` | Một phần; giấy in thật do chủ sở hữu duyệt |

## Chạy trên CI

Điều phối viên chạy sau khi thay đổi đã có trên nhánh workflow:

```bash
gh workflow run r1-auto-windows.yml --ref test/r1-auto -f run_id=123456789
gh workflow run r1-auto-macos.yml --ref test/r1-auto -f run_id=123456790
# Kiểm tra tập con; không dùng kết quả tập con làm duyệt toàn bộ bản dựng:
gh workflow run r1-auto-macos.yml --ref test/r1-auto -f run_id=123456790 -f items=M1-M3,M6
```

`run_id` phải thuộc đúng workflow desktop của kho hiện tại. macOS ưu tiên artifact
arm64 đã ký nếu có; bản không qua cơ chế bảo vệ hệ điều hành sẽ FAIL, không xóa
quarantine hay ký lại. Bộ lọc nhận danh sách, khoảng và `all`; sai nền tảng là lỗi.
Các bước chuẩn bị cần thiết vẫn chạy khi lọc mục. Nếu M1/M2 hỏng, M3 FAIL; M4–M8
vẫn có thể chạy trên bản sao từ chính DMG để thu thêm bằng chứng, không ghi nhận
bản sao đó là đã đạt thao tác chuyển ứng dụng.

Hai workflow cần quyền chỉ đọc `contents` và `actions`. Chính sách tại
[`scripts/check-workflows.py`](../scripts/check-workflows.py) cần cho phép hai job
R1 đọc artifact; yêu cầu cập nhật allowlist đang chờ chủ sở hữu xác nhận theo giới
hạn không sửa các script kiểm tra cũ của công việc này.

## Điều kiện môi trường và bằng chứng

Runner cần desktop tương tác, quyền Trợ năng/ghi màn hình/gửi đầu vào trên macOS,
máy in PDF hệ thống trên Windows và chế độ HiDPI yêu cầu. Thiếu các khả năng này
là FAIL hoặc lỗi chuẩn bị có bằng chứng, không tự động bỏ qua. Các selector hộp
thoại in/cài đặt phải được xác minh bằng lần CI native đầu tiên.

Python công cụ cài dependency từ `requirements.txt`; Python đi kèm ứng dụng chỉ
chạy UNO. Không cài package vào bundle đã ký. Mọi thao tác chuột/phím đi qua
SendInput hoặc Quartz; kết quả được đọc qua UNO/accessibility.

Fixture PDF được sinh tại chỗ bằng generator chữ ký, dấu và quyền hiện có; có
ảnh dấu đỏ, chữ chéo `/ca 0.1`, trường ký và chữ ký thật bị thay đổi sau khi ký.
Đo độ mờ dùng nguyên ngưỡng trong `pdf_watermark_metrics.py`. Chỉ ảnh, PDF tổng hợp,
log kiểm tra và JSON được upload; khóa thử, PFX và profile nằm ngoài artifact.
Chứng thư W14 được xóa sau kiểm tra. Không đọc tài liệu riêng của chủ sở hữu.

Các mục Windows giao cho `test/windows-r1-checks` chỉ chạy script có giao diện
`--install/--out`; nhận thêm `--screenshots` khi script công bố. Khi chỉ có phiên
bản Linux hoặc chưa có script hover, kết quả là `SKIP: pending test/windows-r1-checks`.
SKIP này làm gate thất bại. Không tạo bản kiểm tra Windows thay thế.

Chỉ M4 được phép SKIP với ảnh sau khi phép kiểm trang tùy chọn đạt. PASS ở mục
một phần xác nhận phần tự động trong bảng; không thay thế kiểm giấy in, token thật
hoặc đánh giá hình ảnh. Duyệt bản dựng đòi cả hai workflow chạy đủ mục, mọi kiểm
tra bắt buộc đạt, rồi chủ sở hữu duyệt phần còn lại.
