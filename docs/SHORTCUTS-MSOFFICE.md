# Phím tắt theo Microsoft Office

Chủ dự án (2026-11-04): HST Office dùng phím tắt của Microsoft Office vì phần lớn người dùng
Việt Nam đã quen; khi trùng thì phím của Microsoft Office được ưu tiên hơn phím của LibreOffice.
Giữ nguyên các phím riêng của HST: `Shift+Esc` / macOS `Option+Cmd+K` (Tìm tính năng,
`hst-feature-search.patch`), `Alt+F11` (Macro VBA), `Alt+F8` (hộp thoại Macro), `Alt+Shift+I` (HST Writer: Chèn lại trích dẫn) —
`extensions/hst-vietnamese-tools/Accelerators.xcu`; `Ctrl+Alt+.` / `Ctrl+Alt+,` (thẻ tài liệu), `Ctrl+Alt+Shift+N` (tách thẻ ra cửa sổ mới, `hst-module-window-groups.patch`). `Alt+F` mở Tệp tin (`hst-file-backstage.patch`, như thẻ File của Office) không bị patch này đụng tới.

- Cài đặt: `patches/libreoffice/hst-msoffice-shortcuts.patch` (officecfg `Accelerators.xcu`,
  phím riêng cho macOS bằng `install:module="macosx"`, phím chỉ Windows/Linux bằng
  `install:module="unxwnt"`; Alt+Enter/Ctrl+Enter của Sheets sửa trong `sc`).
  Lệnh mới và phím của chúng: `patches/libreoffice/hst-msoffice-format-keys.patch` (Writer).
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

## Mẹo phím (KeyTips)

Alt rồi thả: chữ trên thẻ; chữ của thẻ, rồi chữ của lệnh; Esc lùi một bước; Alt+chữ mở thẳng thẻ (`hst-ribbon-keytips.patch`). Chữ của thẻ lấy từ trang phím tắt vi-vn của Microsoft: Word F H N G P S M R W L, Excel F H N P M A R W, PowerPoint F H N G K A S R W. Chữ của lệnh: bảng trong `sfx2/source/notebookbar/HstKeyTipTable.hxx`, lệnh ngoài bảng được gán chữ còn trống khi mở thẻ, nên có thể khác Office.

Từ 1.0.2 (chủ dự án 14/11/2026: "Phím Alt của thẻ hiệu ứng nên để giống như MS Office"):

