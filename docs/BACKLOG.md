# HST Office — backlog

**Pivot của owner: 2026-10-29 12:34.** HST Office là bộ ứng dụng **standalone**, build **LibreOffice từ source**, mang thương hiệu HST Office / HST Writer / HST Sheets / HST Slides. Quyết định này thay lựa chọn engine trong brief và ADR 0001. Codex plan/review; Claude implement; push trực tiếp `main`, không PR.

Nguồn thực thi: [kế hoạch standalone](../plans/261029-1234-hst-office-libreoffice-standalone/plan.md). Main hiện tại `577f620` có audit/brand assets; chưa có source build LibreOffice hay installer HST đã kiểm thử. Nhánh `archive/onlyoffice-plugin-first` tại `e0517d71c813535087c401b2683bec0784d71fd8` giữ implementation ONLYOFFICE để tra cứu thuật toán, không dùng làm runtime mới. Giữ [đặc tả NĐ30](VIETNAMESE_OFFICE_SPEC.md), logo gốc và generator hiện có.

`planned` = phải triển khai; `blocked` = vẫn thuộc scope nhưng thiếu điều kiện; `superseded` = cách triển khai cũ đã bị thay; `later` = ngoài đợt Linux đầu. P0 = dữ liệu/crash/điều kiện bắt buộc; P1 = tương thích/khả năng dùng quan trọng; P2 = tiện ích. Không coi blocker hoặc test chưa chạy là PASS.

## Audit, source build và nhận diện

| ID | P | Công việc và nghiệm thu | Phụ thuộc | Trạng thái / phase |
|---|---|---|---|---|
| LO-AUD-01 | P0 | Audit nguồn tại tag; ADR 0002 thay 0001; ghi pivot vào kiến trúc/brief, giữ lịch sử | — | planned · 00 |
| LO-AUD-02 | P0 | Khuyến nghị 26.8.1; pin tag/SHA/archive/hash thật, so 26.2.6; không tự nâng phiên bản | LO-AUD-01 | planned · 00 |
| LO-LEG-01 | P0 | Đọc COPYING, COPYING.MPL, license.xml và notices sinh theo build; MPL cho file chịu MPL, AGPL-3.0 cho mã HST độc lập; kiểm điều kiện tương thích và third-party | LO-AUD-02 | planned · 00 |
| LO-LEG-02 | P0 | Kiểm TDF trademark policy; bỏ dấu hiệu TDF/LibreOffice khỏi nhận diện sản phẩm, giữ “based on LibreOffice” và notices/source đúng | LO-LEG-01 | planned; policy tự động bị chặn · 00/02 |
| LO-LEG-03 | P0 | Giữ nguồn NĐ30; kiểm hiệu lực, provenance bảng mã, font và dictionary trước claim/phân phối tương ứng | LO-LEG-01 | planned; hiệu lực NĐ30 chưa xác nhận · 00/05 |
| LO-BLD-01 | P0 | Fetch source/companion deps theo lock; Ubuntu 24.04 toolchain/config có provenance; source build thật trên VPS | LO-AUD-02 | planned; cần quyền/network · 01 |
| LO-BLD-02 | P0 | Measure CPU/time/RSS tổng/disk liên tục, giữ ≥10 GiB; thử 4 jobs, ccache 2 GiB; envelope 40 GiB phải đo | LO-BLD-01 | planned · 01 |
| LO-BLD-03 | P0 | Có executable tham chiếu upstream và HST, smoke ba module; không dùng binary đổi vỏ để nhận source-built | LO-BLD-02 | planned · 01/02 |
| LO-BRD-01 | P0 | Giữ logo gốc/generator; sinh đủ intro/about/logo/module/OS icons, không fallback sang TDF marks | LO-LEG-02 | planned; asset cũ đã kiểm · 02 |
| LO-BRD-02 | P0 | HST app/module/title/Start Center/About/splash/desktop/package; profile riêng; credits/version/SHA/contact đúng | LO-BRD-01, LO-BLD-03 | planned · 02 |
| LO-BRD-03 | P0 | Help offline/HASON TECH; thay marketing/update URLs; không tạo endpoint giả hoặc xóa license attribution | LO-BRD-02 | planned · 02/03 |

## Mặc định, tốc độ và tính năng Việt

