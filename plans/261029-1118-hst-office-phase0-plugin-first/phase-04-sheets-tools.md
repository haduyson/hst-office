# 04 — Sheets CSV và định dạng Việt

Status: pending. Owner: Claude Sheets. Dependencies: 02 spike PASS. Priority: P0. Context: [brief §5](../../docs/HST_OFFICE_IMPLEMENTATION_BRIEF.md), [index](plan.md). Parallel 03/06, không sửa shared/root.

## Requirements

`vn-spreadsheet-formats`: định dạng selection ngày `dd/mm/yyyy`, VND, percent; nhập CSV UTF-8 BOM/no-BOM, chọn encoding/delimiter, preview. Logic thuần JS không Asc/DOM. Không rewrite chuỗi công thức theo locale; không gửi file lên server. Không đọc filesystem tùy ý: file picker browser được user chọn và API đã spike.

## Files tạo / ownership

- `extensions/vn-spreadsheet-formats/{config.json,index.html,plugin.js,styles.css,csv-preview.js,import-csv.js,apply-format.js}`.
- `extensions/vn-spreadsheet-formats/translations/{langs.json,vi-VN.json,en-US.json}`.
- `extensions/vn-spreadsheet-formats/logic/{detect-csv-encoding.js,parse-csv.js,parse-vietnamese-value.js,vietnamese-formats.js,prepare-csv-cells.js}`.
- `tests/unit/{detect-csv-encoding,parse-csv,parse-vietnamese-value,vietnamese-formats,prepare-csv-cells}.test.js`.
- `tests/fixtures/csv/{utf8-bom.csv,utf8-no-bom.csv,quoted-fields.csv,formula-like-text.csv,invalid-utf8.bin}`, `tests/fixtures/csv/expected.json`.
- `docs/SHEETS_TOOLS.md`, `plans/reports/sheets-261029-hst-office.md`. Không sửa/xóa file phase khác.

## Steps

1. Gate đầu phase: dựng entry `config.json/index.html/plugin.js` thuộc subtree được giao; chạy **cell runtime** thật để chứng minh file picker, typed literal, occupied/protected range và một Undo phục hồi values/formats. Lưu evidence vào report Sheets; chưa đạt thì BLOCKED import, không dùng Writer spike thay proof. Sau gate mới làm logic/import đầy đủ. `detect-csv-encoding` kiểm BOM và UTF-8 fatal decode, trả encoding/candidates/reason; bytes lỗi/mơ hồ dừng cho user chọn decoder thật hỗ trợ. Không coi Windows-1258 là VNI/TCVN3.
2. Parser đúng quoted delimiter, escaped quotes, quoted newline, CRLF/LF, trailing empty cell/row, blank input; tab/comma/semicolon selection. Delimiter detection chỉ đề xuất; phải preview xác nhận. UTF-8 malformed không âm thầm thay bằng U+FFFD.
3. Preview giới hạn hàng hiển thị, vẫn parse/validate toàn input có giới hạn công khai. Contract ban đầu: tối đa 10 MiB/50.000 rows/200 columns, fail sớm có thông báo; acceptance 5.000 rows. Không cắt dữ liệu thầm lặng; đo runtime rồi ghi giới hạn thật.
4. Default nhập text để giữ `00123`, số điện thoại, ngày mơ hồ và strings bắt đầu `=`, `+`, `-`, `@` an toàn; test formula-looking values thành literal, không tự thực thi/external link. User chọn kiểu number/date với preview tường minh; không đặt apostrophe hiển thị sai nếu API có kiểu text.
5. Apply trên ô bắt đầu/selection đã xác minh; kiểm bounds, sheet protected, occupied range và overwrite confirmation. Có Cancel và một Undo phục hồi dữ liệu/format. Nếu batching không atomic, spike/thiết kế safe rollback trước khi triển khai, không leave partial success.
6. Number format đặt qua API locale đã test; date giữ giá trị ngày/số thực, VND/percent không đổi giá trị nền, formula text không sửa. `vietnamese-formats.js` export serializable formats cho generator 05.
7. Runtime workbook: 5.000 rows, nhiều sheet Unicode, SUM/AVERAGE/COUNT/IF/SUMIF/SUMIFS/COUNTIF/COUNTIFS/VLOOKUP/INDEX-MATCH; XLOOKUP/Pivot ghi supported theo test. Roundtrip values/formulas/date/locale separator; empty/invalid/cancel không sửa workbook.

## Validation commands

```bash
node --test tests/unit/detect-csv-encoding.test.js tests/unit/parse-csv.test.js tests/unit/parse-vietnamese-value.test.js
node --test tests/unit/vietnamese-formats.test.js tests/unit/prepare-csv-cells.test.js
node scripts/build-plugins.js --plugin vn-spreadsheet-formats
npm run check:lines
npm run check:offline
```

Manual desktop: install offline → nhập từng fixture, preview/change delimiter → import → Undo/Redo → save XLSX → reopen; compare expected types/values/formulas. Test protected/occupied ranges và file quá giới hạn. Không gọi parse unit test là bằng chứng runtime import thành công.

## Acceptance / review

- [ ] CSV BOM/no-BOM đúng dấu/cột; invalid encoding không mất byte thầm lặng; formula-like text không thực thi.
- [ ] VND/date/percent giữ underlying values/formulas; 5.000 rows không mất hàng; Cancel/Undo đúng.
- [ ] UI Việt/English, privacy/offline và expected data chỉ dùng literals kỹ thuật, không hồ sơ người/công ty giả.

## Parallel, risks, rollback

Ownership toàn subtree Sheets + tests/docs đã liệt kê. CSV injection, kiểu ngày, separator và Undo là gate dữ liệu; thiếu SDK capability phải báo blocker. Rollback plugin theo GUID, revert đúng commit; file input chỉ đọc, workbook gốc không bị ghi đè tự động.
