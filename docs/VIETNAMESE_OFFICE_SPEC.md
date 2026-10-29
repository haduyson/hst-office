# Đặc tả nghiệp vụ Việt Nam

## 1. Nguồn pháp lý NĐ 30/2020/NĐ-CP

- Văn bản: Nghị định 30/2020/NĐ-CP ngày 05/03/2020 về công tác văn thư, Phụ lục I “Thể thức, kỹ thuật trình bày văn bản hành chính và bản sao văn bản”.
- Nguồn: Cổng Thông tin điện tử Chính phủ, <https://vanban.chinhphu.vn/default.aspx?pageid=27160&docid=199378>, tệp ký số <https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/03/30.signed.pdf> — SHA-256 `be2514460c953141923579e4a0ddd0249c611643a59514976790dc1d90589178`, 76 trang (bản scan).
- **Hiệu lực năm 2026: chưa xác minh** (blocker `LEG-05`). Tính năng chỉ hỗ trợ trình bày; **không tuyên bố văn bản hợp lệ pháp lý**.

## 2. Quy định đã trích (Phụ lục I, Phần I)

| Mục | Quy định | Trang PDF |
|---|---|---|
| I.1 Khổ giấy | A4 (210 × 297 mm) | 21 |
| I.2 Kiểu trình bày | Theo chiều dài A4; bảng biểu không làm phụ lục riêng có thể trình bày chiều rộng | 21 |
| I.3 Định lề | Trên, dưới 20–25 mm; trái 30–35 mm; phải 15–20 mm | 21 |
| I.4 Phông | Times New Roman, Unicode TCVN 6909:2001, màu đen | 21 |
| I.7 Số trang | Chữ số Ả Rập, cỡ 13–14, đứng, giữa lề trên, không hiện trang 1 | 21 |
| II.1a Quốc hiệu | IN HOA, cỡ 12–13, đứng, đậm, trên cùng bên phải | 21 |
| II.1b Tiêu ngữ | In thường, cỡ 13–14, đứng, đậm, canh giữa dưới Quốc hiệu, gạch nối có cách chữ, kẻ ngang nét liền dài bằng dòng chữ | 21 |
| II.2b Tên cơ quan ban hành | IN HOA, cỡ 12–13, đứng, đậm, canh giữa dưới cơ quan chủ quản; kẻ ngang 1/3–1/2 dòng chữ. Cơ quan chủ quản: IN HOA, 12–13, đứng | 22 |
| II.3c Số, ký hiệu | “Số” in thường cỡ 13 + “:”; số < 10 thêm 0; ký hiệu IN HOA cỡ 13; “/” giữa số và ký hiệu, “-” giữa các nhóm | 23 |
| II.4c Địa danh, thời gian | In thường, cỡ 13–14, **nghiêng**; ngày < 10 và tháng 1, 2 thêm 0 | 23 |
| II.5b Tên loại, trích yếu | Tên loại IN HOA 13–14 đứng đậm; trích yếu in thường 13–14 đứng đậm; kẻ ngang 1/3–1/2. Công văn: “V/v” in thường cỡ 12–13 đứng, dưới số ký hiệu cách 6pt | 24 |
| II.6e Nội dung | In thường, canh đều, cỡ 13–14; thụt đầu dòng 1 cm hoặc 1,27 cm; cách đoạn ≥ 6pt; dòng từ đơn đến 1,5 lines | 25 |
| II.7đ Quyền hạn, chức vụ người ký | TM./Q./KT./TL./TUQ.; IN HOA cỡ 13–14 đứng đậm; họ tên in thường 13–14 đứng đậm | 26–27 |
| II.9d Nơi nhận | “Kính gửi:” cỡ 13–14 đứng (Tờ trình, Báo cáo lên cấp trên, Công văn). “Nơi nhận:” cỡ 12 **nghiêng, đậm**; danh sách cỡ 11 đứng, gạch đầu dòng, “;” cuối dòng; dòng cuối “- Lưu: VT, …(n).” | 28 |

## 3. Mặc định HST (chọn trong khoảng cho phép)

| Thuộc tính | Mặc định | Lý do |
|---|---|---|
| Lề trên/dưới/trái/phải | 20 / 20 / 30 / 15 mm | Giá trị nhỏ nhất trong khoảng, người dùng chỉnh được trong khoảng |
| Cỡ chữ nội dung | 14 | Trong 13–14 |
| Quốc hiệu / Tên cơ quan | 13 / 13 | Trong 12–13 |
| Thụt đầu dòng | 1,27 cm | Một trong hai giá trị cho phép |
| Giãn dòng / cách đoạn | 1,15 lines / 6 pt | Trong khoảng đơn–1,5; ≥6pt |

## 4. Bảy loại văn bản hỗ trợ

Công văn, Thông báo, Quyết định, Tờ trình, Báo cáo, Giấy mời, Biên bản. Mọi trường (tên cơ quan, số, ký hiệu, địa danh, ngày, trích yếu, nơi nhận, người ký) **do người dùng nhập**; nếu để trống, chèn placeholder dạng `[TÊN CƠ QUAN]`. Không tự điền tên cơ quan/người ký thật.

## 5. Chuyển mã TCVN3 (ABC) / VNI → Unicode

- Chỉ chuyển khi người dùng chọn bảng mã; bộ nhận diện chỉ **gợi ý** kèm mức tin cậy.
- Preview trước, áp dụng trong một bước Undo. Nguồn bảng mã ghi trong [ENCODING_SOURCES](ENCODING_SOURCES.md).

## 6. Bảng tính

- Ngày `dd/mm/yyyy`, tiền `#,##0 ₫` (VND, không thập phân), phần trăm `0,00%` hiển thị theo locale; giá trị nền không đổi.
- Không viết lại công thức theo locale; dấu phân cách tham số do engine quyết định.
- CSV: UTF-8 có/không BOM; chọn delimiter `,` `;` `\t`; preview; mặc định nhập dạng **văn bản** để giữ `00123` và chặn công thức chèn (`=`, `+`, `-`, `@`).
