# HST Office — Đặc tả sản phẩm & kế hoạch triển khai dành cho Codex / Claude

> **Cập nhật 2026-10-29 (chủ dự án):** engine đổi từ ONLYOFFICE sang **LibreOffice build từ source** để HST Office là bộ office độc lập mang thương hiệu riêng — xem [ADR 0002](ADR/0002-libreoffice-standalone.md). Các mục nhắc ONLYOFFICE trong brief dưới đây được hiểu theo LibreOffice; nguyên tắc license/trademark/QA vẫn giữ nguyên. Thêm yêu cầu: điều tra và sửa độ trễ menu chuột phải trên macOS.

> **Phiên bản:** 1.0 — 29/10/2026  
> **Trạng thái:** Tài liệu chỉ đạo triển khai; chưa khẳng định việc fork, đổi thương hiệu hoặc phát hành đã được cấp phép.  
> **Ngôn ngữ làm việc:** Tiếng Việt. Code, tên biến, commit và chú thích kỹ thuật có thể dùng tiếng Anh.

## 0. Chỉ thị thực thi cho AI coding agent

Bạn là kỹ sư trưởng cùng nhóm triển khai **HST Office**, bộ ứng dụng Office **desktop, offline-first, miễn phí cho người dùng**, gồm **đúng ba trình biên tập**:

1. **HST Writer** — xử lý văn bản, tương ứng Word.
2. **HST Sheets** — bảng tính, tương ứng Excel.
3. **HST Slides** — trình chiếu, tương ứng PowerPoint.

Tên sản phẩm thống nhất: **HST Office**. Không tạo thêm sản phẩm PDF Editor, Mail, Notes, Database, Cloud Office hay dịch vụ thương mại trong phạm vi bản đầu. Có thể dùng tính năng **xuất/in PDF bên trong ba ứng dụng**.

**Nguyên tắc:** Tận dụng ONLYOFFICE Desktop Editors và các API/plugin sẵn có; **không tự phát triển lại editor/engine** khi đã có thành phần ổn định. Ưu tiên giữ tương thích DOCX/XLSX/PPTX và trải nghiệm Ribbon quen thuộc với người dùng Microsoft Office. Đừng quảng cáo tương thích 100% nếu chưa đo kiểm chứng minh.

**Cực kỳ quan trọng:** Trước bất kỳ thay đổi rebranding/fork/distribution nào, thực hiện **license & trademark audit**. Miễn phí **không miễn trừ** nghĩa vụ bản quyền, cung cấp mã nguồn hoặc các điều khoản bổ sung. Không loại bỏ thông báo nguồn gốc ONLYOFFICE, bản quyền, giấy phép hay thông báo sửa đổi cần thiết. Không dùng thương hiệu, icon hoặc logo ONLYOFFICE ngoài phạm vi được phép. Nếu có điều khoản không rõ, ghi thành blocker yêu cầu người phụ trách xem xét; **không tự ý bỏ qua**. Tên HST Office là thương hiệu của dự án, không tuyên bố sở hữu engine gốc. Sử dụng logo của HASON TECH và dòng text ở dưới là HST OFFICE (giữ nguyên hình ảnh và thay text).

**Chế độ agent:** làm theo từng phase; mỗi phase phải có mã nguồn, tài liệu, kiểm thử và tiêu chí nghiệm thu. Không báo “hoàn tất” khi chưa chạy được lệnh hoặc chưa có bằng chứng. Không suy diễn lệnh build; đối chiếu README upstream theo commit/tag đã pin. Nếu không có quyền truy cập môi trường hoặc credential, cung cấp hướng dẫn và báo blocker thay vì giả vờ đã thực thi.

## 1. Thông tin sản phẩm, đơn vị phát triển và liên hệ

