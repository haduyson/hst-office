# 03 — Writer hành chính và chuyển mã

Status: pending. Owner: Claude Writer. Dependencies: 02 spike PASS. Priority: P0/P1. Context: [brief §4](../../docs/HST_OFFICE_IMPLEMENTATION_BRIEF.md), [index](plan.md). Parallel với 04/06; đọc shared contract, không sửa shared/root.

## Requirements

Hai plugin `vn-admin-documents`, `vn-encoding-tools`; chỉ editor word. Plain JS modules test Node độc lập. TCVN3/VNI chỉ convert khi bảng mã có nguồn/provenance và user chọn encoding; không đoán rồi âm thầm ghi đè. Preview → xác nhận → apply → Undo. Hỗ trợ trường cơ quan/số/ký hiệu/địa danh/ngày/trích yếu/nơi nhận/chữ ký; không tự điền người/cơ quan.

## Files tạo / sửa; ownership

- Sửa toàn bộ `extensions/vn-admin-documents/` và `tests/unit/nd30-data.test.js` bàn giao từ 02.
- Tạo `extensions/vn-admin-documents/logic/{nd30-validation.js,nd30-layout.js}`, `extensions/vn-admin-documents/admin-form.js`, `extensions/vn-admin-documents/insert-document.js`.
- Tạo `extensions/vn-encoding-tools/{config.json,index.html,plugin.js,styles.css,conversion-preview.js,replace-selection.js}`; `extensions/vn-encoding-tools/translations/{langs.json,vi-VN.json,en-US.json}`.
- Tạo `extensions/vn-encoding-tools/logic/{convert-encoding.js,detect-encoding.js,tcvn3-map.js,vni-map.js}`; `extensions/vn-encoding-tools/data/encoding-provenance.json`.
- Tạo `tests/unit/{nd30-validation,nd30-layout,convert-encoding,detect-encoding}.test.js`, `tests/fixtures/encoding/{tcvn3-cases,vni-cases,unicode-cases}.json`.
- Tạo `docs/WRITER_TOOLS.md`, `docs/ENCODING_SOURCES.md`; `plans/reports/writer-261029-hst-office.md`. Không xóa file.

## Steps

1. Khóa API behavior từ 02, không copy toàn tài liệu qua plain text. Xác định giới hạn selection được thay an toàn; nếu rich text không bảo toàn được thì chặn apply, vẫn có preview, ghi capability blocker, không mất style âm thầm.
2. `nd30-data.js`: bảy loại công văn/thông báo/quyết định/tờ trình/báo cáo/giấy mời/biên bản; export data serializable và validation không DOM. 05 tiêu thụ đúng module này qua exporter JSON, không chép lại lề/quốc hiệu.
3. Form fields trống hoặc placeholder có nhãn; ngày hợp lệ do người dùng nhập/chọn. Lề trong khoảng đã xác minh: trên/dưới 20–25 mm, trái 30–35, phải 15–20; chọn default 20/20/30/15, A4 và typography theo từng loại. Dùng Times New Roman khi máy có, không bundle font; thiếu font báo thay thế.
4. Tách thao tác chèn nội dung và áp page setup; page setup ảnh hưởng toàn tài liệu cần preview/xác nhận riêng. Mẫu mới từ tài liệu trống hoặc chèn tại con trỏ; không replace-all mặc định. Adapter chỉ dùng API đã spike, Escape/Cancel không sửa.
5. Mapping encoding từ nguồn được kiểm chứng và có quyền dùng; golden vectors được đối chiếu độc lập, không sinh expected bằng converter đang test. Longest-match VNI, lower/uppercase, đủ dấu, đ/Đ, punctuation, line breaks, NFC, Unicode sẵn có và chuỗi mơ hồ. `detect-encoding` trả candidates/ambiguity; không có bằng chứng thì yêu cầu chọn.
6. Preview nguyên bản/kết quả; nhớ selection snapshot, kiểm selection chưa đổi trước apply; document read-only/selection rỗng/chuyển editor giữa chừng fail an toàn. Một thao tác Undo phục hồi nội dung và định dạng; lỗi không được xóa selection trước khi có output.
7. Kiểm desktop thật: nhập/copy/paste/tìm tiếng Việt, page margins, font fallback, chèn/Undo/Redo/save/reopen; ghi phạm vi format được bảo toàn. NĐ30 là hỗ trợ trình bày, không chứng nhận tính hợp pháp. “Kiểm tra thể thức” tự động nâng cao là backlog later.

## Validation commands

```bash
node --test tests/unit/nd30-data.test.js tests/unit/nd30-validation.test.js tests/unit/nd30-layout.test.js
node --test tests/unit/convert-encoding.test.js tests/unit/detect-encoding.test.js
node scripts/build-plugins.js --plugin vn-admin-documents
node scripts/build-plugins.js --plugin vn-encoding-tools
npm run check:lines
npm run check:offline
```

Manual runtime trên Linux: cài hai artifact mới khi offline; thử 7 loại, TCVN3/VNI đúng và mơ hồ, mixed Unicode, rich text, Cancel, stale selection, Undo. Mỗi case ghi input hash, expected, actual, screenshot, DOCX sau reopen. Không dùng node test để tuyên bố editor pass.

## Acceptance / review

- [ ] Mapping có provenance + golden cases độc lập; preview không ghi, Cancel không đổi, Undo đúng; không suy đoán conversion mơ hồ.
- [ ] 7 loại schema/fields, A4/lề đúng nguồn; UI vi/en, không bịa dữ liệu; data API sẵn cho 05.
- [ ] Plugin config/package offline đúng contract; missing API/format loss báo blocker, không giấu bằng fallback phá định dạng.

## Parallel, risks, rollback

03/04/06 không đụng cùng file; yêu cầu sửa shared phải chuyển Codex, tích hợp tuần tự. Legacy font glyph không tương đương byte encoding; không gọi mọi file VNI/TCVN3 là UTF-8. Rollback plugin qua GUID/version và revert file thuộc 03; với tài liệu thử dùng Undo/backup copy, không viết ngược hàng loạt lên file gốc.