| ID | P | Công việc và nghiệm thu | Phụ thuộc | Trạng thái / phase |
|---|---|---|---|---|
| LO-CFG-01 | P0 | Tabbed mặc định cả ba module; chuyển classic/English và lưu lựa chọn qua restart/upgrade | LO-BRD-02 | planned · 03 |
| LO-CFG-02 | P0 | UI vi-VN khi OS Việt; A4/TNR defaults; ND30 20/20/30/15 mm; font thiếu được báo, không bundle font thương mại thiếu phép | LO-CFG-01 | planned · 03 |
| LO-CFG-03 | P0 | Không telemetry/crash upload/update TDF/extension fetch tự động; trace cả attempted DNS/connect và chạy offline | LO-CFG-01 | planned · 03/08 |
| LO-PERF-01 | P0 | Nghiên cứu bug tracker, xác minh fix ancestry; Linux baseline/HST đo input→menu visible p50/p95/p99/raw samples | LO-BLD-03 | planned · 04 |
| LO-PERF-02 | P0 | Mac harness CGEvent/AX/frame capture, profiler, cold/warm/context/long-session matrix; tách physical/synthetic gestures | LO-PERF-01 | planned harness; execution blocked: chưa có Mac · 04 |
| LO-PERF-03 | P0 | Sửa bằng config an toàn/upstream backport/source patch theo trace; đo trước/sau và giữ chức năng menu | LO-PERF-01, LO-PERF-02 | blocked cho claim sửa lỗi Mac · 04 |
| LO-EXT-01 | P0 | Spike Python-UNO OXT thật: bundled discovery, dialog, insert/Undo/save/reopen, không hạ macro security | LO-BLD-03, LO-CFG-01 | planned · 05 |
| LO-EXT-02 | P0 | Wizard 7 loại NĐ30; port data/layout/validation từ archive, preview/Cancel/Undo, A4/margins/styles, fields do user nhập | LO-EXT-01, LO-LEG-03 | planned · 05 |
| LO-EXT-03 | P1 | TCVN3/VNI→Unicode có mapping/vector độc lập, chọn encoding, preview, stale-selection guard, Undo giữ format | LO-EXT-01, LO-LEG-03 | planned · 05 |
| LO-EXT-04 | P0 | VND/dd/mm/yyyy/percent qua UNO; giá trị/công thức/date serial không bị đổi | LO-EXT-01 | planned · 05 |
| LO-EXT-05 | P0 | CSV UTF-8 native defaults và tool preview; BOM/quotes/newlines/5.000 rows; leading zeros/formula text an toàn, Cancel/Undo/overwrite guard | LO-EXT-01 | planned · 03/05 |
| LO-EXT-06 | P1 | Autotext NĐ30 dùng chung data; vi/en, keyboard/focus/accessibility; help offline | LO-EXT-02 | planned · 05 |
| LO-EXT-07 | P1 | Spellcheck vi-VN với aff/dic pin và license cho phép; đúng/sai/suggestion có test | LO-LEG-03, LO-EXT-01 | planned; license/source chưa xác nhận · 05 |
| LO-TPL-01 | P0 | 7 OTT: công văn/thông báo/quyết định/tờ trình/báo cáo/giấy mời/biên bản | LO-EXT-02 | planned · 06 |
| LO-TPL-02 | P0 | 6 OTS: chấm công/lương/dự toán/thu chi/thống kê/danh sách; typed cells/formulas/print settings | LO-EXT-04 | planned · 06 |
| LO-TPL-03 | P0 | 5 OTP: họp cơ quan/báo cáo đơn vị/giảng dạy/hội nghị/báo cáo doanh nghiệp | LO-EXT-01 | planned · 06 |
| LO-TPL-04 | P0 | Catalog offline/Template Manager; mở bản mới; 18 mẫu edit/save/reopen/export OOXML/PDF, normalized rebuild hashes trên build tree | LO-TPL-01, LO-TPL-02, LO-TPL-03 | planned · 06; final installed QA ở LO-QA-02 |

## Packaging, QA, CI và bàn giao

