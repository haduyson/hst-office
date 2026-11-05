**Rà soát độc lập thể thức văn bản Việt Nam và đầu ra HST Office**

Ngày chốt nghiên cứu: **05/11/2026**. Checkout: `31caeef051afaa7507417483e8894843635bce1d`. Phạm vi: nghiên cứu pháp lý, đọc nguồn, sinh và đo tài liệu thử nghiệm; không sửa mã sản phẩm, không commit hoặc push. Không suy rộng kết quả đến các ngày sau 05/11 trong tháng 11/2026.

**Kết luận dành cho chủ sản phẩm**

1. **Bốn con số mặc định 20 / 20 / 30 / 15 mm, theo thứ tự trên / dưới / trái / phải, nằm trong khoảng NĐ30 cho phép.** Cả bốn đều ở cận dưới. Không có căn cứ gọi riêng bộ số này là “sai chuẩn”. Tuy nhiên, đầu ra thực tế có vấn đề: mẫu cài sẵn thêm đầu trang vào bên dưới lề trên, khiến thân trang từ trang 2 bắt đầu ở **27,27 mm**, vượt trần 25 mm. Xuất và mở lại DOCX làm thân trang đầu bắt đầu ở **28,65 mm** trong phép thử.
2. **Hai đường tạo văn bản của HST không tương đương.** Bộ sinh `.ott` và trình hướng dẫn dùng chung JSON nhưng khác cách bố trí đầu trang, đường kẻ, giãn dòng và chữ ký. Trình hướng dẫn giữ được thân trang ở 20 mm trong phép thử; ngược lại, nó đặt sai chế độ UNO cho giãn dòng 1,15. Có thêm lỗi lệch hàng số/ngày, căn cứ quyết định chưa in nghiêng, và bố trí biên bản khác mẫu phụ lục.
3. **Công văn đã có**, cả trong danh mục mẫu và trình hướng dẫn. Việc cần ưu tiên là hoàn thiện mẫu 1.5 và kết xuất nhiều trang/DOCX, không phải bổ sung một mục Công văn trùng lặp.
4. **Thông tư cần nhóm mẫu VBQPPL riêng.** Căn cứ là NĐ78/2025 **đã được NĐ187/2025 sửa đổi và thay toàn bộ Phụ lục I–IV**. Lề trên/dưới/phải của nhóm này là 15–20 mm, trái 30–35 mm; số trang cỡ 13; chức vụ người ký cỡ 13; số văn bản có năm ban hành. Không thể chỉ đổi tên “THÔNG BÁO” thành “THÔNG TƯ”. Bộ lề mặc định HST tình cờ nằm trong giao của hai khoảng, nhưng không làm hai thể thức trở thành một.
5. Về hiệu lực: đã tải bản gốc NĐ30, NĐ78, NĐ187 và các phụ lục cần đối chiếu. Kết quả chỉ mục CSDL quốc gia ghi NĐ30 “Còn hiệu lực”, NĐ78 “Hết hiệu lực một phần”. **Không tải trực tiếp được trang lịch sử hiệu lực của CSDL**, nên không chứng nhận đã loại trừ tuyệt đối mọi sửa đổi/thay thế đến 05/11/2026. Không tìm thấy văn bản thay NĐ30 hoặc sửa tiếp NĐ78 ngoài NĐ187 trong phạm vi tra cứu; phân biệt rõ điều này với một xác nhận hiệu lực đầy đủ.

**1. Cách đọc bằng chứng**

- **[PL]**: đọc được văn bản gốc/phụ lục trên máy chủ chính thức; PDF scan được OCR để tìm kiếm và kiểm tra ảnh trang ở các điểm quyết định. Số trang dưới đây là **trang PDF tính từ 1**, khác số trang in lại ở đầu mỗi phụ lục.
- **[ĐO]**: sinh/mở/xuất tài liệu thật, đọc XML ODF/OOXML, đo khung bố cục Writer và tọa độ chữ/đường kẻ PDF.
- **[MÃ]**: đọc nguồn, chưa đồng nghĩa với kết quả khi chạy.
- **[SL]**: suy luận hoặc đề xuất sản phẩm. **[CX]**: chưa xác minh được.

“Đạt” trong các bảng là đạt **thuộc tính đang xét**, không phải chứng nhận toàn bộ văn bản hợp lệ. Nội dung nghiệp vụ, thẩm quyền ban hành, chữ ký và con dấu không được chứng minh bằng một bản mẫu trống.

Các trích dẫn trong dấu ngoặc kép là phần văn bản quy định; phần giải thích ngoài ngoặc là diễn giải. Liên kết nguồn ký hiệu S1–S10 được liệt kê đầy đủ cuối báo cáo.

**2. Văn bản áp dụng và tình trạng kiểm chứng**

| Nhóm / câu hỏi | Quy tắc và trích nguyên văn nguồn | HST hiện tại | Kết luận và mức bằng chứng |
|---|---|---|---|
| Văn bản hành chính nhà nước | NĐ30 Điều 2.1: “Nghị định này áp dụng đối với cơ quan, tổ chức nhà nước và doanh nghiệp nhà nước”; Điều 8.4 dẫn Phụ lục I. [S1, tr.1, 5] | Bảy loại trong `nd30.json` tự nhận theo NĐ30 | [PL] Đúng hệ quy chiếu cho các mẫu hành chính này. |
| Phân biệt VBQPPL với hành chính | Điều 4.2.a: “Đối với văn bản quy phạm pháp luật được thực hiện theo quy định của Luật Ban hành văn bản quy phạm pháp luật”; văn bản hành chính thực hiện theo Chương II NĐ30. [S1, tr.3] | Chưa có mô hình VBQPPL riêng | [PL] Không suy rộng định dạng NĐ30 sang mọi văn bản nhà nước. Văn bản chuyên ngành còn phải xét quy định ngành. |
| Hiệu lực gốc của NĐ30 | Điều 37: “Nghị định này có hiệu lực thi hành kể từ ngày ký.” Ngày ký 05/03/2020; Điều 37 làm hết hiệu lực NĐ110/2004 và NĐ09/2010. [S1, tr.1, 19] | Tài liệu và dữ liệu HST ghi hiệu lực 2026 chưa xác minh | [PL] Xác minh được ngày hiệu lực gốc. Không lấy ngày ký số đăng tải 09/03/2020 làm ngày có hiệu lực. |
| NĐ30 có bị sửa/thay đến tháng 11/2026? | Chỉ mục của CSDL Bộ Nội vụ hiển thị “Hiệu lực: Còn hiệu lực”; trang liên quan liệt kê văn bản bị hết hiệu lực. [S2] | `legalStatus2026 = UNVERIFIED` | [CX] Không tìm thấy văn bản sửa/thay trong tra cứu chính thức, nhưng mở trực tiếp CSDL lỗi 502/403/DNS. Chỉ mục có độ trễ vài tháng. Có cơ sở tiếp tục đối chiếu NĐ30, chưa đủ cơ sở khẳng định một cách tuyệt đối “chưa từng sửa đổi đến 05/11/2026”. |
| NĐ78/2025 | Điều 78.1: “Nghị định này có hiệu lực thi hành từ ngày 01 tháng 4 năm 2025.” Điều 78.2 làm hết hiệu lực NĐ34/2016, NĐ154/2020, NĐ59/2024. [S3, PDF chính tr.62] | Không có Thông tư trong danh mục | [PL] Đây là hệ quy định mới cho VBQPPL; NĐ78 không phải văn bản thay NĐ30 về công tác văn thư. |
| Sửa đổi NĐ78 | NĐ187 Điều 3.3.a: “Thay thế Phụ lục I ban hành kèm theo Nghị định số 78/2025/NĐ-CP bằng Phụ lục I ban hành kèm theo Nghị định này”; các điểm b–d thay tương tự Phụ lục II–IV. Điều 4: “Nghị định này có hiệu lực thi hành từ ngày 01 tháng 7 năm 2025.” [S4, tr.38] | Chưa có dữ liệu NĐ78/NĐ187 | [PL] Phải dùng phụ lục thay thế từ 01/07/2025, không chỉ phụ lục NĐ78 tháng 4. Đã đọc cả hai bản Phụ lục I. |
| NĐ78 có sửa tiếp sau NĐ187? | Chỉ mục CSDL ghi “Hết hiệu lực một phần”; có VBHN4231/VBHN-BTP và các phụ lục hợp nhất. [S5] | Chưa theo dõi | [CX] Không tìm thấy sửa tiếp trong tra cứu, nhưng trang lịch sử và PDF hợp nhất không tải được. Kết luận chắc chắn là **78 + 187**, chưa xác nhận tính đầy đủ tuyệt đối của lịch sử đến ngày chốt. Không coi VBHN là một nghị định sửa đổi mới. |
| Văn bản Đảng năm 2026 | Quy định 399-QĐ/TW, Điều 18.2: “Quy định này thay thế Quy định số 66-QĐ/TW, ngày 06/02/2017…” và Quy định 223-QĐ/TW. [S6, tr.18] | Không có nhóm mẫu Đảng | [PL] Đã tải bản ký, hiệu lực từ ngày ký 09/01/2026. Không dùng 66-QĐ/TW như căn cứ hiện hành độc lập. |
| Hướng dẫn trình bày của Đảng | Hướng dẫn 05-HD/VPTW ngày 27/05/2026, Phần III.1: “Hướng dẫn này có hiệu lực từ ngày ký, thay thế Hướng dẫn số 36-HD/VPTW, ngày 04/3/2018…” [S7, tr.29] | Mẫu quốc hiệu nhà nước | [PL] Cần hồ sơ thể thức riêng nếu phục vụ tổ chức Đảng. Đã xác minh việc thay 36; chưa kiểm chứng một danh mục lịch sử sửa đổi đầy đủ sau 05. |

Tra cứu hiệu lực đã dùng các cụm số hiệu đầy đủ cùng “sửa đổi”, “thay thế”, “hiệu lực”, “2026” trên CSDL quốc gia và hệ thống Chính phủ; không coi các kết quả trùng số **30/2026/NĐ-CP** hoặc **78/2024/NĐ-CP** là sửa đổi của hai nghị định đang xét. Những bài tổng hợp chỉ dùng để tìm bản gốc, không dùng thay phụ lục gốc.

