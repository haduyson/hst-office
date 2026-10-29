# ADR 0002 — HST Office là bộ office độc lập build từ LibreOffice

- Trạng thái: **Accepted** — quyết định của chủ dự án ngày 2026-10-29 12:34 (Asia/Ho_Chi_Minh).
- Thay thế: [ADR 0001](0001-plugin-first-unmodified-upstream.md) (plugin-first trên ONLYOFFICE).
- Plan: [plans/261029-1234-hst-office-libreoffice-standalone](../../plans/261029-1234-hst-office-libreoffice-standalone/plan.md).

## Bối cảnh

Chủ dự án yêu cầu HST Office là **bộ office riêng** (tên app, splash, About, icon, installer mang thương hiệu HST), không phải gói plugin. Engine ONLYOFFICE vướng điều khoản 7(b) "giữ logo sản phẩm gốc" và không cấp quyền trademark (LEG-01/LEG-02), nên không rebrand hoàn toàn được nếu chưa có ý kiến pháp lý.

## Quyết định

- Engine: **LibreOffice 26.8.1.1** (tag `libreoffice-26.8.1.1`, commit `bf6ef266…`), build **từ source** đã kiểm chữ ký GPG ([lock](../../upstream/libreoffice-lock.json)). Nhánh 26.2 bị loại vì TDF kết thúc hỗ trợ ngày 2026-11-30.
- Rebrand bằng tuỳ chọn upstream: `--with-product-name="HST Office"`, `--with-vendor="HASON TECH"`, `--with-branding=<HST images>`, cộng patch nhỏ cho chuỗi About/credits/desktop. Ba module hiển thị là HST Writer / HST Sheets / HST Slides.
- Giao diện mặc định: **Tabbed** (NotebookBar, giống Ribbon); người dùng vẫn chuyển được sang thanh công cụ cổ điển.
- Tính năng Việt chuyển sang dạng native: extension Python-UNO tích hợp sẵn (NĐ30, chuyển mã TCVN3/VNI, định dạng VND/ngày, CSV), 18 mẫu ODF, từ điển chính tả `vi` của upstream.
- Nền tảng đầu tiên: Linux x86_64 `.deb` build trên VPS. Windows/macOS: pipeline chuẩn bị sẵn, chạy khi có máy build (OPS-01, SIGN-01).
- Lỗi chuột phải chậm trên macOS: điều tra bằng bằng chứng (`sample`/Instruments), sửa bằng cấu hình hoặc patch; chỉ báo đã sửa khi có số đo trước/sau trên Mac thật.

## Hệ quả

- Giấy phép: file nguồn LibreOffice đã sửa giữ **MPL-2.0** và phải công bố source; mã HST viết mới (extension, script, generator) dùng **AGPL-3.0** — MPL-2.0 cho phép kết hợp với giấy phép GNU (Secondary License), các file mới là file riêng. Mẫu văn bản CC BY 4.0. Từ điển `vi` giữ GPLv2 của tác giả.
- Thương hiệu: gỡ tên/logo LibreOffice/TDF khỏi nhận diện sản phẩm; giữ ghi nhận trung thực "dựa trên LibreOffice" trong About/credits (theo chính sách trademark TDF).
- Bỏ: 4 plugin ONLYOFFICE (lưu ở nhánh `archive/onlyoffice-plugin-first`). Giữ: audit, brand assets, dữ liệu NĐ30.
- Chi phí: build lớn (~30–40 GB, hàng giờ CPU) và phải rebase patch mỗi bản LibreOffice mới; DOCX/XLSX/PPTX kém trung thực hơn ONLYOFFICE ở một số trường hợp — đo trong [COMPATIBILITY_MATRIX](../COMPATIBILITY_MATRIX.md).
