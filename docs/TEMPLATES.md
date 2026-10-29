# Mẫu tiếng Việt của HST Office

Bộ mẫu gồm **7 Writer `.ott`, 6 Sheets `.ots`, 5 Slides `.otp`**. Nguồn nội dung
là JSON; bộ sinh dùng Python standard library (`zipfile` và XML), không chạy
LibreOffice, không tải tài nguyên và không nhúng phông chữ. Nội dung mẫu có giấy
phép **CC BY 4.0**, ghi nhận HST Office; mã bộ sinh và kiểm tra có giấy phép
**AGPL-3.0-only**.

## Danh mục và nguồn dữ liệu

| Ứng dụng | Mẫu |
|---|---|
| Writer | Công văn, Thông báo, Quyết định, Tờ trình, Báo cáo, Giấy mời, Biên bản |
| Sheets | Chấm công, Bảng lương, Dự toán, Thu chi, Thống kê, Danh sách |
| Slides | Họp cơ quan, Báo cáo đơn vị, Giảng dạy, Hội nghị, Báo cáo doanh nghiệp |

[Danh mục nguồn](../templates/catalog.json) liên kết ID, ứng dụng, tiêu đề và mô tả
vi/en, giấy phép, nguồn JSON, đường dẫn mẫu và thẻ danh mục. Các nguồn nằm trong
`templates/writer/`, `templates/sheets/`, `templates/slides/` và tuân theo
[JSON Schema](../templates/schema.json). `manifest.json` được sinh thêm SHA-256
của từng nguồn, mẫu, thẻ danh mục và hai tệp dữ liệu dùng chung.

Writer đọc trực tiếp [nd30.json](../data/vietnamese/nd30.json); Sheets đọc trực
tiếp [number-formats.json](../data/vietnamese/number-formats.json). Không sửa các
tệp này từ tác vụ mẫu. Thể thức và giới hạn nghiệp vụ được giải thích trong
[đặc tả tiếng Việt](VIETNAMESE_OFFICE_SPEC.md). Hiệu lực pháp lý của NĐ30 năm 2026
chưa được xác minh; bộ mẫu hỗ trợ trình bày, không chứng nhận tính hợp lệ pháp lý.

## Sinh và kiểm tra

Chạy từ thư mục gốc kho mã, với Python 3.12:

```bash
SOURCE_DATE_EPOCH=1767225600 python3 scripts/generate-templates.py --out dist/templates
python3 scripts/check-templates.py dist/templates --rebuild-check
python3 -m unittest discover -s tests/unit -p test_templates.py -v
```

`--output` là tên thay thế của `--out`; bộ sinh và bộ kiểm tra đều nhận
`--catalog templates/catalog.json`. Bộ kiểm tra cũng nhận `--directory`.
Không truyền `--soffice` cho bộ sinh: yêu cầu sinh ODF trực tiếp thay thế bước
sinh qua UNO trong bản kế hoạch ban đầu.

Kết quả có `writer/*.ott`, `sheets/*.ots`, `slides/*.otp`, `previews/*.svg` và
`manifest.json`. SVG là **thẻ danh mục từ nguồn**, không phải ảnh chụp hay bằng
chứng kết xuất văn bản. Bộ sinh không xóa các tệp cũ không thuộc danh mục; bộ
kiểm tra báo lỗi nếu còn mẫu ODF thừa.

Tệp `mimetype` luôn đứng đầu ZIP, không nén và không có extra fields. Các thành
viên còn lại sắp xếp theo tên; toàn bộ dùng ZIP_STORED để tránh khác biệt zlib.
Ngày trong metadata lấy từ `SOURCE_DATE_EPOCH`; nếu thiếu, mặc định cố định là
`1767225600` (2026-01-01 UTC). ZIP dùng cùng thời điểm UTC, giới hạn dưới là
1980-01-01 và độ chính xác hai giây. Hai lần sinh cùng nguồn và epoch phải có
cùng SHA-256 cho toàn bộ 37 tệp, kể cả manifest và thẻ danh mục.

Bộ kiểm tra xác nhận 18 tệp đúng tên, MIME, manifest, CRC, XML, Unicode NFC,
hash, placeholder, công thức, khổ trang và cấu trúc bố cục. Nó từ chối macro,
script, liên kết ngoài, tham chiếu nội bộ hỏng, phông nhúng và tệp lạ trong ZIP.
Đây là kiểm tra cấu trúc theo hợp đồng dự án, không thay thế trình kiểm định
Relax NG đầy đủ hoặc kiểm tra bằng ứng dụng thực.

## Sử dụng và bố cục

Trong **File → New → Templates / Template Manager**, chọn mẫu để tạo tài liệu
mới rồi **Save As** vào thư mục của người dùng. Không mở bản mẫu đã cài bằng
lệnh Edit Template để nhập dữ liệu công việc. Giữ các trường trong `[...]` cho
đến khi có dữ liệu thật; mẫu không tự đặt tên cơ quan, người ký hay ngày ký.

Writer dùng A4, lề và cỡ chữ từ dữ liệu NĐ30, khai báo Times New Roman. Đầu trang
là bảng hai cột không viền với quốc hiệu, tiêu ngữ, cơ quan, số và ngày. Các
đường kẻ dưới cơ quan, tiêu ngữ và trích yếu là đường vector có chiều rộng theo
dữ liệu chung. Công văn đặt `V/v` dưới số, không thêm tiêu đề “CÔNG VĂN”. Trang
đầu không có số; các trang sau có trường số trang giữa lề trên. Biên bản có
khối chủ trì và thư ký. Phông được khai báo nhưng không được phân phối kèm.

