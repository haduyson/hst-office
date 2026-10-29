# Plugin contract

> **Lịch sử (không còn áp dụng).** Contract plugin ONLYOFFICE, thay bởi [EXTENSION_CONTRACT](EXTENSION_CONTRACT.md) theo [ADR 0002](ADR/0002-libreoffice-standalone.md). Mã nguồn ở nhánh `archive/onlyoffice-plugin-first`.

## 1. Danh sách plugin (GUID cố định — không đổi giữa các phiên bản)

| Thư mục | GUID | Editor | Mục đích |
|---|---|---|---|
| `extensions/vn-admin-documents` | `asc.{535252E5-A2B9-475A-B273-33F549C3CC5D}` | word | Soạn văn bản hành chính NĐ30, áp lề A4 |
| `extensions/vn-encoding-tools` | `asc.{8A4ECB32-A9A3-4DB7-BB6F-BBACC0C194DD}` | word | Chuyển mã TCVN3/VNI → Unicode |
| `extensions/vn-spreadsheet-formats` | `asc.{2098C2B4-AB91-403E-8E41-1683744CD329}` | cell | Định dạng VND/ngày/%, nhập CSV tiếng Việt |
| `extensions/vn-templates` | `asc.{A1C9AB68-72D0-4FDB-AA96-F40C11AB8FDC}` | word, cell, slide | Thư viện mẫu tiếng Việt offline |

## 2. Cấu trúc nguồn

```text
extensions/<id>/
  config.json            # https://api.onlyoffice.com/docs/plugins/configuration ; "url": "index.html"
  index.html             # nạp vendor/plugins.js rồi plugin.bundle.js (đường dẫn tương đối, không CDN)
  plugin.js              # entry ESM → esbuild bundle IIFE `plugin.bundle.js`
  *.js                   # UI/adapter riêng của plugin
  styles.css
  logic/*.js             # ESM thuần, không Asc/DOM/fs → node:test
  translations/langs.json, vi-VN.json, en-US.json
extensions/shared/       # ui-helpers, editor-bridge, plugin-ui.css, about.html — copy vào mọi package
```

## 3. Nội dung bắt buộc của mỗi `.plugin`

| Đường dẫn trong ZIP | Nguồn |
|---|---|
| `config.json`, `index.html`, `styles.css`, `translations/*` | `extensions/<id>/` |
| `plugin.bundle.js` | esbuild từ `plugin.js` (+ `logic/`, `shared/`) |
| `shared/plugin-ui.css`, `about.html` | `extensions/shared/` |
| `vendor/plugins.js` | `third_party/onlyoffice-plugin-sdk/plugins.js` (nguyên văn, giữ header) |
| `resources/light|dark/icon*.png` | `assets/brand/icons/` |
| `LICENSE` (AGPL-3.0 HST), `LICENSE-ONLYOFFICE.txt` (AGPL + **Additional Terms** nguyên văn), `NOTICE.txt` | gốc repo, `third_party/.../LICENSE.txt`, sinh từ `NOTICE.md` |
| `build-info.json` | version, git commit, SHA-256 từng file nguồn |

Không đóng gói `plugins-ui.js`/`plugins.css` upstream (chứa PerfectScrollbar và ảnh UI ONLYOFFICE CC BY-SA).

ZIP: `config.json` ở gốc, không thư mục bọc, không `../`/symlink, thứ tự sắp xếp, mtime `1980-01-01`, quyền `0644`, deflate mức 9 → byte-identical.

## 4. Contract logic (thuần, test bằng `node --test`)

| Module | Hàm | Input → Output | Lỗi |
|---|---|---|---|
| `vn-admin-documents/logic/nd30-data.js` | `DOCUMENT_TYPES`, `MARGIN_RANGES_MM`, `DEFAULT_MARGINS_MM`, `TYPOGRAPHY` | hằng số JSON-serializable | — |
| `…/logic/nd30-validation.js` | `validateFields(typeId, fields)` | `{ ok, errors:[{field, code}] }` | `typeId` lạ → `code: 'unknown-type'` |
| | `validateMargins(mm)` | `{ ok, errors }` theo `MARGIN_RANGES_MM` | |
| `…/logic/nd30-layout.js` | `buildLayout(typeId, fields)` | `{ blocks:[Paragraph|TwoColumn] }` (§5) | throw `Error('unknown-type')` |
| `vn-encoding-tools/logic/convert-encoding.js` | `convertToUnicode(text, 'tcvn3'|'vni')` | `{ text, changed }` NFC | encoding lạ → throw |
| `…/logic/detect-encoding.js` | `detectEncoding(text)` | `{ candidates:[{encoding, score}], ambiguous }` | không throw |
| `vn-spreadsheet-formats/logic/detect-csv-encoding.js` | `detectCsvEncoding(bytes)` | `{ encoding:'utf-8'|null, bom, reason }` | UTF-8 lỗi → `encoding:null` |
| `…/logic/parse-csv.js` | `parseCsv(text, {delimiter, maxRows, maxColumns})` | `{ rows, rowCount, columnCount }` | vượt giới hạn → throw `limit-exceeded` |
| `…/logic/vietnamese-formats.js` | `NUMBER_FORMATS` | `{ date, vnd, percent }` format code | — |
| `vn-templates/template-catalog.js` | `filterCatalog(catalog, editor, query)` | mảng mục khớp | — |

