# 05 — Mẫu Việt tái tạo và thư viện offline

Status: pending. Owner: Claude templates. Dependencies: 01, 03, 04. Priority: P0. Context: [brief §§4–6,11](../../docs/HST_OFFICE_IMPLEMENTATION_BRIEF.md), [index](plan.md). Chờ data contracts Writer/Sheets ổn định; không edit module của họ.

## Requirements

7 DOCX + 6 XLSX + 5 PPTX từ source text/JSON và generators. Không binary chỉnh tay, không dữ liệu người/cơ quan tưởng tượng, không quốc huy, font thương mại hoặc asset không rõ quyền. Mẫu có field trống/placeholder tường minh; chỉ fixture tính toán dùng literals kỹ thuật với expected độc lập.

## Files tạo / ownership

- `templates/catalog.json`, `templates/schema.json`.
- `templates/writer/{cong-van,thong-bao,quyet-dinh,to-trinh,bao-cao,giay-moi,bien-ban}.json`.
- `templates/sheets/{cham-cong,bang-luong,du-toan,thu-chi,thong-ke,danh-sach}.json`.
- `templates/slides/{hop-co-quan,bao-cao-don-vi,giang-day,hoi-nghi,bao-cao-doanh-nghiep}.json`.
- `scripts/export-template-data.js`, `scripts/generate-templates.py`, `scripts/generate-writer.py`, `scripts/generate-sheets.py`, `scripts/generate-slides.py`, `scripts/normalize-ooxml.py`, `scripts/check-templates.py`, `scripts/check-reproducibility.py`.
- `extensions/vn-templates/{config.json,index.html,plugin.js,styles.css,template-catalog.js}`, `extensions/vn-templates/translations/{langs.json,vi-VN.json,en-US.json}`.
- `tests/unit/template-catalog.test.js`; `tests/templates/{test-writer-templates.py,test-sheets-templates.py,test-slides-templates.py,test-template-reproducibility.py}`.
- `docs/TEMPLATES.md`, `plans/reports/templates-261029-hst-office.md`.
- Outputs ignored: `dist/templates/writer/<7 source slugs>.docx`, `dist/templates/sheets/<6 source slugs>.xlsx`, `dist/templates/slides/<5 source slugs>.pptx`, `dist/templates/catalog.json`, `dist/hst-office-templates.zip`, `build/template-data.json`; filename stem luôn khớp source.
- Không sửa package/lock/shared brand/logic; không xóa file. Generator tạo resource library dưới build staging, không commit binary thủ công.

## Steps

1. Source catalog mỗi mẫu có stable ID, editor, source path, output path, title vi/en, schema version, provenance, required fonts, fields. Schema kiểm uniqueness/path traversal/missing field. Node exporter import ND30 module 03 và format module 04 → JSON; Python đọc JSON, không copy business rules.
2. Dùng libraries đã pin ở 02. DOCX A4, margin/styles/header/numbering theo ND30; không claim pháp lý khi thiếu signoff. XLSX typed number/date/formulas + print area; mẫu lương chỉ cấu trúc/formulas cơ bản, không bịa quy tắc thuế/lương luật định. PPTX 16:9 có master/layouts, title/content/table/chart/image placeholder và notes tiếng Việt; 4:3 là QA capability upstream.
3. Source templates không có số điện thoại/tên cá nhân hay tài khoản thật. Metadata creator chung `HASON TECH`, không username máy. Font requirement/fallback rõ; không nhúng font không phép; media chỉ brand source owner hoặc hình học tạo bằng code.
4. Normalize creation/modified times, ZIP timestamps/order/permissions, stable relationship IDs và deterministic image metadata. `SOURCE_DATE_EPOCH` cố định, toolchain/dependency lock ghi trong manifest. Hai build ở temp directories sạch phải byte-identical; không xóa nội dung/metadata thiết yếu chỉ để đạt hash.
5. Dựng entry `vn-templates` và kiểm packaged catalog/preview resources trong từng editor word/cell/slide; ghi evidence trước khi gọi library dùng được. Plugin có catalog/search/preview từ source, phù hợp editor hiện tại, vi/en và hướng dẫn dùng file thật. Đóng gói template pack để giải nén rồi **File → Open → Save As** trên upstream. Nếu SDK đã chứng minh tải/mở local template an toàn, thêm thao tác đó; nếu chưa, UI chỉ hiển thị hướng dẫn thật, không nút Open giả hay lén dùng DOM/fs. Cách mở pack thủ công là đường bắt buộc luôn hoạt động offline.
6. Builder 02 bundle catalog/data assets từ staging theo contract, plugin không phụ thuộc URL ngoài. DOCX/XLSX/PPTX luôn có trong template pack; index link tên file khớp pack. Khi lưu, hướng dẫn Save As bản mới; không sửa mẫu gốc.
7. Tests XML/package dùng zipfile/lxml và library readers: relations không hỏng, namespaces, widths/margins, Unicode, công thức/typed values, layout counts; no external links/macros. `check-templates` trả nonzero khi thiếu một trong 18 file.
8. Mở tất cả 18 bằng upstream; sửa một field, Save As/reopen. Render/PDF screenshot để so lề và dấu. LibreOffice headless chỉ phép so phụ, không thay ONLYOFFICE/MS Office proof.

## Validation commands

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-templates.lock
node scripts/export-template-data.js --out build/template-data.json
SOURCE_DATE_EPOCH=1767225600 .venv/bin/python scripts/generate-templates.py --out dist/templates
.venv/bin/python scripts/check-templates.py dist/templates
.venv/bin/python tests/templates/test-writer-templates.py
.venv/bin/python tests/templates/test-sheets-templates.py
.venv/bin/python tests/templates/test-slides-templates.py
.venv/bin/python tests/templates/test-template-reproducibility.py
node --test tests/unit/template-catalog.test.js
SOURCE_DATE_EPOCH=1767225600 .venv/bin/python scripts/check-reproducibility.py
node scripts/build-plugins.js --plugin vn-templates
npm run check:lines
```

Repro checker tự tạo 2 temp outputs, chạy generator bằng interpreter hiện tại rồi so SHA; cleanup chỉ temp do nó tạo. Generator tạo template ZIP cạnh `--out` đúng contract. Mỗi Python test có `unittest.main()`, chạy trực tiếp để tránh discovery bỏ qua tên kebab-case. Không tuyên bố reproducible dựa vào `git diff` hoặc XML giống nhưng ZIP khác.

## Acceptance / review

- [ ] Đúng 18 mẫu có source, schema/provenance, hash ổn định; ND30/number-format dùng chung dữ liệu JS.
- [ ] 18 mẫu mở/sửa/lưu/reopen trên Linux thật, không mất dấu/công thức/layout quan trọng; template library có preview và đường mở offline thực dùng.
- [ ] Pack không chứa thông tin giả như hồ sơ thật, macro, external link, asset/font chưa phép; hướng dẫn font fallback trung thực.

## Parallel, risks, rollback

Không parallel với Writer/Sheets đang đổi contracts; sau đó templates ownership độc lập với 06. Rủi ro timestamp/RID, font và download sandbox: bắt bằng reproducibility/runtime tests, không dùng Python readers để xác nhận rendering. Rollback generator/source commit và artifact version; giữ template/user output đã tạo, không tự xóa thư mục người dùng.