**3. Khổ giấy và định lề theo từng hệ văn bản**

| Quy tắc | Trích nguồn gốc | Giá trị HST / đầu ra đã đo | Phán định |
|---|---|---|---|
| A4 hành chính | “Khổ giấy: Khổ A4 (210 mm x 297 mm).” [S1, PL I, Phần I.I.1, tr.21] | XML: 210 × 297 mm; PDF và khung Writer khoảng 210,01 × 297,00 mm | [ĐO] Đạt; sai số chuyển đổi đơn vị dưới 0,02 mm không phải chọn sai khổ giấy. Áp dụng chung các loại ở Điều 7, không có lề riêng cho Công văn, Báo cáo hay Quyết định. |
| Hướng giấy hành chính | “Theo chiều dài của khổ A4.” Ngoại lệ: “Trường hợp nội dung văn bản có các bảng, biểu nhưng không được làm thành các phụ lục riêng thì văn bản có thể được trình bày theo chiều rộng.” [S1, I.2, tr.21] | Bảy mẫu dọc; `nd30_page.py` đặt `IsLandscape=False` | [ĐO/MÃ] Đạt cho mẫu dọc thông thường; chưa hỗ trợ lựa chọn ngoại lệ trong wizard. Không phải mọi văn bản hành chính đều bắt buộc dọc bất kể bảng biểu. |
| Lề hành chính | “Định lề trang: Cách mép trên và mép dưới 20 - 25 mm, cách mép trái 30 - 35 mm, cách mép phải 15 - 20 mm.” [S1, I.3, tr.21] | JSON: trên/dưới/trái/phải = 20/20/30/15; thân trang `.ott`: trang 1 = 20,00; trang 2 thử dài = 27,27 mm | Bộ mặc định **trong khoảng, ở cận dưới**; thân trang tiếp theo **ngoài khoảng**. Chi tiết bảng đo ở phần 5. |
| Bản sao ra giấy | “Các thành phần thể thức bản sao được trình bày trên cùng một tờ giấy (khổ A4), ngay sau phần cuối cùng của văn bản cần sao dưới một đường kẻ nét liền, kéo dài hết chiều ngang của vùng trình bày văn bản.” [S1, PL I, Phần II.II.2.a, tr.35] | Không có mẫu bản sao | [PL/MÃ] Cần khối chứng thực sao cuối bản sao; không phải một trang mẫu quốc hiệu độc lập không gắn với văn bản cần sao. Sơ đồ tr.36 ghi các khoảng lề như hành chính. |
| Bản sao điện tử | “Định dạng Portable Document Format (.pdf), phiên bản 1.4 trở lên”; “Độ phân giải tối thiểu: 200dpi”; “Tỷ lệ số hóa: 100%.” Còn yêu cầu ảnh màu. [S1, PL I, Phần II.I.2, tr.35] | Chưa có quy trình/mẫu sao trong các nguồn được kiểm | [PL] Không được suy ra đáp ứng bản sao điện tử chỉ vì xuất được DOCX/PDF. Thông tin ký sao ở góc trên phải trang đầu, Times New Roman 10, đứng, đen; hình ảnh chữ ký số cơ quan không hiển thị theo mục I.3. |
| A4 và hướng giấy VBQPPL, gồm Thông tư | “Văn bản được trình bày trên trang giấy khổ A4 (210 mi-li-mét (mm) x 297 mi-li-mét (mm)).” “Phần phụ lục của văn bản quy phạm pháp luật có các bảng, biểu thì có thể được trình bày theo chiều rộng.” [S4, PL I, Mục 1.I.1–2, tr.40; bản gốc S3 PL I tr.1 cùng quy tắc] | HST có A4 dọc nhưng chưa có mẫu VBQPPL | [PL] Hướng ngang được nêu cho **phụ lục có bảng/biểu**, khác cách diễn đạt ngoại lệ của NĐ30. |
| Lề VBQPPL hiện hành đã xác minh | “Định lề trang: Cách mép trên và mép dưới, mép phải 15 - 20 mi-li-mét (mm), cách mép trái 30 - 35 mi-li-mét (mm).” [S4, I.3, tr.40] | Nếu dùng bộ số HST 20/20/30/15: trên/dưới ở cận trên, trái/phải ở cận dưới | **Bộ số có thể dùng**, nhưng không được dùng chung toàn bộ mẫu NĐ30. Mức trên/dưới 25 mm hợp NĐ30 sẽ **không hợp** quy tắc này. |
| Giấy văn bản Đảng | “Văn bản giấy và văn bản điện tử trình bày trên khổ giấy A4 (210 mm x 297 mm).” Giấy tờ hành chính có thể A4, A5 hoặc mẫu in sẵn. [S7, Phần II.IV.3, tr.28] | Chỉ A4 dọc hành chính nhà nước | Không đại diện đầy đủ phạm vi văn bản Đảng. |
| Lề văn bản Đảng | “Lề trên: Cách mép trên trang văn bản 20 mm”; lề dưới 20, trái 30, phải 15. Mặt sau khi in hai mặt: trái 15, phải 30; trên/dưới 20. [S7, IV.4.1–4.2, tr.28] | Bộ số HST trùng mặt trước; không có thiết lập lề đối xứng trong mẫu | [PL] Đây là **giá trị cố định của hệ Đảng**, không phải bằng chứng NĐ30 chỉ cho một bộ lề. Không dùng sự trùng hợp để áp mẫu nhà nước cho Đảng. |

**Trong khoảng nhưng ở cực trị và chuyện “thông lệ cơ quan”.** [SL] Với A4, HST chọn vùng thân rộng nhất/cao nhất từ bốn khoảng NĐ30: 165 × 257 mm nếu không bị đầu trang chiếm chỗ. Nếu chọn đồng thời 25/25/35/20 thì vùng này là 155 × 247 mm. Cảm giác “sát mép hơn” có cơ sở hình học. Tuy nhiên, **không có khảo sát đại diện cơ quan trong nghiên cứu này để tuyên bố một bộ số khác là phổ biến nhất hoặc bắt buộc**. Những mức như 25/20/30/20 có thể là lựa chọn thiết kế của sản phẩm, phải ghi là lựa chọn và thử lại xuống dòng; không được gọi là chuẩn pháp lý duy nhất. Ưu tiên sửa khung thân/đầu trang trước khi đổi bộ mặc định.

**4. HST được kiểm tra như thế nào**

Đã đọc [catalog](../../templates/catalog.json), toàn bộ bảy `templates/writer/*.json`, [bộ sinh](../../scripts/generate-templates.py), [writer.py](../../scripts/templates/writer.py), [writer_styles.py](../../scripts/templates/writer_styles.py), [nd30.json](../../data/vietnamese/nd30.json), toàn bộ `nd30*.py`, [wizard_nd30.py](../../extensions/hst-vietnamese-tools/python/hst_office/wizard_nd30.py), [đặc tả](../../docs/VIETNAMESE_OFFICE_SPEC.md) và [tài liệu mẫu](../../docs/TEMPLATES.md). Đọc thêm `actions.py`, `dialogs.py`, `data_files.py` để xác định đường thực thi và mặc định.

| Đường tạo tài liệu | Điều đã xác minh | Điểm cần phân biệt |
|---|---|---|
| Mẫu cài sẵn | `generate-templates.py` gọi `scripts/templates/writer.py`, đọc `data/vietnamese/nd30.json`; sinh `.ott` trực tiếp bằng ODF | Không đi qua `nd30_writer.py`/UNO. JSON loại văn bản chỉ chứa loại và đoạn gợi ý; lề/phông/kiểu nằm trong nguồn chung và bộ sinh. |
| Trình hướng dẫn | `wizard_nd30.py` lấy cùng bảy loại; `actions.py` gọi `build_layout()` rồi `insert_layout()` | Đường kẻ được ước lượng theo chữ; số/ngày được xử lý; chữ ký dùng hàm chung. Hai ô áp dụng trang và số trang mặc định bật vì `Dialog.check(..., state=True)`. |
| Dữ liệu được nạp | `data_files.py` ưu tiên dữ liệu đóng gói trong extension, sau đó dữ liệu checkout | Ở checkout này dùng `data/vietnamese/nd30.json`. Chưa kiểm tra một gói HST đã cài có dữ liệu cũ/khác hay không. |
| Tài liệu mô tả | Đặc tả nói Quốc hiệu mặc định 13; dữ liệu và PDF thực tế là **12 pt** | Đây là sai lệch mô tả, không phải lỗi cỡ chữ pháp lý: 12 vẫn được NĐ30 cho phép. |
| Ảnh xem trước | SVG do bộ sinh tạo là thẻ danh mục; preview wizard là chữ đơn cách | Không phải bằng chứng đo lề, phông hoặc xuống trang. Nghiên cứu này dùng PDF và khung bố cục thật. |

Môi trường đo: Ubuntu 24.04, **LibreOffice 24.2.7.2**, Python/UNO; không có binary HST đã biên dịch trong checkout. Cài công cụ phục vụ nghiên cứu trong môi trường, sinh mọi đầu ra vào `/tmp/hst-nd30-review/`. Không thay nguồn sản phẩm để làm mẫu “đẹp hơn”. Times New Roman **không có**; `fc-match 'Times New Roman'` trả Liberation Serif và PDF xác nhận phông thay thế này. Vì vậy đây là bằng chứng về **đầu ra từ nguồn HST qua engine LibreOffice hệ thống**, chưa phải nghiệm thu HST 26.8 trên Windows/macOS hoặc Microsoft Word.

Đã thực hiện:

1. Sinh cả 18 mục danh mục; mở **7/7 mẫu Writer `.ott`**, xuất PDF, ODT và DOCX; mở lại DOCX và xuất PDF lần nữa.
2. Gọi trực tiếp các hàm sản phẩm `nd30_layout.build_layout()` và `nd30_writer.insert_layout()` qua UNO thật cho **7/7 loại wizard**. Không giả lập UNO, không sửa hàm. Không tương tác cửa sổ wizard trong phép thử này.
3. Tạo bản thử nhiều trang của Công văn: thêm 75 đoạn văn vào bản sao `.ott` tạm thời trước khối chữ ký, và tạo thân 75 đoạn qua wizard. Chạy thêm wizard không đánh số trang để tách tác động của đầu trang. Đây là dữ liệu kiểm tra, không phải thay nội dung mẫu trong repo.
4. Xuất `writer_layout_dump` để lấy biên trang, thân, đầu trang, ô bảng. Đo PDF bằng PyMuPDF: cỡ/phông, đường cơ sở chữ, hộp chữ, đường kẻ. Đối chiếu `word/document.xml`, `word/styles.xml`, `word/header*.xml` và XML ODF.
5. Mở lại ODT/DOCX trong phiên engine riêng và lặp phép đo khung bố cục các trường hợp trọng yếu để phân biệt giá trị cấu hình với kết xuất.

Dữ liệu wizard thử dùng cơ quan giả “ỦY BAN NHÂN DÂN TỈNH A” / “SỞ NỘI VỤ”, số `5`, ký hiệu `SNV-VP`, Hà Nội, `2026-11-05`, trích yếu “Triển khai công tác văn thư”, người ký giả “Nguyễn Văn A”. Các loại khác dùng cùng dữ liệu để kiểm tra renderer; không coi nội dung thử hoặc ký hiệu Công văn này là nội dung nghiệp vụ hợp lệ của các loại khác.

Đo khung theo twip: `mm = twip × 25,4 / 1440`; PDF: `mm = point × 25,4 / 72`. Tọa độ y tính từ mép trên tờ giấy. **Biên khung thân khác mép hộp chữ**: chữ nằm trong dòng có độ cao/phần nhô và bảng có đệm. Khoảng giấy trống sau dòng cuối của một văn bản ngắn không phải lề dưới. Ví dụ Công văn một trang kết thúc chữ khoảng y=141,42 mm, vẫn có lề dưới cấu hình 20 mm, không phải lề dưới 155,58 mm.

**5. Bảng đo lề, đầu/cuối trang và DOCX**

| Quy tắc / nguồn | Trích nguồn | HST đo được | Phán định |
|---|---|---|---|
| Trái 30–35; phải 15–20; dưới 20–25 mm | “cách mép trái 30 - 35 mm, cách mép phải 15 - 20 mm”; trên/dưới 20–25 [S1, tr.21] | Khung thật: trái **30,004**, phải **14,993**, dưới **20,002** mm; vùng ngang **165,012 mm**. DOCX giữ các giá trị này trong phép đo | **Đạt ở cận dưới**, làm tròn đơn vị giải thích 14,993 thay vì 15; không gọi sai vì 0,007 mm. |
| Lề trên mẫu `.ott`, trang đầu | “Cách mép trên và mép dưới 20 - 25 mm” [S1] | Không có đầu trang thật ở `FirstPage`; thân bắt đầu **20,002 mm**; chữ Quốc hiệu bắt đầu khoảng **20,181 mm** ở cả bảy mẫu | **Đạt, cận dưới**. Bảng tên “Header” là bảng trong thân, không phải vùng header lặp của trang. |
| Lề trên `.ott`, trang tiếp theo | Cùng quy tắc [S1] | Công văn dài: đầu trang bắt đầu **20,002**, cao thực **7,267** mm; thân bắt đầu **27,270 mm**. ODF đặt min-height 5 mm và khoảng dưới 2 mm; chiều cao thực còn chịu chữ/đoạn số trang | **Không đạt biên trên của vùng thân**: hơn 25 mm khoảng 2,27 mm. Sáu mẫu còn lại dùng chung hai page layout; kết luận về chúng là suy luận từ cùng nguồn, không giả vờ đã chạy dài cả bảy. |
| Lề trên wizard | Cùng quy tắc [S1] | `TopMargin=10 mm`, header cố định 10 mm, khoảng cách thân đặt 0. Khung đo: đầu trang **10,001–20,002**, thân **20,002 mm** ở trang 1 và trang 2 | **Đạt vùng thân**. Không được chỉ nhìn `TopMargin=10` rồi báo vi phạm: phải tính cả vùng đầu trang và xác nhận khung thật. |
| Đệm bảng ở trang đầu | NĐ30 quy định lề và vị trí thành phần, không quy định đệm ô bắt buộc | Mẫu `.ott`: đệm 0; wizard: đệm trên/dưới **0,97 mm** từ mặc định Writer. Chữ Quốc hiệu wizard bắt đầu **21,152 mm** | Đạt lề; khác khoảng **0,97 mm** so với mẫu do đệm ô, không phải đổi lề trang. |
| Footer / lề dưới | NĐ30 không ấn định một chiều cao footer chung [S1] | Cả hai đường thử: **FooterIsOn=False**, không có khung footer; thân kết thúc y≈277,001 mm | Đạt lề dưới 20 mm. Không trừ thêm một footer tưởng tượng. Chèn vào tài liệu đã có footer chưa được kiểm. |
| Số trang | “cỡ chữ 13 đến 14, kiểu chữ đứng”; “được đặt canh giữa theo chiều ngang trong phần lề trên của văn bản, không hiển thị số trang thứ nhất.” [S1, I.7, tr.21] | `.ott`: 13 pt; trang 2 hộp chữ y=**20,20–25,28**, đường cơ sở 24,29. Wizard: 14 pt; y=**10,22–15,69**, đường cơ sở 14,62. Đều ẩn trang 1 và hiện 2, 3… ở các trang sau | Đạt cỡ/kiểu/ẩn trang đầu. Mẫu đặt số thấp cùng vùng lề trên thực bị phình; lỗi chắc chắn là thân bắt đầu 27,27. NĐ30 **không ghi** số trang phải cách mép trên đúng 10 mm như hướng dẫn Đảng. |
| Canh giữa số trang | Trích dẫn trên [S1] | Tâm số khoảng **112,55 mm**, gần tâm vùng chữ `(30 + 195)/2 = 112,5`; không phải tâm giấy 105 mm | Canh giữa vùng trình bày. Không kết luận lệch chuẩn chỉ từ chênh 7,5 mm với tâm tờ giấy; NĐ30 không cho một tọa độ x tuyệt đối. |
| DOCX của mẫu cài sẵn | Giữ A4 và các khoảng lề [S1] | XML mẫu ngắn: `w:top=1417` ≈24,99 mm; bản dài `1546` ≈27,27 mm; `w:header=1134` ≈20,00 mm. Sau mở lại, **khung thân trang 1 =28,646**, trang 2 bản dài **28,169 mm** | **Không giữ bố cục/lề trên thực**. Bản ngắn nhìn `w:top` riêng còn tưởng đạt; blank first header cao 8,643 mm đẩy thân xuống. |
| DOCX của wizard | Giữ A4 và các khoảng lề [S1] | `w:top=1134`, `header=567`, `bottom=1134`, `left=1701`, `right=850` twip. Đo lại thân trang 1 và 2 =**20,002 mm**, header 10,001 mm | **Giữ khung lề trong phép thử này**. Không đồng nghĩa mọi xuống dòng, phân trang hoặc font đều giống. |
| Tính ổn định phân trang | Không có quy định phải đúng một số trang cho nội dung thử; đây là kiểm tra tương thích | Công văn dài mẫu: **8 trang → 6 trang** sau DOCX; wizard: **7 → 5 trang**. Cả bảy mẫu ngắn vẫn một trang; mỗi mẫu cài sẵn dịch phần đầu xuống khoảng **8,64 mm** sau DOCX | **Không bảo toàn kết xuất**. Cùng nội dung chữ, cùng engine, có thay đổi xuống dòng. Chưa xác định hết nguyên nhân; không gán tất cả cho lề hoặc cho thiếu phông. |

Vùng header trong bản `.ott` dài và trong DOCX **đã được đo bằng khung bố cục**, không suy ra bằng cách cộng mù các thuộc tính UNO. Một số thuộc tính UNO đọc trước bố trí trả chiều rộng bảng không phản ánh khung đang in; báo cáo dùng kích thước `tab/cell` trong layout dump và lưới bảng DOCX để kết luận.

**6. Đối chiếu từng thành phần với Phụ lục I và các mẫu Phụ lục III NĐ30**

Các cỡ chữ dưới đây đã kiểm trong PDF/runs và XML, trừ nơi ghi rõ chỉ đọc mã. “Đạt cỡ/kiểu” không bỏ qua việc môi trường đang thay phông.