| ID | P | Công việc và nghiệm thu | Phụ thuộc | Trạng thái / phase |
|---|---|---|---|---|
| LO-PKG-01 | P0 | Bộ .deb x86_64 từ source, HST package/version/path/deps/icons/profile, bundled OXT/templates/notices/source | LO-BRD-02, LO-CFG-03, LO-TPL-04 | planned · 07 |
| LO-PKG-02 | P0 | Container Ubuntu 24.04 sạch: install/launch/upgrade/uninstall/purge/reinstall, hashes tài liệu và profile giữ nguyên | LO-PKG-01 | blocked execution: Docker socket denied hiện tại · 07 |
| LO-QA-01 | P0 | Fixture recipe/provenance/hash; DOCX/XLSX/PPTX open/edit/save/reopen headless + GUI Xvfb; no P0 crash/data loss | LO-PKG-02 | planned · 08 |
| LO-QA-02 | P0 | Test thật wizard/converter/CSV/18 mẫu/Undo/recovery/offline; version/backend/font/locale/screenshot có evidence | LO-QA-01 | planned · 08 |
| LO-QA-03 | P1 | Writer/Sheets/Slides feature và legacy-format matrix; limitations rõ, không claim Office 100% | LO-QA-01 | planned · 08 |
| LO-QA-04 | P1 | Microsoft Office roundtrip, IME/print/multi-monitor thực; không thay bằng scripted Unicode | LO-QA-01 | blocked: chưa có máy/license/thiết bị · 08 |
| LO-QA-05 | P0 | Native Windows/macOS compatibility và Mac latency before/after | LO-QA-01, LO-PERF-02 | blocked: chưa có máy · 04/08/09 |
| LO-CI-01 | P0 | Quality push-main thật: tests/assets/licenses/OXT/docs, actions pinned, permissions/retention hữu hạn | LO-EXT-01 | planned · 09 |
| LO-CI-02 | P0 | Đo Linux GitHub runner feasibility theo peak/time thực; fail preflight nếu thiếu disk, dùng VPS đã đo khi phù hợp | LO-BLD-02, LO-PKG-01 | planned; API connectivity/quota chưa xác minh · 09 |
| LO-CI-03 | P0 | Windows/macOS manual skeleton + config/toolchain/package/signing prerequisites; invocation fail BLOCKED, không artifact giả | LO-AUD-02 | planned skeleton; native build blocked · 09 |
| LO-DOC-01 | P0 | README/docs index/BUILD/RELEASE_CHECKLIST/COMPATIBILITY_MATRIX đúng standalone và evidence; ADR/brief cũ rõ superseded | LO-QA-01, LO-CI-01 | planned · 10 |
| LO-DOC-02 | P0 | Codex review, Claude sửa, scoped conventional commit/push main không PR/force; theo CI đúng SHA | LO-DOC-01 | blocked publication: Git metadata read-only/network hiện tại · 10 |
| LO-REL-01 | P0 | Linux artifact reviewable: checksum/source/license/clean-install/runtime evidence, platform blockers công khai | LO-PKG-02, LO-QA-02, LO-DOC-01 | planned · 07–10 |
| LO-REL-02 | P1 | Public release/tag và signed native installers sau máy/build/QA/credentials và release authority | LO-REL-01, LO-QA-05 | blocked; không tự publish trong lượt lập kế hoạch |

## Các mục ONLYOFFICE đã superseded và phần được giữ

Bảng cũ được lưu tại Git main `577f620`, [plan plugin-first](../plans/261029-1118-hst-office-phase0-plugin-first/plan.md) và nhánh archive. Các tiêu chí nhắc Asc/CEF/GUID `.plugin`, upstream nguyên bản hoặc “không build engine” không còn là yêu cầu hiện hành.

