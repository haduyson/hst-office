# HST Office — backlog

Ngày: 2026-10-29. Nguồn: [implementation brief](HST_OFFICE_IMPLEMENTATION_BRIEF.md); [kế hoạch giao Claude](../plans/261029-1118-hst-office-phase0-plugin-first/plan.md). Codex plan/review; Claude implement. **Chưa có hạng mục implementation nào hoàn tất.**

Owner chốt Phase 0 + A: plugin/mẫu chạy offline trên upstream nguyên bản, push trực tiếp main. Không engine fork, HST installer, telemetry/cloud/login. P0 = mất dữ liệu/crash hoặc điều kiện bắt buộc; P1 = tương thích/bố cục/khả năng dùng quan trọng; P2 = tiện ích/thẩm mỹ. Priority không tự mở scope.

Status: `this-round / queued` = phải giao lượt này; `this-round / blocked` = vẫn thuộc lượt này nhưng thiếu điều kiện; `later` = lượt sau; `blocked` = ngoài scope và chưa được mở gate. Dependency dùng ID; gói 00–07 là phase plan, khác roadmap gốc. Backlog cấp feature có thể phụ thuộc runtime evidence; không dùng row QA tổng hợp để tạo dependency cycle.

## Audit, pháp lý và kiến trúc

| ID | P | Công việc | Dependency | Acceptance criteria | Status / gói |
|---|---|---|---|---|---|
| AUD-01 | P0 | Pin baseline và 8 repo | — | DesktopEditors v10.0.0/SHA owner; từng dependency SHA/license URL/hash, relation và binary version phân biệt rõ | this-round / queued · 00 |
| AUD-02 | P0 | Đọc license/additional terms nguyên văn | AUD-01 | 8 LICENSE, terms, headers và submodule/font/media provenance; nghĩa vụ attribution/source/trademark ghi theo component, không suy từ GitHub metadata | this-round / queued · 00 |
| AUD-03 | P0 | Resource/build matrix | AUD-01 | 32 vCPU/47 GiB/~56 GiB local; measured CPU/RSS/disk từng job, stop nặng dưới 10 GiB; no engine build local; runner/quota được kiểm khi dùng | this-round / queued · 00/06 |
| AUD-04 | P0 | ADR A so với B | AUD-02 | A được chọn; plugin API/sandbox/upgrade path rõ; B có legal/build/maintenance blockers, không sửa upstream | this-round / queued · 00 |
| AUD-05 | P0 | Baseline runtime availability | AUD-01 | Linux binary pin/hash thật; Windows/macOS/Office có owner/máy hoặc BLOCKED; không suy PASS từ tài liệu | this-round / blocked: chưa có editor · 02/07 |
| LEG-01 | P0 | License mã mới và quyền asset/SDK | AUD-02 | Ghi quyền owner logo, license bridge/dependency/mapping/font và quyết định license mã mới; scope internal/public rõ trước public artifact | this-round / queued · 00/02 |
| LEG-02 | P0 | Notices/source corresponding | AUD-02, LEG-01 | Notice/third-party/license đi kèm package, source SHA/link/rebuild đầy đủ, attribution dễ tìm; không nhận engine là của HST | this-round / queued · 02/07 |
| LEG-03 | P0 | NĐ30 và nguồn mapping | AUD-02 | Nguồn chính thức/hiệu lực/phụ lục được kiểm tại ngày triển khai; mapping TCVN3/VNI có provenance và vectors độc lập | this-round / queued · 00/03 |
| LEG-04 | P0 | Cho phép fork/rebrand/distribute engine | AUD-02, AUD-04 | Người có thẩm quyền duyệt terms/trademark/notice/source, scope thay đổi rõ; quyết định owner mới mở B | blocked: legal gate, ngoài lượt |
| LEG-05 | P1 | Hồ sơ phát hành đầy đủ/SBOM | LEG-01, LEG-02, CI-05 | Dependency/component inventory máy đọc + notices/changelog/source/checksum; không gọi manifest sơ bộ là SBOM hoàn chỉnh | later |

## SDK và nền tảng plugin