| Quy tắc | Trích nguồn gốc | Giá trị HST đã đo / quan sát | Phán định |
|---|---|---|---|
| Phông, mã, màu | “Phông chữ tiếng Việt Times New Roman, bộ mã ký tự Unicode theo Tiêu chuẩn Việt Nam TCVN 6909:2001, màu đen.” [S1, I.4, tr.21] | XML/runs yêu cầu Times New Roman; chữ Unicode tiếng Việt và màu đen. PDF thực dùng **LiberationSerif**, Bold, Italic, BoldItal | Khai báo đúng; **bản PDF ở môi trường này không đúng phông được nêu**. Không khẳng định máy HST có Times New Roman cũng sẽ sai. Phải thử lại khi có phông thật trước khi chốt chiều dài dòng/đường kẻ. |
| Quốc hiệu | “chữ in hoa, cỡ chữ từ 12 đến 13, kiểu chữ đứng, đậm” và phía trên cùng bên phải [S1, II.1.a, tr.21] | Cả hai đường: **12 pt**, hoa, đậm, đứng; bên phải, một dòng | Đạt cỡ/kiểu/vị trí tương đối, **cận dưới**. Đặc tả nói 13 không khớp thực thi. |
| Tiêu ngữ | “cỡ chữ từ 13 đến 14, kiểu chữ đứng, đậm”; dưới Quốc hiệu, “Hai dòng chữ Quốc hiệu và Tiêu ngữ được trình bày cách nhau dòng đơn.” [S1, II.1, tr.21–22] | **14 pt**, đậm, đứng, canh giữa. `.ott` có line-height 100%; wizard hiện ra dòng đơn với chế độ minimum rất nhỏ | Đạt cỡ/kiểu, **cận trên**. Wizard không thực hiện đúng chế độ tỷ lệ như chú thích mã, xem hàng giãn dòng. |
| Đường dưới tiêu ngữ | “đường kẻ ngang, nét liền, có độ dài bằng độ dài của dòng chữ.” [S1, II.1.b] | `.ott`: đường **62,00 mm**, hộp chữ tiêu ngữ khoảng **60,43 mm**; wizard đường khoảng **62,50 mm**, chữ khoảng **60,43 mm** | **Không trùng chiều dài trong bản đo**: dư khoảng 1,57 / 2,07 mm. Phụ lục không cho dung sai. Chưa suy rộng sai số này sang Times New Roman thật; thuật toán ước lượng/fixed width không bảo đảm yêu cầu trên mọi máy. |
| Cơ quan chủ quản / ban hành | Tên ban hành “chữ in hoa, cỡ chữ từ 12 đến 13, kiểu chữ đứng, đậm”; chủ quản 12–13 đứng; tên dài “có thể trình bày thành nhiều dòng.” [S1, II.2.b, tr.22] | **13 / 13 pt**, chủ quản thường, ban hành đậm. Hai placeholder bên trái đều bị xuống **hai dòng** trong mẫu `.ott` | Đạt cỡ/kiểu; xuống dòng **được phép**, không tự nó là vi phạm. Nhưng làm đầu văn bản cao và tác động hàng số/ngày. Chủ quản là “nếu có”; `.ott` luôn có placeholder, wizard bỏ dòng khi trường trống. |
| Bảng đầu văn bản | Các ô 1–4 ở sơ đồ, không có tỷ lệ cột 35:65 bắt buộc [S1, Mục IV, tr.33–34] | Bảng thật **165,012 mm**; trái **57,750**, phải **107,262 mm**, tỷ lệ xấp xỉ 35:65. Lưới DOCX **3274/6081 twip**, giữ nguyên | **Không có căn cứ chấm sai tỷ lệ**. [SL] Cột trái hẹp là nguyên nhân đã thấy của xuống dòng; cần thử tên cơ quan dài/ngắn thay vì coi 35:65 là con số pháp định. |
| Đường dưới tên cơ quan | “có độ dài bằng từ 1/3 đến 1/2 độ dài của dòng chữ” [S1, II.2.b] | `.ott` cố định **24,99 mm**. Với placeholder hai dòng, ngay dòng dài khoảng 45,61 mm kể cả khoảng trắng cuối thì nửa dòng chỉ 22,81 mm; dòng “HÀNH]” khoảng 15,27 mm. Wizard “SỞ NỘI VỤ”: đường khoảng **9,97 mm**, chữ **23,61 mm**, tỷ lệ≈42% | Mẫu placeholder **không đạt tỷ lệ ở bản đo**; wizard đạt ở tên thử ngắn. Không bảo đảm đạt với mọi tên: wizard ước lượng cả chuỗi, không đo dòng đã wrap. |
| Số và ký hiệu | “Từ ‘Số’… cỡ chữ 13”; “với những số nhỏ hơn 10 phải ghi thêm số 0 phía trước”; công văn dùng viết tắt cơ quan và đơn vị/lĩnh vực [S1, II.3, tr.22–23] | **13 pt**, đứng. Wizard chuyển `5` thành `05`, xuất `Số: 05/SNV-VP`. Mẫu có `Số: [số]/[KÝ HIỆU]` | Đạt trình bày và ví dụ wizard. `.ott` không tự đệm số/kiểm tra ký hiệu khi người dùng thay placeholder. Không nên thêm mặc định “CV” như viết tắt tên loại trong số Công văn. |
| Ngày tháng và hàng ngang với số | “được trình bày trên cùng một dòng với số, ký hiệu văn bản”; cỡ 13–14 nghiêng [S1, II.4.c, tr.23] | **14 pt nghiêng**. `.ott`: đường cơ sở ngày **41,17 mm**, số **51,38 mm**, lệch **10,21 mm**. Wizard dữ liệu thử: ngày **39,53**, số **42,35**, lệch **2,82 mm** | Đạt cỡ/kiểu, **không đạt cùng dòng trong hai tình huống đo**. Hai ô có luồng đoạn độc lập; ngày và số không nằm trong một hàng đồng bộ. Đây là lỗi bố cục có căn cứ, không chỉ cảm giác thẩm mỹ. |
| Chuẩn hóa ngày | Ngày <10 và tháng 1,2 thêm 0 [S1, II.4.b, tr.23] | Wizard xuất “ngày **05** tháng **11** năm 2026”; hàm xử lý tháng 1,2 có đệm. `.ott` là chỗ trống | Ví dụ thực đạt; phần xử lý các tháng khác xác minh bằng mã, không tuyên bố đã chạy mọi ngày. Khi wizard bỏ trống ngày, placeholder không tự thêm chữ “ngày” như đường `.ott`; cần rà lại trải nghiệm này. |
| Tên loại/trích yếu văn bản có tên loại | Tên loại hoa 13–14 đậm; trích yếu thường 13–14 đậm; canh giữa [S1, II.5.b, tr.24] | **14 pt**, đậm, canh giữa vùng thân. `.ott` trích yếu khoảng **61,58 mm**, đường **30,00 mm**≈48,7% | Đạt ở placeholder này, cận trên của cỡ và gần cận trên tỷ lệ đường 1/3–1/2. Đường 30 mm cố định sẽ không phù hợp mọi trích yếu. |
| Công văn không có tên loại ở giữa | Mẫu “1.5 - Công văn” đặt V/v dưới số; không có dòng tiêu đề CÔNG VĂN [S1, PL III, tr.48] | Hai đường đều không in tiêu đề CÔNG VĂN; `V/v` 13 pt đứng dưới số, khoảng trước **6 pt** | **Đạt đặc điểm phân biệt Công văn**. V/v placeholder hoặc trích yếu thử wrap hai dòng vì cột hẹp; không tự là lỗi pháp lý. |
| Kính gửi | “cỡ chữ từ 13 đến 14, kiểu chữ đứng”; nhiều người nhận phải xuống dòng, dấu gạch thẳng dưới dấu hai chấm [S1, II.9.d, tr.28] | **14 pt đứng**. `.ott` một dòng căn trái x≈30,04; wizard một người nhận căn giữa. Wizard có nhánh nhiều người nhận, tính thụt theo ước lượng chữ | Đạt cỡ/kiểu cho trường hợp đã đo. Căn trái/giữa không được quy tắc này chốt một tọa độ số; mẫu 1.5 là căn cứ bố cục nên ưu tiên bám mẫu. **Chưa đo trường hợp nhiều người nhận thực**; không coi phép ước lượng dưới dấu hai chấm là đã được kiểm chứng. |
| Nội dung | “được canh đều cả hai lề, kiểu chữ đứng; cỡ chữ từ 13 đến 14”; đầu dòng “1 cm hoặc 1,27 cm” [S1, II.6.e, tr.25] | **14 pt**, canh đều; thụt **12,70 mm**; dòng đầu bắt đầu x≈42,74, dòng sau x≈30,04 | Đạt; cỡ ở cận trên, thụt là một trong **hai giá trị** được ghi. Không diễn giải NĐ30 thành cho mọi giá trị tùy ý giữa 10 và 12,7 mm. |
| Cách đoạn | “khoảng cách giữa các đoạn văn tối thiểu là 6pt” [S1, II.6.e] | Body `.ott` và wizard: **6 pt**, UNO khoảng 2,12 mm, DOCX `after=120` twip | Đạt **cận dưới**. Không áp tối thiểu 6 pt của nội dung để bắt mọi dòng Quốc hiệu/cơ quan cũng phải cách 6 pt. |
| Giãn dòng | “tối thiểu là dòng đơn, tối đa là 1,5 lines.” [S1, II.6.e] | `.ott`: 115%, baseline nội dung dài cách **6,526 mm**≈18,5 pt. Wizard: `Mode=1, Height=115`, DOCX `lineRule=atLeast`, `line=65` twip; baseline cách **5,680 mm**≈16,1 pt | `.ott` đạt 1,15. Wizard **không phải 1,15**: UNO `PROP=0`, `MINIMUM=1` [S8]; đang đặt chiều cao tối thiểu khoảng 1,15 mm. Bản đo hiển thị khoảng dòng đơn nên chưa kết luận vi phạm khoảng đơn–1,5, nhưng rõ ràng sai ý định dữ liệu/đặc tả. |
| Căn cứ ban hành quyết định | “kiểu chữ nghiêng, cỡ chữ từ 13 đến 14”; mỗi căn cứ xuống đoạn, kết thúc theo quy tắc II.6.a [S1, tr.24] | `.ott` `[Căn cứ ban hành quyết định]`, `[Theo đề nghị…]` đều **14 pt đứng**, vì mọi dòng dùng Body. Wizard coi body là các đoạn thường | **Không đạt định dạng căn cứ** trong mẫu có sẵn; wizard chưa có cấu trúc ngữ nghĩa để áp riêng. |
| Thẩm quyền, lời quyết định, Điều | Mẫu 1.2 có dòng “THẨM QUYỀN BAN HÀNH”, “QUYẾT ĐỊNH:”; II.6.đ yêu cầu từ Điều, số và tiêu đề đứng đậm [S1, tr.25, 43] | `.ott` không có dòng thẩm quyền trước căn cứ; “QUYẾT ĐỊNH:” và “Điều 1/2” đều **14 pt thường**, căn đều/thụt Body | **Thiếu cấu trúc và sai kiểu** so với mẫu trực tiếp. Không chỉ sửa lề là hoàn thiện được Quyết định. |
| Quyền hạn/chức vụ/họ tên người ký | “cỡ chữ từ 13 đến 14, kiểu chữ đứng, đậm”; họ tên canh giữa quyền hạn/chức vụ [S1, II.7, tr.26–27] | **14 pt đậm**; bảng ký **82,497 / 82,515 mm**, gần 50:50. Wizard có hai dòng quyền hạn/chức vụ, tên canh giữa; khoảng trống chủ động 60 pt trong đoạn giữa | Đạt cỡ/kiểu/vị trí tương đối với văn bản thông thường. **60 pt không phải số luật bắt buộc**. Mẫu `.ott` dùng đoạn trống khác, nên khoảng ký không đồng nhất với wizard. |
| Nơi nhận | “cỡ chữ 12, kiểu chữ nghiêng, đậm”; danh sách “cỡ chữ 11, kiểu chữ đứng”; sát lề trái và ngang hàng quyền hạn/chức vụ [S1, II.9.d, tr.28] | Nhãn **12 pt đậm nghiêng**, danh sách **11 pt đứng**, cùng hàng bảng với người ký. Có `;` và dòng Lưu kết thúc `.` | Đạt cỡ/kiểu và vị trí chung. Hai cỡ khác nhau có đường cơ sở không hoàn toàn trùng nhưng nằm cùng hàng; không báo lỗi chỉ vì khác hộp chữ. |
| “Như trên” và dòng lưu | Với Công văn/Tờ trình/Báo cáo cấp dưới gửi cấp trên: sau “Nơi nhận” là “Như trên” [S1, II.9.b, tr.27]; mẫu 1.5 tr.48 | `.ott` chỉ có `- [Nơi nhận];`, không hướng dẫn riêng “Như trên”. Wizard chỉ có “Như trên” nếu người dùng nhập; tự thêm `Lưu: VT, [đơn vị soạn thảo]` khi thiếu | **Chưa hoàn thiện mẫu hướng dẫn**. Phép thử nhập “Như trên” đạt; không được coi đây là tính năng tự chèn. Số lượng bản lưu/ký hiệu soạn thảo chưa có trường riêng; tùy trường hợp và chú thích mẫu. |
| Biên bản | Mẫu 1.9: **THƯ KÝ bên trái, CHỦ TỌA bên phải**, nơi nhận dưới; có thời gian bắt đầu/kết thúc, địa điểm, thành phần, chủ trì, thư ký, diễn biến [S1, tr.52] | `.ott` đặt **CHỦ TRÌ trái, THƯ KÝ phải**, họ tên bên trái baseline≈166,71, bên phải≈175,35 mm, lệch **8,64 mm**. Wizard vẫn một khối người ký chung, không tạo hai bên thư ký/chủ tọa | **Không khớp mẫu 1.9**; wizard thiếu cấu trúc đặc thù. `.ott` có các gợi ý nội dung nhưng chưa đủ để nói “đã hỗ trợ đúng mẫu”. Ngày ở đầu phải được dùng chung trong HST dù mẫu 1.9 không thể hiện dòng ngày ở đó. |
| Dấu/chữ ký số, độ khẩn, phụ lục, thông tin liên hệ | Các vị trí tương ứng ở II.7–8, III và sơ đồ IV [S1, tr.26–34] | Mẫu để chỗ ký; không sinh dấu/chữ ký thực, khối độ khẩn, phụ lục hay metadata sao | **Chưa được hỗ trợ/kiểm chứng bởi bộ mẫu được xét**. Không kết luận về các tính năng ký số khác của toàn sản phẩm vì ngoài phạm vi nguồn này. |