- Chữ của lệnh theo từng ứng dụng và từng thẻ, lấy từ Office 2021 cài trên máy HST4 (`data/ribbon/office-keytips-reference.json`, ghi bằng UI Automation; máy chỉ có giao diện tiếng Anh nên dùng chữ tiếng Anh). Ví dụ Alt, R, C là Chú thích mới ở thẻ Xem lại của mọi ứng dụng; Alt, N, SI là Trang chiếu mới ở thẻ Chèn của Slides. Bảng `data/ribbon/keytips-office-parity.json` sinh ra `hst-ribbon-keytips-office.patch`.
- Tên thẻ ribbon trong giao diện tiếng Việt không còn chữ gạch dưới (Office cũng không có). Trước đây "~Hiệu ứng" gạch chữ H, trong khi Alt+H mở Trang đầu.
- `scripts/check-keytips-parity.py` (chạy trong CI) báo lỗi khi chữ của thẻ, chữ của lệnh, chữ gạch dưới của thẻ hoặc một phím tắt trong `data/ribbon/shortcuts-office-parity.json` lệch khỏi Office. Nút » (các nhóm không đủ chỗ trên ribbon) và khối bên phải đã thu gọn cũng có chữ; mở chúng bằng chữ thì các lệnh trong khung hiện ra cũng có chữ, Esc đóng khung (`hst-ribbon-chevron.patch`).

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
| Hộp thoại Phông chữ | Ctrl+D | Cmd+D | Gạch dưới kép | Ký tự (Phông chữ) | đổi | **Gạch dưới kép** chuyển sang Ctrl+Shift+D (phím Word) |
| Gạch dưới kép | Ctrl+Shift+D | Cmd+Shift+D | Đoạn phải-sang-trái | Gạch dưới kép | đổi | **Đoạn phải-sang-trái** chỉ còn trên menu Định dạng |
| Giãn dòng đơn / đôi / 1,5 | Ctrl+1 / 2 / 5 | Cmd+1 / 2 / 5 | Tiêu đề 1 / 2 / 5 | Giãn dòng 1 / 2 / 1,5 | đổi | **Tiêu đề 1, 2** chuyển sang Ctrl+Alt+1, 2; **Tiêu đề 5** chỉ còn ở danh sách kiểu (Ctrl+3, Ctrl+4 vẫn là Tiêu đề 3, 4) |
| Danh sách dấu đầu dòng | Ctrl+Shift+L | Cmd+Shift+L | không có | Bật/tắt dấu đầu dòng | đổi | Shift+F12 vẫn dùng được |
| Kiểu Normal | Ctrl+Shift+N | Cmd+Shift+N | Mẫu mới (Templates) | Kiểu đoạn mặc định | đổi | **Tạo từ mẫu** trong Writer còn ở Tệp tin ▸ Mới ▸ Mẫu (Ctrl+Shift+N vẫn là Mẫu trong Sheets) |
| Tiêu đề 1 / 2 / 3 | Ctrl+Alt+1 / 2 / 3 | Cmd+Option+1 / 2 / 3 | không có | Tiêu đề 1 / 2 / 3 | đổi | |
| Ngắt trang | Ctrl+Enter | Cmd+Return | Ngắt trang | không đổi | khớp | |
| Sao chép / dán định dạng | Ctrl+Alt+C / Ctrl+Alt+V | Cmd+Option+C / V | Ctrl+Alt+C = Chèn chú thích; Ctrl+Alt+V = Dán đặc biệt | Sao chép / dán định dạng văn bản | đổi | Định dạng ký tự và đoạn, cùng cơ chế với cọ "Sao chép định dạng" nhưng không vào chế độ chuột; bản chép giữ tới lần chép sau; chỉ chọn một phần đoạn thì chỉ dán định dạng ký tự. Chưa dán được sang tài liệu khác. **Chèn chú thích** và **Dán đặc biệt**: hai dòng dưới |
| Chèn chú thích | Ctrl+Alt+M | Cmd+Option+A | Ctrl+Alt+C | Ctrl+Alt+M; macOS Cmd+Option+A | đổi | Sheets, Slides vẫn Ctrl+Alt+C (Excel, PowerPoint không dùng phím này cho định dạng) |
| Dán đặc biệt | trang Word không ghi phím | Cmd+Control+V | Ctrl+Alt+V | Ctrl+Alt+Shift+V; macOS Cmd+Control+V | đổi | Trang Word cho Windows dành Ctrl+Alt+V cho dán định dạng. HST dùng Ctrl+Alt+Shift+V (trước đó trùng Ctrl+Shift+V), và còn trên ribbon, menu Sửa. Excel, PowerPoint vẫn Ctrl+Alt+V nên Sheets, Slides không đổi |
| Dán chỉ văn bản | Ctrl+Shift+V | Cmd+Shift+V | Dán đặc biệt | Dán văn bản không định dạng | đổi | **Dán đặc biệt**: xem dòng trên |
| Lặp lại thao tác | F4 | Cmd+Y | Thuộc tính hình ảnh | Lặp lại | đổi | **Thuộc tính hình ảnh** còn ở menu chuột phải / nhấp đúp vào hình |
| Chính tả và ngữ pháp | F7 | Cmd+Option+L hoặc F7 | F7; macOS Cmd+Shift+; | thêm macOS Cmd+Option+L | khớp / đổi (macOS) | |
| Lưu thành | F12 | Cmd+Shift+S | Đánh số (bật/tắt) | Lưu thành (Win/Linux) | đổi | **Bật/tắt đánh số** còn trên ribbon/menu Định dạng; macOS F12 giữ Đánh số |
| Đổi chữ hoa/thường | Shift+F3 | Shift+F3 | Xoay vòng kiểu chữ | không đổi | khớp | |
| Xóa định dạng ký tự | Ctrl+Space | — | không có | Xóa định dạng trực tiếp (Win/Linux) | một phần | HST xóa cả định dạng đoạn trực tiếp; Ctrl+Space có thể bị bộ gõ (IBus/Fcitx) dùng để đổi bộ gõ trên Linux |
| Xóa định dạng đoạn | Ctrl+Q | — | Thoát | Loại bỏ định dạng đoạn văn (Win/Linux) | đổi | Chỉ xóa định dạng đoạn trực tiếp, giữ định dạng ký tự, ngắt trang và kiểu trang. **Thoát** trong Writer dùng Alt+F4 hoặc menu Tệp tin; macOS Cmd+Q vẫn là Thoát, trang Word cho Mac không ghi phím xóa định dạng đoạn nên macOS không có phím |
| Chỉ số trên | Ctrl+Shift+= (+) | Cmd+Shift+= | Ctrl+Shift+P | Chỉ số trên (thêm) | đổi | Ctrl+Shift+P vẫn dùng được |
| Chỉ số dưới | Ctrl+= | Cmd+= | Ctrl+Shift+B | Chỉ số dưới (thêm) | đổi | Ctrl+Shift+B vẫn dùng được. Trang Word hiện ghi chỉ số dưới là Ctrl+Shift+Minus; HST giữ Ctrl+Shift+- là gạch nối không ngắt |
| Chèn trường ngày / giờ | Alt+Shift+D / T | Control+Shift+D / T | không có | Ngày / Giờ (thay đổi được) | đổi | |
| Thụt lề đoạn | Ctrl+M | Control+Shift+M | Xóa định dạng trực tiếp | Tăng thụt lề | đổi | **Xóa định dạng trực tiếp** chuyển sang Ctrl+Space (macOS: Control+M như cũ) |
| Bỏ thụt lề | Ctrl+Shift+M | Cmd+Shift+M | Chế độ sửa (toàn cục) | Giảm thụt lề | đổi | **Chế độ sửa** còn ở menu Sửa |
| Thụt lề treo | Ctrl+T | Cmd+T | macOS Cmd+T = Kiểu dáng | Thụt lề treo | đổi | **Kiểu dáng** (macOS) vẫn có F11 |
| Đánh dấu trích dẫn (Mark Citation, mục lục trích dẫn pháp lý) | Alt+Shift+I | Cmd+Option+Shift+I | không có | Chèn lại trích dẫn | khác | HST: gõ `[3` hoặc `[3, tr. 15` rồi nhấn phím để trích lại nguồn số 3 (không có ô đánh dấu trích dẫn pháp lý); macOS Option+Shift+I |

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
| Chèn trang tính mới | Shift+F11 | Shift+F11 | Lưu thành mẫu | Chèn trang tính (không hộp thoại) | một phần | Excel chèn trước trang hiện tại, HST chèn ở cuối. **Lưu thành mẫu** còn ở Tệp tin ▸ Mẫu |
| Xuống dòng trong ô | Alt+Enter | Option+Return | Ctrl+Enter (Alt+Enter = điền vùng chọn) | Alt+Enter | đổi | **Điền vùng chọn** chuyển sang Ctrl+Enter (phím Excel); trong ô nhập công thức Shift+Enter vẫn xuống dòng |
| Mở rộng vùng chọn | Ctrl+Shift+mũi tên | Cmd+Shift+mũi tên | như Excel | không đổi | khớp | |
| Tính lại | F9 | F9 | Tính lại | không đổi | khớp | |
| Lưu thành | F12 | Cmd+Shift+S | Nhóm (Group) | Lưu thành (Win/Linux) | đổi | **Nhóm** còn ở Dữ liệu ▸ Nhóm và Phác thảo; macOS F12 giữ Nhóm |

