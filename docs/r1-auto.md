# Checklist R1 tự động

Hai workflow `r1-auto-windows.yml` và `r1-auto-macos.yml` kiểm tra hiện vật của một
lần dựng đã hoàn tất thành công. Không thay extension hoặc ký lại ứng dụng.
Windows chạy hai máy sạch ở tỉ lệ 100% và 150%; macOS dùng runner arm64 và yêu cầu
chế độ màn hình thực 2×. Runner macOS chỉ có chế độ 1×, nên `mac_hidpi.py` thêm một
màn hình ảo HiDPI của WindowServer (CGVirtualDisplay) làm màn hình chính: ứng dụng vẽ
thật ở backing scale 2. Ảnh không được phóng to để thay thế HiDPI.

Mỗi lượt có `results.json`: `platform`, `run_id`, mã SHA-256 bộ cài, `display`,
`results`, `owner_review`. Mỗi phần tử kết quả có `item`, `status`, `detail`,
`screenshot`; chi tiết chứa số đo, nhãn cửa sổ và danh sách ảnh. Ảnh dùng đường dẫn
tương đối trong artifact. Kết quả được ghi trước khi chạy và sau từng mục, nên
lỗi chuẩn bị, crash hoặc timeout không biến thành thành công. `summary.md` và
`GITHUB_STEP_SUMMARY` có một dòng cho mỗi mục cùng phần chủ sở hữu duyệt.

| Mục | Kiểm tra | Script trong `tests/runtime/r1auto/` | Phạm vi |
|---|---|---|---|
| W1 | UI MSI, ô mặc định tích sẵn, mã cài đặt, dấu đăng ký; không câu hỏi mặc định ở ba lần mở | `windows_install.py`, `delegated.py` | Tự động |
| W2 | Giới thiệu chứa 1.0.0; không hỏi lại mặc định | `documents.py`, `delegated.py` | Tự động |
| W3 | UserChoice/ProgID/open command và mở `.docx` qua shell | `documents.py`, `default_session.py` | Tự động |
| W4 | Mở Writer, đóng, mở Sheets ba lượt trong cùng tiến trình | `documents.py` | Tự động |
| W5 | Nhập `quyet`, Tab, đọc loại đã chọn, popup và focus | `nd30.py` | Tự động |
| W6 | `check-windows-nd30-type-hover.py`: rê chuột thật trên danh sách Loại văn bản | `delegated.py` | Tự động |
| W7 | Nhập chữ có dấu, khung ký tự, ảnh 100%/150% | `nd30.py` | Một phần; duyệt nét chữ |
| W8 | Hình học nhóm ribbon, thứ tự thu nhỏ/gập, banner gọn | `ribbon_fit.py` | Tự động |
| W9 | Alt+Q, `bảng`, vị trí và dòng cuối danh sách | `ribbon.py` | Tự động |
| W10 | Rê qua ô kiểu, đọc kiểu và undo/redo trước/trong/sau, Ctrl+Z | `ribbon.py` | Tự động |
| W11 | `check-windows-options-pages.py`: từng trang HST Office trong hộp Tùy chọn thật | `delegated.py` | Tự động |
| W12 | PDF tổng hợp: dấu đỏ, độ mờ, lý do chữ ký, đường in và thumbnail gần đây | `pdf_checks.py` | Một phần; giấy in thật do chủ sở hữu duyệt |
| W13 | Đọc PDF trong Draw, đo độ mờ và chữ đen trên ảnh | `pdf_checks.py` | Tự động |
| W14 | Chứng thư phần mềm thử; PDF cấm ký, nút mật khẩu quyền, SHA-256 không đổi | `permission_check.py`, `software_certificate.py` | Một phần; token thật chỉ chủ sở hữu |
| W15 | Văn bản Đảng hai mặt, đo PDF lề trang lẻ/chẵn, ảnh xem trước in | `documents.py` | Tự động |
| W16 | Mở `.xlsx/.ods`, `.docx/.odt`, `.pptx/.odp` từ Explorer: nhấp đúp, chuột phải ▸ Open, Open with ▸ HST, động từ shell; profile mới, office tắt, đang chạy, vừa đóng; đo thời gian tới cửa sổ tài liệu đứng trước Explorer | `open_routes.py`, `open_routes_windows.py` | Tự động |
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

