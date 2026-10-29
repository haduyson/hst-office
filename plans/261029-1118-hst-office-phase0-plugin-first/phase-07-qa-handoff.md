# 07 — QA, review và bàn giao main

Status: pending. Owner: Claude integration; Codex review. Dependencies: 03–06. Priority: P0. Context: [brief §§11–13](../../docs/HST_OFFICE_IMPLEMENTATION_BRIEF.md), [index](plan.md), [backlog](../../docs/BACKLOG.md). Gói tuần tự, không parallel shared edits.

## Requirements

Kết luận theo evidence thật: Node/OOXML checks, desktop Linux, Windows/macOS, Microsoft Office là các lớp khác nhau. Không suy khả năng engine từ plugin unit tests; không tuyên bố tương thích 100%. Không P0 mất dữ liệu/crash trong bộ đã chạy; P1 phải sửa hoặc giữ delivery blocker, không hạ severity để pass.

## Files tạo / sửa; ownership

- Tạo `docs/README.md`, `docs/COMPATIBILITY_MATRIX.md`, `docs/QA.md`, `docs/SUPPORT.md`.
- Tạo `tests/fixtures/fixture-manifest.json`, `scripts/generate-qa-fixtures.py`, `scripts/check-fixture-privacy.py`, `scripts/check-qa-evidence.py`.
- Tạo `tests/smoke/desktop-cases.json`, `tests/roundtrip/roundtrip-cases.json`, `tests/roundtrip/compare-ooxml.py`.
- Tạo `plans/reports/qa-261029-hst-office.md`, `plans/reports/review-261029-hst-office.md`.
- Tạo `docs/qa-evidence/linux/evidence.json`, `docs/qa-evidence/linux/{writer-preview,writer-undo,sheets-preview,sheets-undo,slides-reopened,template-library,offline-network}.png`, `docs/qa-evidence/linux/{writer-reopened.docx,sheets-reopened.xlsx,slides-reopened.pptx}`; giữ subset sanitized ≤10 MiB cùng commit reports, không chỉ local ignored output.
- Sửa `package.json`, `package-lock.json`, `requirements-templates.lock` nếu cần integration dependency; `.github/workflows/{quality.yml,plugins.yml}` để bỏ bootstrap conditions và enforce đủ scope; `docs/{BLOCKERS,UPSTREAM_BASELINE,DEVELOPMENT,PLUGIN_INSTALLATION,RELEASE_CHECKLIST}.md`.
- Codex cập nhật `docs/BACKLOG.md`, index và phase status sau review; Claude gửi evidence, không tự đóng gate. Không xóa file. Chỉ docs/plans chứa Markdown theo workspace rule; không tạo root README/NOTICE Markdown. `docs/README.md` là navigation entry.

## Steps

