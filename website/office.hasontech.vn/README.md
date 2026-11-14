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
- `assets/img/og-hst-office.jpg`: 1200×628, dưới 200 KB, xuất từ banner mới `assets/marketing/hst-office-banner-quangba-1200x628.png` ở gốc dự án HST Office.
- Khi thay CSS, JS hoặc ảnh đã cache, tăng tham số `?v=` ở các URL tham chiếu tương ứng. Máy chủ đặt cache dài hạn cho tài sản tĩnh.

Thư mục bàn giao không chứa `plans/`, `.verify/` hay script kiểm tra tạm.