| ID cũ | Trạng thái sau pivot | Thay thế / phần giữ |
|---|---|---|
| AUD-01/02/04/05, LEG-04 | **superseded — ONLYOFFICE engine/license/rebrand gate** | LO-AUD/LEG; owner đã chọn source-built LibreOffice, không hỏi lại đường A/B |
| AUD-03, LEG-01/02/03 | carried forward với engine mới | Resource measurements, notices/source, ND30/mapping provenance qua 00/01/05 |
| SDK-01/02/03/04/05 | **superseded — ONLYOFFICE SDK/iframe/bridge/.plugin** | LO-EXT-01 và native UNO contract; vẫn giữ offline/Undo/install safety |
| WRT-07, BRD-02, TPL-02 | **superseded — plugin-only UI/About/catalog** | Native wizard, app About và Template Manager; data/algorithm tham khảo được giữ |
| WRT-01–06/08/10; SHT-01–07; SLD-01–03/05; UX-01/02; QA-01–07 | carried forward | UNO features và real-runtime QA 03–08; giới hạn Office/IME/phần cứng vẫn phải báo |
| WRT-09, SHT-08, SLD-04, TPL-01 | carried forward, native templates | Đủ 7/6/5; OTT/OTS/OTP và OOXML roundtrip, shared-data generation |
| BRD-01 | giữ bằng chứng baseline | Asset/generator đã kiểm; mở rộng cho standalone ở LO-BRD-01 |
| BRD-03/04, REL-01 phần Linux | **superseded — cấm standalone/installer ở lượt cũ** | Nay là scope bắt buộc LO-BRD/PKG/REL; không còn ONLYOFFICE legal gate |
| CI-01/02/03/04; REL-01 phần Windows; REL-02 | **superseded — plugin artifact/ONLYOFFICE build workflow** | Quality/native OXT/Linux source CI; Win/Mac skeleton vẫn BLOCKED vì máy, không vì engine choice |
| LEG-05, CI-05, REL-04 | carried forward theo phạm vi release mới | Inventory/notices/source/checksums hiện tại; public tag và đa nền tảng cần release gates |
| WRT-11, SHT-09/10, UX-03, REL-03 | later | Kiểm thể thức nâng cao, cảnh báo tương thích nâng cao, UX sâu, RPM/AppImage; không tự mở scope |

## Kế hoạch theo phiên bản (chủ dự án, 2026-10-30)

- **v1.0.0-beta.2:** khóa phạm vi — chỉ hoàn tất và build các phần đang làm (tab tài liệu, nút × đóng tất cả tab, 18 mẫu HST, sách F1 offline, kiểm tra cập nhật, trình cài tiếng Việt, icon mới, bản dịch). Không thêm việc mới.
- **v1.0.0-beta.3:** banner Start Center — mỗi nhãn giải pháp (AIOS, eChatbot, Zalo Mini App, HST SEO, HST Post, AI Dễ Lắm) bấm được riêng, mở URL trong `data/hst/solutions.json` kèm UTM `utm_medium=start-center` (chuyển nhãn từ chữ trong ảnh sang nút thật). Sửa tồn đọng từ beta.2:
  - `ProductName` trong version resource Windows (`include/default.rc`, hiện ở Properties → Details của `soffice.exe`) vẫn là "LibreOffice" → "HST Office".
  - Menubar cổ điển đôi khi hiện lại khi chuyển tab giữa Calc/Impress trên GTK3 (cosmetic; sửa trong vcl GTK menubar/sfx2), xác minh trên desktop thật và Windows.
  - Crash GTK3 hiếm (menubar/clipboard) khi mở tài liệu ngay sau khi đóng tài liệu ẩn dưới Xvfb, xảy ra cả khi tắt tab; xác minh trên desktop thật.