- **Tên sản phẩm:** HST Office
- **Tên hiển thị ba trình biên tập:** HST Writer, HST Sheets, HST Slides (nhãn trong giao diện; cần kiểm chứng trước khi thay tên executable/installer theo giấy phép và kỹ thuật).
- **Mô hình phát hành:** miễn phí hoàn toàn; ứng dụng máy tính cho Windows, Linux và macOS; không bắt buộc tạo tài khoản, không cần Internet để tạo/mở/chỉnh sửa/lưu tệp cục bộ.
- **Đơn vị phát triển/tùy biến và phát hành (theo phạm vi thực tế):** Công ty TNHH Công nghệ Hà Sơn — **HASON TECH**.
- **Địa chỉ:** 300 Xô Viết Nghệ Tĩnh, phường Cẩm Lệ, Thành phố Đà Nẵng, Việt Nam.
- **Website:** https://hasontech.vn
- **Điện thoại:** 0236 3.507.507
- **Email:** lienhe@hasontech.vn

### Nội dung giới thiệu đầy đủ (chỉ dùng tại trang Giới thiệu / website nếu phù hợp)

**Đồng hành tận tâm trên hành trình số**

HASON TECH nghiên cứu và phát triển hệ sinh thái sản phẩm, giải pháp AI “Make in Vietnam” gắn với nhu cầu thực tế. Chúng tôi đồng hành cùng khách hàng từ tư vấn định hướng, xây dựng nền tảng, kết nối dữ liệu đến ứng dụng AI, vận hành và tối ưu liên tục — để công nghệ tạo ra giá trị thiết thực.

- Chuyển đổi số toàn diện từ chiến lược, dữ liệu đến AI.
- Phục vụ cơ quan nhà nước, giáo dục, doanh nghiệp và cộng đồng.
- Sản phẩm AI “Make in Vietnam” phù hợp nghiệp vụ Việt.
- Triển khai nhanh, bảo mật dữ liệu, tối ưu chi phí.

### Bản giới thiệu ngắn (dùng trong About hoặc trang khởi động khi không đủ chỗ)

> **HST Office** là bộ công cụ soạn thảo văn bản, bảng tính và trình chiếu miễn phí, được HASON TECH phát triển/tùy biến nhằm phục vụ nhu cầu văn phòng của người Việt Nam. Xây dựng dựa trên công nghệ nguồn mở và tôn trọng các giấy phép thành phần.

**Lưu ý xuất xứ:** Nếu sử dụng/điều chỉnh ONLYOFFICE, tại About phải có mục dễ tiếp cận **“Nguồn mở & ghi nhận tác giả”** nêu rõ engine gốc ONLYOFFICE/Ascensio System SIA, nguồn mã, phiên bản gốc, ngày/sự thay đổi, giấy phép, thông báo pháp lý và cách nhận nguồn tương ứng. Không tạo ấn tượng rằng HASON TECH đã viết engine lõi nếu không đúng.

## 2. Mục tiêu sản phẩm, hệ điều hành và phạm vi

### 2.1. Nền tảng

- **Windows:** ưu tiên Windows 10/11 x64; xuất bộ cài `.exe`/`.msi` nếu toolchain và license cho phép.
- **macOS:** Apple Silicon và Intel trong phạm vi upstream hỗ trợ; `.dmg` hoặc `.pkg`; xác minh quy trình code signing/notarization trước phát hành đại trà.
- **Linux:** Ubuntu/Debian x64 trước (`.deb`); sau đó `.rpm`/AppImage nếu khả thi và kiểm thử.
- Giao diện tiếng Việt mặc định khi hệ điều hành là tiếng Việt (hoặc cho phép người dùng chọn); có tùy chọn English.
- Chạy offline với các tính năng chỉnh sửa cốt lõi. Không phụ thuộc server cho thao tác văn phòng căn bản.
- Dùng tệp cục bộ, lưu an toàn; tránh xóa/ghi đè tệp không có xác nhận hoặc cơ chế backup/recovery.

### 2.2. Phạm vi loại trừ bản đầu

- Không bắt buộc AI assistant, cloud sync, collaboration real-time, tài khoản cloud, marketplace riêng.
- Không phát triển editor PDF độc lập; chỉ in/xuất PDF từ Writer/Sheets/Slides nếu engine cho phép.
- Không hứa tương thích hoàn chỉnh VBA, macro Microsoft Office, Power Query, add-in COM, hiệu ứng PowerPoint đặc thù.

## 3. Hướng tiếp cận engine và quyết định kiến trúc

