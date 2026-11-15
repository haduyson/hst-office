# HST Office landing page

Trang tĩnh HTML/CSS/JS, không cần bước build. `index.html` là trang chính;
`404.html` dùng chung CSS. Ảnh, font và JavaScript nằm trong `assets/`.

## Bản phát hành và liên kết tải

- Sửa trạng thái nền tảng, phiên bản và nhãn trong [config.js](config.js).
- Sửa đích chuyển hướng trong [.htaccess](.htaccess) (tệp trong `tai/<phiên bản>/`), giữ nguyên các URL `/tai/*`.
- Cả bốn link `/tai/windows`, `/tai/macos-arm`, `/tai/macos-intel`, `/tai/linux` và `/tai/sha256` đang được bật, phục vụ từ `tai/<phiên bản>/` trên site.
- Khi đổi trạng thái phát hành, cập nhật cả HTML dự phòng trong [index.html](index.html) để trang vẫn đúng khi tắt JavaScript.
- `.htaccess` cần Apache/LiteSpeed hỗ trợ rewrite. Máy chủ tĩnh thông thường chỉ xem được giao diện, không xử lý các chuyển hướng này.

## Hướng dẫn cài đặt (/cai-dat/)

- Menu **Hướng dẫn** gồm **Hướng dẫn cài đặt** (`/cai-dat/`) và **Hướng dẫn sử dụng** (`/huong-dan/`); menu và chân trang dựng từ `scripts/site_chrome.py`, áp cho các trang bằng `python3 scripts/apply-chrome.py`.
- `/cai-dat/` và `/cai-dat/go-loi/` dựng bằng `python3 scripts/build-install-guide.py` từ nội dung trong `scripts/install-guide/` (cần Pillow). Tên bộ cài lấy theo `version` trong `config.js`, nên **khi ra bản mới phải chạy lại script này**.
- Ảnh: ảnh gốc ở `scripts/install-guide/images/<tên>.png`, viết `<img src="images/<tên>.png" alt="…">` trong nội dung; script ghi bản thu nhỏ `.png` + `.webp` vào `cai-dat/images/` và gắn `?v=`.
- Mục này nằm ngoài `/huong-dan/` vì `scripts/sync-help.py` xóa và dựng lại toàn bộ thư mục đó. Liên kết cũ `/#cai-dat-linux` được `main.js` chuyển sang `/cai-dat/#linux`.

## Manifest cập nhật

`update/latest.json` + `update/latest.json.sig` báo phiên bản mới cho ứng dụng. Sửa manifest thì phải ký lại (`scripts/release/sign-update-manifest.py`) và tải lên cả hai tệp; xem `docs/UPDATE_CHECK.md` ở gốc dự án.

## Tài sản giao diện

- Nhãn “MIỄN PHÍ VĨNH VIỄN”: nền `#0E7A36`, chữ và ngôi sao trắng; tương phản đạt AA.
- `assets/img/og-hst-office.jpg` (ảnh chia sẻ của trang chủ, chủ quyết giữ nguyên; `pages.json` đánh dấu `keep_existing_image` nên script không thay): 1200×628, dưới 200 KB, xuất từ banner mới `assets/marketing/hst-office-banner-quangba-1200x628.png` ở gốc dự án HST Office.
- Ảnh chia sẻ mạng xã hội riêng từng trang: `assets/img/og/<slug>.jpg` (1200×630, dưới 300 KB), dựng từ mẫu `scripts/og/template.html` và danh sách `scripts/og/pages.json` bằng `python3 scripts/render-og-images.py` (cần Playwright + Chromium; tuỳ chọn `--chromium <tệp chạy>`, `--sheet <jpg>` để ghép lưới duyệt, `--check` chỉ kiểm tra). Script gắn `og:image*`/`twitter:image*` kèm `?v=<sha256>` cho mọi trang; `sync-help.py` và `build-install-guide.py` gắn cùng thẻ qua `scripts/og_meta.py`. **Thêm trang mới**: thêm mục vào `pages.json` rồi chạy lại script (thiếu mục thì trang tạm dùng ảnh của mục cha và có cảnh báo).
- Khi thay CSS, JS hoặc ảnh đã cache, tăng tham số `?v=` ở các URL tham chiếu tương ứng. Máy chủ đặt cache dài hạn cho tài sản tĩnh.

Thư mục bàn giao không chứa `plans/`, `.verify/` hay script kiểm tra tạm.
