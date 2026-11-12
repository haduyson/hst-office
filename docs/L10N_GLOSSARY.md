# Thuật ngữ giao diện tiếng Việt của HST Office

Bản dịch giao diện gồm bản dịch tiếng Việt có sẵn của lõi, lớp bổ sung do AI dịch
([`l10n/vi/`](../l10n/vi/), chỉ điền chuỗi còn trống) và các sửa đè có lý do
([`l10n/vi-overrides.jsonl`](../l10n/vi-overrides.jsonl), áp bằng
[`scripts/l10n/apply-overrides.py`](../scripts/l10n/apply-overrides.py) khi build). Danh sách máy đọc là
[`data/l10n/vi-glossary.json`](../data/l10n/vi-glossary.json) (`corrections`), dùng bởi
[`scripts/l10n/term-report.py`](../scripts/l10n/term-report.py). **Chưa có người bản ngữ duyệt** toàn bộ bản dịch.

## Thuật ngữ cốt lõi (bắt buộc)

| Tiếng Anh | Tiếng Việt | Ghi chú |
|---|---|---|
| Spreadsheet | Bảng tính | tài liệu/ứng dụng (HST Sheets) |
| Sheet | Trang tính | một thẻ trong bảng tính; không dùng "trang" trơn |
| Cell / Row / Column | Ô / Hàng / Cột | "dòng" dành cho dòng chữ (Line) |
| Slide | Trang chiếu | không dùng "ảnh chiếu", "hình chiếu" |
| Slide Show | Trình chiếu | |
| Handouts | Bản phát tay | |
| Save / Save As | Lưu / Lưu thành | không dùng "Cất", "Lưu mới" |
| Undo / Redo | Hoàn tác / Làm lại | |
| Copy / Cut / Paste | Sao chép / Cắt / Dán | "Chép" chỉ khi chỗ hẹp (đã có trong bản gốc) |
| Comment | Chú thích | không dùng "bình luận", "đánh giá" |
| Pivot Table | Bảng tổng hợp | không dùng "Bộ lọc" |
| Format | Định dạng | |
| Style / Paragraph Styles | Kiểu dáng / Kiểu dáng đoạn văn | |
| Frame | Khung | |
| Page Style | Kiểu dáng trang | |
| Header / Footer | Đầu trang / Chân trang | |
| Home (thẻ ribbon) | Trang đầu | |
| File / file (menu, thẻ ribbon, mọi chuỗi) | Tệp tin / tệp tin | quyết định của chủ dự án (2026-11-06): thay cho "tập tin" ở mọi chỗ, giữ chữ hoa và phím tắt (T). Lõi và lớp AI được đổi khi build bằng `replacements` trong [`vi-glossary.json`](../data/l10n/vi-glossary.json) ([`vi_terms.py`](../scripts/l10n/vi_terms.py), chạy trong `apply-overrides.py`); chuỗi do patch HST thêm phải tự viết "Tệp tin". "Tệp" trơn vẫn dùng được trong câu ("Mở tệp") |
| Certificate | Chứng thư số | quyết định của chủ dự án (2026-11-01): thuật ngữ pháp lý của Luật Giao dịch điện tử và cách gọi của VNPT-CA, Viettel-CA. Nhãn ngắn được viết "chứng thư" khi đã rõ là chứng thư số ("Lựa chọn chứng thư", "Xem chứng thư", "Cấp bởi"); câu đầy đủ dùng "chứng thư số". Không dùng "chứng chỉ", "chứng nhận" trong ký số. Chứng chỉ SSL của trang web (uui) chưa đổi |
| Thẻ ribbon theo Microsoft (2026-11-04) | Bố cục (Layout, Writer), Bố trí trang (Page Layout, Sheets), Công thức, Dữ liệu, Tham khảo (References), Gửi thư, Thiết kế, Chuyển tiếp, Hoạt hình, Nhà phát triển | nguồn: support.microsoft.com/vi-vn trang phím tắt Word, Excel, PowerPoint; `Tệp` và `Trang chủ` của Microsoft vẫn giữ `Tệp tin`, `Trang đầu` của HST. Tên nhóm chưa tìm thấy trong trang vi-vn mang `UNVERIFIED` trong `reason` của `l10n/vi-overrides.jsonl` |
| Tên thẻ và tên nhóm ribbon | Viết hoa chữ đầu | quyết định của chủ dự án (2026-11-13): chỉ viết hoa chữ đầu, như mọi nhãn tiếng Việt khác: "Bố trí trang", "Thiết kế bảng", "Định dạng ảnh", "Định dạng hình dạng", "Bố trí bảng", "Đầu trang & chân trang", "Thiết lập trang", "Sắp xếp & lọc". Tên riêng và chữ viết tắt giữ nguyên (HST, VBA, 3D). Thay cho cách viết hoa từng chữ chép theo bộ office thương mại (2026-11-04). [`test_vi_ribbon_terms.py`](../tests/unit/test_vi_ribbon_terms.py) kiểm tra các dòng `Tabbed*` trong `l10n/` và nhãn HST trong `data/ribbon/` |
| Menu bar (Menubar) | Thanh trình đơn | quyết định của chủ dự án (2026-11-13): không dùng "Thanh menu". Mục bật/tắt có trong trình đơn Xem cổ điển, nút ≡ và thẻ Xem; "menu HST", "menu Tệp tin" vẫn viết như cũ |
| Media | Đa phương tiện | quyết định của chủ dự án (2026-11-13): thẻ ngữ cảnh, nhóm của thẻ Chèn, trình đơn Chèn; không dùng "Phương tiện" trơn |
| KeyTips | Mẹo phím | nguồn: support.microsoft.com/vi-vn trang phím tắt Word, Excel |
| Search Commands (Shift+Esc) | Tìm tính năng | quyết định của chủ dự án (2026-11-04): ô tìm lệnh theo tên, gõ không dấu cũng được; có ở Trợ giúp, menu HST và thẻ Trang đầu. Ô nhập ghi "Gõ tên tính năng, không dấu cũng được". Không dùng "Tìm lệnh" |
| Dấu "..." / "…" cuối nhãn | không dùng | quyết định của chủ dự án (2026-11-06): "chỗ nào không bị cắt bớt chữ thì đừng hiện '...'". Nhãn mở hộp thoại cũng viết trơn ("Thuộc tính", "Lưu thành", "Chữ ký số"). Giữ "…" ở chữ báo đang làm ("Đang tải…", "Đợi…"), câu và thông báo, chỗ "…" thay phần bị lược ("1, 2, 3, ..."). Áp khi build bằng [`vi_ellipsis.py`](../scripts/l10n/vi_ellipsis.py) (ngoại lệ: [`vi-ellipsis-keep.json`](../data/l10n/vi-ellipsis-keep.json)); tiếng Anh giữ nguyên |
| Cancel / Yes / No | Hủy / Có / Không | viết "Hủy", không "Huỷ"; không dùng "Thôi", "Đồng ý" cho Yes |
| Dấu thanh trên oa/oe/uy | Xóa, hòa, khỏe, hủy, Tùy | kiểu mới: thanh đặt trên nguyên âm đầu khi vần đứng cuối âm tiết (không "Xoá", "hoà", "huỷ", "Tuỳ"); `apply-overrides.py` tự sửa mọi `.po` tiếng Việt khi build ([`vi_tone.py`](../scripts/l10n/vi_tone.py)); nếu chữ phím tắt nằm trên nguyên âm mang dấu thì dời sang chữ ASCII kế bên ("Xó~a") |

