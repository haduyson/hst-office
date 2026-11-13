# Ribbon 1.0.2: sắp lại theo thói quen người dùng

Nguồn: bản audit ngày 13/11/2026 (`plans/reports/fable52-261113-1224-ribbon-ux-audit.md`), chủ dự án duyệt
làm hết P0, P1, P2 trong 1.0.2 (13/11/2026 13:20). Trang này ghi cơ chế mới và bảng "lệnh chuyển đi đâu"
cho ghi chú phát hành. Mọi lệnh bỏ khỏi ribbon vẫn còn trong thanh trình đơn và tìm được bằng Alt+Q.

## Cơ chế dùng chung

| Việc | Ở đâu |
|---|---|
| Nhóm mở lại vào chỗ trống theo mức độ dùng; chỉ nhóm ít dùng nhất mới thành nút "Tên nhóm ▾" | [`hst-ribbon-ux-engine.patch`](../../patches/libreoffice/hst-ribbon-ux-engine.patch) (`HstRibbonRegrow.hxx`), kiểm thử [`test_ribbon_regrow.py`](../../tests/unit/test_ribbon_regrow.py) |
| Thứ tự thu gọn của mọi thẻ | [`data/ribbon/scaling-priorities.json`](../../data/ribbon/scaling-priorities.json) → [`generate-ribbon-priorities.py`](../../scripts/patches/generate-ribbon-priorities.py) |
| Nhãn riêng của ribbon (`hst-ribbon-label`), dòng thứ hai của chú giải (`hst-ribbon-description`) | engine patch (vcl builder) |
| Banner một bề ngang cho mọi thẻ; tên nhóm cùng một hàng; thẻ ngữ cảnh có màu nhấn và tự mở sau lệnh chèn; gợi ý một lần dưới ô tìm | engine patch |
| Phím Alt mới, Trợ giúp = Y | [`hst-ribbon-ux-keytips.patch`](../../patches/libreoffice/hst-ribbon-ux-keytips.patch) |
| Nội dung thẻ | bộ sinh `scripts/patches/generate-ribbon-ux-{writer,calc,impress-draw}.py` |
| Một luật bố cục cho mọi nhóm của bốn ứng dụng: nhóm 1–3 lệnh là nút lớn (biểu tượng lớn, nhãn bên dưới) cao bằng nhóm, ở mọi bề ngang; nhóm nhiều lệnh xếp hai hàng nhỏ, không còn nút nhỏ đứng một mình trong cột | luật [`ribbon_layout_rules.py`](../../scripts/patches/ribbon_layout_rules.py) → bộ sinh [`generate-ribbon-ux-uniform.py`](../../scripts/patches/generate-ribbon-ux-uniform.py) (patch cuối sửa `.ui` của ribbon); thang thu gọn giữ nút lớn: [`hst-ribbon-ux-few-command-groups.patch`](../../patches/libreoffice/hst-ribbon-ux-few-command-groups.patch) |
| Banner luôn hiện ở mọi bề ngang (kể cả 1366), chỉ thu hẹp theo tỉ lệ, tối thiểu 260 px; không bản thu gọn, không ẩn | [`hst-ribbon-ux-banner-yield.patch`](../../patches/libreoffice/hst-ribbon-ux-banner-yield.patch) |

Thẻ cuối giữ tên "Phần mở rộng": nhóm tiện ích tiếng Việt đứng đầu, rồi HASON TECH và phần mở rộng, cuối cùng
một nhóm "Nhà phát triển" gom macro, điều khiển biểu mẫu và XML. Thuật ngữ: "Macro", "Trộn thư".

## Lệnh chuyển đi đâu