### Nguyên tắc chọn ONLYOFFICE

1. **Bước A — Baseline:** cài/bật ONLYOFFICE Desktop Editors upstream nguyên trạng trên máy kiểm thử, chốt phiên bản/tag/commit, đánh giá khả năng đáp ứng thực tế.
2. **Bước B — Plugin-first:** phát triển bổ sung nội dung/tác vụ bằng SDK plugin và Office API/macros, tránh fork engine cho tính năng có thể cắm thêm.
3. **Bước C — Fork có kiểm soát:** chỉ sửa Desktop Editors shell / giao diện native / packaging khi cần thiết, có tài liệu lý do, ảnh hưởng khi cập nhật upstream, và xác minh license/trademark.
4. **Bước D — Distribution gate:** chỉ phát hành installer HST Office sau khi hoàn thành audit giấy phép, notices, branding, bản build có khả năng tái tạo và kiểm thử trên OS tương ứng.

Plugin SDK không có quyền truy cập tùy ý vào filesystem hay DOM nội bộ editor; nếu một chức năng cần các quyền đó, cần chọn API/kiến trúc phù hợp thay vì “hack” vượt sandbox.

### Repo gợi ý

```text
hst-office/
  README.md
  LICENSES/
  NOTICE.md
  THIRD_PARTY_NOTICES.md
  docs/
    ARCHITECTURE.md
    UPSTREAM_BASELINE.md
    LICENSE_AUDIT.md
    BUILD_MATRIX.md
    VIETNAMESE_OFFICE_SPEC.md
    COMPATIBILITY_MATRIX.md
    RELEASE_CHECKLIST.md
    ADR/
  extensions/
    vn-admin-documents/
    vn-encoding-tools/
    vn-templates/
    vn-spreadsheet-formats/
  templates/
    writer/
    sheets/
    slides/
  tests/
    fixtures/  # chỉ dùng file mẫu được quyền phân phối, KHÔNG chứa tài liệu nhạy cảm
    smoke/
    roundtrip/
  scripts/
  .github/workflows/
  upstream/  # tài liệu hướng dẫn pin submodule/fork, không tự sao chép mã nguồn vô tội vạ
```

Tổ chức chính xác cần điều chỉnh theo cấu trúc upstream, không ép bố cục này lên source engine nếu gây xung đột.

## 4. Đặc tả chức năng: HST Writer

### 4.1. Cốt lõi ưu tiên P0

- Tạo/mở/chỉnh sửa/lưu DOCX, mở DOC/ODT/RTF/TXT theo khả năng hỗ trợ của engine, thông báo khi chức năng không được giữ nguyên.
- Ribbon quen thuộc: Home, Insert, Layout, References, Review, View, File.
- Kiểu chữ (font), cỡ chữ, màu, bold/italic/underline, highlight, styles, headings; căn trái/phải/giữa/đều; lề, tab, thụt đầu dòng, khoảng cách dòng/đoạn.
- A4 mặc định có thể tùy biến; A3, dọc/ngang; thước đo cm/mm; header/footer, đánh số trang, ngắt trang và section.
- Bảng, merge/split cells, danh sách, bullet/numbering, hình ảnh, shapes, chú thích, textbox.
- Tìm kiếm/thay thế tiếng Việt; mục lục tự động; footnote/endnote nếu engine hỗ trợ; nhận xét và theo dõi thay đổi khi có.
- Print Preview, in, xuất PDF; AutoRecover và cảnh báo khi thoát có sửa đổi chưa lưu.

### 4.2. Đặc thù Việt Nam P0/P1

