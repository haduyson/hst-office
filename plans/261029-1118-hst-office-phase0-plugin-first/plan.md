---
title: "HST Office: Phase 0 và plugin-first"
description: "Giao Claude audit, spike và bộ plugin/mẫu Việt chạy trên ONLYOFFICE nguyên bản."
status: pending
priority: P1
effort: "18–25 ngày công; chưa gồm thời gian chờ legal/máy QA"
branch: main
tags: [docs, feature, experimental]
created: 2026-10-29
---

# HST Office — kế hoạch giao Claude

Trạng thái: **kế hoạch đã soạn; triển khai chưa bắt đầu**. Codex lập kế hoạch/review; Claude triển khai. [Brief](../../docs/HST_OFFICE_IMPLEMENTATION_BRIEF.md) và [backlog](../../docs/BACKLOG.md) là đầu vào. Không viết implementation trong lượt lập kế hoạch này.

## Kết quả và ranh giới đã chốt

- Phase 0 audit + spike; đường A: 4 plugin offline và mẫu DOCX/XLSX/PPTX trên **ONLYOFFICE Desktop Editors nguyên bản**. Nhãn HST chỉ thuộc plugin/mẫu/tài liệu.
- Không fork engine, sửa shell/Home/About upstream, installer HST, telemetry, cloud, login, AI hay dữ liệu cá nhân thật. Workflow desktop chỉ skeleton có TODO và trạng thái blocked.
- Baseline chủ dự án xác minh: `v10.0.0`, 2026-10-13, `daf8c6948148827201b2907ac1134d222fbfa7b4`. Không tự nâng phiên bản; pin riêng repo phụ thuộc, SDK, binary và license.
- Máy thực tế: Ubuntu 24.04, 32 vCPU, 47 GiB RAM tổng, khoảng 56 GiB disk trống. Chưa cài ONLYOFFICE; không compile engine tại đây. GitHub shell lỗi DNS; `.git` read-only chặn staging/commit, chưa push được.
- Logo nguồn: `assets/brand/source/hasontech-logo-original.png`, 476×393; giữ nguyên mark HS, thay chữ bằng `HST OFFICE` trong asset dẫn xuất.

## Phases và dependencies

Số dưới đây là gói công việc của lượt này, không thay số roadmap trong brief. **Phase 0 của brief chỉ đạt sau 00 + spike 02**; chưa đạt thì không triển khai feature 03–05.

| Gói | Nội dung / owner Claude | Phụ thuộc | Trạng thái | Ước lượng |
|---|---|---|---|---|
| 00 | [Audit, baseline, legal và ADR](phase-00-audit-baseline.md) | — | pending | 2–3 ngày |
| 01 | [Asset HASON TECH và provenance](phase-01-brand-assets.md) | 00: audit phạm vi asset | pending | 1 ngày |
| 02 | [SDK offline, build và spike hành chính](phase-02-plugin-foundation-spike.md) | 00, 01 | pending | 3–4 ngày |
| 03 | [Writer, NĐ30 và chuyển mã](phase-03-writer-tools.md) | 02: spike đạt | pending | 3–4 ngày |
| 04 | [Sheets, CSV và định dạng Việt](phase-04-sheets-tools.md) | 02: spike đạt | pending | 3–4 ngày |
| 05 | [Mẫu tái tạo và thư viện offline](phase-05-vietnamese-templates.md) | 01, 03, 04 | pending | 3–4 ngày |
| 06 | [CI thật và skeleton desktop](phase-06-ci-workflows.md) | 02 | pending | 1–2 ngày |
| 07 | [QA, evidence và bàn giao main](phase-07-qa-handoff.md) | 03–06 | pending | 2–3 ngày |

03, 04, 06 được làm song song: ownership riêng, không cùng sửa package/lock/shared files. 05 nối tiếp 03/04 để tái dùng logic; 07 tích hợp. Mỗi phase liệt kê file chính xác; mọi đường dẫn tính từ `/home/office` nếu không ghi khác.

## Quy tắc giao việc

- CWD `/home/office`; timezone `Asia/Ho_Chi_Minh`; tài liệu/UI tiếng Việt, locale máy `C.UTF-8`; tên code/commit tiếng Anh, kebab-case. Reports tại `/home/office/plans/reports/`.
- Claude đọc brief + phase + dependency evidence. Chỉ sửa file được giao; không hoàn tác việc người khác. Codex giữ quyền tích hợp, đổi contract và cập nhật trạng thái plan/backlog.
- Từng file code tự viết **<200 LOC**; không minify để né kiểm tra. SDK vendor nguyên văn và bundle sinh tự động được kiểm checksum, không chia/sửa mã upstream để giảm LOC.
- Mọi validation trong phase là **lệnh cần tạo/rồi chạy khi triển khai**, không phải kiểm thử đã chạy hôm nay. Thiếu runtime/credential: ghi `BLOCKED`, tuyệt đối không thay bằng mock hoặc `echo success`.
- Commit conventional; push trực tiếp `main` sau review, không PR bắt buộc, không force-push. Root/shared manifests chỉ owner 02 rồi owner 07 được sửa; branch chính tích hợp tuần tự.

## Acceptance của lượt triển khai

- [ ] Audit nguyên văn LICENSE/additional terms tại SHA; asset/SDK provenance; A/B ADR; blocker legal của B còn nguyên.
- [ ] 4 `.plugin` có config ở ZIP root, GUID ổn định `asc.{UUID}`, vi/en, icon và SDK local; cài/gỡ offline được trên Linux baseline.
- [ ] Spike tạo/chèn hành chính, lưu DOCX, đóng/mở lại có nội dung đúng; Writer preview/chuyển mã/Undo và Sheets preview/CSV/định dạng có evidence thật.
- [ ] 7 mẫu Writer, 6 Sheets, 5 Slides sinh từ source; 2 lần build cùng toolchain cho cùng SHA-256; không tên người/cơ quan bịa, không dữ liệu cá nhân.
- [ ] Node unit tests, structural tests, CI và QA Linux đạt; giữ công thức/Unicode; Windows/macOS/MS Office chỉ ghi PASS khi đã chạy thật, còn lại BLOCKED/NOT RUN.
- [ ] Không sửa upstream, không tải dữ liệu tài liệu lên mạng; no-network runtime evidence tách khỏi static checks; notices và hướng dẫn offline đi kèm artifact.
- [ ] README trong docs, backlog, matrix, checksum/source manifest và main phản ánh đúng kết quả; không tuyên bố v1.0 hay installer đã phát hành.

## Điểm cần xác minh khi thực thi

Quyền license mã mới/asset phân phối, SHA dependency và SDK, hiệu lực NĐ30, API/Undo/CSV trong runtime, máy Windows/macOS/MS Office còn mở; giao 00/02/07 xử lý, không cần đổi quyết định A. Quota Actions/signing chỉ là gate phát hành sau.

## Validation log — planning only

Đã đọc đủ brief; kiểm 10 docs, 8 phase, 66 backlog IDs, links, dependency DAG, required sections và cú pháp Bash. Review assumptions/contracts/failure/security đã xử lý cell probe, Python test discovery/YAML dependency, build order, mutation timeout và evidence retention; không còn finding high/critical trong plan. Chưa chạy implementation/runtime tests. Staging thất bại vì `.git/index.lock` read-only; remote check thất bại DNS, không commit/push.

## Unresolved questions