| ID | P | Công việc | Dependency | Acceptance criteria | Status / gói |
|---|---|---|---|---|---|
| SDK-01 | P0 | Contract và core thuần JS | AUD-04 | Node 22 ESM/node:test; schema ND30/CSV/catalog; adapters tách Asc/DOM; authored code <200 LOC/file | this-round / queued · 00/02 |
| SDK-02 | P0 | SDK offline/package | SDK-01, LEG-01, BRD-01 | Config GUID asc.{UUID}, index/scripts/vi/en/icons, SDK local pin; ZIP root đúng, notices đủ, không path traversal, không runtime CDN | this-round / queued · 02 |
| SDK-03 | P0 | Spike hành chính trên upstream | SDK-02, AUD-05 | Install offline → nhập/chèn công văn → Undo → Save As DOCX → reopen đúng; screenshot/hash/version thật; mở gate feature | this-round / blocked: chờ runtime · 02 |
| SDK-04 | P0 | Offline/privacy và lỗi an toàn | SDK-03 | No upload/login/cloud/telemetry plugin; trace upstream riêng; Cancel trước dispatch không ghi; mutation timeout báo unknown, khóa retry/đối chiếu để tránh ghi trùng; unsupported telemetry ghi blocker | this-round / queued · 02/07 |
| SDK-05 | P1 | Cài/gỡ và locales | SDK-02 | Manual archive + user-profile fallback 3 OS có hướng dẫn; Linux install/uninstall thật không xóa tài liệu; Việt/English, vi-VN fallback được test | this-round / queued · 02/07 |

## Writer

| ID | P | Công việc | Dependency | Acceptance criteria | Status / gói |
|---|---|---|---|---|---|
| WRT-01 | P0 | DOCX create/open/edit/save | SDK-03 | Linux upstream + plugin create/edit/reopen giữ Unicode/text/table/image/format; no P0 loss/crash | this-round / queued · 07 |
| WRT-02 | P1 | DOC/ODT/RTF/TXT và cảnh báo giới hạn | AUD-05 | Matrix từng định dạng: mở/lưu/mất tính năng; limitation rõ, không hứa giữ hoàn toàn format; sửa engine nếu cần để later | this-round / queued: khảo sát · 07 |
| WRT-03 | P0 | Ribbon và định dạng cơ bản | AUD-05 | Kiểm styles/headings/font/bold/italic/underline/color/highlight/alignment/tabs/indent/spacing; no branded shell changes | this-round / queued: baseline QA · 07 |
| WRT-04 | P0 | Trang, bảng và nội dung | AUD-05 | A4/A3/orientation/cm-mm/header-footer/page-section breaks; merge/split/bullets/numbering/images/shapes/caption/textbox có evidence/limits | this-round / queued: baseline QA · 07 |
| WRT-05 | P1 | References/review | AUD-05 | Search/replace tiếng Việt, TOC, footnote/endnote, comments/track changes được kiểm; unsupported ghi rõ | this-round / queued: baseline QA · 07 |
| WRT-06 | P0 | IME/font tiếng Việt | AUD-05 | Nhập/copy/paste/find không mất dấu; font thiếu có fallback rõ, không bundle Times New Roman/Arial thiếu phép; IME từng OS có trạng thái | this-round / queued · 07 |
| WRT-07 | P0 | Plugin hành chính | SDK-03, LEG-03 | 7 loại, quốc hiệu/tiêu ngữ/cơ quan/số/ngày/trích yếu/nơi nhận/ký tên do user nhập; A4/margins verified; insertion/Undo an toàn | this-round / queued · 03 |
| WRT-08 | P1 | TCVN3/VNI → Unicode | SDK-03, LEG-03 | Golden vectors đủ dấu/hoa thường/đ/Đ; preview + explicit encoding + stale selection guard; Cancel không ghi, Undo khôi phục format; mơ hồ không autoapply | this-round / queued · 03 |
| WRT-09 | P0 | 7 template DOCX | WRT-07, BRD-01 | Công văn/thông báo/quyết định/tờ trình/báo cáo/giấy mời/biên bản có source, regenerate hash, mở/sửa/lưu/reopen | this-round / queued · 05 |
| WRT-10 | P0 | In/PDF và recovery | AUD-05 | Print Preview/export PDF/unsaved prompt/AutoRecover test trên copy; không xóa gốc; thiếu printer thật ghi NOT RUN | this-round / queued · 07 |
| WRT-11 | P1 | Kiểm tra thể thức nâng cao | WRT-07, LEG-03 | Chỉ cảnh báo cấu trúc/định dạng, giải thích rule và không chứng nhận hợp pháp; false positives được đo | later |

