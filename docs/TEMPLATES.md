# Mẫu tiếng Việt của HST Office

Bộ mẫu gồm **68 Writer `.ott`, 11 Sheets `.ots`, 5 Slides `.otp`** (84 mẫu). Nguồn nội dung
là JSON; bộ sinh dùng Python standard library (`zipfile` và XML), không chạy
LibreOffice, không tải tài nguyên và không nhúng phông chữ. Nội dung mẫu có giấy
phép **CC BY 4.0**, ghi nhận HST Office; mã bộ sinh và kiểm tra có giấy phép
**AGPL-3.0-only**.

## Danh mục và nguồn dữ liệu

| Ứng dụng | Mẫu |
|---|---|
| Writer: Hành chính NĐ 30 (37) | Đủ 29 loại Điều 7; Quyết định gián tiếp (mẫu 1.3) kèm văn bản được ban hành, văn bản kèm theo dạng tệp điện tử riêng; phụ lục 2.1, 2.2; bản sao 3.1 (Sao y, Sao lục, Trích sao), 3.2 |
| Writer: Quy phạm pháp luật (2) | Thông tư mẫu 14, mẫu 15 kèm Quy định/Quy chế/Điều lệ/Danh mục, theo NĐ 78/2025 sửa bởi NĐ 187/2025 |
| Writer: Đảng (22) | Theo Quy định 399-QĐ/TW và Hướng dẫn 05-HD/VPTW: Nghị quyết, Quyết định, Chỉ thị, Kết luận, Quy chế, Quy định, Thông tri, Hướng dẫn, Thông báo, Thông cáo, Báo cáo, Kế hoạch, Chương trình, Đề án, Phương án, Tờ trình, Công văn, Biên bản, Giấy giới thiệu, Giấy mời, Phụ lục, Bản sao |
| Writer: Biểu mẫu văn thư (7) | Bì văn bản, dấu “ĐẾN”, phiếu giải quyết văn bản đến, danh mục hồ sơ, mục lục hồ sơ, mục lục văn bản, biên bản giao nhận (Phụ lục IV, V NĐ 30) |
| Sheets: sổ văn thư (5) | Sổ đăng ký văn bản đi, đến; sổ gửi bưu điện; sổ sử dụng bản lưu; sổ theo dõi giải quyết; mỗi tệp có trang bìa và trang sổ theo Phụ lục IV |
| Sheets | Chấm công, Bảng lương, Dự toán, Thu chi, Thống kê, Danh sách |
| Slides | Họp cơ quan, Báo cáo đơn vị, Giảng dạy, Hội nghị, Báo cáo doanh nghiệp |

Mỗi hồ sơ quy tắc là một tệp riêng: [nd30.json](../data/vietnamese/nd30.json), [qppl.json](../data/vietnamese/qppl.json) (lề trên, dưới, phải 15–20, trái 30–35; số có năm; chức vụ và số trang cỡ 13), [dang.json](../data/vietnamese/dang.json) (lề cố định, giãn dòng 20 pt, tiêu đề “ĐẢNG CỘNG SẢN VIỆT NAM”, dấu sao, 5 gạch nối, số “Số 05-QĐ/TU”). `nd30.validate_margins` kiểm theo hồ sơ của loại văn bản. Loại văn bản và chỗ giữ chỗ ở [document-types.json](../data/vietnamese/document-types.json) và `data/vietnamese/skeletons-*.json`.

**Không có mẫu trong nghị định:** Phụ lục III NĐ 30 không có mẫu riêng cho Hợp đồng, Bản ghi nhớ, Bản thỏa thuận, Thư công. Bốn mẫu này theo thể thức chung của Phụ lục I, không mang số mẫu; siêu dữ liệu `Căn cứ` của từng tệp và trang hướng dẫn nói rõ. Hướng dẫn 05 cũng không có mẫu nội dung riêng từng loại, chỉ có sơ đồ và bảng cỡ chữ. Cỡ phong bì không được nghị định quy định, HST chọn 220 × 110 mm.

**Chưa làm theo quyết định của chủ dự án:** các mẫu VBQPPL khác của Phụ lục III NĐ 187: mẫu 01–13 và 16–26 (mẫu 26 là phụ lục; cách đánh số phụ lục La Mã và số trang riêng đã có khi gõ dòng “Phụ lục I” trong thân Thông tư). Văn bản Đảng chưa có mẫu: Cương lĩnh, Điều lệ, Chiến lược, Tuyên bố, Lời kêu gọi, Quy hoạch, Dự án; giấy tờ Giấy chứng nhận, Giấy đi đường, Giấy nghỉ phép, Phiếu chuyển, Phiếu gửi, Thư công (Điều 6 Quy định 399).

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