- Unicode UTF-8 và nhập tiếng Việt qua Unikey/EVKey/IME của OS; dấu không mất khi nhập/copy/paste/tìm kiếm.
- Font: lựa chọn Times New Roman, Arial và font sẵn có trên máy; **không đóng gói font thương mại thiếu giấy phép**.
- Mẫu **văn bản hành chính theo Nghị định 30/2020/NĐ-CP**, kiểm tra quy định còn hiệu lực trước khi phát hành: công văn, thông báo, quyết định, tờ trình, báo cáo, giấy mời, biên bản.
- Chèn mẫu: quốc hiệu/tiêu ngữ, tên cơ quan, số/ký hiệu, địa danh/ngày tháng, trích yếu, nơi nhận, ký tên; người dùng vẫn tự nhập hoặc chọn dữ liệu, không tự bịa tên cơ quan/người ký.
- Mặc định/thao tác nhanh cho A4; theo Phụ lục I NĐ 30/2020: lề trên/dưới 20–25 mm, trái 30–35 mm, phải 15–20 mm (mẫu cụ thể kiểm theo loại văn bản và quy định hiện hành).
- Công cụ chuyển mã TCVN3 (ABC) / VNI → Unicode **chỉ khi xác minh rõ bảng mã**; có preview trước khi áp dụng, Undo và kiểm thử dấu/hoa thường.
- Tính năng “Kiểm tra thể thức” giai đoạn P1: cảnh báo vấn đề cấu trúc/định dạng; không tự tuyên bố văn bản hợp lệ pháp lý.

## 5. Đặc tả chức năng: HST Sheets

### P0

- Tạo/mở/chỉnh sửa/lưu XLSX; hỗ trợ nhập CSV, mở XLS/ODS theo khả năng engine.
- Worksheet, formula bar, row/column, range, copy/paste, sort/filter, freeze panes, định dạng ô, merge cells, print area/page breaks.
- Các hàm cơ bản và phổ biến: SUM, AVERAGE, COUNT, IF, SUMIF/SUMIFS, COUNTIF/COUNTIFS, VLOOKUP, INDEX/MATCH; kiểm tra XLOOKUP trên phiên bản engine thực tế.
- Conditional formatting, data validation, biểu đồ; bảng tổng hợp/Pivot theo khả năng engine và kiểm thử thực tế.
- Định dạng ngày `dd/mm/yyyy`, VND, phần trăm, dấu thập phân/hàng nghìn theo locale Việt Nam; dấu phân cách tham số công thức cần xác định qua engine và locale, không tự thay thế công thức thô.
- CSV UTF-8 BOM/no-BOM, chọn encoding, delimiter, preview để tránh lỗi dấu tiếng Việt.
- Mẫu quản lý văn phòng: bảng chấm công, bảng lương mẫu, dự toán, thu chi, thống kê, danh sách.

### P1

- Kiểm tra round-trip công thức, tên sheet Unicode, biểu đồ, conditional formatting, named ranges, external links.
- Nếu một tính năng Excel nâng cao không tương thích, thông báo rõ trước khi lưu; tránh mất dữ liệu âm thầm.

## 6. Đặc tả chức năng: HST Slides

### P0

- Tạo/mở/chỉnh sửa/lưu PPTX; nhập PPT/ODP theo khả năng engine.
- Slide 16:9/4:3, themes, templates, layouts, slide master; chèn và sửa textbox, ảnh, shapes, tables, charts.
- Điều chỉnh vị trí/căn chỉnh/group/layers, bullets, speaker notes, trình chiếu fullscreen.
- Transition, animation, multimedia và presenter tools theo tính năng được engine hỗ trợ, có kiểm thử chéo.
- In handouts, xuất PDF.
- Bộ mẫu tiếng Việt: họp cơ quan, báo cáo đơn vị, giảng dạy, hội nghị, báo cáo doanh nghiệp. Không dùng quốc huy hoặc biểu trưng cơ quan nhà nước trong template mặc định nếu không có quyền/phù hợp.

## 7. Yêu cầu UX/thiết kế giao diện

- Đảm bảo trải nghiệm Ribbon quen thuộc: tổ chức nút lệnh và phím tắt giống hệ quy chiếu người dùng Microsoft Office **trong phạm vi không sao chép asset/thương hiệu bị hạn chế**.
- Chữ tiếng Việt đủ chỗ, không bị cắt trong Ribbon/dialog; tooltip rõ nghĩa; icon nhất quán.
- Bộ cài và tên ứng dụng hiển thị **HST Office**; giao diện được nhận diện phù hợp thương hiệu HASON TECH, nhưng **không xóa attribution bắt buộc của upstream**.
- Màn hình Home: Tạo tài liệu, Tạo bảng tính, Tạo trình chiếu, Mở tệp, Gần đây, Mẫu tiếng Việt.
- About: phiên bản HST Office, engine upstream và phiên bản, bản quyền/giấy phép và nguồn mã, thông tin liên hệ, nguồn hỗ trợ.
- Không telemetry mặc định nếu chưa có chính sách minh bạch và lựa chọn của người dùng; tuyệt đối không tự tải nội dung tài liệu cá nhân lên server.
- Tương thích DPI/scale đa màn hình, dark/light mode nếu upstream hỗ trợ ổn định.