Windows có thêm `-f overlay_extension=true`: extension HST dựng từ commit của nhánh
thay bản đi kèm ngay sau khi cài, trước lần khởi động đầu, để thử một bản sửa
extension trên bộ cài có sẵn mà không dựng lại (kết quả đó không phải duyệt bản dựng).

W16 dùng profile mặc định như Explorer: mở bằng nhấp đúp, chuột phải ▸ Open,
Open with ▸ HST Sheets/Writer/Slides và động từ `open`/`new` của ProgID, khi profile
mới, khi office đã tắt, khi đang chạy (tài liệu thành một tab) và ngay khi tài liệu
cuối vừa đóng. Đạt khi cửa sổ tài liệu đã vẽ nội dung và đứng trước Explorer; câu
hỏi khởi động phủ lên tài liệu đã mở xong vẫn đạt. `W16/open-routes.json` ghi thời
gian, cửa sổ theo thứ tự chồng, cửa sổ đang được chọn và mọi tiến trình khởi chạy;
office không hiện cửa sổ được lấy dump vào `crash/`.

Các job R1 cần quyền chỉ đọc `contents` và `actions`; chúng nằm trong allowlist
đọc artifact của [`scripts/check-workflows.py`](../scripts/check-workflows.py).

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

W1/W2/W6/W11 gọi các script `check-windows-*.py` mà `windows-smoke.yml` dùng, với
cùng tham số (W1/W2: `--expect registered`, vì ô mặc định đã tích lúc cài). Mỗi
script có giới hạn 900 s; dòng `FAIL` hoặc mã thoát khác 0 là FAIL.

Giao diện mặc định là tiếng Việt trên mọi hệ điều hành: MSI luôn cài gói giao diện
tiếng Việt (kèm en-US), và ngôn ngữ giao diện mặc định là `vi`. Profile của mỗi mục
không lưu ngôn ngữ giao diện; trước mỗi mục, probe kiểm tra trên runner tiếng Anh rằng
profile mới dùng giao diện lõi tiếng Việt. Kiểm tra chữ của giao diện lõi (W9, W12,
W14) chỉ nhận chữ tiếng Việt.

## Không treo

Mọi bước chờ đều có hạn. M1/M2 chạy trong tiến trình con (`prepare.py`, 900 s) có
`startup-stack.log` ghi ngăn xếp mỗi 60 s; `open` không chặn, hộp “tải từ Internet”
của Gatekeeper được trả lời Mở qua System Events (chỉ hộp nêu tên HST Office), mỗi
lần duyệt cây Trợ năng có hạn 2 s/lệnh và 15 s/lượt. Mỗi mục khác chạy trong probe
có hạn 420 s. Hết hạn là FAIL kèm ảnh, rồi lượt chạy tiếp mục sau.

## Đọc ribbon qua accessibility của hệ điều hành

Engine hiện tại không đưa `XAccessible` của cửa sổ toolkit qua UNO (cửa sổ khai báo 18 interface, không có
accessibility). W8, W9, W10, phần thanh công cụ của M4 và M7 vì vậy đọc cây accessibility của hệ điều hành, như
bản Linux đọc AT-SPI: UI Automation từ HWND của office trên Windows (cầu MSAA/IAccessible2 của VCL tự bật khi có
client hỏi), AX từ cửa sổ của ứng dụng trên macOS (không cần `AXEnhancedUserInterface`). `ribbon_os.py` chuẩn hóa
vai trò (nhóm có chú thích, nút nhóm đã gập, dấu », banner — nhận theo vai trò và kích thước vì banner đổi sản
phẩm). Mỗi kết quả ghi `method`; cây được lưu `os-tree-*.log`.

- Hình học ribbon được so trong chính hệ tọa độ của cây. Trên macOS AX báo ribbon lệch dọc khoảng 150 điểm, nên
  điểm rê chuột được đổi sang màn hình bằng một lần hiệu chỉnh (gốc ribbon → gốc vùng khách của khung).
- Màn hình ảo HiDPI macOS rộng 1920 điểm: ở 1440 điểm ribbon đã gọn sẵn, không thấy bước thu nhỏ trước khi gập.
- W10 bắt đầu từ đoạn “Tiêu đề 1” và chỉ rê các mục của bộ sưu tập kiểu nằm dưới hàng thẻ; nếu bộ sưu tập chỉ hiện
  kiểu hiện tại thì cuộn sang mục kế.
