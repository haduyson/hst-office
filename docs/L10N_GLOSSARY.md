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
| Save / Save As | Lưu / Lưu thành… | không dùng "Cất", "Lưu mới" |
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
| File (menu) | Tập tin | giữ theo bản dịch lõi |

Giữ nguyên ký tự phím tắt (`~`, `_`), biến (`%PRODUCTNAME`, `$(ARG1)`, `%1`, `%s`) và số dạng số nhiều;
`python3 scripts/l10n/check-translations.py <tệp.jsonl> --strict` kiểm tra các điểm này.

## Đợt rà soát 2026-10-30 (đã sửa)

86 dòng trong `l10n/vi-overrides.jsonl` (mỗi dòng có `reason`) cho menu, thẻ ribbon và hộp thoại hay dùng:

- "Save As" → **Lưu thành…** (trước là "Lưu mới…") ở menu Tập tin, sfx2, uui, Writer; "Luôn lưu thành:" trong Tùy chọn → Tải/Lưu (khôi phục phím tắt).
- "Save" → **Lưu** thay cho "Cất" (Tùy chọn, hộp thoại tệp đang mở).
- Trình chiếu: "Chiếu ảnh"/"ảnh chiếu" → **Trình chiếu**/**trang chiếu** (menu Trình chiếu, ẩn/hiện, sắp xếp, trang chiếu tóm tắt, trình chiếu tùy chọn…); "Insert Slide" trước dịch nhầm thành "Chế độ chèn"; "Handouts" → "Bản phát tay".
- Bảng tính: "Pivot Table" từng dịch là "Bộ lọc" → **Bảng tổng hợp**; "Insert Columns" dịch nhầm "Chèn dòng" → **Chèn cột**; "Insert Rows" → **Chèn hàng**; các lệnh chuyển trang tính.
- Chú thích (Comment) thống nhất; Hoàn tác (Undo) thống nhất, sửa một chú giải bị trộn câu.
- Lỗi chính tả/dấu: "Tranh tính", "Vản bản cuối trang", "Định đạng"; chú giải hộp thoại In ghi nhầm "Tạo một tài liệu chủ mới."
- Lỗi viết hoa "GIãn cách…", "GIá" (11 chuỗi); hộp thoại Đoạn văn: dấu hai chấm và phím tắt nhãn khoảng cách đoạn; Trang bắt đầu: "…để tạo mới một cái" → "…để tạo tài liệu mới".
- Lớp AI (`l10n/vi/`): 3 chuỗi "Lưu dưới dạng …" → "Lưu thành …".

## Phím truy cập (Alt+chữ) trong menu và ribbon

Trong mỗi cấp menu (Writer, Calc, Impress, Draw, Trang bắt đầu, kể cả menu HST) và mỗi thanh thẻ ribbon,
không hai mục nào dùng chung một chữ sau `~`/`_`. Chữ đó phải là chữ ASCII (hoặc số) có trong nhãn,
ưu tiên chữ đầu của một từ có nghĩa; không dùng chữ có dấu (Đ, Ư, Ơ, Ô, Ê, Â, Ă…) vì Alt+ư/ơ không gõ
ổn định. Chỉ dời vị trí `~`, không đổi chữ của nhãn. Thẻ ngữ cảnh (Bảng, Ảnh, Vẽ, Đối tượng, Đa phương tiện,
In, Biểu mẫu…) chỉ cần khác các thẻ luôn hiện; hai thẻ ngữ cảnh không cùng lúc hiện được phép trùng.
Mục không có `~` (menu HST trong `Addons.xcu`) do VCL tự gán chữ còn trống.

| Menu chính (cả 4 ứng dụng) | Phím | | Thẻ ribbon (Writer/Calc/Impress) | Phím |
|---|---|---|---|---|
| Tập tin | T | | Tập tin | T |
| Chỉnh sửa | S | | Trang đầu | R |
| Xem | X | | Chèn | C |
| Chèn | C | | Bố trí / Bố cục | B |
| Định dạng | D | | Xem lại | L |
| Công cụ | G | | Xem | X |
| Cửa sổ | A | | Công cụ | N |
| Trợ giúp | I | | Phần mở rộng | P |

Kiểm tra: `python3 scripts/l10n/check-access-keys.py --strict` (chạy trong `scripts/ci-quality.sh`). Script
dựng menu/ribbon từ cây nguồn (hoặc từ [`l10n/access-keys-snapshot.json`](../l10n/access-keys-snapshot.json)
khi không có cây, như trên CI), thêm menu HST đọc trực tiếp từ `Addons.xcu` (không nằm trong snapshot), rồi áp
`vi-overrides.jsonl`. Các trùng lặp
không tránh được nếu không đổi chữ nằm trong [`l10n/access-keys-exceptions.json`](../l10n/access-keys-exceptions.json)
(22 mục, ví dụ Tập tin: "Mở từ xa"/"Xuất" cùng X; Calc → Trang tính 5 cặp; Bảng → Chọn → "Ô" không có chữ
ASCII), chờ người bản ngữ quyết định. Phím ít quen cần duyệt: Hoàn tác=O, Sao chép=P, In=N, Thoát=O, Tìm=M (Calc/Impress/Draw).

**Khi báo "snapshot stale"** (đã đổi menubar `.xml`, `notebookbar.ui`, `*Commands.xcu` hoặc nhãn tiếng Anh trong
cây nguồn đã vá, lỗi liệt kê các mục bị đổi):

1. `python3 scripts/l10n/check-access-keys.py --write-snapshot` (cần cây `upstream/libreoffice` đã áp các patch);
2. `python3 scripts/l10n/check-access-keys.py --strict`: nếu có trùng mới, chỉ dời `~` bằng dòng trong
   `vi-overrides.jsonl` (không đổi chữ); chỉ thêm vào `access-keys-exceptions.json` khi nhãn thật sự hết chữ;
3. commit `l10n/access-keys-snapshot.json` cùng commit với thay đổi menu/ribbon và các dòng override.

Đổi bản dịch (`msgstr`) hay sửa menu HST không làm snapshot cũ.

## Cần người duyệt (chưa sửa, cần quyết định)

1. **Bookmark**: lõi dùng "Liên kết lưu" khắp nơi, bảng thuật ngữ ghi "Dấu trang". Đổi toàn bộ (~30 chuỗi) hay giữ?
2. **Clipboard**: "Bảng nháp" và "Bảng tạm" lẫn lộn (lõi và lớp AI, ~25 chuỗi). Đề xuất "Bảng tạm".
3. **Certificate**: "Chứng nhận" (lớp AI, ~13 chuỗi) và "Chứng chỉ" (bảng thuật ngữ).
4. **Layout** (thẻ ribbon): Writer/Impress "Bố trí", Calc "Bố cục". Chọn một.
5. **Home**: một số thanh Impress còn "Trang chủ" thay vì "Trang đầu".
6. **File**: menu "Tập tin" trong khi tài liệu HST và hướng dẫn hay viết "tệp". Có đổi menu sang "Tệp" không?
7. **Chart**: "Đồ thị" (menu Chèn) và "Biểu đồ" (nơi khác).
8. **Selection / Master / Copy / Alignment**: `term-report.py` liệt kê ~400 khác biệt trong lớp AI, phần lớn là biến thể chấp nhận được ("Lựa chọn"/"Vùng chọn", "Trang chiếu mẫu"/"Trang cái", "Căn"/"Canh"). Cần người bản ngữ chốt từng cặp.
9. Văn phong chung các hộp thoại Định dạng ô, Đoạn văn, Tìm và thay thế, In: chưa đọc lại toàn bộ bằng mắt người.

Báo cáo đầy đủ: `python3 scripts/l10n/term-report.py l10n/vi --json <tệp>`.