**Các khác biệt cần lưu ý khi sử dụng wizard trên tài liệu có sẵn.** [MÃ] Khi tắt “áp dụng trang”, wizard không bảo đảm lề/A4 của tài liệu đích; layout vẫn tính chiều rộng từ bộ mặc định. Khi đã có header, `apply_page_layout()` bỏ qua việc ghi lại số trang để giữ nội dung header cũ; vì vậy không thể bảo đảm số trang đúng chỗ/ẩn trang 1 trong trường hợp đó. Chỉ áp page style của vị trí con trỏ, không chuẩn hóa mọi section/page style của một tài liệu nhiều kiểu trang. Các nhánh tài liệu cũ có header/footer, nhiều section, bảng ngang và nhiều người nhận **chưa chạy thực tế** trong nghiên cứu này.

**7. Thông tư: phần nào dùng lại được và phần nào phải khác**

Nguồn hiện dùng là **Phụ lục I, III kèm NĐ187**, thay các phụ lục tương ứng của NĐ78. Mẫu số **14** là Thông tư của Bộ trưởng/Thủ trưởng cơ quan ngang bộ quy định trực tiếp (tr.105–106); mẫu số **15** là Thông tư ban hành Quy định/Quy chế/Điều lệ/Danh mục và văn bản kèm theo (tr.107–108). Không nhầm “Thông tư” với “Thông tri” của Đảng hoặc với “Thông báo” hành chính.

| Quy tắc | Trích nguồn | HST nếu tái dùng mẫu hành chính | Phán định |
|---|---|---|---|
| Lề và khổ | “mép trên và mép dưới, mép phải 15 - 20…”; trái 30–35; A4 [S4, tr.40] | Bộ số mặc định 20/20/30/15 hợp, nhưng `.ott`/DOCX thực đẩy thân quá 20 | Có thể dùng lại **giá trị mặc định**, phải có ràng buộc riêng và sửa bố cục. Không kế thừa dải 20–25 trên/dưới. |
| Quốc hiệu, tiêu ngữ, thân | Quốc hiệu 12–13 đậm; tiêu ngữ 13–14 đậm; thân 13–14, canh đều [S4, tr.41, 47] | Các cỡ hiện có nằm trong khoảng | Có thể dùng lại một phần style; vẫn phải kiểm tra phông thực tế. |
| Số văn bản có năm | “gồm số thứ tự của văn bản, năm ban hành văn bản, tên viết tắt của loại văn bản…” [S4, II.3.d, tr.42]; mẫu 14: `Số:…/20…/TT-…` [tr.105] | Chuỗi chung `Số: [số]/[KÝ HIỆU]`, không có trường năm có cấu trúc | Cần schema và kiểm tra riêng, ví dụ `05/2026/TT-BNV`. Không để tính đúng phụ thuộc người dùng nhét cả năm vào trường ký hiệu. |
| Tên loại | “Tên loại văn bản… cỡ chữ 14, kiểu chữ đứng, đậm” [S4, II.4.b, tr.42] | Style tên loại 14 | Có thể dùng lại cỡ; phải thêm loại THÔNG TƯ thuộc nhóm VBQPPL. |
| Căn cứ và câu ban hành | “Căn cứ ban hành văn bản… cỡ chữ 14, kiểu chữ nghiêng”; phần dưới căn cứ của thông tư có tên người/cơ quan ban hành, cụm “ban hành” và tên văn bản, 14 nghiêng [S4, III.1, tr.46–47] | Body hiện 14 đứng, không phân biệt căn cứ; mẫu quyết định dùng “QUYẾT ĐỊNH:” | **Không thể tái dùng nguyên cấu trúc hành chính.** Mẫu 14 có “Theo đề nghị của…” và “Bộ trưởng/Thủ trưởng cơ quan ngang bộ ban hành Thông tư…”. |
| Chức vụ người ký | “Chức vụ của người có thẩm quyền ký văn bản được trình bày bằng chữ in hoa, cỡ chữ 13, kiểu chữ đứng, đậm.” [S4, II.7.b, tr.45] | HST 14 pt | **Không đạt nếu dùng nguyên style**. Họ tên vẫn 13–14 theo II.7.c. |
| Số trang | “cỡ chữ 13, kiểu chữ đứng, không hiển thị số trang thứ nhất” [S4, I.7, tr.40] | Mẫu 13, wizard 14 | Mẫu đạt cỡ; wizard **14 không đạt quy tắc VBQPPL**. Phải đánh số riêng văn bản kèm theo và từng phụ lục. |
| Tổ chức nội dung | Điều/khoản/điểm và tên các cấp được quy định riêng [S4, III.2, tr.47–48] | Các chuỗi body thường, chưa có styles điều/khoản/căn cứ | Cần mẫu trực tiếp, ban hành kèm theo, sửa đổi/bãi bỏ và phụ lục, không chỉ tiêu đề mới. |
| Thụt đầu dòng | “lùi vào từ 1 cen-ti-mét (cm) đến 1,27 cen-ti-mét (cm)” [S4, III.2.a, tr.47] | 12,7 mm | Đạt. Cách diễn đạt của hệ VBQPPL là **từ…đến**, khác “1 cm hoặc 1,27 cm” trong NĐ30. |
| Nơi nhận | II.8 nêu cơ quan giám sát/kiểm tra, công báo, triển khai, liên quan, lưu; nhãn 12 đậm nghiêng, danh sách 11 đứng [S4, tr.45–46] | Dùng lại cỡ được, nội dung chỉ placeholder | Phải có gợi ý phù hợp việc ban hành VBQPPL; không tự thêm Kính gửi như Công văn. |

[SL] Nên dùng chung các thành phần kỹ thuật như đo phông, canh giữa, bảng không viền và tạo trường số trang, nhưng tách **hồ sơ quy tắc** `hành chính NĐ30` và `VBQPPL NĐ78+187`. Chọn rõ “Quyết định cá biệt” hay “Quyết định quy phạm”; tương tự với Nghị quyết. Tên gọi giống nhau không đủ để chọn thể thức.

**8. Văn bản Đảng nếu HST mở rộng phạm vi**

| Quy tắc | Trích nguồn | HST hiện tại | Phán định |
|---|---|---|---|
| Tiêu đề | “ĐẢNG CỘNG SẢN VIỆT NAM”; Phụ lục 2 quy định 15 pt, hoa, đứng, đậm [S6, Điều 15; S7 tr.31] | Quốc hiệu nhà nước 12 pt và tiêu ngữ | Không dùng mẫu hiện tại làm mẫu Đảng. |
| Tên cơ quan và số | Tên chủ quản/ban hành 14 pt; số/ký hiệu 14 pt; minh họa “Số 127-QĐ/TW” [S7, PL2, tr.31] | 13 pt; có `Số:` và dấu `/` theo cấu trúc hành chính | Cần kiểu số và khối đầu riêng; dấu sao dưới tên cơ quan theo S7 II.2.2.1. |
| Tên loại và nội dung | Tên loại 15–16, trích yếu 14–15, nội dung 14–15 [S7, tr.31–32] | Tên loại/thân 14 | Thân 14 nằm trong khoảng; tên loại 14 không đáp ứng. |
| Giãn dòng và thụt | “chữ đầu dòng lùi vào khoảng 10 mm”; “khoảng cách giữa các dòng (Line spacing) từ 18pt đến 22pt (Exactly)” [S7, II.6.2.2, tr.12] | 12,7 mm; mẫu 115%, wizard minimum | Không kế thừa cấu hình dòng hành chính. |
| Số trang | “tại điểm giữa, cách mép trên trang văn bản 10 mm và cách đều hai mép phải, trái của phần có chữ”; không hiện trang thứ nhất [S7, IV.5.1, tr.28] | `.ott` thấp hơn; wizard có đầu trang 10 mm nhưng chưa phải hồ sơ Đảng | Tạo cấu hình Đảng riêng; không dùng quy tắc 10 mm này để khẳng định NĐ30 cũng ghi đúng 10 mm. |
| Nơi nhận và chữ ký | Nhãn Nơi nhận 14, đứng, gạch chân; danh sách 12; quyền hạn như `T/M`, `K/T`; chức vụ ký 14 đứng [S7, tr.32–33 và phần II.7] | Nhãn 12 đậm nghiêng; danh sách 11; `TM.`, `KT.` theo hành chính | Khác thể thức đáng kể dù bốn lề mặt trước trùng nhau. |
| Công văn/Tờ trình | Trích yếu Công văn 12 nghiêng; “Kính gửi”/“Kính trình” 14 nghiêng, người nhận 14–15 đứng [S7, tr.32–33] | V/v 13 đứng; Kính gửi 14 đứng | Không chuyển thành mẫu Đảng chỉ bằng thay Quốc hiệu. |