- Trang Giao diện của M4 được đo bằng độ đậm vùng trang trên ảnh chụp, như kịch bản hồ sơ beta.5.
- `getCharacterBounds` của ô nhập trả về khung rỗng: W7/M5 đo hàng chữ ngay trên ảnh chụp sau khi gõ.
- Phím thật gõ theo nhịp người (80 ms/ký tự); trên Windows tiến trình công cụ tự đưa cửa sổ office lên trước.
- macOS: office của probe được mở qua LaunchServices (`open -n -W`).
- M2: HST Office phải tự mở lại từ Applications sau khi chuyển; nếu không, M2 FAIL và harness mở lại như chủ sở
  hữu chỉ để M3 vẫn chạy.

## Hồ sơ beta.5 cũ (macOS)

Job `old-profile` của `r1-auto-macos.yml` (runner riêng) làm như kịch bản
`ui-parity-old-profile` của `windows-smoke.yml`: tải DMG beta.5 **đã phát hành**
(`office.hasontech.vn/tai/1.0.0-beta.5/`, SHA-256 cố định), cài vào Applications, mở
một lần với hồ sơ mặc định, gỡ ứng dụng (hồ sơ còn), cài bản cần kiểm tra rồi mở.
Yêu cầu: câu hỏi khởi động xuất hiện (lần đầu có thể là lời chào, câu hỏi mặc định
phải đến ở lần mở kế tiếp) và mọi trang Tùy chọn ▸ HST Office không trắng
(`mac_old_profile.py`, `mac_options_pages.py`). Kết quả: `old-profile-results.json`.

Chỉ M4 được phép SKIP với ảnh sau khi phép kiểm trang tùy chọn đạt. PASS ở mục
một phần xác nhận phần tự động trong bảng; không thay thế kiểm giấy in, token thật
hoặc đánh giá hình ảnh. Duyệt bản dựng đòi cả hai workflow chạy đủ mục, mọi kiểm
tra bắt buộc đạt, rồi chủ sở hữu duyệt phần còn lại.

## Máy Windows thật trong mạng LAN (`tests/realwin/`)

Bộ công cụ chạy trên hai PC Windows thật của chủ sở hữu qua SSH (khóa `HST_WINTEST_KEY`), không qua CI.
Mọi tệp chỉ nằm dưới `C:\hst-test` (tệp lớn: `D:\hst-test`); `remote.py` từ chối ghi ra ngoài.

- `remote.py HOST ps|push|pull|ui`: chạy PowerShell bằng `-File` (không dùng `-Command -`), chép tệp, và chạy lệnh
  trong phiên người dùng đang đăng nhập qua `interactive-task.ps1` (tác vụ lập lịch tạm, chạy ẩn qua wscript,
  chỉ bắt đầu khi bàn phím/chuột đã rảnh ≥ 1 phút theo `GetLastInputInfo`, luôn xóa tác vụ).
- `install-msi.ps1`: cài/nâng cấp MSI với tùy chọn mặc định; `hst-state.ps1`: sản phẩm đã đăng ký, hồ sơ HST
  (băm, số mục, UILocale, SymbolStyle — không đọc nội dung khác).
- `hst_session_probe.py` (Python đi kèm HST): mở Writer/Sheets/Slides như người dùng, đo thời gian tới cửa sổ tài
  liệu, đọc ngôn ngữ giao diện và kiểu biểu tượng, chụp ảnh và đóng sạch (`Desktop.terminate`).
- `window-shot.ps1`: chỉ chụp cửa sổ HST/bộ office tham chiếu; mọi điểm ảnh mà cửa sổ khác (ứng dụng khác,
  thông báo, màn hình nền) che đều tô đen, góc thông báo luôn tô đen. Không dùng `PrintWindow` (không vẽ được
  vùng Skia/GPU).
- So sánh VBA: `make-vba-corpus.py` sinh tài liệu macro tổng hợp; `vba-reference-run.ps1` chạy trong bộ office
  tham chiếu qua COM (PowerShell 32-bit, kiểm tra máy chủ COM đúng là Microsoft Office — WPS có thể chiếm CLSID);
  `vba_hst_run.py` chạy trong HST qua UNO (`--visible` cho kết quả như người dùng; headless thiếu sự kiện và
  Names); `vba_compare.py` lập bảng khác biệt. `collect-results.py` ghi `results.json` theo dạng r1auto.