## HST Slides ↔ PowerPoint

| Lệnh Microsoft | Win/Linux | macOS (Microsoft) | Trước (HST) | Sau (HST) | Trạng thái | Ghi chú / phím bị thay |
|---|---|---|---|---|---|---|
| Trình chiếu từ đầu | F5 | Cmd+Shift+Return | F5 | thêm macOS Cmd+Shift+Return | khớp / đổi (macOS) | |
| Trình chiếu từ trang hiện tại | Shift+F5 | — | Shift+F5 | không đổi | khớp | Trang PowerPoint đọc ngày 2026-11-04 không ghi phím này |
| Trang chiếu mới | Ctrl+M | Cmd+Shift+N | Ctrl+M | thêm macOS Cmd+Shift+N | khớp / đổi (macOS) | macOS: **Mẫu mới** trong Slides còn ở Tệp tin ▸ Mới ▸ Mẫu |
| Nhân đôi đối tượng | Ctrl+D | Control+D | không có | Nhân đôi trang chiếu | một phần | HST nhân đôi trang chiếu; nhân đôi đối tượng dùng Shift+F3 (hộp thoại Nhân bản) |
| Bản sao trang chiếu | Ctrl+Shift+D | Cmd+Shift+D | không có | Nhân đôi trang chiếu | đổi | |
| Nhóm | Ctrl+G | Cmd+Option+G | Ctrl+Shift+G | Ctrl+G; macOS Cmd+Option+G | đổi | |
| Bỏ nhóm | Ctrl+Shift+G | Cmd+Option+Shift+G | Ctrl+Alt+Shift+G | Ctrl+Shift+G (Ctrl+Alt+Shift+G vẫn dùng được) | đổi | **Nhóm** (Ctrl+Shift+G) chuyển sang Ctrl+G |
| Lưu thành | F12 | Cmd+Shift+S | không có | Lưu thành (Win/Linux) | đổi | |