## 5. Schema dữ liệu dùng chung

- **ND30 constants** (`logic/nd30-data.js`, đơn vị mm/pt):
  - `MARGIN_RANGES_MM: {top|bottom|left|right: [min, max]}`; `DEFAULT_MARGINS_MM: {top, bottom, left, right}`; `PAGE_SIZE_MM: {width: 210, height: 297}`.
  - `TYPOGRAPHY: {fontFamily: string, <element>: pt, bodyFirstLineIndentMm, paragraphSpacingPt, lineSpacing}`.
  - `DOCUMENT_TYPES: [{id, label, typeName, officialLetter: bool, kinhGui: bool}]`, `id ∈ {cong-van, thong-bao, quyet-dinh, to-trinh, bao-cao, giay-moi, bien-ban}`.
  - `PLACEHOLDERS: {<field>: string}` — chèn khi trường trống.
- **Form fields** (đều là chuỗi, có thể rỗng): `parentAgency, agency, number (chỉ chữ số, ≤6), symbol (không khoảng trắng/“/”), place, date (ISO YYYY-MM-DD hợp lệ), summary, kinhGui (nhiều dòng), body (nhiều dòng, ≤100000 ký tự), signerAuthority, signerTitle, signerName, recipients (nhiều dòng)`; trường khác ≤2000 ký tự.
- **Mã lỗi validation:** `unknown-type, not-text, too-long, number-digits-only, symbol-no-space-or-slash, invalid-date, margin-not-number, margin-out-of-range`.
- **`build/template-data.json`** (do `scripts/export-template-data.js` sinh, generator Python đọc): `{schemaVersion: 1, nd30: {pageSizeMm, defaultMarginsMm, marginRangesMm, typography, documentTypes, layouts: {<typeId>: buildLayout(typeId, {})}}, numberFormats: {date, vnd, percent}}`.
- **Layout block** (`nd30-layout`): `{type:'paragraph', align:'left'|'center'|'right'|'justify', runs:[{text, bold, italic, size}], spacingAfterPt, indentFirstMm, ruleWidthMm?}` hoặc `{type:'two-column', widthsPct:[l,r], left:[paragraph…], right:[paragraph…]}`.
- **Template catalog** (`templates/catalog.json`): `{schemaVersion:1, templates:[{id, editor:'word'|'cell'|'slide', source, output, title:{vi,en}, description:{vi,en}, fonts:[…], fields:[…]}]}`; `id` = tên file, không `/`, `..`.

## 6. Pipeline

```bash
npm ci && npm run lint && npm test
node scripts/export-template-data.js --out build/template-data.json
SOURCE_DATE_EPOCH=1767225600 .venv/bin/python scripts/generate-templates.py --out dist/templates
npm run build:plugins && npm run check:plugins
```

## 7. Quy tắc API (an toàn dữ liệu)

- Chỉ API công khai: `Asc.plugin.callCommand(fn, isClose, isCalc, cb)` (tham số qua `Asc.scope`, hàm không dùng closure), `Asc.plugin.executeMethod(name, args, cb)`. Không DOM editor, không fs.
- Một mutation tại một thời điểm; Áp dụng bị khóa khi đang chạy; Cancel chỉ trước khi gửi.
- Timeout sau khi gửi → “kết quả chưa xác định — kiểm tra tài liệu hoặc dùng Undo”, không retry.

## 8. Ma trận API — chỉ PASS khi đã chạy thật trên Desktop 10.0.0.169

| API | Editor | Phép thử spike | Trạng thái |
|---|---|---|---|
| Cài plugin từ thư mục user `sdkjs-plugins/{GUID}` | all | plugin xuất hiện trong tab Plugins | UNVERIFIED |
| `callCommand` + `Api.GetDocument().InsertContent([...])` | word | chèn công văn tại con trỏ | UNVERIFIED |
| Một `callCommand` = một bước Undo | word | Undo 1 lần xóa toàn bộ nội dung chèn | UNVERIFIED |
| `GetFinalSection().SetPageSize/SetPageMargins` | word | lề = 20/20/30/15 mm sau lưu DOCX | UNVERIFIED |
| `executeMethod('GetSelectedText')` | word | đọc vùng chọn chuyển mã | UNVERIFIED |
| `ApiRange`/run-level replace giữ định dạng | word | chữ đậm vẫn đậm sau chuyển mã | UNVERIFIED |
| `Api.GetActiveSheet().GetRange().SetValue/SetNumberFormat` | cell | VND/ngày giữ giá trị nền | UNVERIFIED |
| Đọc file qua `<input type=file>` trong iframe plugin | cell | nhập CSV người dùng chọn | UNVERIFIED |
| Mở mẫu cục bộ từ plugin | word/cell/slide | — | UNVERIFIED (mặc định: hướng dẫn File → Open) |