Đây là phạm vi bổ sung có liên quan đến một bộ ứng dụng văn phòng Việt Nam; **chưa có mẫu Đảng trong danh mục hiện tại**. Không đưa “Thông tri”, “Kết luận” của Đảng vào danh sách loại hành chính ở Điều 7 NĐ30 rồi gắn nhãn cùng căn cứ.

**9. Đủ 29 loại hành chính: HST có gì, thiếu gì**

Điều 7 NĐ30 liệt kê **29 loại**, gồm cả Công văn và Thư công. Bảng chữ viết tắt Phụ lục III.I chỉ có 27 dòng tên loại, **không có nghĩa Điều 7 chỉ có 27 loại**. HST hiện có 7/29 nhãn loại, thiếu 22. “Có” dưới đây nghĩa có mục nguồn/catalog và wizard, không có nghĩa mọi chi tiết đã đạt.

Ưu tiên là đề xuất [SL]: **P0** hoàn thiện đầu ra hiện có; **P1** bổ sung sớm do tái dùng được cấu trúc phụ lục, nhu cầu chủ sản phẩm hoặc lấp khoảng trống rõ; **P2** tiếp theo/cần xác nhận nhu cầu và nội dung; **P3** sau khi rõ nhóm người dùng. Không có dữ liệu sử dụng sản phẩm để coi thứ tự này là thống kê nhu cầu.

| STT | Loại theo Điều 7 | Viết tắt ở PL III.I | HST hôm nay | Mẫu/cấu trúc cần có và ưu tiên |
|---:|---|---|---|---|
| 1 | Nghị quyết (cá biệt) | NQ | Thiếu | Mẫu 1.1; **P1**, phân biệt Nghị quyết VBQPPL. |
| 2 | Quyết định (cá biệt) | QĐ | Có | **P0** hoàn thiện 1.2; **P1** thêm 1.3 và văn bản ban hành/phê duyệt kèm theo. |
| 3 | Chỉ thị | CT | Thiếu | Mẫu 1.4; P2. |
| 4 | Quy chế | QC | Thiếu | 1.4, thêm biến thể kèm quyết định; **P1**. |
| 5 | Quy định | QyĐ | Thiếu | 1.4/kèm quyết định; **P1**. Không dùng nhầm QĐ của Quyết định. |
| 6 | Thông cáo | TC | Thiếu | 1.4; P2. |
| 7 | Thông báo | TB | Có | 1.4; P0 sửa bố cục chung. |
| 8 | Hướng dẫn | HD | Thiếu | 1.4; **P1**, cấu trúc nội dung có mục/điểm. |
| 9 | Chương trình | CTr | Thiếu | 1.4; **P1**, bảng tiến độ nếu cần. |
| 10 | Kế hoạch | KH | Thiếu | 1.4; **P1**, khoảng trống rõ trong bộ văn bản vận hành. |
| 11 | Phương án | PA | Thiếu | 1.4; P2. |
| 12 | Đề án | ĐA | Thiếu | 1.4; P2, thường cần nội dung/phụ lục dài. |
| 13 | Dự án | DA | Thiếu | 1.4; P2, không thay các biểu mẫu ngành. |
| 14 | Báo cáo | BC | Có | 1.4; P0 chung; thêm lựa chọn báo cáo gửi cấp trên có Kính gửi. |
| 15 | Biên bản | BB | Có | **P0**, sửa đúng hai người ký của mẫu 1.9 và cấu trúc wizard. |
| 16 | Tờ trình | TTr | Có | 1.4 có Kính gửi; P0 chung. |
| 17 | Hợp đồng | HĐ | Thiếu | P2; không có mẫu nội dung hợp đồng riêng trong danh mục 1.1–1.10. Cần bên ký/điều khoản theo loại hợp đồng. |
| 18 | Công văn | Không có dòng tên loại riêng | **Có** | **P0**, hoàn thiện 1.5; không thêm mục trùng. Ký hiệu theo cơ quan–đơn vị/lĩnh vực. |
| 19 | Công điện | CĐ | Thiếu | Mẫu 1.6; P2, cấu trúc điện và người nhận riêng. |
| 20 | Bản ghi nhớ | BGN | Thiếu | P2; không có mẫu riêng trong 1.1–1.10, cần xác định các bên/nội dung. |
| 21 | Bản thỏa thuận | BTT | Thiếu | P2; tương tự, không tự nhận mẫu nội dung do nghị định ban hành. |
| 22 | Giấy ủy quyền | GUQ | Thiếu | 1.4; P1/P2 tùy nhu cầu, trường bên ủy quyền/phạm vi/thời hạn. |
| 23 | Giấy mời | GM | Có | 1.7; P0 chung, giữ các trường thời gian/địa điểm/nội dung/chuẩn bị. |
| 24 | Giấy giới thiệu | GGT | Thiếu | Mẫu 1.8; **P1**, có người được giới thiệu, nơi đến, công việc, hiệu lực giấy. |
| 25 | Giấy nghỉ phép | GNP | Thiếu | Mẫu 1.10; P2, gồm phần xác nhận nơi nghỉ nếu cần. |
| 26 | Phiếu gửi | PG | Thiếu | 1.4; **P1**, phục vụ luồng văn thư. |
| 27 | Phiếu chuyển | PC | Thiếu | 1.4; **P1**, phục vụ luồng văn thư. |
| 28 | Phiếu báo | PB | Thiếu | 1.4; P2. |
| 29 | Thư công | Không có dòng tên loại riêng | Thiếu | P2/P3 theo nhu cầu. **Không có mẫu Thư công đánh số riêng** trong danh mục mẫu của PL III; không tự đặt “mẫu 1.11” rồi gán cho nghị định. |

Tên loại và ký hiệu lấy từ [S1, Điều 7 tr.4, Phụ lục III tr.40]. Cần bảo toàn chữ hoa/thường của **TTr, CTr, QyĐ**. [MÃ] `nd30_layout._header()` hiện `.upper()` toàn bộ trường ký hiệu: nhập `TTr-...` thành `TTR-...`. NĐ30 II.3.c viết ký hiệu bằng chữ in hoa, trong khi bảng viết tắt quy định dạng riêng như trên; sản phẩm nên dùng lựa chọn viết tắt chính thức và xử lý nhất quán, không coi upper-case toàn chuỗi là đủ kiểm tra hợp lệ. Chưa thực hiện kiểm thử giao diện cho các loại mới.

**10. Đối chiếu đầy đủ danh mục mẫu trong Phụ lục III NĐ30**

| Quy tắc / mẫu trong nguồn | Trích tên mẫu và vị trí [S1] | HST có gì / đã quan sát | Phán định và đề nghị |
|---|---|---|---|
| 1.1 | “Nghị quyết (cá biệt)” — tr.42 | Không có | P1. |
| 1.2 | “Quyết định (cá biệt) quy định trực tiếp” — tr.43 | `quyet-dinh` gần khung này nhưng thiếu thẩm quyền/căn cứ nghiêng/kiểu Điều | P0 hoàn thiện, không gọi đạt đầy đủ. |
| 1.3 | “Quyết định (quy định gián tiếp)” — tr.44; văn bản kèm theo bản giấy/điện tử tr.45–46 | Không có biến thể kèm theo | P1: một bộ gồm quyết định và văn bản kèm, có đánh số/metadata thích hợp. |
| 1.4 | “Văn bản có tên loại” — tr.47 | Thông báo, Tờ trình, Báo cáo; Giấy mời/Biên bản đang dùng chung nhiều phần | Mẫu 1.4 áp dụng 17 loại được chú thích: chỉ thị, quy chế, quy định, thông cáo, thông báo, hướng dẫn, chương trình, kế hoạch, phương án, đề án, dự án, báo cáo, tờ trình, giấy ủy quyền, phiếu gửi, phiếu chuyển, phiếu báo. Nên phát triển nền chung nhưng có trường nội dung đúng từng loại. |
| 1.5 | “Công văn” — tr.48 | Có thật, không có tiêu đề Công văn, có V/v | P0: số/ngày cùng hàng, Như trên, nhiều người nhận, đầu trang/DOCX. Phần liên hệ ở chân theo chú thích “nếu cần”; không phải mọi Công văn buộc có footer. |
| 1.6 | “Công điện” — tr.49 | Không có | P2. |
| 1.7 | “Giấy mời” — tr.50 | Có các trường gợi ý cơ bản | P0 bố cục chung; rà theo đúng mẫu riêng. |
| 1.8 | “Giấy giới thiệu” — tr.51 | Không có | P1. |
| 1.9 | “Biên bản” — tr.52 | Có nhưng đảo vị trí ký trong `.ott`; wizard thiếu hai người ký | P0. |
| 1.10 | “Giấy nghỉ phép” — tr.53 | Không có | P2. |
| 2.1 | “Phụ lục văn bản hành chính giấy” — tr.54 | Không có | P1: từ Phụ lục, số La Mã khi nhiều phụ lục, tên, dẫn chiếu văn bản ban hành. |
| 2.2 | “Mẫu Phụ lục văn bản hành chính điện tử” — tr.55 | Không có | P1/P2: phân biệt phụ lục cùng tệp và không cùng tệp; vị trí thông tin ký số theo mẫu, không chỉ đổi đuôi tệp. |
| 3.1 | “Bản sao sang định dạng giấy” — tr.56 | Không có | **P1**: hỗ trợ ba lựa chọn **SAO Y / SAO LỤC / TRÍCH SAO**, ký hiệu **SY / SL / TrS**, khối sao cuối văn bản và đường phân cách ngang toàn vùng chữ. |
| 3.2 | “Bản sao sang định dạng điện tử” — tr.57 | Không có | **P1** thiết kế luồng sao; phần ký số/độ phân giải/PDF cần kiểm chứng riêng. Không nhân đôi quốc hiệu hoặc chỉ thêm chữ “SAO Y” rồi coi xong. |

