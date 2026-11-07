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

### Bản nháp nguồn cập nhật 1.0.1 (xóa sau khi phát hành)

`update/1.0.1-draft/latest-2.json` và `latest.json` là đầu ra của `scripts/release/generate-update-manifest.py` cho 1.0.1, chỉ để duyệt: Windows là nền tảng bình thường (có `installers.windows`, `downloads.windows` = `/tai/windows`), ghi chú trỏ `/diem-moi/#v1.0.1`. Mã SHA256 và kích thước là chỗ trống nên trình kiểm tra manifest từ chối bản nháp; `.htaccess` không phục vụ thư mục `*-draft`. Kênh beta giữ mục beta 5 như hiện tại: bản beta nhận bản mới nhất của hai kênh, tức là 1.0.1.

Lúc phát hành không sửa tay bản nháp: chạy lại script trên đúng các tệp đã tải từ bản phát hành nháp (ghi đè `update/latest*.json` đang chạy), ký cả hai tệp, đối chiếu với bản nháp rồi xóa thư mục nháp:

```bash
python3 scripts/release/generate-update-manifest.py --tag v1.0.1 --date 2026-11-10 \
  --notes "https://office.hasontech.vn/diem-moi/#v1.0.1" \
  --assets-dir <thư-mục-tải> --sums <thư-mục-tải>/SHA256SUMS
python3 scripts/release/sign-update-manifest.py website/office.hasontech.vn/update/latest-2.json
python3 scripts/release/sign-update-manifest.py website/office.hasontech.vn/update/latest.json
u=website/office.hasontech.vn/update; for f in latest-2.json latest.json; do
  diff <(sed -E 's/"sha256": "[^"]*"/"sha256": "-"/; s/"size": [0-9]+/"size": 0/' "$u/1.0.1-draft/$f") \
       <(sed -E 's/"sha256": "[^"]*"/"sha256": "-"/; s/"size": [0-9]+/"size": 0/' "$u/$f"); done
git rm -r website/office.hasontech.vn/update/1.0.1-draft
```

## Tài sản giao diện

- Nhãn “MIỄN PHÍ VĨNH VIỄN”: nền `#0E7A36`, chữ và ngôi sao trắng; tương phản đạt AA.
- `assets/img/og-hst-office.jpg`: 1200×628, dưới 200 KB, xuất từ banner mới `assets/marketing/hst-office-banner-quangba-1200x628.png` ở gốc dự án HST Office.
- Khi thay CSS, JS hoặc ảnh đã cache, tăng tham số `?v=` ở các URL tham chiếu tương ứng. Máy chủ đặt cache dài hạn cho tài sản tĩnh.

Thư mục bàn giao không chứa `plans/`, `.verify/` hay script kiểm tra tạm.