- **v1.0.0-beta.4:** công cụ tự nhận diện USB Token ký số trên Linux/macOS (lệnh *HST ▸ Thiết lập USB Token*: tìm thư viện PKCS#11 của driver nhà cung cấp chữ ký số Việt Nam đã cài, khai báo vào kho chứng thư NSS mà HST dùng, báo kết quả tiếng Việt; thay 3 lệnh gõ tay trong trang F1 "Ký số tài liệu bằng USB Token"). Ưu tiên **VNPT-CA** (token chủ dự án dùng, 2026-10-31: driver Windows "ePass2003Auto" = Feitian ePass2003; thử ngày 2026-10-31 trên Mac M2: OpenSC thấy đầu đọc "FT ePass2003Auto" nhưng báo "token not recognized" — token VNPT khởi tạo theo định dạng riêng của Feitian, OpenSC không đọc được; phải dùng driver của VNPT: gói "VNPT-CA Token Manager" 1.0.1 cho macOS (vnpt-ca.vn, tệp 31122025145306.pkg = Apple Silicon, 31122025145204.pkg = Intel) cài thư viện PKCS#11 `/usr/local/lib/libvnptca_p11_v8.dylib` (universal arm64+x86_64, hỗ trợ ePass2003) — công cụ HST nhận diện đường dẫn này), sau đó Viettel-CA, BKAV-CA, FPT-CA, MISA, EasyCA. Cần chủ dự án thử bằng token VNPT-CA thật.
  - Lối tắt đổi ngôn ngữ giao diện (chủ dự án duyệt 2026-10-31): menu *HST ▸ Ngôn ngữ giao diện ▸ Tiếng Việt / English / Theo máy* (nhãn luôn tiếng Việt), ghi `UILocale` của người dùng, hỏi "Khởi động lại ngay?" và mở lại các tài liệu đang mở. Chỉ là lối tắt tới *Công cụ ▸ Tùy chọn ▸ Ngôn ngữ và vùng ▸ Chung ▸ Giao diện người dùng* đã có sẵn. Khởi động lại phải mở lại **mọi** tài liệu đang mở, kể cả chưa lưu/chưa đặt tên (dựa trên cơ chế khôi phục phiên; không dùng quiet-quit vì xóa cờ "đã sửa"). Kèm các sửa an toàn từ đợt rà soát ngôn ngữ ([báo cáo](../plans/reports/codex-language-selection-261031-0943-audit-design.md)): giá trị `en`/`en-GB` bị xóa về Mặc định lúc khởi động; Tùy chọn không khóa ô ngôn ngữ khi quản trị đã khóa và không báo lỗi khi ghi thất bại; gói tiếng Việt thiếu một phần cho giao diện lẫn lộn. Quy tắc "chọn English thì các phần luôn-tiếng-Việt chuyển sang tiếng Anh" đã bị chủ dự án bỏ (2026-10-31): các phần đó vẫn luôn tiếng Việt.
- **v1.0.0-beta.4 (bổ sung, chủ dự án 2026-10-31: gom toàn bộ việc dự kiến cho 1.0 vào beta.4, trừ chuyển repo):**
  - Chuyển mã TCVN3/VNI → Unicode trong Bảng tính (hiện chỉ có trong Văn bản).
  - Rà và sửa phím tắt Alt+chữ bị trùng trên ribbon/menu tiếng Việt (KEY-01/02 của đợt rà soát UX).
  - Kiểm tra độ tương phản chế độ tối của các hộp thoại HST (cần ảnh từ máy thật).
  - Lỗi nhỏ tồn từ beta.3: mẫu "Japanese normal" hiện tên tiếng Anh; khung định dạng trang chiếu ở thanh bên trống khi giao diện tiếng Anh.
  - Hỗ trợ token không có driver macOS/Linux của nhà cung cấp: dùng OpenSC (ePass2003 và các token PKCS#15) hoặc driver của hãng sản xuất token (Thales SafeNet Authentication Client, Feitian, Bit4id); công cụ *HST ▸ Thiết lập USB Token* nhận diện cả các thư viện này và hướng dẫn cài khi thiếu.
  - Khóa cấu hình kiểm tra cập nhật qua `.xcd`/registry (đưa schema vào lõi).
  - Gói Linux cho Ubuntu 22.04, Debian 13 và Ubuntu 26.04 (build riêng hoặc gói Python kèm theo).
  - Trang "Điểm mới" riêng cho nút "Xem điểm mới".
  - Ký số bộ cài Windows (cần chứng chỉ ký mã; macOS đã ký Developer ID + notarize từ beta.3 nếu chạy thử thành công).
- **v1.0.0:** chuyển repo sang tổ chức `hasontech` trước bản chính thức.

## Blockers và câu hỏi còn mở

- Môi trường: cấp Git/network/apt/Docker cho Claude; phiên lập kế hoạch có 53.5 GiB free, 18 GiB RAM available, Docker socket denied, `gh api` lỗi kết nối. Chỉ dọn cache ONLYOFFICE do dự án sở hữu khi cần; giữ ≥10 GiB.
- Mac: cần máy/OS/version/gesture/tài liệu tái hiện và GUI permissions; Windows cần builder riêng. Linux không chứng minh Mac hết delay. Signing/notarization chưa được cấp.
- Pháp lý/nội dung: cần policy TDF đầy đủ, dictionary license, nguồn bảng mã và trạng thái hiệu lực NĐ30; không tự thay license owner đã chọn hay bundle font thiếu quyền.
- Release: chưa có artifact/CI run đo thật; không công bố PASS hoặc link tải giả. Không telemetry, cloud/login, PDF editor riêng hay thêm module mới.
