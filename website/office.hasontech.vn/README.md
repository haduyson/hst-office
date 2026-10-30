# HST Office landing page

Trang tĩnh HTML/CSS/JS, không cần bước build. `index.html` là trang chính;
`404.html` dùng chung CSS. Ảnh, font và JavaScript nằm trong `assets/`.

## Bản phát hành và liên kết tải

- Sửa trạng thái nền tảng, phiên bản và nhãn trong [config.js](config.js).
- Sửa đích chuyển hướng GitHub trong [.htaccess](.htaccess), giữ nguyên các URL `/tai/*`.
- Windows, Linux và `/tai/sha256` đang được bật; hai bản macOS đang chuẩn bị.
- Khi đổi trạng thái phát hành, cập nhật cả HTML dự phòng trong [index.html](index.html) để trang vẫn đúng khi tắt JavaScript.
- `.htaccess` cần Apache/LiteSpeed hỗ trợ rewrite. Máy chủ tĩnh thông thường chỉ xem được giao diện, không xử lý các chuyển hướng này.

## Manifest cập nhật

`update/latest.json` + `update/latest.json.sig` báo phiên bản mới cho ứng dụng. Sửa manifest thì phải ký lại (`scripts/release/sign-update-manifest.py`) và tải lên cả hai tệp; xem `docs/UPDATE_CHECK.md` ở gốc dự án.

## Tài sản giao diện

- Nhãn “MIỄN PHÍ VĨNH VIỄN”: nền `#0E7A36`, chữ và ngôi sao trắng; tương phản đạt AA.
- `assets/img/og-hst-office.jpg`: 1200×628, dưới 200 KB, xuất từ banner mới `assets/marketing/hst-office-banner-quangba-1200x628.png` ở gốc dự án HST Office.
- Khi thay CSS, JS hoặc ảnh đã cache, tăng tham số `?v=` ở các URL tham chiếu tương ứng. Máy chủ đặt cache dài hạn cho tài sản tĩnh.

Thư mục bàn giao không chứa `plans/`, `.verify/` hay script kiểm tra tạm.