## Mẫu của LibreOffice còn lại

`hst-templates-hst-only.patch` (chủ dự án 2026-11-05) không cài các mẫu tiếng Anh của LibreOffice (thư thương mại, danh
thiếp, CV, sơ yếu) và `draw/bpmn.otg` (có tên LibreOffice); `hst-file-backstage-polish.patch` đã bỏ mẫu tiếng Nhật, tiếng
Trung. Còn lại trong danh sách mẫu, cùng các mẫu HST trên:

- Writer: Mặc định, Hiện đại, Đơn giản (`styles/`).
- Sheets: chỉ 6 mẫu HST; LibreOffice không có mẫu Sheets nào.
- Slides: 23 nền trình chiếu `presnt/`, tên hiển thị đã dịch (Tổ ong, Kẹo…).

Bước `scripts/templates/apply-presnt-vi.py` trong mọi kịch bản build (cạnh `apply-icon-overrides.py`, chạy lại được, có `--check`) làm sạch cây nguồn: chữ Latinh chỉ còn nằm trong `Freshes/content.xml` và trong ảnh thu nhỏ của cả 23 nền (các nền khác có ô giữ chỗ trống); ảnh thu nhỏ mới ở `assets/templates/presnt-thumbnails/` có chữ tiếng Việt, tạo bởi `scripts/templates/render-thumbnails.py presnt`. Bỏ mô tả “LibreOffice Impress Template” của Candy, Freshes, Grey Elegant, Growing Liberty, Yellow Idea (giấy phép chuyển sang thuộc tính `License`, ghi nhận ở [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md)), bỏ `meta:generator` tên LibreOffice ở mọi nền, bỏ đường dẫn xuất Inkscape trong SVG của Blueprint Plans. Đã xem riêng từng ảnh nhúng PNG, JPG của từng nền (32 tệp, 8 SVG kiểm bằng nội dung): không có tên hay logo LibreOffice.

Ảnh thu nhỏ của các mẫu HST ở `assets/templates/thumbnails/` là trang đầu thật của mẫu, render bằng `render-thumbnails.py catalog`; bộ sinh nhúng vào `Thumbnails/thumbnail.png`. Sau khi đổi bố cục cần render lại.

Kiểm tra: `tests/runtime/check-template-lists.py` (danh sách thật và ảnh chụp để nhìn).

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
cùng SHA-256 cho mọi tệp, kể cả manifest và thẻ danh mục.

Bộ kiểm tra xác nhận mọi tệp mẫu đúng tên, MIME, manifest, CRC, XML, Unicode NFC,
hash, placeholder, công thức, khổ trang và cấu trúc bố cục. Nó từ chối macro,
script, liên kết ngoài, tham chiếu nội bộ hỏng, phông nhúng và tệp lạ trong ZIP.
Đây là kiểm tra cấu trúc theo hợp đồng dự án, không thay thế trình kiểm định
Relax NG đầy đủ hoặc kiểm tra bằng ứng dụng thực.

## Sử dụng và bố cục

Trong **File → New → Templates / Template Manager**, chọn mẫu để tạo tài liệu
mới rồi **Save As** vào thư mục của người dùng. Không mở bản mẫu đã cài bằng
lệnh Edit Template để nhập dữ liệu công việc. Giữ các trường trong `[...]` cho
đến khi có dữ liệu thật; mẫu không tự đặt tên cơ quan, người ký hay ngày ký.

