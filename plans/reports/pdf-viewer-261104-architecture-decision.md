# HST PDF — kiến trúc trình xem PDF nhẹ và ký số (quyết định, 2026-11-04)

Yêu cầu chủ dự án: "Nâng cấp trải nghiệm người dùng khi xem PDF và ký số trên PDF, ưu tiên nhẹ, nhanh, giao diện phổ thông". Chọn: trình xem PDF **riêng** (HST PDF) có nút **Ký số** nổi bật; sửa PDF vẫn ở HST Draw. Thiết kế: canvas `PdfViewer` (tiêu đề, thanh công cụ, dải trang thu nhỏ, trang giữa, bảng "Ký số tài liệu", thanh trạng thái).

## Đo trước khi làm (Linux, Xvfb, gtk3, build `upstream/libreoffice/instdir` hiện tại)

Tệp mẫu: hợp đồng tiếng Việt do chính HST Office xuất PDF (`tests/runtime/pdf_samples.py`), 50 trang (163 KB) và 300 trang (882 KB), chỉ có chữ — trường hợp nặng nhất cho Draw vì mỗi dòng chữ thành một hình.

| Cách mở | 50 trang | 300 trang |
|---|---|---|
| HST Draw hiện tại (`loadComponentFromURL`, hiện cửa sổ; lần 1 / lần 2) | 28,2 s / 27,5 s | 45,3 s / 36,4 s |
| PDFium: mở tệp và dựng ảnh trang 1 (đo qua `GraphicProvider`, cùng thư viện PDFium đi kèm; ước lượng trước khi làm) | 0,04–0,07 s | 0,12–0,13 s |

Draw chậm vì nhập toàn bộ tài liệu (`sdext` pdfimport chạy tiến trình `xpdfimport`, dựng mọi trang thành hình vẽ, rồi Bộ điều hướng liệt kê hàng nghìn hình) trước khi hiện trang đầu. PDFium chỉ đọc bảng xref và vẽ trang đang xem: chi phí gần như không phụ thuộc số trang.

## Phương án

1. **Draw rút gọn, chỉ đọc** — vẫn phải nhập cả tài liệu: không thể nhanh hơn 27–45 s. Loại.
2. **Chương trình riêng ngoài tiến trình soffice** — phải tự khởi tạo UNO/NSS, không dùng chung kho chứng thư/USB Token và hộp thoại PIN với ký văn bản; thêm một tệp chạy cho ba hệ điều hành. Loại.
3. **Chọn: cửa sổ xem PDF trong tiến trình HST Office, vẽ bằng PDFium** —
   - Một *frame loader* UNO (`org.hasontech.comp.PdfViewerFrameLoader`) đăng ký cho kiểu `pdf_Portable_Document_Format`. Mọi đường mở (Tập tin ▸ Mở, nhấp đúp/dòng lệnh, Trung tâm khởi động, tài liệu gần đây) đi qua `LoadEnv` nên tự vào HST PDF.
   - Loader chuyển sang Draw/Writer gốc (`com.sun.star.comp.office.FrameLoader`) khi: tắt tùy chọn "Mở tệp PDF bằng HST PDF", tải ẩn (`Hidden`, `--convert-to`, macro), bộ lọc khác `draw_pdf_import` (PDF lai có ODF, chọn bộ lọc Writer/Impress trong hộp thoại Mở), hoặc nút **Sửa trong HST Draw**.
   - Cửa sổ là `InterimItemWindow` dựng từ `.ui` (giống Trung tâm khởi động): thanh công cụ, dải thu nhỏ, trang giữa, bảng ký số, thanh trạng thái. Trang vẽ bằng `vcl::pdf::PDFium` (đã đi kèm), chỉ trang đang thấy, có bộ đệm; dải thu nhỏ vẽ dần lúc rảnh.
   - Tìm chữ, bôi sáng, chép chữ: API văn bản của PDFium (`findStart`, `getCharBox`, `getUnicode`).
   - In: `vcl::PrinterController` vẽ từng trang bằng PDFium (hộp thoại In chuẩn).
   - Ký số: cùng hộp thoại chọn chứng thư số và cùng kho NSS/Windows như ký văn bản (`DocumentDigitalSignatures`), nên USB Token và hộp thoại PIN giống hệt. Ký bằng `vcl::filter::PDFDocument::Sign` (chính mã "Ký PDF có sẵn" của Draw), hình chữ ký là một trang PDF cỡ trang đích do `vcl::PDFWriter` vẽ tại khung người dùng kéo. Luôn lưu bản sao qua hộp thoại Lưu (có hỏi khi ghi đè).
   - Kiểm tra chữ ký có sẵn: `PDFSignatureHelper` (cùng thư viện `xmlsecurity`).
   - Mã đặt trong thư viện `xmlsecurity` (đã liên kết vcl, svl, sfx2; không thêm thư viện mới), chuỗi trong miền `xsc`, tùy chọn trong lược đồ cấu hình riêng `Office/HSTPdfViewer.xcs` (không sửa `Common.xcs` để khỏi dịch lại cả cây), một ô chọn ở Công cụ ▸ Tùy chọn ▸ HST Office ▸ Chung.

## Mục tiêu đo sau khi làm

Thời gian đến trang đầu ≤ 1 s cho 50 trang và ≤ 1,5 s cho 300 trang trên cùng máy (kiểm thử runtime khẳng định ngưỡng này, số đo thật ghi trong báo cáo cuối).

## Phạm vi ngoài

Sửa nội dung PDF, chú thích, biểu mẫu: ở HST Draw. Dấu thời gian (TSA) theo cấu hình ký văn bản hiện có.