## Sheets

| ID | P | Công việc | Dependency | Acceptance criteria | Status / gói |
|---|---|---|---|---|---|
| SHT-01 | P0 | XLSX lifecycle và formats nhập | SDK-03 | Create/open/edit/save/reopen XLSX không mất dữ liệu; XLS/ODS/CSV có test riêng và limitations | this-round / queued · 07 |
| SHT-02 | P0 | Worksheet và thao tác ô | AUD-05 | Formula bar/row-column/ranges/copy-paste/sort/filter/freeze/format/merge/print area/page breaks được test | this-round / queued: baseline QA · 07 |
| SHT-03 | P0 | Công thức phổ biến | AUD-05 | SUM/AVERAGE/COUNT/IF/SUMIF/SUMIFS/COUNTIF/COUNTIFS/VLOOKUP/INDEX-MATCH expected đúng; XLOOKUP xác minh theo binary; locale separator không rewrite formula | this-round / queued · 04/07 |
| SHT-04 | P1 | CF/validation/chart/Pivot | AUD-05 | Conditional formatting/data validation/chart giữ sau save; Pivot capability thực đo, không quảng cáo nếu chưa hỗ trợ | this-round / queued: baseline QA · 07 |
| SHT-05 | P0 | CSV UTF-8 | SDK-03 | BOM/no-BOM, delimiter/quotes/newlines/empty fields, chọn encoding+preview; malformed không âm thầm U+FFFD; 5.000 rows đủ; limits công khai | this-round / queued · 04 |
| SHT-06 | P0 | Nhập CSV an toàn | SHT-05 | Formula-looking text literal, giữ leading zero; overwrite/protected range/Cancel/Undo không mất dữ liệu, no upload | this-round / queued · 04 |
| SHT-07 | P0 | Locale date/VND/percent | SDK-03 | dd/mm/yyyy, VND/percent/decimal-grouping display đúng; underlying values/formulas không đổi; type/date ambiguity có preview | this-round / queued · 04 |
| SHT-08 | P0 | 6 template XLSX | SHT-07, BRD-01 | Chấm công/lương/dự toán/thu chi/thống kê/danh sách; dữ liệu trống, typed cells/formulas/print settings; tái tạo hash | this-round / queued · 05 |
| SHT-09 | P1 | Advanced roundtrip | SHT-01, SHT-03 | Sheet Unicode/named ranges/external links/charts/CF có case; Excel hợp pháp đối chiếu công thức và giá trị; không fetch link ngoài khi offline | later: chờ máy Office; inventory lượt này |
| SHT-10 | P1 | Cảnh báo unsupported nâng cao | SHT-09 | Báo giới hạn trước tác vụ có rủi ro theo API khả dụng; không nhận có save interception nếu SDK không cung cấp | later |

## Slides và thư viện mẫu

