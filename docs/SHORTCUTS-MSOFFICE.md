# Phím tắt theo Microsoft Office

Chủ dự án (2026-11-04): HST Office dùng phím tắt của Microsoft Office vì phần lớn người dùng
Việt Nam đã quen; khi trùng thì phím của Microsoft Office được ưu tiên hơn phím của LibreOffice.
Giữ nguyên các phím riêng của HST: `Shift+Esc` / macOS `Option+Cmd+K` (Tìm tính năng,
`hst-feature-search.patch`), `Alt+F11` (Macro VBA), `Alt+F8` (hộp thoại Macro) —
`extensions/hst-vietnamese-tools/Accelerators.xcu`; `Ctrl+Alt+.` / `Ctrl+Alt+,` (thẻ tài liệu). `Alt+F` mở Tập tin (`hst-file-backstage.patch`, như thẻ File của Office) không bị patch này đụng tới.

- Cài đặt: `patches/libreoffice/hst-msoffice-shortcuts.patch` (officecfg `Accelerators.xcu`,
  phím riêng cho macOS bằng `install:module="macosx"`, phím chỉ Windows/Linux bằng
  `install:module="unxwnt"`; Alt+Enter/Ctrl+Enter của Sheets sửa trong `sc`).
- Nguồn tham chiếu duy nhất: trang phím tắt Microsoft (đọc 2026-11-04):
  [Word](https://support.microsoft.com/en-us/office/keyboard-shortcuts-in-word-95ef89dd-7142-4b50-afb2-f762f663ceb2),
  [Excel](https://support.microsoft.com/en-us/office/keyboard-shortcuts-in-excel-1798d9d5-842a-42b8-9c99-9b7213f0040f),
  [PowerPoint](https://support.microsoft.com/en-us/office/use-keyboard-shortcuts-to-create-powerpoint-presentations-ebb3d20e-dcd4-444f-a38e-bb5c5ed180f4),
  [Word cho Mac](https://support.microsoft.com/en-us/accessibility/word/keyboard-shortcuts-in-word),
  [Excel cho Mac](https://support.microsoft.com/en-us/accessibility/excel/keyboard-shortcuts-in-excel).
- Kiểm tra: `tests/runtime/check-msoffice-shortcuts.py` (Linux, GTK3, Xvfb). Phím macOS và
  Windows chưa chạy thử trên máy thật.

Ký hiệu: trên macOS `MOD1` = ⌘ Cmd, `MOD2` = ⌥ Option, `MOD3` = Control. "Trước" là phím của bản
LibreOffice 26.8.1.1 + các patch HST trước đó; "Sau" là HST Office 1.0.0-beta.5.
Trạng thái: **khớp** (đã đúng từ trước), **đổi** (patch này đổi/thêm), **một phần** (phím đúng
nhưng lệnh HST làm khác một chút), **thiếu** (HST chưa có lệnh tương đương).

## HST Writer ↔ Word

| Lệnh Microsoft | Win/Linux | macOS (Microsoft) | Trước (HST) | Sau (HST) | Trạng thái | Ghi chú / phím bị thay |
|---|---|---|---|---|---|---|
| Đậm / Nghiêng / Gạch dưới | Ctrl+B/I/U | Cmd+B/I/U | như Word | như Word | khớp | |
| Căn giữa / trái / phải / đều | Ctrl+E/L/R/J | Cmd+E/L/R/J | như Word | như Word | khớp | |
| Tìm và thay thế | Ctrl+H | Control+H | Ctrl+H; macOS Cmd+Option+F | không đổi | khớp (Win/Linux) | macOS: Control+H là phím xóa lùi của Cocoa nên không dùng được; giữ Cmd+Option+F |
| Tìm | Ctrl+F | Cmd+F | thanh Tìm | không đổi | khớp | Word mở ngăn Điều hướng, HST mở thanh Tìm |
| Đi tới (Go To) | Ctrl+G | Cmd+Option+G | Ctrl+G; macOS Cmd+G = tìm tiếp | thêm macOS Cmd+Option+G | khớp / đổi (macOS) | |
| Chèn siêu liên kết | Ctrl+K | Cmd+K | Ctrl+K | không đổi | khớp | |
| Tăng / giảm cỡ chữ | Ctrl+Shift+> / < | Cmd+Shift+> / < | không có | Phóng to / Thu nhỏ chữ | đổi | gắn cả hai mã phím (`GREATER`/`POINT`, `LESS`/`COMMA`) cho mọi bàn phím |
| Tăng / giảm 1 pt | Ctrl+] / [ | Cmd+] / [ | Phóng to / Thu nhỏ chữ | không đổi | một phần | HST nhảy theo dãy cỡ chữ, không đúng 1 pt |
| Hộp thoại Phông chữ | Ctrl+D | Cmd+D | Gạch dưới kép | Ký tự… (Phông chữ) | đổi | **Gạch dưới kép** chuyển sang Ctrl+Shift+D (phím Word) |
| Gạch dưới kép | Ctrl+Shift+D | Cmd+Shift+D | Đoạn phải-sang-trái | Gạch dưới kép | đổi | **Đoạn phải-sang-trái** chỉ còn trên menu Định dạng |
| Giãn dòng đơn / đôi / 1,5 | Ctrl+1 / 2 / 5 | Cmd+1 / 2 / 5 | Tiêu đề 1 / 2 / 5 | Giãn dòng 1 / 2 / 1,5 | đổi | **Tiêu đề 1, 2** chuyển sang Ctrl+Alt+1, 2; **Tiêu đề 5** chỉ còn ở danh sách kiểu (Ctrl+3, Ctrl+4 vẫn là Tiêu đề 3, 4) |
| Danh sách dấu đầu dòng | Ctrl+Shift+L | Cmd+Shift+L | không có | Bật/tắt dấu đầu dòng | đổi | Shift+F12 vẫn dùng được |
| Kiểu Normal | Ctrl+Shift+N | Cmd+Shift+N | Mẫu mới (Templates) | Kiểu đoạn mặc định | đổi | **Tạo từ mẫu** trong Writer còn ở Tập tin ▸ Mới ▸ Mẫu (Ctrl+Shift+N vẫn là Mẫu trong Sheets) |
| Tiêu đề 1 / 2 / 3 | Ctrl+Alt+1 / 2 / 3 | Cmd+Option+1 / 2 / 3 | không có | Tiêu đề 1 / 2 / 3 | đổi | |
| Ngắt trang | Ctrl+Enter | Cmd+Return | Ngắt trang | không đổi | khớp | |
| Sao chép / dán định dạng | Ctrl+Alt+C / Ctrl+Alt+V (yêu cầu ghi Ctrl+Shift+C/V) | Cmd+Option+C / V | Ctrl+Alt+C = Chèn chú thích | không đổi | thiếu | HST chỉ có cọ "Sao chép định dạng" (một lần nhấp), chưa có lệnh chép/dán định dạng riêng |
| Dán chỉ văn bản | Ctrl+Shift+V | — | Dán đặc biệt | Dán văn bản không định dạng | đổi | **Dán đặc biệt** chuyển sang Ctrl+Alt+V (phím Dán đặc biệt của Word các bản trước) |
| Lặp lại thao tác | F4 | Cmd+Y | Thuộc tính hình ảnh | Lặp lại | đổi | **Thuộc tính hình ảnh** còn ở menu chuột phải / nhấp đúp vào hình |
| Chính tả và ngữ pháp | F7 | Cmd+Option+L hoặc F7 | F7; macOS Cmd+Shift+; | thêm macOS Cmd+Option+L | khớp / đổi (macOS) | |
| Lưu thành | F12 | Cmd+Shift+S | Đánh số (bật/tắt) | Lưu thành… (Win/Linux) | đổi | **Bật/tắt đánh số** còn trên ribbon/menu Định dạng; macOS F12 giữ Đánh số |
| Đổi chữ hoa/thường | Shift+F3 | Shift+F3 | Xoay vòng kiểu chữ | không đổi | khớp | |
| Xóa định dạng ký tự | Ctrl+Space | — | không có | Xóa định dạng trực tiếp (Win/Linux) | một phần | HST xóa cả định dạng đoạn trực tiếp; Ctrl+Space có thể bị bộ gõ (IBus/Fcitx) dùng để đổi bộ gõ trên Linux |
| Xóa định dạng đoạn | Ctrl+Q | — | Thoát | không đổi | thiếu | HST chưa có lệnh chỉ xóa định dạng đoạn; Ctrl+Q vẫn là Thoát |
| Chỉ số trên | Ctrl+Shift+= (+) | Cmd+Shift+= | Ctrl+Shift+P | Chỉ số trên (thêm) | đổi | Ctrl+Shift+P vẫn dùng được |
| Chỉ số dưới | Ctrl+= | Cmd+= | Ctrl+Shift+B | Chỉ số dưới (thêm) | đổi | Ctrl+Shift+B vẫn dùng được. Trang Word hiện ghi chỉ số dưới là Ctrl+Shift+Minus; HST giữ Ctrl+Shift+- là gạch nối không ngắt |
| Chèn trường ngày / giờ | Alt+Shift+D / T | Control+Shift+D / T | không có | Ngày / Giờ (thay đổi được) | đổi | |
| Thụt lề đoạn | Ctrl+M | Control+Shift+M | Xóa định dạng trực tiếp | Tăng thụt lề | đổi | **Xóa định dạng trực tiếp** chuyển sang Ctrl+Space (macOS: Control+M như cũ) |
| Bỏ thụt lề | Ctrl+Shift+M | Cmd+Shift+M | Chế độ sửa (toàn cục) | Giảm thụt lề | đổi | **Chế độ sửa** còn ở menu Sửa |
| Thụt lề treo | Ctrl+T | Cmd+T | macOS Cmd+T = Kiểu dáng | Thụt lề treo | đổi | **Kiểu dáng** (macOS) vẫn có F11 |

## HST Sheets ↔ Excel

| Lệnh Microsoft | Win/Linux | macOS (Microsoft) | Trước (HST) | Sau (HST) | Trạng thái | Ghi chú / phím bị thay |
|---|---|---|---|---|---|---|
| Sửa ô hiện hành | F2 | F2 | như Excel | không đổi | khớp | |
| Đổi tham chiếu tuyệt đối/tương đối | F4 (khi sửa công thức) | Cmd+T hoặc F4 | F4 | không đổi | khớp | F4 lặp lại thao tác khi không sửa ô: **thiếu** |
| Ngày hiện tại | Ctrl+; | Control+; | Ctrl+; ; macOS Cmd+; | thêm macOS Control+; | khớp / đổi (macOS) | |
| Giờ hiện tại | Ctrl+Shift+: | Cmd+; | Ctrl+Shift+; | thêm mã phím `COLON`; macOS Cmd+; = giờ | khớp / đổi (macOS) | macOS: **Cmd+; ngày** chuyển sang Control+; (phím Excel cho Mac) |
| AutoSum | Alt+= | Cmd+Shift+T | không có | Tổng | đổi | macOS: **Cmd+Shift+T (ô Tên)** bị thay; Win/Linux Ctrl+Shift+T vẫn là ô Tên |
| Định dạng ô | Ctrl+1 | Cmd+1 | như Excel | không đổi | khớp | |
| Bật/tắt Lọc | Ctrl+Shift+L | Cmd+Shift+F hoặc Control+Shift+L | Ctrl+Shift+L | không đổi | khớp | macOS dùng Cmd+Shift+L |
| Tạo bảng | Ctrl+T | Cmd+T | macOS Cmd+T = Kiểu dáng | Chèn bảng (hộp thoại) | đổi | **Kiểu dáng** (macOS) vẫn có F11 |
| Điền xuống | Ctrl+D | Cmd+D | Điền xuống | không đổi | khớp | |
| Điền sang phải | Ctrl+R | Cmd+R | Căn phải | Điền sang phải | đổi | **Căn phải** còn trên ribbon và hộp thoại Định dạng ô |
| Định dạng Số (2 chữ số, phân cách nghìn) | Ctrl+Shift+! | Control+Shift+! | Số thập phân | không đổi | khớp | |
| Định dạng Tiền tệ | Ctrl+Shift+$ | Control+Shift+$ | Tiền tệ | không đổi | khớp | |
| Định dạng Phần trăm | Ctrl+Shift+% | Control+Shift+% | Phần trăm | không đổi | khớp | |
| Định dạng Ngày | Ctrl+Shift+# | Control+Shift+# | Ngày (chỉ mã phím `3`) | thêm mã phím `NUMBERSIGN` | đổi | GTK gửi `#`, không gửi `3` |
| Định dạng Giờ | Ctrl+Shift+@ | Control+Shift+@ | Khoa học | Giờ | đổi | **Khoa học** chuyển sang Ctrl+Shift+^ (phím Excel) |
| Định dạng Khoa học | Ctrl+Shift+^ | Control+Shift+^ | Chuẩn (General) | Khoa học | đổi | **Chuẩn** chuyển sang Ctrl+Shift+~ |
| Định dạng Chung (General) | Ctrl+Shift+~ | Control+Shift+~ | không có | Chuẩn | đổi | |
| Chọn cả cột / cả hàng | Ctrl+Space / Shift+Space | Control+Space / Shift+Space | như Excel | không đổi | khớp | |
| Xóa ô / Chèn ô | Ctrl+- / Ctrl+Shift++ | Cmd+- / Control+Shift+= | Ctrl+- / Ctrl++ | thêm `Ctrl+Shift+=`; macOS Control+Shift+= | khớp / đổi (macOS) | |
| Trang tính trước / sau | Ctrl+PgUp / PgDn | Option+←/→ | Ctrl+PgUp / PgDn | không đổi | khớp (Win/Linux) | macOS chưa đổi, chưa thử |
| Chèn trang tính mới | Shift+F11 | Shift+F11 | Lưu thành mẫu | Chèn trang tính (không hộp thoại) | một phần | Excel chèn trước trang hiện tại, HST chèn ở cuối. **Lưu thành mẫu** còn ở Tập tin ▸ Mẫu |
| Xuống dòng trong ô | Alt+Enter | Option+Return | Ctrl+Enter (Alt+Enter = điền vùng chọn) | Alt+Enter | đổi | **Điền vùng chọn** chuyển sang Ctrl+Enter (phím Excel); trong ô nhập công thức Shift+Enter vẫn xuống dòng |
| Mở rộng vùng chọn | Ctrl+Shift+mũi tên | Cmd+Shift+mũi tên | như Excel | không đổi | khớp | |
| Tính lại | F9 | F9 | Tính lại | không đổi | khớp | |
| Lưu thành | F12 | Cmd+Shift+S | Nhóm (Group) | Lưu thành… (Win/Linux) | đổi | **Nhóm** còn ở Dữ liệu ▸ Nhóm và Phác thảo; macOS F12 giữ Nhóm |

## HST Slides ↔ PowerPoint

| Lệnh Microsoft | Win/Linux | macOS (Microsoft) | Trước (HST) | Sau (HST) | Trạng thái | Ghi chú / phím bị thay |
|---|---|---|---|---|---|---|
| Trình chiếu từ đầu | F5 | Cmd+Shift+Return | F5 | thêm macOS Cmd+Shift+Return | khớp / đổi (macOS) | |
| Trình chiếu từ trang hiện tại | Shift+F5 | — | Shift+F5 | không đổi | khớp | Trang PowerPoint đọc ngày 2026-11-04 không ghi phím này |
| Trang chiếu mới | Ctrl+M | Cmd+Shift+N | Ctrl+M | thêm macOS Cmd+Shift+N | khớp / đổi (macOS) | macOS: **Mẫu mới** trong Slides còn ở Tập tin ▸ Mới ▸ Mẫu |
| Nhân đôi đối tượng | Ctrl+D | Control+D | không có | Nhân đôi trang chiếu | một phần | HST nhân đôi trang chiếu; nhân đôi đối tượng dùng Shift+F3 (hộp thoại Nhân bản) |
| Bản sao trang chiếu | Ctrl+Shift+D | Cmd+Shift+D | không có | Nhân đôi trang chiếu | đổi | |
| Nhóm | Ctrl+G | Cmd+Option+G | Ctrl+Shift+G | Ctrl+G; macOS Cmd+Option+G | đổi | |
| Bỏ nhóm | Ctrl+Shift+G | Cmd+Option+Shift+G | Ctrl+Alt+Shift+G | Ctrl+Shift+G (Ctrl+Alt+Shift+G vẫn dùng được) | đổi | **Nhóm** (Ctrl+Shift+G) chuyển sang Ctrl+G |
| Lưu thành | F12 | Cmd+Shift+S | không có | Lưu thành… (Win/Linux) | đổi | |

## Tổng hợp

| | Khớp | Đổi | Một phần | Thiếu |
|---|---|---|---|---|
| Writer ↔ Word (29 dòng) | 9 | 16 | 2 | 2 |
| Sheets ↔ Excel (25 dòng) | 15 | 9 | 1 | 0 |
| Slides ↔ PowerPoint (8 dòng) | 3 | 4 | 1 | 0 |
| **Tổng (62 dòng)** | **27** | **29** | **4** | **2** |

Dòng "khớp / đổi (macOS)" tính là khớp. Phần "thiếu" là lệnh Microsoft mà HST chưa có (không
phải phím chưa gắn): chép/dán định dạng và xóa riêng định dạng đoạn (Ctrl+Q). Ngoài ra trong
Sheets, F4 khi không sửa ô chưa lặp lại thao tác (ghi ở dòng F4).

## Phím LibreOffice bị thay

Mọi lệnh dưới đây vẫn còn trên menu/ribbon; cột "Giờ ở" là phím mới nếu có.

| Ứng dụng | Phím | Lệnh LibreOffice cũ | Giờ ở |
|---|---|---|---|
| Writer | Ctrl+D | Gạch dưới kép | Ctrl+Shift+D |
| Writer | Ctrl+Shift+D | Đoạn phải-sang-trái | menu Định dạng |
| Writer | Ctrl+1 / Ctrl+2 | Tiêu đề 1 / 2 | Ctrl+Alt+1 / 2 |
| Writer | Ctrl+5 | Tiêu đề 5 | danh sách kiểu |
| Writer | Ctrl+Shift+N | Mẫu mới (Templates) | Tập tin ▸ Mới ▸ Mẫu |
| Writer | Ctrl+Shift+V | Dán đặc biệt | Ctrl+Alt+V |
| Writer | F4 | Thuộc tính hình ảnh | menu chuột phải |
| Writer | F12 (Win/Linux) | Bật/tắt đánh số | ribbon, Định dạng ▸ Dấu đầu dòng và đánh số |
| Writer | Ctrl+M (Win/Linux) | Xóa định dạng trực tiếp | Ctrl+Space |
| Writer | Ctrl+Shift+M | Chế độ sửa | menu Sửa |
| Writer | Cmd+T (macOS) | Kiểu dáng | F11 |
| Sheets | Ctrl+R | Căn phải | ribbon |
| Sheets | Ctrl+Shift+2 | Định dạng Khoa học | Ctrl+Shift+6 (^) |
| Sheets | Ctrl+Shift+6 | Định dạng Chuẩn | Ctrl+Shift+` (~) |
| Sheets | Shift+F11 | Lưu thành mẫu | Tập tin ▸ Mẫu |
| Sheets | F12 (Win/Linux) | Nhóm | Dữ liệu ▸ Nhóm và Phác thảo |
| Sheets | Alt+Enter | Điền vùng chọn | Ctrl+Enter |
| Sheets | Ctrl+Enter (trong ô) | Xuống dòng | Alt+Enter |
| Sheets | Cmd+T (macOS) | Kiểu dáng | F11 |
| Sheets | Cmd+Shift+T (macOS) | Ô Tên | bấm vào ô Tên |
| Sheets | Cmd+; (macOS) | Ngày hiện tại | Control+; |
| Slides | Ctrl+Shift+G | Nhóm | Ctrl+G |
| Slides | Cmd+Shift+N (macOS) | Mẫu mới | Tập tin ▸ Mới ▸ Mẫu |

## Chưa xác minh

- macOS: mọi phím `install:module="macosx"` và phím ký hiệu (`Cmd+Shift+>`, `Control+Shift+#`,
  `Control+Shift+~`) chưa thử trên máy Mac; Option+Return trong Sheets đi qua cùng mã như Alt+Enter.
- Windows: phím ký hiệu (`Ctrl+Shift+>`/`<`, `Ctrl+Shift+#`/`~`, `Ctrl+Shift+=`, `Ctrl+Shift+:`)
  được gắn cả hai mã phím nhưng chưa thử trên Windows thật.
- Bàn phím không phải Mỹ (Telex/VNI qua Unikey, bàn phím Pháp/Đức…) có thể gửi mã phím khác cho các
  phím ký hiệu.

## Mặc định của tài liệu mới

`patches/libreoffice/hst-msoffice-defaults.patch`, kiểm tra bằng `tests/runtime/check-msoffice-save-format.py`
và `tests/runtime/check-defaults.py`.

| Mục | Trước | Sau | Lý do |
|---|---|---|---|
| Định dạng lưu | `.odt` / `.ods` / `.odp` | `.docx` / `.xlsx` / `.pptx` (`ooSetupFactoryDefaultFilter`) | Quyết định của chủ dự án |
| Hỏi "giữ định dạng" | khi lưu định dạng khác ODF | chỉ khi lưu đè tệp khác định dạng mặc định, ví dụ `.doc`, `.xls`, `.ppt` | `WarnAlienFormat` vẫn bật; `sfx2` không hỏi khi định dạng trùng mặc định |
| Khổ giấy | A4 (theo vùng vi) | không đổi | |
| Lề trang Writer | 2 cm mọi phía (mặc định LibreOffice, HST chưa từng chọn) | 2,54 cm mọi phía (Normal của Word) | `hst-defaults.patch` và BACKLOG không chọn lề chung. Lề NĐ 30 (20/20/30/15 mm) do trình soạn Văn bản hành chính đặt, không đổi |
| Phông Writer | Times New Roman (NĐ 30, `hst-defaults.patch`) | không đổi | Đã được duyệt; Liberation Serif thay thế cùng số đo khi máy không có |
| Phông Sheets, Slides | Liberation Sans | Calibri, không có thì Carlito (kèm trong bộ cài, cùng số đo) | Calibri là mặc định của Excel/PowerPoint 2007–2021; Carlito có đủ dấu tiếng Việt |
| Cỡ chữ Sheets | 10 pt | không đổi | Excel dùng 11 pt; đổi cỡ làm đổi chiều cao hàng, chờ chủ dự án quyết |

Khôi phục tự động vẫn lưu bản sao ODF (`ooSetupFactoryActualFilter`), không mất dữ liệu khi tài
liệu đang là `.docx`. Tệp `.docx`/`.xlsx` không chứa macro: nếu đã viết macro hãy chọn `.docm`/`.xlsm`.
Word 365 và Excel 365 đời mới dùng phông Aptos; chưa có phông tự do cùng số đo nên HST theo Calibri.