| Ứng dụng | Trước | Nay |
|---|---|---|
| Writer, Sheets, Slides | Trang đầu ▸ Công cụ ▾ | bỏ; Writer có nhóm "Tiện ích Việt" (Văn bản hành chính, Chuyển mã Unicode, Đọc số thành chữ), mọi ứng dụng có nhóm "Chỉnh sửa" (Tìm, Thay thế, Chọn ▾) |
| Writer | Dán đặc biệt (biểu tượng riêng) | Dán ▾ |
| Writer | Chèn ▸ Phần mở rộng, Đa phương tiện ▸ Nhạc | Phần mở rộng (thẻ cuối); Chèn ▸ Minh họa ▸ Âm thanh và video |
| Writer | 13 biểu tượng hình vẽ | Chèn ▸ Minh họa ▸ Hình dạng ▾ |
| Writer | Chèn ▸ Trang ▸ Cột | Bố cục ▸ Thiết lập trang ▸ Cột |
| Writer | Bố cục ▸ Ngắt trang, Ngắt bằng tay | Bố cục ▸ Thiết lập trang ▸ Ngắt ▾ |
| Writer | Tham khảo ▸ Nâng cấp phác thảo, Cơ sở dữ liệu thư tịch | bỏ (thanh trình đơn); Tham khảo ▸ Trích dẫn ▸ Quản lý nguồn |
| Writer | Xem ▸ Đối tượng | bỏ; Bám lưới ở Xem ▸ Hiện |
| Writer | Phần mở rộng ▸ Bảo vệ, Mẫu | Xem lại ▸ Bảo vệ; Phần mở rộng ▸ Mẫu tài liệu |
| Writer | Bố trí bảng: các biểu tượng xóa/chọn | Xóa ▾, Chọn ▾ |
| Writer | Định dạng ảnh: Trình đơn neo và 6 kiểu cuộn | Ngắt dòng văn bản ▾ |
| Sheets | Trang đầu ▸ Ô: 8 biểu tượng hàng/cột/trang tính | Chèn ▾, Xóa ▾, Định dạng ▾ |
| Sheets | Sắp xếp, Lọc trong Công cụ ▾ | Trang đầu ▸ Chỉnh sửa ▸ Sắp xếp và lọc ▾ |
| Sheets | Phần mở rộng ▸ Tiền VND, Định dạng ngày | còn ở đó và thêm ở Trang đầu ▸ Số (₫, Ngày dd/mm/yyyy) |
| Sheets | Chèn ▸ Cập nhật/Xóa bảng tổng hợp | thẻ ngữ cảnh "Phân tích bảng tổng hợp" |
| Sheets | Bố trí trang ▸ Vùng in (4 biểu tượng), Chèn Ngắt Hàng/Cột | Vùng in ▾, Ngắt trang ▾ |
| Sheets | Bố trí trang ▸ Co vừa một trang ngang | Bố trí trang ▸ Thiết lập trang ▸ Thu phóng ▾ (cả ở thẻ Xem trước khi in), lệnh của nhánh co bản in (`.uno:PrintScaleMenu`, hoàn tác được, theo từng trang tính) |
| Sheets | Dữ liệu ▸ Luồng, Nguồn XML, Nhà cung cấp dữ liệu…; Xáo trộn | Dữ liệu ▸ Nguồn khác ▾; bỏ (thanh trình đơn) |
| Sheets | Công thức ▸ Chế độ điền | bỏ (thanh trình đơn) |
| Sheets | Xem ▸ Cửa sổ ▾ (Cố định ngăn) | Xem ▸ Cửa sổ ▸ Cố định ngăn ▾ (luôn hiện) |
| Sheets, Writer, Slides | Xem ▸ Macro, Phần mở rộng ▸ Vĩ lệnh, Basic | Phần mở rộng ▸ Nhà phát triển (Chạy macro, Quản lý macro…) |
| Slides | Chèn ▸ Đổi tên, Chuyển lên/xuống trang chiếu | thanh trình đơn Trang chiếu |
| Slides | Trình chiếu ▸ Thu gọn bản trình chiếu | Tệp tin ▸ Xuất ▸ Nén bản trình chiếu |
| Slides | Hoạt hình ▸ Tương tác | Chèn ▸ Liên kết ▸ Tương tác |
| Slides | Xem lại ▸ Gạch nối từ; Xem ▸ Thanh thẻ khung xem | bỏ (thanh trình đơn) |
| Draw | Xuất/PDF (tên thẻ) | PDF |
| Draw | Sắp xếp ▸ 6 biểu tượng căn chỉnh, Méo mó, Đặt tới tròn | Căn chỉnh ▾, Biến đổi ▾ |
| Draw | Xem ▸ 9 nút bám dính | Bám dính ▾ |
| Mọi ứng dụng | Khối "Tên thẻ ▾" cuối thẻ | bỏ; lệnh chỉ có ở đó đã vào nhóm |

## Chưa làm trong 1.0.2

- Writer: tên ngắn trong thư viện kiểu (tên kiểu là tên của bộ kiểu, cần quyết định dịch chung); thư viện kiểu
  bảng, "Hàng tiêu đề"/"Hàng xen kẽ"; "Trang đầu khác", "Trang chẵn lẻ khác" (chưa có lệnh).
- Draw: "Xoay trang" (Draw chưa có lệnh).
- Tệp tin: làm mờ phần còn lại của cửa sổ khi bảng Tệp tin mở.
- Áp dụng sau khi gộp nhánh: nội dung thẻ "Gửi thư" (nhánh trộn thư), "Tách ra cửa sổ mới" (nhánh cửa sổ
  theo ứng dụng), khung chọn vị trí chữ ký ngay sau "Ký số" của HST PDF (nhánh khung chữ ký).

## Trước khi đẩy nhánh

Kiểm thử đơn vị không chạy bước kiểm tra trợ năng của bản dựng (gla11y), nên một thay đổi `.ui` qua hết kiểm thử vẫn có
thể làm hỏng bản dựng (mục trình đơn không nhãn, `labelled-by` thiếu `label-for`, dòng miễn trừ cũ khi lớp của nút
đổi). Trước khi đẩy, áp toàn bộ series lên cây mới rồi chạy
[`scripts/patches/gla11y-fresh-tree.sh`](../../scripts/patches/gla11y-fresh-tree.sh) `<cây> <tarball>`: mọi mô-đun
giao diện mà series sửa phải báo 0 lỗi nghiêm trọng.

Script đó chạy luôn
[`scripts/patches/check-ribbon-layout.py`](../../scripts/patches/check-ribbon-layout.py) `--tree <cây>`: luật bố cục
phải đúng ở mọi nhóm của bốn ứng dụng (0 lỗi). Series chỉ thêm ở cuối, nên một patch sau
`hst-ribbon-ux-uniform-layout.patch` sửa `.ui` của ribbon phải tự theo luật này; khi bộ sinh của ứng dụng thay đổi,
sinh lại patch đó bằng `generate-ribbon-ux-uniform.py --tree <cây áp series tới trước nó>`. Khi chụp lại ribbon, chạy thêm
`check-ribbon-layout.py --shots <thư mục ảnh>`: banner phải hiện ở mọi ảnh, rộng ít nhất 200 px.
