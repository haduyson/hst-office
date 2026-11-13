# HST Office landing page

Trang tĩnh HTML/CSS/JS, không cần bước build. `index.html` là trang chính;
`404.html` dùng chung CSS. Ảnh, font và JavaScript nằm trong `assets/`.

## Bản phát hành và liên kết tải

- Sửa trạng thái nền tảng, phiên bản và nhãn trong [config.js](config.js).
- Sửa đích chuyển hướng trong [.htaccess](.htaccess) (tệp trong `tai/<phiên bản>/`), giữ nguyên các URL `/tai/*`.
- Cả bốn link `/tai/windows`, `/tai/macos-arm`, `/tai/macos-intel`, `/tai/linux` và `/tai/sha256` đang được bật, phục vụ từ `tai/<phiên bản>/` trên site.
- Từ 1.0.2 thêm `/tai/linux-rpm` (Fedora/openSUSE, `.rpm`) và `/tai/linux-appimage` (mọi bản Linux, `.AppImage`): quy tắc trong `.htaccess` đã trỏ sẵn `tai/1.0.2/`, nút trên trang đang tắt (`available: false` trong `config.js`). Khi đăng 1.0.2: chép hai tệp (và `.AppImage.asc`, `HSTOffice_1.0.2_Linux_x86-64.SHA256SUMS{,.asc}`) vào `tai/1.0.2/`, đặt khóa công khai ký gói Linux ở `tai/RPM-GPG-KEY-hasontech` (cùng tệp `data/hst/RPM-GPG-KEY-hasontech` trong repo; hướng dẫn cài `.rpm` trên trang dùng URL này), bật hai mục trong `config.js`, đăng thêm `update/latest-3.json` + `.sig` (bản 1.0.2 đọc tệp này trước; xem `docs/UPDATE_INSTALL.md`).
- Khi đổi trạng thái phát hành, cập nhật cả HTML dự phòng trong [index.html](index.html) để trang vẫn đúng khi tắt JavaScript.
- `.htaccess` cần Apache/LiteSpeed hỗ trợ rewrite. Máy chủ tĩnh thông thường chỉ xem được giao diện, không xử lý các chuyển hướng này.

## Manifest cập nhật

`update/latest.json`, `update/latest-2.json` và (từ 1.0.2) `update/latest-3.json`, mỗi tệp kèm `.sig`, báo phiên bản mới cho ứng dụng. Sửa manifest thì phải ký lại (`scripts/release/sign-update-manifest.py`) và tải lên cả hai tệp; xem `docs/UPDATE_CHECK.md` ở gốc dự án.

## Tài sản giao diện

- Nhãn “MIỄN PHÍ VĨNH VIỄN”: nền `#0E7A36`, chữ và ngôi sao trắng; tương phản đạt AA.
- `assets/img/og-hst-office.jpg`: 1200×628, dưới 200 KB, xuất từ banner mới `assets/marketing/hst-office-banner-quangba-1200x628.png` ở gốc dự án HST Office.
- Khi thay CSS, JS hoặc ảnh đã cache, tăng tham số `?v=` ở các URL tham chiếu tương ứng. Máy chủ đặt cache dài hạn cho tài sản tĩnh.

Thư mục bàn giao không chứa `plans/`, `.verify/` hay script kiểm tra tạm.