## 8. Môi trường phát triển & nguyên tắc dùng 50 GB SSD

**VPS dev hiện có (không nâng cấp trước khi có dữ liệu chứng minh nhu cầu):**

- 8 vCPU
- 16 GB RAM
- 50 GB SSD
- Giả định Ubuntu Server x64; xác minh OS và dung lượng trống thực tế.

**Nhiệm vụ VPS:** vibe coding, chạy tests nhẹ, lint, build extensions/plugins, quản lý cấu hình, git. **Không buộc biên dịch toàn bộ engine upstream trên VPS 50 GB.**

- Không lưu nhiều copy source upstream và artifacts trên cùng VPS.
- Lưu repo và tag/commit cố định; dùng shallow clone khi hợp lý, không làm hỏng khả năng tham chiếu license/source.
- Đặt cảnh báo dung lượng còn dưới 10 GB; dọn cache có kiểm soát (không xóa dữ liệu người dùng hoặc source chưa push).
- Tài liệu mẫu và output release đặt trong GitHub Artifacts/Releases hoặc kho lưu trữ bên ngoài; chú ý giới hạn dung lượng và retention.
- Không dùng `rm -rf`/prune tự động ngoài những thư mục cache đã xác nhận.

## 9. CI/CD GitHub: tận dụng runner và giới hạn

- **GitHub Actions**: chạy lint/test/plugin build, kiểm thử tích hợp, packaging từng OS; publish bản beta/release khi kiểm thử đạt.
- Mỗi OS một job/matrix riêng khi phù hợp. GitHub Ubuntu standard runner **không mặc định đủ SSD để compile toàn bộ ONLYOFFICE** (upstream build_tools tham chiếu môi trường 100 GB SSD).
- Với full engine build, dùng self-hosted runner dung lượng lớn, larger runner trả phí, hoặc máy build riêng; **đừng giả định GitHub Actions miễn phí đủ tài nguyên**.
- CI public repo standard runner có thể miễn phí theo chính sách hiện hành, nhưng kiểm tra lại quota, chính sách và kích thước runner trên tài khoản tại lúc thực hiện.
- Không nhúng key/certificate vào repo; dùng GitHub Secrets; cấp quyền workflow tối thiểu; pin actions ở phiên bản/hash đáng tin cậy.
- macOS signing/notarization yêu cầu tài khoản/chứng chỉ phù hợp; Windows code signing tùy chiến lược phân phối. Chưa có chứng chỉ thì đánh dấu bản thử nghiệm, không giả mạo trạng thái verified.
- Mỗi release: version, changelog, SHA-256, danh sách OS/arch, dấu vết commit, source corresponding, SBOM/third-party notices khi khả thi.

### Workflow tối thiểu đề xuất

- `quality.yml`: trên pull request — lint, format, unit tests, kiểm tra license notices, tệp mẫu.
- `plugins.yml`: build plugin/extensions; upload artifact, chạy smoke tests nếu có runtime phù hợp.
- `desktop-linux.yml`: build/packaging Linux theo hướng dẫn upstream **chỉ sau khi xác định runner đủ sức**.
- `desktop-windows.yml`: Windows runner, dùng toolchain upstream được hỗ trợ.
- `desktop-macos.yml`: macOS runner, code signing/notarize khi đủ điều kiện.
- `release.yml`: phát hành từ tag đã duyệt, dùng build artifacts được kiểm chứng, checksum, GitHub Releases.

**Không tạo CI giả chỉ có lệnh `echo success`.** Nếu chưa có builder thực tế, cung cấp skeleton workflow có `TODO` và ghi rõ chưa hoạt động.