| ID | P | Công việc | Dependency | Acceptance criteria | Status / gói |
|---|---|---|---|---|---|
| SLD-01 | P0 | PPTX lifecycle/PPT/ODP | SDK-03 | PPTX create/edit/save/reopen; PPT/ODP có matrix riêng, không mất nội dung silent | this-round / queued · 07 |
| SLD-02 | P0 | Layout và objects | AUD-05 | 16:9/4:3, theme/master/layout/text/image/shape/table/chart, alignment/group/layers/bullets/notes/fullscreen được kiểm | this-round / queued: baseline QA · 07 |
| SLD-03 | P1 | Transition/animation/media/presenter | AUD-05 | Fixture riêng, so binary/runtime; không có máy/thiết bị ghi NOT RUN; Microsoft Office fidelity cần QA-05 | this-round / queued: khảo sát · 07 |
| SLD-04 | P0 | 5 template PPTX | BRD-01, SDK-03 | Họp cơ quan/báo cáo đơn vị/giảng dạy/hội nghị/báo cáo doanh nghiệp; layouts/notes/fonts Việt; không quốc huy, tái tạo hash | this-round / queued · 05 |
| SLD-05 | P1 | Handouts/PDF | AUD-05 | In handouts/export PDF có output so slide/font, printer thiếu ghi rõ; không thêm PDF editor | this-round / queued · 07 |
| TPL-01 | P0 | Pipeline tạo mẫu | SDK-01, WRT-07, SHT-07 | 18 source JSON + schema + locked generator; hai build sạch cùng toolchain byte-identical; OOXML relationships hợp lệ | this-round / queued · 05 |
| TPL-02 | P0 | Thư viện mẫu offline | TPL-01, SDK-02 | Plugin thứ tư có catalog/preview vi/en; pack thật, File → Open → Save As hoạt động offline; không nút mở giả/URL cloud | this-round / queued · 05 |

## Brand, UX và sản phẩm

| ID | P | Công việc | Dependency | Acceptance criteria | Status / gói |
|---|---|---|---|---|---|
| BRD-01 | P0 | Dẫn xuất HASON TECH → HST OFFICE | AUD-02 | Source PNG bất biến; mark pixel nguyên vẹn, text HST OFFICE; full logo/mark/icons 28/56, font provenance và script tái tạo | this-round / queued · 01 |
| BRD-02 | P0 | About/contact trong plugin | SDK-02, LEG-02 | HASON TECH/contact theo brief, engine nguyên bản + phiên bản/license/source/attribution rõ, không claim engine HST viết | this-round / queued · 02/07 |
| UX-01 | P1 | Việt/English và accessibility plugin | SDK-02 | Không cắt dấu, keyboard/tab/focus/labels, error/Cancel rõ, 100%/150%/200% và light/dark có QA | this-round / queued · 03–07 |
| UX-02 | P1 | Locale/DPI/theme upstream | AUD-05 | Khảo sát Vietnamese OS default/language switch/multi-monitor/DPI/light-dark; ghi thiếu locale, không patch shell | this-round / queued: khảo sát · 07 |
| UX-03 | P2 | Tinh chỉnh accessibility/UX sâu | UX-01, UX-02 | Đóng gaps có evidence, không làm mất phím tắt và không hứa screen reader support chưa test | later |
| BRD-03 | P1 | Home/About/Ribbon/native labels HST | LEG-04 | HST Writer/Sheets/Slides, Home/new/open/recent/templates và attribution đúng legal; không copy Microsoft assets | blocked: đường B ngoài scope |
| BRD-04 | P0 | Installer HST và nhận diện OS | LEG-04, BRD-03 | Tên executable/installer/icon và attribution/source đúng; clean-machine install/uninstall giữ tài liệu | blocked: legal/build gate |

## CI, QA và phát hành