Các bản sao **không cộng thêm vào 29 loại Điều 7**. Phụ lục III có 10 mã mẫu chính 1.1–1.10, hai mẫu phụ lục và hai mẫu bản sao; bên trong 1.3 còn có biến thể văn bản kèm theo. Vì vậy một con số “7 mẫu” không phản ánh mức bao phủ loại **và** hình thức.

Để không bỏ sót các **biểu mẫu nghiệp vụ ở Phụ lục IV–V**, bảng dưới kiểm kê thêm toàn bộ tên mẫu. Đã đọc các trang gốc 58–68 và so với cả 18 mục của catalog, gồm Writer, Sheets và Slides. Những mẫu này không làm tăng số loại văn bản ở Điều 7; cũng không phải tất cả đều nên đóng thành mẫu Writer A4 thông thường.

| Quy tắc / nhóm | Trích tên mẫu trong nguồn [S1] | HST hiện tại | Phán định và đề nghị [SL] |
|---|---|---|---|
| PL IV, tr.58 | “Mẫu sổ đăng ký văn bản đi” | Không có trong catalog | P2; thích hợp bảng dữ liệu/Sheets và bản in, gồm bìa, trang đầu, nội dung đăng ký. |
| PL IV, tr.59 | “Mẫu bì văn bản” | Không có | P2; cần mẫu phong bì và địa chỉ, không áp máy móc khổ A4 của văn bản bên trong. |
| PL IV, tr.59 | “Mẫu sổ gửi văn bản đi bưu điện” | Không có | P2; bảng theo dõi gửi/nhận. |
| PL IV, tr.60 | “Mẫu sổ sử dụng bản lưu” | Không có | P2; bảng theo dõi sử dụng, không phải một loại văn bản ban hành mới. |
| PL IV, tr.61 | “Mẫu dấu ‘ĐẾN’”; nguồn quy định hình chữ nhật, 35 × 50 mm | Không có mẫu tương ứng trong catalog | P2/P3; thành phần tiếp nhận văn bản, không xếp như mẫu Công văn mới. Chưa kiểm chức năng đóng dấu ở phần khác của sản phẩm. |
| PL IV, tr.61 | “Mẫu sổ đăng ký văn bản đến” | Không có | P2; nên đi cùng sổ văn bản đi. |
| PL IV, tr.62 | “Mẫu phiếu giải quyết văn bản đến” | Không có | P2; mẫu Writer có ý kiến lãnh đạo cơ quan, lãnh đạo đơn vị và người giải quyết. Khác Phiếu chuyển của Điều 7. |
| PL IV, tr.63 | “Mẫu sổ theo dõi giải quyết văn bản đến” | Không có | P2; bảng tiến độ/trách nhiệm giải quyết. |
| PL V, tr.65 | “Mẫu danh mục hồ sơ” | Không có | P2; có đề mục, tiêu đề, thời hạn bảo quản, người lập và ghi chú. |
| PL V, tr.66 | “Mẫu mục lục hồ sơ, tài liệu nộp lưu” | Không có | P2; phân biệt hồ sơ bảo quản vĩnh viễn/có thời hạn và số tờ/số trang theo chú thích nguồn. |
| PL V, tr.67 | “Mẫu mục lục văn bản, tài liệu trong hồ sơ” | Không có | P2; nguồn chú thích áp dụng cho hồ sơ có thời hạn bảo quản vĩnh viễn. |
| PL V, tr.68 | “Mẫu biên bản giao nhận hồ sơ, tài liệu” | Chỉ có Biên bản họp chung, không có mẫu giao nhận này | P2; thêm biến thể biên bản với bên giao/bên nhận và số lượng hồ sơ, tài liệu. |

Phụ lục VI, tr.69–76 là yêu cầu hệ thống quản lý tài liệu điện tử và các bảng trường thông tin đầu vào, **không phải danh mục mẫu văn bản trình bày để bổ sung từng mục vào Writer**. Chưa nghiệm thu các luồng quản lý, tiếp nhận, sao, nộp lưu hoặc hệ thống điện tử của HST trong nghiên cứu này. Các biểu mẫu nghiệp vụ trên được kiểm kê theo bản NĐ30 đã tải, cùng giới hạn kiểm chứng hiệu lực nêu ở phần 2; khi triển khai còn phải đối chiếu quy định chuyên ngành lưu trữ áp dụng lúc đó.

**11. Đề xuất thứ tự công việc — chưa triển khai**

| Ưu tiên | Kết quả nên đạt | Lý do/bằng chứng |
|---|---|---|
| P0 | Thống nhất cách bố trí đầu trang của `.ott` và wizard theo **biên thân thật**; giữ trang đầu/tiếp theo khi xuất DOCX | Đã đo 27,27 / 28,65 mm vượt khoảng; ảnh hưởng toàn bộ bộ mẫu dùng chung. Không sửa bằng việc chỉ đổi JSON lề trên. |
| P0 | Đặt số/ngày cùng hàng; xử lý tên cơ quan dài; đo đường kẻ theo dòng thực/phông thật | Lệch baseline 10,21 mm trong mẫu, 2,82 mm trong wizard; đường cơ quan/tiêu ngữ không bảo đảm tỷ lệ. |
| P0 | Sửa chế độ giãn dòng wizard; tạo cấu trúc riêng cho Quyết định/Biên bản; hoàn thiện Nơi nhận và ký hiệu loại | Bằng chứng UNO `MINIMUM` thay vì `PROP`; căn cứ đứng và biên bản đảo bên ký. Đây là vấn đề khác với lề. |
| P0 | Kiểm tra lại trên HST có Times New Roman và Word nếu tuyên bố tương thích DOCX | PDF hiện dùng phông thay; phép thử dài đổi số trang; chưa chạy binary HST hoặc Word. |
| P1 | Thêm **Thông tư trực tiếp (mẫu 14), Thông tư ban hành kèm theo (mẫu 15)** và văn bản kèm theo | Đáp ứng yêu cầu cụ thể của chủ sản phẩm, theo NĐ78+187. Cần hồ sơ quy tắc riêng, số có năm, căn cứ và điều khoản, chức vụ/số trang 13. |
| P1 | Kế hoạch, Hướng dẫn, Chương trình, Quy chế, Quy định; Nghị quyết cá biệt; Quyết định gián tiếp | Lấp khoảng trống Điều 7 bằng nền 1.4 và các mẫu 1.1/1.3 có căn cứ rõ. |
| P1 | Giấy giới thiệu, Phiếu gửi, Phiếu chuyển; phụ lục; ba hình thức sao | Mẫu phụ lục đã có sẵn trong nghị định, bộ HST hiện hoàn toàn thiếu phần sao. |
| P2 | Mẫu VBQPPL sửa đổi/bổ sung/bãi bỏ, Thông tư liên tịch, Nghị quyết HĐND/Quyết định UBND quy phạm | PL III NĐ187 có các mẫu 16–26: cần chọn đúng thẩm quyền/phạm vi, không dùng Quyết định cá biệt thay thế. |
| P2/P3 | Những loại hành chính còn lại; nhóm văn bản Đảng | Quyết định theo nhóm khách hàng. Bộ Đảng phải theo 399 + 05 năm 2026, không lấy 36 năm 2018 làm mốc hiện hành. |

Điều kiện kiểm chứng cho đợt sửa sau: đo biên thân/header/footer ở trang 1 và 2+, thử tên cơ quan dài/ngắn, trích yếu dài, người nhận nhiều dòng, chữ ký nhiều dòng, phụ lục riêng; xuất–mở lại DOCX/PDF trên engine đích với phông thật. Cần kiểm tra cả bộ mẫu và wizard; kiểm thử chỉ đọc JSON hoặc nhìn page-style margin không phát hiện được lỗi đã thấy.

**12. Giới hạn và những điều không xác minh được**

| Vấn đề | Tình trạng thực tế | Hệ quả đối với kết luận |
|---|---|---|
| Hiệu lực pháp lý tuyệt đối đến 05/11/2026 | Bản gốc tải được; trang thuộc tính/lịch sử CSDL nhiều lần 502/403 hoặc DNS; một số thông tin chỉ xem được qua chỉ mục | Chắc chắn về nội dung/phụ lục đã tải và quan hệ thay thế ghi trong NĐ187, 399, 05; không khẳng định tra cứu lịch sử đầy đủ chỉ từ việc “không tìm thấy”. |
| VBHN4231/VBHN-BTP | Tìm thấy chỉ mục và URL các phụ lục, tải trực tiếp bị 403 | Không trích như tài liệu đã đọc. Dùng NĐ78 gốc + NĐ187 gốc để đối chiếu. |
| Bản 399 trên máy chủ THADS | URL trả 403 | Đã tìm và tải thành công **cùng văn bản gốc** qua CDN Chính phủ; nguồn sử dụng là S6, không trích nội dung từ trang lỗi. |
| NĐ187 bản Công báo qua endpoint tải | Không nhận được PDF đọc được ở URL đã thử | Dùng bản ký 152 trang từ `datafiles.chinhphu.vn`, S4. |
| HST phát hành và Microsoft Word | Không có HST binary/Word để chạy | Phép đo là nguồn checkout trên LibreOffice 24.2.7.2. Không chứng minh một lỗi riêng của HST 26.8 hay khả năng tương thích Word. |
| Phông Times New Roman | Không cài trong môi trường | Mọi con số chiều dài hộp chữ/đường kẻ, xuống dòng có điều kiện phông thay. Khổ giấy/biên khung đo vẫn xác định được. |
| Đo in giấy | Chưa in ra máy in | Không suy rộng sang scaling của driver, lề không in được hoặc tùy chọn “fit to page”. |
| Tình huống nâng cao | Chưa chạy nhiều section, header/footer có sẵn, nhiều người nhận, tên/ký hiệu cực dài, landscape/mirror | Không tuyên bố bao phủ các nhánh đó. Có đánh dấu suy luận từ nguồn khi cần. |
| “Thông lệ phổ biến của cơ quan” | Không có mẫu khảo sát đại diện | Phân biệt cận của khoảng pháp lý với lựa chọn thẩm mỹ. Không lấy bài hướng dẫn/blog hay một mẫu cơ quan làm luật. |
| Chữ ký số/bản sao có giá trị pháp lý | Chỉ rà thể thức và chỗ đặt thông tin trong bộ mẫu | Không kiểm chứng nghiệp vụ sao, chứng thư, con dấu hoặc thẩm quyền. |