## 10. License, trademark & nguồn mở — cổng bắt buộc trước rebrand

- Kiểm tra đầy đủ license hiện hành của **ONLYOFFICE/DesktopEditors**, **ONLYOFFICE/desktop-apps**, **core**, `sdkjs`, plugin, media/assets, fonts, installer dependencies và các submodule** tại đúng upstream commit**.
- ONLYOFFICE repository công bố AGPLv3; một số repository có **additional terms** về attribution, thông báo sửa đổi, UI legal notices, thương hiệu và license của nội dung không phải code. Xem LICENSE nguyên văn, không suy ra tất cả repository có cùng điều kiện.
- Không xóa thông báo bản quyền hoặc nguồn gốc. Ở About và tài liệu đi kèm, nêu rõ **“HST Office sử dụng phiên bản được tùy biến từ ONLYOFFICE Desktop Editors; ONLYOFFICE là phần mềm gốc của Ascensio System SIA”** nếu đó là mô tả đúng của bản build.
- Công bố source tương ứng theo nghĩa vụ áp dụng và xác định rõ quy trình cung cấp source/bản sửa đổi. Không viết “mã nguồn đóng” đối với thành phần phải công bố.
- Xác minh quyền đặt tên, sửa icon/splash/installer; tránh dùng trademark ONLYOFFICE như thể thuộc HASON TECH. Tên HST Office và logo HASON TECH phải có asset do bên dự án cung cấp, không tự lấy logo trên web để phát hành.
- Việc miễn phí không có nghĩa mọi điều khoản được bỏ qua. **Nếu có điểm pháp lý chưa rõ, hoãn rebrand/phát hành** và đề xuất hỏi người có chuyên môn pháp lý hoặc chủ sở hữu quyền.

## 11. Kiểm thử/QA và tiêu chí nghiệm thu

### Bộ dữ liệu kiểm thử

- Writer: công văn NĐ30, hợp đồng 30–100 trang, bảng nhiều trang, header/footer, section, footnote, mục lục, hình ảnh, ghi chú, track changes, văn bản có dấu tiếng Việt và nhiều font.
- Sheets: bảng lương/chấm công, dữ liệu CSV UTF-8, hàng nghìn dòng, nhiều sheet, công thức, filter/conditional formatting, biểu đồ, kiểu dữ liệu thời gian/VND.
- Slides: slide nhiều bố cục, ảnh, charts, themes, slide master, animation, presenter notes, font tiếng Việt.
- Không đưa dữ liệu cá nhân thật hoặc tài liệu mật vào repository.

### Phương pháp

1. Tạo/mở tài liệu trên Microsoft Office (bằng máy kiểm thử có bản quyền hợp pháp) → mở HST Office → chỉnh sửa → lưu → mở lại Microsoft Office.
2. So sánh hình thức/định dạng qua screenshot hoặc render PDF theo từng trang/slide; so sánh giá trị và công thức đối với spreadsheet.
3. So sánh nội dung tệp trước/sau; kiểm tra lỗi Unicode, ảnh và bảng, không mất dữ liệu khi crash/recover.
4. Ghi nhận lỗi theo mức P0 (mất dữ liệu/crash), P1 (sai bố cục/không tương thích nghiêm trọng), P2 (thẩm mỹ/tiện ích).

### Điều kiện phát hành v1.0

- Ba ứng dụng chạy offline trên các OS/arch được công bố.
- Có thể tạo, mở, sửa, lưu DOCX/XLSX/PPTX cho bộ fixture đại diện và không phát hiện mất dữ liệu mức P0.
- Giao diện tiếng Việt hiển thị đúng; bộ mẫu văn phòng Việt Nam được kiểm thử.
- About/contact, license/attribution/source link đúng; hồ sơ legal audit đã duyệt.
- Installer được kiểm tra trên máy sạch, uninstall không xóa tài liệu của người dùng.
- Có hướng dẫn dùng, phát hành và báo lỗi.

## 12. Lộ trình triển khai ưu tiên

### Phase 0 — Audit & Spike (điều kiện tiên quyết)

