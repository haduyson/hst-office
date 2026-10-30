# Brief: landing page office.hasontech.vn (HST Office)

Người yêu cầu: chủ dự án HST Office (HASON TECH). Ngày: 2026-10-30.

## Mục tiêu
Một landing page tiếng Việt, một trang, đẹp, nhanh, chuẩn SEO, giới thiệu **HST Office** — bộ ứng dụng văn phòng **MIỄN PHÍ VĨNH VIỄN** cho người Việt — và cho tải bộ cài.

## Cách làm (bắt buộc)
- **Thiết kế và viết code bằng Codex CLI, model gpt-6-astra, reasoning effort xhigh** (`codex exec -c model_reasoning_effort=xhigh ...`, sandbox `workspace-write` trong một thư mục làm việc; không dùng `--full-auto`). Bạn (phiên remote) điều phối, review, sửa lỗi, rồi deploy.
- Trang **tĩnh** (HTML + CSS + JS tối thiểu, không framework nặng, không build step bắt buộc). Ảnh tối ưu (WebP + fallback, lazy-load), Lighthouse mục tiêu ≥ 90 cả 4 mục, responsive tốt ở mobile.

## Triển khai
- Máy chủ: **VPS 239** (103.122.221.239) — thông tin truy cập bạn đã có trong phiên này. DNS `office.hasontech.vn` đã trỏ về IP này.
- Hosting: subdomain dưới user **hasontech** (cùng hosting). Thư mục web: **`/domains/office.hasontech.vn/public_html`** (đường dẫn trong home của user hasontech, ví dụ `/home/hasontech/domains/office.hasontech.vn/public_html` — xác minh thực tế trên VPS).
- Nếu subdomain chưa được tạo trong control panel thì tạo đúng cách của panel đang dùng (không sửa tay cấu hình web server của site khác). Bật HTTPS (Let's Encrypt qua panel) và chuyển hướng HTTP→HTTPS.
- **An toàn:** chỉ đụng thư mục/subdomain này. Không sửa site khác của user hasontech hay site khác trên VPS. Sao lưu `public_html` hiện có (nếu có nội dung) trước khi ghi đè. File thuộc user `hasontech`, quyền 644/755. Không đặt secret/khóa vào code trang.
- Sau deploy: kiểm tra `https://office.hasontech.vn` trả 200, chứng chỉ hợp lệ, ảnh và link tải chạy.

## Tài sản (lấy từ repo trên máy này: `/home/office`)
- Logo: `/home/office/branding/libreoffice/logo.svg` (logo HST OFFICE), biểu tượng `/home/office/assets/brand/hst-office-mark.png`.
- Icon ứng dụng (bộ "Ô vuông"): `/home/office/assets/brand/icons/hst-{office,writer,sheets,slides,draw,math,base}-{256,512,1024}.png` và `.svg`.
- Banner: `/home/office/assets/marketing/hst-office-banner-quangba-1910x1000.png` (dùng làm ảnh OG/social share 1200×628: `hst-office-banner-quangba-1200x628.png`).
- Ảnh chụp giao diện thật (tiếng Việt): `/home/office/tests/output/screenshots-policy/` (10-writer-ribbon, 12-calc-first, 14-impress-first, 02-start-center, 08-about…), `/home/office/tests/output/screenshots-tabs/02-three-tabs-calc.png` (nhiều tab trong một cửa sổ), `/home/office/tests/output/screenshots-backlog/nd30-wizard-filled.png`, `welcome-dialog-vi.png`. Cắt/viền khung cửa sổ cho đẹp; không dùng ảnh có lỗi hiển thị.
- **Phong cách (chủ dự án yêu cầu): màu sắc rực rỡ, đẹp, sinh động — đúng tinh thần 2 banner Codex đã thiết kế** (`assets/marketing/hst-office-banner-quangba-*.png`, `hst-office-banner-sapramat-*.png`): nền gradient xanh sáng/xanh trời, cửa sổ ứng dụng dạng kính 3D phát sáng, khối màu module tươi, nhãn xanh lá đậm chữ trắng "MIỄN PHÍ VĨNH VIỄN" nổi bật, chiều sâu và ánh sáng mềm. Có thể dùng chính `bg-quangba.png` / `bg-sapramat.png` (ảnh nền không chữ) trong `assets/marketing/` hoặc nhờ Codex tạo thêm minh họa cùng phong cách (không chữ trong ảnh — chữ tiếng Việt luôn là HTML). Tránh giao diện nhạt, xám, "template".
- Màu: xanh HST `#0B6FC1`, chữ `#322E2E`; Văn bản `#2F5BD3`, Bảng tính `#1E8E3E`, Trình chiếu `#E8590C`; nhãn "Miễn phí vĩnh viễn": nền xanh lá đậm `#0E7A36`, chữ trắng (chủ dự án chọn). Font hỗ trợ tiếng Việt tốt (Be Vietnam Pro hoặc Noto Sans, self-host hoặc Google Fonts).

## Nội dung trang (tiếng Việt, đúng chính tả, có dấu)
1. **Hero:** logo, "Bộ ứng dụng văn phòng dành cho người Việt", badge **MIỄN PHÍ VĨNH VIỄN** + "Dùng trọn đời · Không thu phí bản quyền", nút tải chính (tự nhận hệ điều hành: Windows/macOS/Linux) + link "Các phiên bản khác", ảnh giao diện.
2. **Ba ứng dụng:** Văn bản · Bảng tính · Trình chiếu (dùng icon bộ Ô vuông).
3. **Tính năng nổi bật:** giao diện tiếng Việt; mẫu văn bản hành chính theo Nghị định 30 (có trình hướng dẫn); chuyển mã TCVN3/VNI sang Unicode; mở và lưu tệp Word, Excel, PowerPoint (DOCX/XLSX/PPTX); giao diện thân thiện, dễ dàng sử dụng (không dùng chữ "ribbon" trên trang — chủ dự án); mở nhiều tài liệu dạng tab trong một cửa sổ; chạy trên Windows, macOS, Linux; dùng offline, không cần tài khoản. Chỉ nêu tính năng có thật — không bịa (không AI, không đám mây, không đồng bộ).
4. **Tải về:** 3 khối Windows / macOS / Linux:
   - Windows 10/11 64-bit: `.msi`
   - macOS (Apple Silicon / Intel): `.dmg` — **đang chuẩn bị**, hiển thị "Sắp có" nếu chưa có file.
   - Linux (Ubuntu/Debian 64-bit): `.deb` (gói `.tar.gz`), kèm lệnh cài ngắn.
   - Link tải: `https://github.com/haduyson/hst-office/releases/download/<TAG>/<FILE>`; hiện tại TAG = `v1.0.0-beta.1`, file: `HSTOffice_1.0.0_Win_x86-64_en-US_vi.msi`, `HSTOffice_1.0.0_Linux_x86-64_deb.tar.gz`, `SHA256SUMS`. Đặt TAG và tên file ở **một chỗ cấu hình duy nhất** (ví dụ `config.js`) để đổi bản phát hành dễ (beta.2 sắp ra, sẽ thêm macOS `.dmg`). Ghi chú nhãn "Bản thử nghiệm (beta)".
   - **Bổ sung (chủ dự án): luôn có sẵn đủ 3 nút tải cho Windows / macOS / Linux** (macOS có 2 lựa chọn: Apple Silicon và Intel). Nút nào chưa có link thì hiển thị trạng thái "Sắp có" (vẫn đẹp, không phải nút hỏng); khi điền link vào cấu hình thì nút tự bật. Bảng link dự kiến (tên file đã cố định theo workflow phát hành):

     | Nền tảng | Hiện tại (đã có) | Dự kiến bản kế tiếp `v1.0.0-beta.2` |
     |---|---|---|
     | Windows | `…/v1.0.0-beta.1/HSTOffice_1.0.0_Win_x86-64_en-US_vi.msi` | `…/v1.0.0-beta.2/HSTOffice_1.0.0_Win_x86-64_en-US_vi.msi` |
     | Linux | `…/v1.0.0-beta.1/HSTOffice_1.0.0_Linux_x86-64_deb.tar.gz` | `…/v1.0.0-beta.2/HSTOffice_1.0.0_Linux_x86-64_deb.tar.gz` |
     | macOS Apple Silicon | (chưa có → "Sắp có") | `…/v1.0.0-beta.2/HSTOffice_1.0.0_macOS_arm64.dmg` |
     | macOS Intel | (chưa có → "Sắp có") | `…/v1.0.0-beta.2/HSTOffice_1.0.0_macOS_x86_64.dmg` |

     (`…` = `https://github.com/haduyson/hst-office/releases/download`.) Bây giờ gắn link **beta.1** cho Windows và Linux; macOS để "Sắp có". Ghi sẵn link beta.2 trong cấu hình dưới dạng chú thích để bật khi phát hành.
   - **Link tải cố định trên domain:** các nút trỏ tới `https://office.hasontech.vn/tai/windows`, `/tai/macos-arm`, `/tai/macos-intel`, `/tai/linux`, `/tai/sha256` — chuyển hướng 302 (cấu hình ở một file duy nhất, ví dụ `.htaccess` nếu web server là Apache/LiteSpeed, hoặc cấu hình tương đương) sang link GitHub hiện hành. Khi ra bản mới chỉ sửa file chuyển hướng; link chia sẻ ra ngoài không bao giờ đổi. Link chưa có thì chuyển về mục "Tải về" của trang.
   - Ghi chú ngắn: bản thử nghiệm chưa ký số → Windows SmartScreen chọn "More info → Run anyway"; macOS chuột phải → Open; kiểm tra SHA256.
5. **Câu hỏi thường gặp:** có thật sự miễn phí? (có, vĩnh viễn, nguồn mở); dùng cho doanh nghiệp/cơ quan được không?; mở được tệp Word/Excel cũ không?; có cần Internet không?; dữ liệu có gửi đi đâu không? (không); cài tiện ích thế nào? (tự tải tệp .oxt, tự chịu trách nhiệm); hỗ trợ ở đâu?
6. **Chân trang:** "Sản phẩm của HASON TECH", Công ty TNHH Công nghệ Hà Sơn (HASON TECH), 300 Xô Viết Nghệ Tĩnh, phường Cẩm Lệ, TP. Đà Nẵng · Điện thoại (0236) 3.507.507 · lienhe@hasontech.vn · hasontech.vn; dòng "© 2026 HASON TECH · © 2000–2026 The Document Foundation và các tác giả LibreOffice"; "Phần mềm nguồn mở theo giấy phép MPL-2.0". Danh sách giải pháp HASON TECH đúng thứ tự: AIOS, eChatbot, Zalo Mini App, HST SEO, HST Content, AI Dễ Lắm (link hasontech.vn có UTM `utm_source=office-hasontech-vn&utm_medium=landing&utm_campaign=hst-office-1-0`).

## Quy định thương hiệu/pháp lý
- **Không** ghi "© HASON TECH. All rights reserved" cho toàn bộ sản phẩm. Chỉ dùng dòng bản quyền ở mục 6.
- Không dùng logo/ảnh LibreOffice; được phép nhắc "dựa trên mã nguồn mở LibreOffice" ở FAQ/chân trang nếu cần, không dùng làm điểm quảng bá chính. Không có nút "Donate".
- Link GitHub chỉ dùng cho nút tải (được phép trên website).

## SEO / kỹ thuật
- `lang="vi"`, title ~60 ký tự, meta description ~155 ký tự, Open Graph + Twitter card (ảnh banner 1200×628), favicon từ icon HST Office, `schema.org/SoftwareApplication` (offers price 0, VND), sitemap.xml, robots.txt, canonical `https://office.hasontech.vn/`.
- Không tracker bên thứ ba nếu chưa được yêu cầu.

## Bàn giao
- Code nguồn trang cũng lưu một bản trong repo: `/home/office/website/office.hasontech.vn/` (không commit ảnh quá 500 KB/ảnh; không commit secret). Báo lại cho phiên `office`: URL, ảnh chụp trang (desktop + mobile), điểm Lighthouse, những gì đã sao lưu/thay đổi trên VPS.