## Thêm trong 1.0.2 (đối chiếu Office 2021 trên HST4)

`patches/libreoffice/hst-msoffice-shortcuts-parity.patch`; toàn bộ 210 dòng đối chiếu (khớp, đổi, khác có lý do) ở
`data/ribbon/shortcuts-office-parity.json`.

| Ứng dụng | Phím | Lệnh mới | Trước đó |
|---|---|---|---|
| Writer | Ctrl+F2 | Xem trước khi in | Trường (hộp thoại) |
| Writer | Ctrl+Shift+E | Theo dõi thay đổi | Nhảy tới chú thích cuối trang / neo |
| Writer | Ctrl+Shift+8 (Ctrl+*) | Hiện dấu định dạng | không có (Ctrl+F10 vẫn dùng được) |
| Writer, Sheets, Slides, PDF | Shift+F7 | Từ điển đồng nghĩa | Tự động kiểm tra chính tả |
| Writer | Ctrl+Alt+F / Ctrl+Alt+D | Chú thích cuối trang / cuối văn bản | không có |
| Sheets | Ctrl+F2 | Xem trước khi in | Hàm (hộp thoại) |
| Sheets | Shift+F3 | Chèn hàm | Xoay vòng kiểu chữ |
| Sheets | Shift+F9 | Tính lại | Theo dấu ô tham chiếu |
| Sheets | Ctrl+5 | Gạch ngang chữ | Giãn dòng 1,5 |
| Sheets | Ctrl+Shift+F3, Shift+F2, Ctrl+9, Ctrl+0 | Tạo tên, Chú thích, Ẩn hàng, Ẩn cột | không có |
| Sheets | Alt+Shift+→ / ← | Nhóm / Bỏ nhóm | không có |
| Slides | Alt+F8, Ctrl+Shift+> / <, Shift+F9, Alt+Shift+F9, Ctrl+T, Ctrl+Alt+V | Macro, cỡ chữ, lưới, thước, Phông chữ, Dán đặc biệt | không có |
| PDF | F12 | Lưu thành | không có |