Giữ nguyên ký tự phím tắt (`~`, `_`), biến (`%PRODUCTNAME`, `$(ARG1)`, `%1`, `%s`) và số dạng số nhiều;
`python3 scripts/l10n/check-translations.py <tệp.jsonl> --strict` kiểm tra các điểm này.

## Đợt rà soát 2026-10-30 (đã sửa)

86 dòng trong `l10n/vi-overrides.jsonl` (mỗi dòng có `reason`) cho menu, thẻ ribbon và hộp thoại hay dùng:

- "Save As" → **Lưu thành** (trước là "Lưu mới") ở menu Tệp tin, sfx2, uui, Writer; "Luôn lưu thành:" trong Tùy chọn → Tải/Lưu (khôi phục phím tắt).
- "Save" → **Lưu** thay cho "Cất" (Tùy chọn, hộp thoại tệp đang mở).
- Trình chiếu: "Chiếu ảnh"/"ảnh chiếu" → **Trình chiếu**/**trang chiếu** (menu Trình chiếu, ẩn/hiện, sắp xếp, trang chiếu tóm tắt, trình chiếu tùy chọn…); "Insert Slide" trước dịch nhầm thành "Chế độ chèn"; "Handouts" → "Bản phát tay".
- Bảng tính: "Pivot Table" từng dịch là "Bộ lọc" → **Bảng tổng hợp**; "Insert Columns" dịch nhầm "Chèn dòng" → **Chèn cột**; "Insert Rows" → **Chèn hàng**; các lệnh chuyển trang tính.
- Chú thích (Comment) thống nhất; Hoàn tác (Undo) thống nhất, sửa một chú giải bị trộn câu.
- Lỗi chính tả/dấu: "Tranh tính", "Vản bản cuối trang", "Định đạng"; chú giải hộp thoại In ghi nhầm "Tạo một tài liệu chủ mới."
- Lỗi viết hoa "GIãn cách", "GIá" (11 chuỗi); hộp thoại Đoạn văn: dấu hai chấm và phím tắt nhãn khoảng cách đoạn; Trang bắt đầu: "…để tạo mới một cái" → "…để tạo tài liệu mới".
- Lớp AI (`l10n/vi/`): 3 chuỗi "Lưu dưới dạng …" → "Lưu thành …".

## Hộp thoại chữ ký số và nút chuẩn (beta.4.1)

- Nút chuẩn GTK (`msgctxt "stock"`, mỗi module một bản): bỏ hậu tố phím tắt kiểu "Trợ giúp (H)", "Huỷ (C)"; chữ phím tắt nằm trong từ:
  _Thêm, _Hủy, Đó_ng, _Xóa, _Chỉnh sửa, Trợ g_iúp, _Mới, Loại _bỏ, Đặt _lại, _Có. "_Yes" của `framework` được sửa bằng
  `hst-framework-stock-yes-vi.patch` (dòng đó là ngữ cảnh của `hst-document-tabs.patch`, không sửa bằng override).
- beta.5: 555 chuỗi còn lại có hậu tố "(X)" (cui, sd, chart2, extensions, sfx2, filter…) đã đặt chữ phím tắt vào trong từ, không trùng
  trong cùng hộp thoại; khi hết chữ thì sửa lời ("Đỏ:" → "Mà_u đỏ:", "Ẩn" → "Ẩn c_hữ") hoặc dời phím của nhãn gốc cùng hộp thoại.
  Không còn chuỗi "(X)" nào trong `.po`/`.mo` tiếng Việt.
- "Huỷ"/"huỷ" → "Hủy"/"hủy" ở mọi module; nút Cancel chuẩn của VCL "Thôi" → "Hủy".
- Ký số (xmlsecurity, Tùy chọn → Bảo mật, dòng chữ ký, ký PDF, GPG, cảnh báo macro, thanh trạng thái): "chứng chỉ"/"chứng nhận" → "chứng thư số"/"chứng thư"; cột "ID Kỹ thuật số được cấp bởi" → "Cấp bởi";
  tiêu đề tài liệu đã ký "tên.odt (Đã ký)".

## Phím truy cập (Alt+chữ) trong menu và ribbon

Trong mỗi cấp menu (Writer, Calc, Impress, Draw, Trang bắt đầu, kể cả menu HST) và mỗi thanh thẻ ribbon,
không hai mục nào dùng chung một chữ sau `~`/`_`. Chữ đó phải là chữ ASCII (hoặc số) có trong nhãn,
ưu tiên chữ đầu của một từ có nghĩa; không dùng chữ có dấu (Đ, Ư, Ơ, Ô, Ê, Â, Ă…) vì Alt+ư/ơ không gõ
ổn định. Chỉ dời vị trí `~`, không đổi chữ của nhãn. Thẻ ngữ cảnh (Bảng, Ảnh, Vẽ, Đối tượng, Đa phương tiện,
In, Biểu mẫu…) chỉ cần khác các thẻ luôn hiện; hai thẻ ngữ cảnh không cùng lúc hiện được phép trùng.
Mục không có `~` (menu HST trong `Addons.xcu`) do VCL tự gán chữ còn trống.

| Menu chính (cả 4 ứng dụng) | Phím | | Thẻ ribbon (Writer/Calc/Impress) | Phím |
|---|---|---|---|---|
| Tệp tin | T | | Tệp tin | T |
| Chỉnh sửa | S | | Trang đầu | R |
| Xem | X | | Chèn | C |
| Chèn | C | | Bố trí / Bố cục | B |
| Định dạng | D | | Xem lại | L |
| Công cụ | G | | Xem | X |
| Cửa sổ | A | | Công cụ | N |
| Trợ giúp | I | | Phần mở rộng | P |

**Hộp thoại**: khi có cây nguồn, script còn đọc mọi hộp thoại `.ui` (mỗi đối tượng gốc một nhóm, menu bật lên là nhóm riêng,
chỉ nhãn có `use-underline`). Trùng phím trong hộp thoại là lỗi strict khi một dòng override đã chọn phím đó và bản tiếng Anh
không trùng; trùng do bản dịch gốc là cảnh báo (`--verbose` liệt kê). CI không có cây nguồn nên bỏ qua phần này
([`access_keys_dialogs.py`](../scripts/l10n/access_keys_dialogs.py)).
beta.5 sửa thêm các phím trùng của bản dịch gốc trong hộp thoại (293 → 37 cảnh báo, 158 → 3 phím không phải ASCII).
Phần còn lại: 20 trùng y như bản tiếng Anh (hai nút cùng tên "_Mới", "_X:", C/M/Y/K…), 17 hộp thoại hết chữ ASCII
(Toán: Giãn cách, Khung, Bảng, Xem của Calc…), 3 nhãn chỉ có ký hiệu (">>", "<<", "..."). Nhập văn bản CSV còn một ngoại lệ trong
`access-keys-exceptions.json` (hết chữ).

**Theo Microsoft Office** (quyết định của chủ dự án 2026-11-04: "cố gắng giữ nguyên phím tắt giống Microsoft Office"): khi
Microsoft Office tiếng Việt có nhãn/phím tắt cho lệnh tương đương thì dùng đúng như vậy; không kiểm chứng được bản tiếng Việt thì
theo chữ của bản tiếng Anh nếu chữ đó có trong từ tiếng Việt; phím Ctrl/Alt giữ y như Microsoft Office. Mỗi dòng override ghi
nguồn hoặc giả định trong `reason`. Hộp Tìm và thay thế dùng thuật ngữ Word/Excel ("Tìm gì", "Thay thế bằng", "Tìm Tiếp",
"Thay thế", "Thay thế Tất cả", "Tìm Tất cả", "Khớp chữ hoa/thường", "Chỉ tìm toàn bộ từ", "Khớp toàn bộ nội dung ô",
"Xem trong", "Theo Hàng/Theo Cột"; nguồn: trang hỗ trợ Excel tiếng Việt của Microsoft) và không còn trùng phím trong các điều
khiển mà Writer hoặc Calc cùng hiện; vài tùy chọn hiếm (Tìm xấp xỉ, tùy chọn tiếng châu Á/CTL, Theo định dạng hiển thị) không
có phím.

Kiểm tra: `python3 scripts/l10n/check-access-keys.py --strict` (chạy trong `scripts/ci-quality.sh`). Script
dựng menu/ribbon từ cây nguồn (hoặc từ [`l10n/access-keys-snapshot.json`](../l10n/access-keys-snapshot.json)
khi không có cây, như trên CI), thêm menu HST đọc trực tiếp từ `Addons.xcu` (không nằm trong snapshot), rồi áp
`vi-overrides.jsonl`. Các trùng lặp
không tránh được nếu không đổi chữ nằm trong [`l10n/access-keys-exceptions.json`](../l10n/access-keys-exceptions.json)
(22 mục, ví dụ Tệp tin: "Mở từ xa"/"Xuất" cùng X; Calc → Trang tính 5 cặp; Bảng → Chọn → "Ô" không có chữ
ASCII), chờ người bản ngữ quyết định. Phím ít quen cần duyệt: Hoàn tác=O, Sao chép=P, In=N, Thoát=O, Tìm=M (Calc/Impress/Draw).

**Khi báo "snapshot stale"** (đã đổi menubar `.xml`, `notebookbar.ui`, `*Commands.xcu` hoặc nhãn tiếng Anh trong
cây nguồn đã vá, lỗi liệt kê các mục bị đổi):

1. `python3 scripts/l10n/check-access-keys.py --write-snapshot` (cần cây `upstream/libreoffice` đã áp các patch);
2. `python3 scripts/l10n/check-access-keys.py --strict`: nếu có trùng mới, chỉ dời `~` bằng dòng trong
   `vi-overrides.jsonl` (không đổi chữ); chỉ thêm vào `access-keys-exceptions.json` khi nhãn thật sự hết chữ;
3. commit `l10n/access-keys-snapshot.json` cùng commit với thay đổi menu/ribbon và các dòng override.

Đổi bản dịch (`msgstr`) hay sửa menu HST không làm snapshot cũ.

## Hộp thoại thường dùng theo Microsoft Office (beta.5)

Thuật ngữ lấy từ trang hỗ trợ tiếng Việt của Microsoft (`support.microsoft.com/vi-vn`); dòng nào không kiểm chứng được ghi `UNVERIFIED` trong `reason` của `vi-overrides.jsonl`.

| Tiếng Anh | Tiếng Việt | | Tiếng Anh | Tiếng Việt |
|---|---|---|---|---|
| Font (hộp thoại, thẻ) | Phông chữ | | Data Validation | Xác thực dữ liệu |
| Line and Page Breaks | Ngắt dòng và ngắt trang | | Settings / Input Message | Thiết đặt / Thông báo nhập |
| Before / After (đoạn văn) | Trước / Sau | | Name Manager / Refers to | Trình quản lý tên / Tham chiếu tới |
| Multiple / At least / Exactly | Nhiều / Tối thiểu / Chính xác | | Print area | Vùng in |
| Bullets / Numbering / Multilevel | Dấu đầu dòng / Đánh số / Danh sách đa mức | | Chart | Biểu đồ (không dùng "đồ thị" trong hộp thoại biểu đồ) |
| Wrap Text | Ngắt dòng văn bản | | Show type | Kiểu chiếu |
| Page Setup / Orientation | Thiết lập trang / Hướng | | Conditional rules | Trình quản lý quy tắc định dạng có điều kiện |

Thẻ dùng chung (`include/vcl/tabs.hrc`) đổi một chỗ là đổi ở mọi hộp thoại. Chưa đổi vì cần tách trong C++: "Nền" (Excel: Tô màu, Word: Tô bóng), "Vị trí" của Phông chữ (Word: Nâng cao, nhưng cùng chuỗi với hộp thoại Đánh số đại cương), tiêu đề "Thuộc tính trang" dùng chung Draw và Impress.

## Cần người duyệt (chưa sửa, cần quyết định)

1. **Bookmark**: lõi dùng "Liên kết lưu" khắp nơi, bảng thuật ngữ ghi "Dấu trang". Đổi toàn bộ (~30 chuỗi) hay giữ?
2. **Clipboard**: "Bảng nháp" và "Bảng tạm" lẫn lộn (lõi và lớp AI, ~25 chuỗi). Đề xuất "Bảng tạm".
3. ~~**Certificate**~~: đã chốt "chứng thư số" (xem bảng thuật ngữ cốt lõi).
4. **Layout** (thẻ ribbon): Writer/Impress "Bố trí", Calc "Bố cục". Chọn một.
5. **Home**: một số thanh Impress còn "Trang chủ" thay vì "Trang đầu".
6. ~~**File**~~: đã chốt "Tệp tin" (chủ dự án, 2026-11-06; xem bảng thuật ngữ cốt lõi).
7. **Chart**: đã thống nhất "Biểu đồ" ở mọi `.po` có tiếng Anh là Chart, cả menu Chèn (`Biể~u đồ`) và ribbon. "Đồ thị" chỉ còn cho nghĩa khác (đồ thị của hàm, bản đồ ảnh dịch cũ).
8. **Selection / Master / Copy / Alignment**: `term-report.py` liệt kê ~400 khác biệt trong lớp AI, phần lớn là biến thể chấp nhận được ("Lựa chọn"/"Vùng chọn", "Trang chiếu mẫu"/"Trang cái", "Căn"/"Canh"). Cần người bản ngữ chốt từng cặp.
9. Văn phong chung các hộp thoại Định dạng ô, Đoạn văn, Tìm và thay thế, In: chưa đọc lại toàn bộ bằng mắt người.

Báo cáo đầy đủ: `python3 scripts/l10n/term-report.py l10n/vi --json <tệp>`.