**13. Nguồn và khả năng tái lập**

| Mã | Nguồn chính thức, URL | Phần sử dụng / kết quả tải |
|---|---|---|
| S1 | [Trang NĐ30 trên Cổng Chính phủ](https://vanban.chinhphu.vn/default.aspx?pageid=27160&docid=199378); [PDF ký số 76 trang](https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/03/30.signed.pdf) | PDF tải thành công. Điều 2/4/7/8/9/37; PL I tr.21–36; PL II viết hoa tr.37–39; PL III tr.40–57; kiểm kê biểu mẫu PL IV–V tr.58–68 và phân biệt phạm vi PL VI tr.69–76. SHA-256 trùng hash đã ghi trong repo. |
| S2 | [CSDL Bộ Nội vụ – toàn văn NĐ30](https://vbpl.moj.gov.vn/bonoivu/Pages/vbpq-toanvan.aspx?ItemID=141142&dvid=320); [lịch sử](https://vbpl.moj.gov.vn/bonoivu/Pages/vbpq-lichsu.aspx?ItemID=141142); [liên quan](https://vbpl.moj.gov.vn/bonoivu/Pages/vbpq-vanbanlienquan.aspx?ItemID=141142&Keyword=) | Chỉ mục tìm kiếm cung cấp trạng thái “Còn hiệu lực”; mở trực tiếp các trang thử bị lỗi. Không coi đây là bản lịch sử đã tải đầy đủ. |
| S3 | [Trang NĐ78, các tệp đính kèm](https://chinhphu.vn/default.aspx?docid=213310&pageid=27160); [PDF chính 63 trang](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/4/78ndcp-1.signed.pdf); [PL I gốc 15 trang](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/4/78-pl1.pdf); [PL II gốc](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/4/pl2.pdf) | Tải thành công. PL I gốc dùng đối chiếu lịch sử; **không dùng thay PL I đã được NĐ187 thay thế**. PL II gốc đã tải nhưng không là căn cứ mẫu Thông tư hiện dùng. |
| S4 | [NĐ187/2025 – PDF ký số đầy đủ 152 trang](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/7/187-ndcp.signed.pdf) | Tải thành công. Điều 3–4 tr.38; PL I tr.40–55; danh mục PL III tr.76–78; mẫu 14 tr.105–106, mẫu 15 tr.107–108. Đây là nguồn chính cho VBQPPL của báo cáo. |
| S5 | [CSDL thuộc tính NĐ78](https://vbpl.moj.gov.vn/bocongthuong/Pages/vbpq-thuoctinh.aspx?ItemID=176696&Keyword=78%2F2025%2FN%C4%90-CP); [lịch sử NĐ78](https://vbpl.moj.gov.vn/kontum/Pages/vbpq-lichsu.aspx?ItemID=176696&Keyword=&dvid=256); [VBHN PL I](https://vbpl.vn/FileData/TW/Lists/vbpq/Attachments/180228/VBHN-4231-Phu%20luc%201.pdf); [VBHN PL III](https://vbpl.vn/FileData/TW/Lists/vbpq/Attachments/180228/VBHN-4231-Phu%20luc%203.pdf) | Chỉ mục có trạng thái/tên tài liệu; truy cập trực tiếp không thành công. Đưa URL để kiểm lại, **không gán trích dẫn nội dung chưa đọc** cho các PDF này. |
| S6 | [Trang Chính phủ liên kết bản gốc 399-QĐ/TW](https://xaydungchinhsach.chinhphu.vn/quy-dinh-so-399-qd-tw-cua-ban-bi-thu-ve-the-loai-tham-quyen-ban-hanh-va-the-thuc-van-ban-cua-dang-119260119124508363.htm); [PDF ký, 18 trang](https://xdcs.cdnchinhphu.vn/446259493575335936/2026/1/19/qudtw399-signed-36389-17688019659091585913983.pdf) | Tải thành công từ liên kết PDF của trang. Đã đọc Điều 15–18, đặc biệt quan hệ thay thế ở tr.18. |
| S7 | [Hướng dẫn 05-HD/VPTW ngày 27/05/2026 – PDF trên Kiểm toán nhà nước](https://www.sav.gov.vn/Files/Others/761e611b-48d7-4b86-a5a2-4c17bac0f753/05.HD.VPTW.pdf) | Tải thành công, 36 trang. Phần quy tắc chung tr.28, hiệu lực tr.29; PL 1 sơ đồ tr.30, PL 2 cỡ/kiểu chữ tr.31–34. |
| S8 | [LibreOffice SDK: LineSpacingMode](https://api.libreoffice.org/docs/idl/ref/namespacecom_1_1sun_1_1star_1_1style_1_1LineSpacingMode.html); [LineSpacing](https://api.libreoffice.org/docs/idl/ref/structcom_1_1sun_1_1star_1_1style_1_1LineSpacing.html) | Đọc thành công tài liệu API chính thức: `PROP=0`, `MINIMUM=1`. Kết hợp ODF `style:line-height-at-least` (thân: `0.0453in`, khoảng 1,15 mm), OOXML `atLeast` và PDF thực để xác định lỗi giãn dòng. |
| S9 | [URL 399 trên THADS đã thử](https://thads.moj.gov.vn/noidung/tintuc/Lists/CongTacDang/Attachments/328/1.qudtw399_signed_36389%20%281%29.pdf) | 403. Nguồn thay thế thành công là S6. |
| S10 | [Endpoint Công báo NĐ187 đã thử](https://congbao.chinhphu.vn/tai-ve-van-ban-so-187-2025-nd-cp-45623-57829?format=pdf) | Không nhận được PDF đọc được. Nguồn thay thế thành công là S4. |

Các hash của nguồn gốc đã tải, để tái lập đúng bản:

```text
S1  30.signed.pdf
be2514460c953141923579e4a0ddd0249c611643a59514976790dc1d90589178
S3  78ndcp-1.signed.pdf
bf9133d5c6b8f771535e56111b20e994a1b2981bfeb5087500eaa020f1842b5a
S3  78-pl1.pdf
9bbee4fbf63a5b837e75ed3babb7ade6787f955a2434bc452869dab7c4a69475
S4  187-ndcp.signed.pdf
60fd1511d55fc4da36bde8a579e52e330afe3adec3d493b9a5f3a3579b08f6ed
S6  qudtw399-signed-36389-17688019659091585913983.pdf
3cf03d3970a22a569798448097f91acc9af2fc8a45d73b87712a87b080d1f705
S7  05.HD.VPTW.pdf
dba6843ce82a15961dfe1b0c7f413bc3200478f591d98cc9fc427c99e84c3cd7
```

Lệnh sinh mẫu và kiểm tra phông đã dùng, đầu ra ngoài checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate-templates.py \
  --out /tmp/hst-nd30-review/templates
soffice --version
fc-match 'Times New Roman'
soffice -env:UserInstallation=file:///tmp/hst-nd30-review/lo-cli \
  --headless --convert-to pdf --outdir /tmp/hst-nd30-review/pdf \
  /tmp/hst-nd30-review/templates/writer/*.ott
```

Trong phiên nghiên cứu, thư mục kết quả tạm (`/tmp/hst-nd30-review/`) giữ `.ott`, các PDF/DOCX/ODT dưới `runtime/`, harness chạy renderer (`/tmp/hst-nd30-review/measure_runtime.py`), harness đo lại (`/tmp/hst-nd30-review/postrender.py`), số đo PDF (`/tmp/hst-nd30-review/pdf-measurements.json`), số đo khung bố cục (`/tmp/hst-nd30-review/layout-measurements.json`) và các `*-layout.xml`. Đây là tệp tạm ngoài repo, có thể mất khi môi trường được dọn; các kết quả quyết định đã chép đầy đủ vào báo cáo này. Lần chạy harness đầu xuất xong tài liệu nhưng lỗi tuần tự hóa UNO sang JSON; phép trích thông số được chạy lại bằng `inspect_saved.py` và `postrender.py`, không dùng kết quả mô phỏng hoặc coi lần lỗi là thành công toàn bộ.

Mẫu Công văn `.ott` sinh từ checkout có SHA-256 `805b194f7895e784a63f54333ddfdb0c9c7ed78f801c6122a042d9c7cbb6c2cb`. Để tái lập kiểm tra dài, chèn trước bảng `Signature` 75 đoạn style `Body`, đánh số `01.` đến `75.`, mỗi đoạn có nội dung:

> Đo kiểm bố cục văn bản hành chính. Dòng nội dung này dùng để kiểm tra lề trang, khoảng cách dòng và vị trí số trang khi văn bản kéo dài qua nhiều trang.

Các vị trí mã cần xem khi đánh giá nguyên nhân, chưa chỉnh sửa: page layouts của bộ mẫu (`/work/scripts/templates/writer_styles.py:48`), bảng đầu và các đoạn mẫu (`/work/scripts/templates/writer.py:33`), bố trí wizard (`/work/extensions/hst-vietnamese-tools/python/hst_office/nd30_layout.py:1`), đầu trang wizard (`/work/extensions/hst-vietnamese-tools/python/hst_office/nd30_page.py:1`), chế độ giãn dòng UNO (`/work/extensions/hst-vietnamese-tools/python/hst_office/nd30_text.py:39`).
