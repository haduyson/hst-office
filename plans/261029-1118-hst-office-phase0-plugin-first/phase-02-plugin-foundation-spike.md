# 02 — SDK offline và spike thật

Status: pending. Owner: Claude foundation. Dependencies: 00, 01. Priority: P0. Context: [contract/audit phase](phase-00-audit-baseline.md), [brief §12 Phase 0](../../docs/HST_OFFICE_IMPLEMENTATION_BRIEF.md). Kết thúc gói này mới mở feature 03–05.

## Requirements

PoC `vn-admin-documents` cài offline, chèn công văn với field người dùng nhập, Save As DOCX rồi mở lại trên Linux upstream đã pin. Không giả lập Asc/editor. [Cài desktop](https://api.onlyoffice.com/docs/desktop-editors/usage-api/adding-plugins): ZIP nội dung ở archive root, đổi đuôi `.plugin`; Plugin Manager → Install plugin manually. Plugin folder fallback chỉ ở user profile, không sửa installation upstream.

## Files tạo / sửa; ownership

- Tạo `package.json`, `package-lock.json`, `requirements-templates.txt`, `requirements-templates.lock`, `eslint.config.js`.
- Tạo `scripts/build-plugins.js`, `scripts/bundle-plugin.js`, `scripts/package-plugin.py`, `scripts/check-plugins.js`, `scripts/check-source-lines.js`, `scripts/check-notices.js`, `scripts/check-offline-assets.js`, `scripts/check-doc-links.py`, `scripts/measure-job.py`.
- Tạo `vendor/onlyoffice/plugins.js`, `vendor/onlyoffice/license.txt`, `vendor/onlyoffice/provenance.json`; nguyên văn bridge từ SHA đã audit, không tải CDN lúc runtime.
- Tạo `extensions/shared/plugin-ui.js`, `extensions/shared/plugin-ui.css`, `extensions/shared/editor-bridge.js`, `extensions/shared/about.html`.
- Tạo `extensions/vn-admin-documents/{config.json,index.html,plugin.js,styles.css}`, `extensions/vn-admin-documents/logic/nd30-data.js`, `extensions/vn-admin-documents/translations/{langs.json,vi-VN.json,en-US.json}`.
- Tạo `tests/unit/nd30-data.test.js`, `tests/unit/plugin-package.test.js`; `docs/DEVELOPMENT.md`, `docs/PLUGIN_INSTALLATION.md`, `docs/NOTICE.md`, `docs/THIRD_PARTY_NOTICES.md`.
- Tạo `plans/reports/spike-261029-hst-office.md`, `docs/qa-evidence/spike/{evidence.json,inserted.png,reopened.png,cong-van.docx}`. Chỉ commit evidence đã kiểm không PII, tổng ≤10 MiB; outputs tạm ignored: `dist/plugins/vn-admin-documents.plugin`, `tests/output/spike/`.
- Sửa `.gitignore` thêm `.venv/`, caches/report outputs đúng phạm vi; `upstream/upstream-lock.json`, `docs/{PLUGIN_CONTRACT,UPSTREAM_BASELINE,LICENSE_AUDIT,BLOCKERS}.md` theo evidence. Không xóa file. Sau phase, chuyển ownership admin plugin/tests cho 03; root/shared đóng băng đến 07.

## Steps

1. Resolve dependencies pin exact + npm lock; chỉ ESLint/esbuild cần cho JS, `node:test` built-in. Python dùng python-docx/openpyxl/python-pptx cho templates và PyYAML cho workflow validator, versions + transitive hashes trong lock; cài venv local, không system pip. Kiểm SDK license trước copy.
2. Chốt 4 GUID `asc.{UUID}` ổn định trong contract; `config.json` theo [SDK configuration](https://api.onlyoffice.com/docs/plugins/configuration), `minVersion` theo bản đã test. Admin/encoding chỉ `word`, sheets chỉ `cell`, library `word/cell/slide`; không tạo sản phẩm PDF.
3. [Entry point](https://api.onlyoffice.com/docs/plugins/configuration/entry-point) load bridge local rồi bundle IIFE; init/button hooks thật. [Localization](https://api.onlyoffice.com/docs/plugins/configuration/localization) có nameLocale/descriptionLocale/buttons + langs.json/vi-VN/en-US, mapping vi/vi-VN và en fallback được test. UI giữ dấu, chọn Việt/English, labels/focus/keyboard/Cancel truy cập được và layout không cắt chữ khi scale.
4. Shared bridge nhận JSON thuần, lỗi/timeout trả về UI; xác minh API ở đúng runtime. Một mutation in-flight, khóa Apply; Cancel chỉ trước dispatch. Sau dispatch timeout có thể đã ghi: báo **kết quả chưa xác định**, không retry, không báo “không thay đổi”; đối chiếu tài liệu/operation rồi mới cho tiếp tục hoặc Undo đã chứng minh. Spike delayed/lost callback trên engine thật, kiểm không duplicate write. Nếu dùng callCommand, truyền qua `Asc.scope`, không capture module/closure. Không DOM nội bộ/fs tùy ý/API giả. Đo selection/Undo/action grouping Writer; giao cell-specific probe đầu 04.
5. Builder discover plugin có config, bundle core ESM vào archive; copy SDK, shared About, icons từ 01 vào **mỗi** package. Fixed ZIP timestamps/order/permissions, version/source hash; không entry `../`, symlink hay thư mục wrapper. `check-plugins` kiểm GUID uniqueness, root config, translation/icon/local link đủ, notices và inventory. Khi có vn-templates, thiếu/stale generated catalog/template data là lỗi; không dùng cache từ build cũ.
6. Scripts npm: `lint`, `test` (node --test), `check:lines`, `check:notices`, `check:offline`, `build:plugins`, `check:plugins`; Python generator commands chạy trực tiếp ở 05. Mỗi script phải làm việc thật; line gate 199 dòng tối đa cho authored JS/Python/CSS/HTML, chỉ vendor nguyên văn/generated bundle được khai báo riêng.
7. Cài binary upstream từ URL/hash audit, ghi binary version. Dùng desktop GUI thật nếu có; Xvfb chỉ cấp display, không tự chứng minh thao tác UI. Không có GUI automation/operator thì spike BLOCKED với thiếu capability cụ thể.
8. Profile test cô lập; cài `.plugin` qua UI khi ngắt mạng. Người dùng nhập hoặc để placeholder `[TÊN CƠ QUAN]`, không giả thông tin. Chèn nội dung, Undo/Redo, Save As `tests/output/spike/cong-van.docx`, đóng/mở lại. Review rồi lưu bản evidence vào `docs/qa-evidence/spike/`; manifest ghi fixture recipe/hash, plugin hash, binary version, commands, actual/expected và đường dẫn screenshot/output. Reports link tới bản tracked; log lớn chỉ artifact phụ, không là proof duy nhất.
9. Network trace phân biệt plugin và upstream. Không dùng CDN/fetch telemetry, không cloud/login; nếu upstream phát telemetry không tắt được qua setting hỗ trợ, ghi blocker cho cam kết no-telemetry, không sửa binary. Ghi CPU/RSS/disk từng job bằng measure-job; free <10 GiB fail trước job nặng, không tự prune.

## Validation commands

```bash
npm ci
npm run lint
node --test tests/unit/nd30-data.test.js tests/unit/plugin-package.test.js
npm run check:lines
npm run check:notices
node scripts/build-plugins.js --plugin vn-admin-documents
node scripts/check-plugins.js dist/plugins --expected 1
npm run check:offline
unzip -l dist/plugins/vn-admin-documents.plugin
python3 -m zipfile -t tests/output/spike/cong-van.docx
sha256sum tests/output/spike/cong-van.docx
```

Command ZIP chỉ kiểm container, **không** thay runtime evidence. `check:offline` phân biệt URL attribution tĩnh với resource/network call; không chặn link license vô hại. Test package dùng artifact build thật; không mock SDK. Narrow test file tạo package bằng helper production trước assert, không cần sẵn dist từ lượt trước.

## Acceptance / review

- [ ] Binary và SDK đã pin; PoC install/insert/Undo/save/reopen offline có evidence. Cancel trước dispatch không đổi; mutation timeout báo unknown/không retry, không claim tài liệu nguyên vẹn khi chưa đối chiếu.
- [ ] API matrix ghi method, args, min version, evidence Writer page setup/selection. Cell CSV/typed cells/Undo và library resource access còn UNVERIFIED, có gate/owner 04 và 05; không gọi Writer spike là proof cho editor khác.
- [ ] Build 2 lần byte-identical; cold profile không network vẫn chạy. Nội dung không rời máy; chỉ copy fixture vào output test.
- [ ] Codex review audit + spike rồi đóng Phase 0 brief; thiếu runtime thì không mở 03–05.

## Parallel, risks, rollback

Không sửa shared với agent khác. SDK/CDN mismatch, sandbox CEF, network upstream là rủi ro phải chứng minh. Nếu thiếu API, ghi BLOCKED feature liên quan và lựa chọn trong SDK; không hack fs, fork hay giảm acceptance. Rollback bằng gỡ riêng GUID HST qua Plugin Manager, revert source commit; không gỡ plugin mặc định/ONLYOFFICE, không xóa tài liệu. Theo dõi/stop đúng PID Xvfb/editor/profile mình tạo.
