# ADR 0001 — Plugin-first trên ONLYOFFICE Desktop Editors nguyên bản

> **SUPERSEDED** ngày 2026-10-29 bởi [ADR 0002](0002-libreoffice-standalone.md): chủ dự án chọn bộ office độc lập dựa trên LibreOffice. Công việc ONLYOFFICE lưu ở nhánh `archive/onlyoffice-plugin-first`.

- Trạng thái: **Accepted** (chủ dự án chọn ngày 2026-10-29)
- Bối cảnh: [brief §3, §13.3](../HST_OFFICE_IMPLEMENTATION_BRIEF.md), [LICENSE_AUDIT](../LICENSE_AUDIT.md), [BUILD_MATRIX](../BUILD_MATRIX.md)

## Vấn đề

HST Office cần ba trình biên tập Writer/Sheets/Slides cho người Việt, miễn phí, offline. Có hai đường:

- **A — Plugin-first:** chạy ONLYOFFICE Desktop Editors v10.0.0 chính thức, không sửa; HST cung cấp plugin `.plugin` + gói mẫu DOCX/XLSX/PPTX.
- **B — Fork/rebrand shell:** fork `desktop-apps` (+ build `core/sdkjs/web-apps`), đổi tên/logo/About, phát hành installer “HST Office”.

## So sánh

| Tiêu chí | A — Plugin-first | B — Fork shell |
|---|---|---|
| Phạm vi API | Plugin SDK + Office JS API (`callCommand`, `executeMethod`); sandbox iframe, không fs/DOM nội bộ | Toàn quyền UI native/web-apps |
| Cập nhật upstream | Cài bản mới, chạy lại QA plugin | Rebase fork, build lại toàn engine mỗi bản |
| Tài nguyên build | Node/Python; **ước lượng** nhỏ (chưa đo — sẽ đo ở CI), dự kiến chạy trên GitHub `ubuntu-latest` (chưa xác minh quota/billing) | brief/build_tools nêu ~100 GB SSD/OS; cần runner lớn/self-hosted mỗi OS |
| License | Mã HST AGPL-3.0; giữ header bridge; About plugin nêu ONLYOFFICE gốc | AGPL + Additional Terms 1–5: notice sửa đổi có ngày trong UI, **7(b) giữ logo sản phẩm gốc**, không trademark license |
| Thương hiệu | “HST Office” chỉ trên plugin/mẫu/docs; app vẫn là ONLYOFFICE | Đổi tên app; xung đột tiềm năng với 7(b)/trademark → cần ý kiến pháp lý |
| Rủi ro dữ liệu | Thấp: engine không đổi | Cao hơn: build tự làm, cần QA đầy đủ 3 OS |
| Đáp ứng brief | Plugin/mẫu Việt, NĐ30, chuyển mã, CSV/VND; không đổi được tên app/Home/About native | Đáp ứng đủ yêu cầu nhận diện (Home/About/installer) |

## Quyết định

Chọn **A** cho vòng hiện tại. B giữ ở trạng thái **BLOCKED** cho tới khi đóng `LEG-01`, `LEG-02`, `LEG-04` (xem [BLOCKERS](../BLOCKERS.md)) và có runner build đủ lớn. Không fork trước khi audit được người có thẩm quyền duyệt.

## Hệ quả

- Yêu cầu brief §7 về màn hình Home/About/installer mang tên HST Office **chưa đáp ứng** ở vòng này; ghi vào backlog dạng blocked.
- Ghi nhận tác giả nằm trong About của từng plugin + docs, mô tả đúng: *plugin chạy trên ONLYOFFICE Desktop Editors gốc (chưa sửa đổi) của Ascensio System SIA*.
- Workflow desktop chỉ là skeleton `workflow_dispatch` tự fail với thông báo BLOCKED.
- Khi mở B: thêm ADR mới mô tả fork point, patch tối thiểu, chiến lược rebase và notice sửa đổi.