Còn khác Office (có lý do trong bảng): F1 (Trợ giúp do hệ điều hành mở), Ctrl+F1 (chưa có thu gọn ribbon), Ctrl+Shift+C/V
và Ctrl+Alt+V của Word (HST theo Office bản mới 2024+, máy HST4 là Office 2021), Ctrl+Shift+A (chưa có lệnh Chữ hoa),
Shift+F12 / Ctrl+F12 / Ctrl+Shift+F12 của Word (giữ Dấu đầu dòng, Chèn bảng như cũ), Ctrl+E và Ctrl+Alt+L của Excel
(chưa có Flash Fill, Áp dụng lại bộ lọc), Ctrl+F2 của Slides (không có xem trước khi in).

## Tổng hợp

| | Khớp | Đổi | Một phần | Thiếu |
|---|---|---|---|---|
| Writer ↔ Word (31 dòng) | 9 | 20 | 2 | 0 |
| Sheets ↔ Excel (25 dòng) | 15 | 9 | 1 | 0 |
| Slides ↔ PowerPoint (8 dòng) | 3 | 4 | 1 | 0 |
| **Tổng (64 dòng)** | **27** | **33** | **4** | **0** |

Dòng "khớp / đổi (macOS)" tính là khớp. Hiện không còn lệnh Microsoft nào trong các bảng trên mà HST
chưa có; trong Sheets, F4 khi không sửa ô chưa lặp lại thao tác (ghi ở dòng F4).

`Ctrl+Q` trong Sheets và Slides vẫn là Thoát: PowerPoint cũng vậy; Excel dùng phím này mở Phân tích nhanh
(Quick Analysis), HST chưa có tính năng đó.

## Phím LibreOffice bị thay

Mọi lệnh dưới đây vẫn còn trên menu/ribbon; cột "Giờ ở" là phím mới nếu có.