| ID | P | Công việc | Dependency | Acceptance criteria | Status / gói |
|---|---|---|---|---|---|
| CI-01 | P0 | Quality thật | SDK-02 | Node tests/lint/LOC/license/offline/docs checks; GitHub push main/PR, action SHA pinned, permissions tối thiểu; không mock pass | this-round / queued · 06 |
| CI-02 | P0 | Plugin/template artifacts | CI-01, TPL-01 | Đủ 4 plugins/18 mẫu ở final; checksums/commit/notices/reproducibility, retention/quota rõ; artifact upload chỉ sau legal artifact gate | this-round / queued · 06/07 |
| CI-03 | P0 | Desktop skeleton | AUD-03, AUD-04 | 3 workflow manual-only TODO/BLOCKED, invocation exit nonzero, không installer/echo success; OS build thật chưa được claim | this-round / queued · 06 |
| CI-04 | P0 | Direct-main integration | CI-01 | Review trước conventional commit; stage scoped/no secrets, push main không force; remote CI theo đúng SHA hoặc blocker thật | this-round / blocked: .git read-only và shell DNS · 07 |
| CI-05 | P1 | Tag release plugin/template | LEG-01, LEG-02, CI-02, QA-03 | Owner duyệt tag; release.yml dùng artifact đã test, checksum/source/changelog; không tự publish trong lượt này | later |
| QA-01 | P0 | Fixture provenance/privacy | SDK-01 | Tất cả fixtures có nguồn/recipe/hash/expected; vectors kỹ thuật, templates trống; không real PII/tài liệu mật hay hồ sơ giả | this-round / queued · 03–07 |
| QA-02 | P0 | Unit/structural/repro | SDK-01, TPL-01 | node:test pure logic, OOXML/package validators và 2-build hashes thật; missing cases không silent skip | this-round / queued · 03–07 |
| QA-03 | P0 | Linux runtime/offline/data safety | SDK-03, WRT-08, SHT-06, TPL-02 | 4 plugin/18 mẫu install/use/save/reopen/Undo; no P0 crash/loss; network/runtime evidence; gỡ plugin không xóa tài liệu | this-round / blocked: chờ runtime · 07 |
| QA-04 | P0 | Compatibility matrix | AUD-05, QA-01 | Mỗi case/version/OS/arch PASS/FAIL/NOT RUN/BLOCKED; manifest/hash và subset evidence sanitized tracked còn đọc được sau artifact expiry; P0/P1/P2 rõ, không claim 100% | this-round / queued · 07 |
| QA-05 | P1 | Microsoft Office roundtrip | QA-01, QA-03 | Office có license → upstream+plugin → Office; text/values/formulas/screenshots/PDF từng trang/slide không sai nghiêm trọng | blocked: chưa có máy/license xác nhận; ghi matrix lượt này |
| QA-06 | P0 | Windows/macOS runtime | SDK-02, QA-01 | Windows 10/11 x64, macOS ARM64/Intel theo hỗ trợ upstream; offline/IME/font/plugin smoke có evidence riêng | blocked: chưa xác nhận máy; ghi matrix lượt này |
| QA-07 | P0 | Hướng dẫn/bàn giao | LEG-02, QA-03 | docs navigation, install/uninstall/build/use/report lỗi, giới hạn, backlog/plan đồng bộ; không ghost process | this-round / queued · 07 |
| REL-01 | P0 | Linux .deb; Windows .exe/.msi | LEG-04, BRD-04, QA-06 | Build procedure pinned thật, runner đủ disk; installer máy sạch/uninstall không xóa docs; source notices checksum đầy đủ | blocked: legal/engine build ngoài scope |
| REL-02 | P0 | macOS .dmg/.pkg, signing | LEG-04, BRD-04, QA-06 | Toolchain upstream đúng arch, signing/notarization bằng cert hợp lệ, secrets quản lý đúng; không giả verified | blocked: legal/credentials/build ngoài scope |
| REL-03 | P2 | Linux .rpm/AppImage | REL-01 | Khả thi upstream, tested distro/arch và license/source rõ | later |
| REL-04 | P0 | Public beta → v1.0 miễn phí | REL-01, REL-02, QA-05, QA-06, LEG-05 | 3 editor offline trên mọi OS đã công bố; không P0; UI/mẫu/notice/source/contact đúng, feedback và rollback; owner duyệt release | blocked: ngoài lượt |

## Non-goals và gates còn mở

Không PDF editor riêng, Mail/Notes/Database, cloud sync, collaboration server, login, telemetry, AI cloud, marketplace riêng. VBA/Power Query/COM/hiệu ứng PowerPoint đặc thù không được hứa tương thích. “Later/blocked” không được biến thành fake implementation để đóng backlog.

Unresolved questions: người duyệt license phân phối mã mới/SDK/assets; hiệu lực NĐ30 tại ngày phát hành; SHA và API capabilities thực; máy Windows/macOS/Microsoft Office; truy cập GitHub từ shell. Các câu hỏi đã có owner/gate ở 00/02/07, không mở lại quyết định đường A.