1. Full build từ clean generated outputs riêng, đủ 4 plugin/18 mẫu. Scan privacy/secrets/source provenance; script scanner hỗ trợ review, không chứng minh tuyệt đối không PII. Contact pháp nhân từ brief chỉ ở About/docs, không điền vào fixtures như hồ sơ.
2. Generate fixtures từ source/recipe có seed/hash/expected: Writer 30–100 trang nội dung kỹ thuật lặp có nhãn, bảng qua trang/header/footer/section/TOC/footnote/comments/tracked changes; Sheets 5.000 rows, multi-sheet Unicode, formulas/filter/CF/chart/named ranges; Slides master/layout/notes/theme/chart/images/animation. Nếu library chưa tạo được tính năng, chuẩn bị trên upstream/Microsoft Office được cấp phép và lưu recipe/provenance; không tuyên bố generator đã cover.
3. Matrix các hàng riêng create/open/edit/save/reopen, DOC/ODT/RTF/TXT, XLS/ODS/CSV, PPT/ODP, print/PDF; IME/dấu/font fallback; undo/recovery/unsaved prompt; layout/Ribbon/DPI/theme; advanced XLOOKUP/Pivot/links/animation/media/presenter. PASS/FAIL/NOT RUN/BLOCKED kèm OS/arch, binary version, fixture hash, evidence link và severity.
4. Linux runtime offline cài/gỡ 4 GUID, mở 18 templates, preview/Cancel/overwrite/Undo/Redo, save/reopen; vô hiệu network thực ở môi trường test, kiểm không cần login/cloud. Ghi setting/trace upstream riêng; không nhận cam kết “không telemetry” chỉ từ việc cắt mạng. Evidence manifest lưu results tất cả cases, recipe/input/plugin/output hashes và runtime version; commit subset screenshot/output ở paths trên sau privacy review. Report links phải đọc được từ fresh checkout; artifact 14 ngày chỉ bổ sung log lớn.
5. Roundtrip MS Office hợp pháp → upstream + HST plugin → MS Office: values/formulas/Unicode/relationships + screenshots/PDF từng trang/slide. Không có máy/license thì BLOCKED hàng đó; LibreOffice đối chiếu phụ ghi rõ. Windows 10/11 x64, macOS ARM64/Intel, Linux x64 có availability riêng; không giả supported từ tag.
6. Crash/recovery thử trên bản copy trong profile cô lập, chỉ stop PID do QA tạo; xác minh tài liệu gốc không đổi và warning khi unsaved. Gỡ plugin không xóa tài liệu. Không thử installer HST vì chưa tồn tại; giữ installer gate blocked.
7. Docs: cài/gỡ offline, build/test, catalog mẫu, giới hạn encoding/CSV/API/fonts, báo lỗi bằng fixture đã redacted. About plugin ghi HASON TECH/contact từ brief và ONLYOFFICE/Ascensio System SIA + baseline/license/source; không nói engine đã được HST tùy biến.
8. Codex review data-loss/API/package/license/CI claims trước commit. Commit conventional tập trung; chỉ stage file đã review, không `.env`, credential, binary user data, `.claude/.codex`. Main có commit mới thì fetch/integrate trước push, không force; remote unavailable thì giữ local deliverables và ghi blocker. Không merge PR hay publish release được ngụy trang thành yêu cầu này.
9. Ghi command/PID/port/profile mọi process, kiểm process đã có trước khi start; reuse/stop đúng owner. Kết thúc stop toàn process mình tạo. Báo `DONE` cho phạm vi đã đạt, hoặc `BLOCKED` và backlog IDs; không tự mở fork để giải blocker.

## Validation commands

```bash
npm ci
npm run lint
npm test
npm run check:lines
npm run check:notices
node scripts/export-template-data.js --out build/template-data.json
SOURCE_DATE_EPOCH=1767225600 .venv/bin/python scripts/generate-templates.py --out dist/templates
.venv/bin/python scripts/check-templates.py dist/templates
.venv/bin/python scripts/check-reproducibility.py
npm run build:plugins
node scripts/check-plugins.js dist/plugins --expected 4
npm run check:offline
python3 scripts/check-fixture-privacy.py
python3 scripts/check-qa-evidence.py --platform linux --require-runtime
python3 scripts/check-doc-links.py docs plans/261029-1118-hst-office-phase0-plugin-first
python3 scripts/create-artifact-manifest.py --dir dist
git diff --check
git status --short
git push origin main
gh run list --branch main --limit 5
```

Bootstrap venv/locked requirements như 05 trước lệnh `.venv`; lệnh cuối chỉ sau commit/review. Evidence checker bắt thiếu screenshot/output/runtime version, hash mismatch và link không resolvable trong checkout; không tự tạo PASS. Không chạy code implementation trong lượt lập kế hoạch hiện tại.

## Acceptance / rollback

Risks: font substitution/Office fidelity không thể chứng minh bằng XML; Linux không đại diện mọi OS; crash test sai profile có thể hại dữ liệu. Chỉ dùng profile và bản copy QA riêng, giữ bằng chứng chưa chạy, không đóng gate bằng kết quả suy diễn.

- [ ] Linux evidence đạt cho 4 plugin/18 templates, no data-loss, replayable fixture steps; audit/Node/CI PASS không bị đánh tráo thành GUI PASS.
- [ ] Matrix công khai giới hạn và máy chưa có; legal/Windows/macOS/MS Office/signing gates còn mở nếu chưa chứng minh. Không cản giao plugin Linux bằng cách đòi installer ngoài scope.
- [ ] Source/notices/hash/docs đúng artifact và commit; main push/CI có URL khi thành công, nếu lỗi ghi nguyên nhân thật.
- [ ] Codex đã review, backlog/index khớp; không orphan process. Rollback revert commit theo thứ tự dependency, cài lại plugin artifact trước; không force-push/xóa tài liệu, giữ evidence QA.