Sheets dùng Liberation Sans, khai báo thêm Arial. Mỗi mẫu có năm dòng nhập,
tiêu đề ở dòng 4, dữ liệu dòng 5–9 và tổng dòng 10. Bốn dòng đầu được cố định và
lặp lại khi in; vùng in bao trọn biểu mẫu A4 ngang. Ô mã là văn bản để giữ số 0
đầu; số, tiền và tỷ lệ là giá trị số; ô ngày để trống với định dạng ngày và nhận
giá trị ngày khi người dùng nhập. Định dạng ngày, VND, số nguyên và phần trăm
được chuyển từ dữ liệu vi-VN sang kiểu số ODF, không sửa giá trị nền.

Các ô xanh nhạt chứa công thức SUM/IF hoặc phép tính số học. Thu chi tính lũy
kế; thống kê chặn phép chia cho kế hoạch bằng 0; danh sách chỉ đếm tên đã nhập.
Chấm công là bảng tuần có thể sửa quy ước. Bảng lương cộng/trừ các khoản người
dùng nhập, không tự áp thuế hay bảo hiểm. Dự toán không giả định thuế hoặc tỷ
lệ dự phòng. Ô công thức có thuộc tính được bảo vệ, nhưng **trang tính chưa bật
bảo vệ** để người dùng sửa cấu trúc. Hướng dẫn trong mẫu giải thích việc bật
bảo vệ và sao chép công thức khi thêm dòng.

Slides dùng khổ 320 × 180 mm (16:9), hai master, năm bố cục và bảng màu riêng
cho từng chủ đề. Mỗi tệp có trang tiêu đề, nội dung, phân đoạn, bảng và biểu đồ;
mọi trang có ghi chú tiếng Việt. Biểu đồ là đối tượng ODF có dữ liệu nội bộ
bằng 0 và nhãn placeholder; phải điền số liệu đã xác minh trước khi trình bày.
Không có quốc huy hay dấu cơ quan. Bộ kiểm tra runtime có phép đổi sang 4:3
bằng cách tăng chiều cao, giữ nguyên nội dung rồi xuất PPTX để kiểm tra.

## Tích hợp bộ cài

[hst-template-paths.xcu](../config/hst-template-paths.xcu) thêm đường dẫn nội bộ
`$(insturl)/share/template/hst` vào `org.openoffice.Office.Paths/Template`.
Coordinator/bộ đóng gói cần chép cây kết quả vào đường dẫn đó và đưa XCU vào
registry layer của HST. Ba thư mục `writer`, `sheets`, `slides` cung cấp nhóm
mẫu; danh mục JSON dành cho giao diện danh mục offline của HST.

XCU không đổi `WritePath` hoặc `UserPaths`, nên mẫu cá nhân được giữ riêng.
Không chạy bộ sinh vào thư mục mẫu cá nhân. Việc xuất hiện trong Start Center,
Template Manager và mở thành tài liệu chưa đặt tên cần được xác minh trên bộ
HST đã cài; tệp cấu hình riêng lẻ chưa chứng minh tích hợp thành công.

## Kiểm tra runtime và giới hạn bằng chứng

```bash
python3 tests/runtime/check-templates.py \
  --soffice /usr/bin/soffice \
  --catalog dist/templates/manifest.json \
  --expected tests/fixtures/templates/expected.json \
  --output tests/output/templates
```

Harness tạo profile riêng dưới `tests/output/template-profiles/`, không dùng
profile đang mở. Mỗi tiến trình có timeout, PID và lệnh trong log; tiến trình
quá hạn được dừng theo process group và profile được dọn. Mỗi lần chạy dùng
thư mục kết quả mới, không tái dùng tệp xuất cũ.

Khi môi trường cho phép, harness mở đủ 18 mẫu, xuất PDF và DOCX/XLSX/PPTX, tạo
bản chỉnh sửa riêng, lưu/mở lại ODF và mở lại OOXML. Nó kiểm tra chữ Việt trong
PDF, số trang, A4/lề trong XML DOCX, master/notes/biểu đồ trong PPTX và tỷ lệ
4:3. Với Sheets, dữ liệu thử nghiệm tách riêng tại
[expected.json](../tests/fixtures/templates/expected.json); kết quả công thức
được đọc từ XLSX do LibreOffice tính lại, gồm dữ liệu trống, số khác 0, số âm và
nhánh chia cho 0. Không coi giá trị cache ban đầu trong OTS là bằng chứng tính.

Mã thoát: **0 PASS**, **1 FAIL**, **2 BLOCKED**. `runtime.json` ghi phiên bản
office, nền tảng, locale, backend, phông thay thế và kết quả từng mẫu.

Ngày 2026-10-29: kiểm tra cấu trúc, tái sinh và unit test đã chạy; runtime
**BLOCKED** trong sandbox Codex vì thao tác bind/listen socket AF_UNIX bị từ
chối. LibreOffice hệ thống là **24.2.7.2**; phép chuyển đổi thực đầu tiên thoát
1, không tạo PDF. Chưa có bằng chứng xuất PDF/OOXML, tính lại công thức hoặc
kiểm duyệt hình ảnh. Times New Roman thiếu, được fontconfig thay bằng
Liberation Serif; chưa thể xác nhận kết xuất đúng phông NĐ30. Cần chạy lại trên
host cho phép LibreOffice IPC và sau đó trên HST 26.8.1.1. Kết quả LibreOffice
không chứng minh tương thích với Microsoft Office.