- Xác định phiên bản upstream, các repo phụ thuộc và giấy phép tại commit cụ thể.
- Chạy ONLYOFFICE Desktop Editors gốc trên Windows/Linux/macOS kiểm thử hoặc xác định OS chưa có máy test.
- Proof-of-concept plugin “Mẫu văn bản hành chính Việt Nam” trên engine nguyên bản; chứng minh tạo/chèn được nội dung và lưu DOCX.
- Đánh giá phương án đóng gói/rebranding, chi phí build, runner/SSD thực tế.
- Deliverables: `UPSTREAM_BASELINE.md`, `LICENSE_AUDIT.md`, `ARCHITECTURE.md`, bảng blockers và PoC chạy được.

### Phase 1 — MVP dùng được

- HST Writer/Sheets/Slides: mở-tạo-sửa-lưu các định dạng chính (dựa trên engine có sẵn).
- Bộ mẫu tối thiểu tiếng Việt; bộ cài Linux beta hoặc extension cài trên upstream, tùy khả năng và legal gate.
- Unit/smoke/round-trip test; README hướng dẫn phát triển.

### Phase 2 — Việt hóa chuyên sâu

- Word: hành chính NĐ30, chuyển mã TCVN3/VNI→Unicode, kiểu chữ/lề và kiểm tra định dạng.
- Excel: CSV UTF-8, định dạng ngày tháng/VND, mẫu báo cáo, công thức phổ biến.
- Slides: mẫu tiếng Việt và QA trình chiếu.
- Accessibility, các trường hợp lỗi và tài liệu sử dụng.

### Phase 3 — Packaging 3 OS & Release

- Test matrix Windows/macOS/Linux; fix các lỗi nền tảng.
- Build pipeline thật, checksum, license notices, release notes.
- Beta công khai → phản hồi → release v1.0 miễn phí.

## 13. Những việc Codex và Claude phải làm đầu tiên

1. Đọc đặc tả này và tạo backlog chi tiết có P0/P1/P2, dependency, acceptance criteria.
2. Truy cập và xác minh các tài liệu upstream/changelog/license **tại thời điểm thực thi**; ghi rõ phiên bản, commit SHA, các khác biệt so với tài liệu này.
3. Trình bày **hai đường đi**: (A) plugin-first chạy trên bản upstream, (B) fork/rebrand shell; kết luận cái nào khả thi và hợp lệ, không tự động fork trước audit.
4. Tạo cấu trúc repo, ADR và các tài liệu Phase 0. Cung cấp một PoC plugin thực sự có thể cài và dùng offline.
5. Đo lượng SSD/RAM/CPU thực dùng tại mỗi job; nếu full build cần >50 GB trên VPS thì **chuyển sang runner khác**, không lấp đầy disk production/dev.
6. Sau Phase 0 mới bắt đầu code theo backlog; mỗi PR có tests, ảnh/chứng cứ cho hành vi giao diện và cập nhật docs.
7. Không thêm AI cloud, login hay telemetry nếu chưa được duyệt riêng.

## 14. Links kiểm chứng chính thức

- Desktop Editors source: https://github.com/ONLYOFFICE/DesktopEditors
- ONLYOFFICE build_tools (hướng dẫn build và yêu cầu tài nguyên): https://github.com/ONLYOFFICE/build_tools
- Desktop app source/license: https://github.com/ONLYOFFICE/desktop-apps
- ONLYOFFICE Plugins API: https://api.onlyoffice.com/docs/plugins/get-started/overview
- Desktop plugin install: https://api.onlyoffice.com/docs/desktop-editors/usage-api/adding-plugins
- GitHub-hosted runners: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- GitHub Actions billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Nghị định 30/2020/NĐ-CP: xác minh trên Cổng thông tin văn bản pháp luật chính thức trước khi triển khai các mẫu pháp lý.

---

**Thước đo thành công:** HST Office miễn phí, ổn định, thân thiện với người dùng quen Microsoft Office, có ba trình biên tập phục vụ người Việt; giao diện tiếng Việt, tương thích thực tế với DOCX/XLSX/PPTX và tuân thủ pháp luật nguồn mở. **Không hy sinh khả năng lưu đúng dữ liệu để đổi lấy rebranding hoặc thêm tính năng.**