| Ứng dụng | Phím | Lệnh LibreOffice cũ | Giờ ở |
|---|---|---|---|
| Writer | Ctrl+D | Gạch dưới kép | Ctrl+Shift+D |
| Writer | Ctrl+Shift+D | Đoạn phải-sang-trái | menu Định dạng |
| Writer | Ctrl+1 / Ctrl+2 | Tiêu đề 1 / 2 | Ctrl+Alt+1 / 2 |
| Writer | Ctrl+5 | Tiêu đề 5 | danh sách kiểu |
| Writer | Ctrl+Shift+N | Mẫu mới (Templates) | Tệp tin ▸ Mới ▸ Mẫu |
| Writer | Ctrl+Shift+V, rồi Ctrl+Alt+V | Dán đặc biệt | Ctrl+Alt+Shift+V (macOS Cmd+Control+V), ribbon, menu Sửa |
| Writer | Ctrl+Alt+C | Chèn chú thích | Ctrl+Alt+M (macOS Cmd+Option+A), ribbon, menu Chèn |
| Writer | Ctrl+Alt+Shift+V (Win/Linux) | Dán không định dạng | Ctrl+Shift+V |
| Writer | Ctrl+Q (Win/Linux) | Thoát | Alt+F4, Tệp tin ▸ Thoát |
| Writer | F4 | Thuộc tính hình ảnh | menu chuột phải |
| Writer | F12 (Win/Linux) | Bật/tắt đánh số | ribbon, Định dạng ▸ Dấu đầu dòng và đánh số |
| Writer | Ctrl+M (Win/Linux) | Xóa định dạng trực tiếp | Ctrl+Space |
| Writer | Ctrl+Shift+M | Chế độ sửa | menu Sửa |
| Writer | Cmd+T (macOS) | Kiểu dáng | F11 |
| Sheets | Ctrl+R | Căn phải | ribbon |
| Sheets | Ctrl+Shift+2 | Định dạng Khoa học | Ctrl+Shift+6 (^) |
| Sheets | Ctrl+Shift+6 | Định dạng Chuẩn | Ctrl+Shift+` (~) |
| Sheets | Shift+F11 | Lưu thành mẫu | Tệp tin ▸ Mẫu |
| Sheets | F12 (Win/Linux) | Nhóm | Dữ liệu ▸ Nhóm và Phác thảo |
| Sheets | Alt+Enter | Điền vùng chọn | Ctrl+Enter |
| Sheets | Ctrl+Enter (trong ô) | Xuống dòng | Alt+Enter |
| Sheets | Cmd+T (macOS) | Kiểu dáng | F11 |
| Sheets | Cmd+Shift+T (macOS) | Ô Tên | bấm vào ô Tên |
| Sheets | Cmd+; (macOS) | Ngày hiện tại | Control+; |
| Slides | Ctrl+Shift+G | Nhóm | Ctrl+G |
| Slides | Cmd+Shift+N (macOS) | Mẫu mới | Tệp tin ▸ Mới ▸ Mẫu |
| Writer | Ctrl+F2 | Trường (hộp thoại) | Chèn ▸ Trường ▸ Thêm trường |
| Writer | Ctrl+Shift+E | Nhảy tới chú thích / neo | Công cụ ▸ Tùy biến (gán lại phím được) |
| Writer, Sheets, Slides, PDF | Shift+F7 | Tự động kiểm tra chính tả | thẻ Xem lại |
| Sheets | Ctrl+F2 | Hàm (hộp thoại) | Shift+F3, thẻ Công thức |
| Sheets | Shift+F3 | Xoay vòng kiểu chữ | Định dạng ▸ Văn bản |
| Sheets | Shift+F9 | Theo dấu ô tham chiếu | thẻ Công thức |
| Sheets | Ctrl+5 | Giãn dòng 1,5 (khi sửa chữ trong ô) | hộp thoại Đoạn văn |

## Chưa xác minh

- Alt+F4 đi qua trình quản lý cửa sổ / Windows nên máy kiểm tra (Xvfb, không có trình quản lý cửa sổ) không thử được.
  Slides chưa có Ctrl+Shift+C/V của PowerPoint (sao chép / dán định dạng đối tượng); `Ctrl+Alt+C/V` chỉ có ở Writer.
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
| Phông châu Á của Writer (Tùy chọn > Phông cơ bản (Châu Á)) | phông CJK của nền tảng (Noto Serif CJK SC, NSimSun…) | Times New Roman, cả trong mẫu HST (`hst-writer-cjk-default-font.patch`) | Khi phông châu Á khác, Word lưu mỗi chữ Việt dựng sẵn U+1E00–U+1EFF thành một run riêng: tệp `.docx` qua Word phình 4–6 lần và mở chậm khoảng 8 lần. Văn bản không có chữ CJK hiển thị không đổi |
| Phông Sheets, Slides | Liberation Sans | Calibri, không có thì Carlito (kèm trong bộ cài, cùng số đo) | Calibri là mặc định của Excel/PowerPoint 2007–2021; Carlito có đủ dấu tiếng Việt |
| Cỡ chữ Sheets | 10 pt | 11 pt cho bảng tính **mới** (kiểu Mặc định, `hst-sheets-default-font-size.patch`) | Như Excel (chủ dự án 2026-11-05). Tệp đã có giữ nguyên cỡ của tệp. Hàng trống theo cỡ chữ, cả ở trang tính thêm sau: khoảng 13,8 pt với Carlito (Excel 15 pt) |
| Tên phông trong tệp lưu | | `.xlsx`, `.pptx` mới ghi `Calibri`, không ghi `Carlito`, kể cả máy không cài Calibri | Bộ lọc xuất tự đổi về tên Microsoft; đã kiểm tra thật trên máy không có Calibri (`tests/runtime/check-defaults.py`). Trong ứng dụng, ô phông chữ hiện `Carlito` khi máy không có Calibri |

Khôi phục tự động vẫn lưu bản sao ODF (`ooSetupFactoryActualFilter`), không mất dữ liệu khi tài
liệu đang là `.docx`. Tệp `.docx`/`.xlsx` không chứa macro: nếu đã viết macro hãy chọn `.docm`/`.xlsm`.
Word 365 và Excel 365 đời mới dùng phông Aptos; chưa có phông tự do cùng số đo nên HST theo Calibri.