Mẫu Writer và trình hướng dẫn dùng chung một bố cục: `hst_office.nd30_layout.build_layout()` tạo các khối, rồi
`scripts/templates/writer.py` (ODF) hoặc `nd30_writer.py` (UNO) kết xuất, nên hai đường không thể lệch nhau. Một kiểu trang
cho mọi trang: lề trang 10 mm cộng đầu trang cao cố định 10 mm, thân trang bắt đầu ở 20 mm ở trang 1 và các trang sau, cả
PDF lẫn DOCX mở lại; số trang nằm trong dải đầu trang, giữa vùng chữ, trang đầu trống. Đầu văn bản là bảng không viền:
cơ quan bên trái, quốc hiệu và tiêu ngữ bên phải, hàng sau là số và ngày (cùng đường cơ sở, kể cả khi xuống dòng), rồi `V/v`
với Công văn. Đường kẻ là viền dưới đoạn văn, dài theo dòng chữ thật (`nd30_metrics.py`, bảng độ rộng trong
`data/vietnamese/font-metrics-times.json`); với mẫu `.ott` đường kẻ tính theo chỗ giữ chỗ, sau khi điền tên thật cần chỉnh
lại nếu lệch nhiều, còn trình hướng dẫn tính theo tên đã nhập. Biên bản theo mẫu 1.9: Thư ký bên trái, Chủ tọa bên phải,
Nơi nhận bên dưới. Phông được khai báo nhưng không được phân phối kèm. Dấu chỉ mức độ khẩn là con dấu khắc sẵn đóng tay
(Phụ lục I, Phần II.2.b), mẫu không sinh.

Đo trên bản HST thật cho mọi loại Writer, nội dung nhiều trang: `tests/runtime/check-template-layout.py` (PDF, DOCX mở lại;
thân trang, lề, số trang, hàng số và ngày, đường kẻ). Máy đo không có Times New Roman, dùng Liberation Serif (cùng độ rộng ký tự).

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

Khi môi trường cho phép, harness mở đủ các mẫu, xuất PDF và DOCX/XLSX/PPTX, tạo
bản chỉnh sửa riêng, lưu/mở lại ODF và mở lại OOXML. Nó kiểm tra chữ Việt trong
PDF, số trang, A4/lề trong XML DOCX, master/notes/biểu đồ trong PPTX và tỷ lệ
4:3. Yêu cầu riêng của từng loại (quốc hiệu–tiêu ngữ hay tiêu đề Đảng, số/ký
hiệu, nơi nhận/kính gửi, chữ ký, đoạn giữ chỗ để sửa, khổ giấy và lề theo hồ
sơ NĐ30/VBQPPL/Đảng, sổ đăng ký) nằm trong bảng
[requirements.json](../tests/fixtures/templates/requirements.json); mẫu nào
trong catalog không có mục trong bảng thì FAIL. Với Sheets, dữ liệu thử nghiệm tách riêng tại
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

## Phát hành trong sản phẩm

Bộ mẫu đi kèm extension `hst-vietnamese-tools` (mọi hệ điều hành, không cần sửa bộ cài):
`scripts/build-extensions.py` chạy bộ sinh với `SOURCE_DATE_EPOCH=1767225600` và đặt các
tệp vào `template/hst-van-ban/`, `template/hst-bang-tinh/`, `template/hst-trinh-chieu/`
của gói, cùng `template/groupuinames.xml` (tên nhóm hiển thị "HST — Văn bản hành chính",
"HST — Bảng tính", "HST — Trình chiếu"). `Paths.xcu` của extension thêm `%origin%/template`
vào đường dẫn mẫu, nên Trình quản lý mẫu (Trang bắt đầu → Mẫu, Tệp tin → Mẫu) liệt kê
đủ các nhóm, thêm `template/hst-qppl/` ("HST — Văn bản quy phạm pháp luật"), `template/hst-dang/` ("HST — Văn bản của Đảng"), `template/hst-van-thu/` ("HST — Biểu mẫu văn thư").
Kiểm tra khi chạy: `tests/runtime/check-template-manager.py`.

## Tìm mẫu

Trình hướng dẫn **HST → Văn bản hành chính…**: ô *Loại văn bản* là ô tìm nhanh, lọc ngay khi gõ, không cần dấu (`cong van`, `gm`, `ttr`, `qd`), chia nhóm Hành chính, Quy phạm pháp luật, Đảng, Biểu mẫu văn thư; mũi tên lên xuống, Enter, Esc. Cách so khớp như **Tìm tính năng**: `nd30_search.fold` làm giống `foldForSearch` trong `hst-feature-search.patch`. Sổ văn thư mở thành bảng tính mới. **Tìm tính năng** chỉ liệt kê lệnh, nên mọi loại văn bản được thêm vào từ khóa của lệnh này trong `FeatureSearch.xcu`.

Kiểm tra: `tests/unit/test_nd30_search.py`, `tests/runtime/check-nd30-search.py`.

Trang **Mới** của Tệp tin chỉ có ba ô mẫu và lưới `TemplateLocalView`, chưa có ô tìm. Nếu cần, thêm một ô nhập phía trên lưới và gọi `filterItems` như Trình quản lý mẫu; đây là thay đổi C++ và `.ui`, chưa làm.
