# Nút tải HST Office cho hasontech.vn

[`download-buttons.html`](download-buttons.html) là một khối HTML/CSS tự chứa (kèm một đoạn script nhỏ) để dán vào
trang tải trên hasontech.vn: ba thẻ Windows (.msi), macOS (.dmg Apple Silicon / Intel), Linux (.deb trong .tar.gz),
nhãn "Miễn phí vĩnh viễn", hướng dẫn kiểm tra SHA-256 và ghi chú SmartScreen/Gatekeeper cho bộ cài chưa ký.
CSS đều có tiền tố `.hst-dl`, không ảnh hưởng phần còn lại của trang. Liên kết GitHub chỉ dùng trên website,
không xuất hiện trong sản phẩm.

## Tên tệp

Theo [release.yml](../../.github/workflows/release.yml) và
[collect-release-assets.sh](../../scripts/release/collect-release-assets.sh), mỗi release có:

| Nền tảng | Tệp |
|---|---|
| Windows | `HSTOffice_<version>_Win_x86-64_en-US_vi.msi` |
| macOS Apple Silicon | `HSTOffice_<version>_macOS_arm64.dmg` |
| macOS Intel | `HSTOffice_<version>_macOS_x86_64.dmg` |
| Linux | `HSTOffice_<version>_Linux_x86-64_deb.tar.gz` |
| Mã kiểm tra | `SHA256SUMS` |

URL: `https://github.com/haduyson/hst-office/releases/download/<tag>/<tệp>`. `<version>` là nội dung tệp
[`VERSION`](../../VERSION) lúc build (ví dụ `1.0.0`); `<tag>` là tag nhập khi chạy release (ví dụ `v1.0.0`
hoặc `v1.0.0-beta.2`, tên tệp vẫn là `1.0.0`).

## Cập nhật cho mỗi bản phát hành

1. Mở trang release trên GitHub, xác nhận đủ 5 tệp ở bảng trên (nếu thiếu một nền tảng, ẩn thẻ tương ứng).
2. Trong `download-buttons.html` sửa `data-tag` và `data-version` ở thẻ `<div class="hst-dl" …>`.
3. Sửa luôn giá trị trong các `href` và chữ hiển thị (dùng khi trình duyệt tắt script hoặc CMS lọc `<script>`),
   ví dụ đổi từ 1.0.0 sang 1.0.1:
   `sed -i 's/v1\.0\.0/v1.0.1/g; s/1\.0\.0/1.0.1/g' docs/website/download-buttons.html`
   (với tag beta, sửa `data-tag` và phần `/download/<tag>/` bằng tay).
4. Mở tệp trong trình duyệt, bấm thử từng nút (phải tải được, không ra trang 404), rồi dán toàn bộ khối vào trang.
5. Nếu bộ cài Windows/macOS đã được ký số, bỏ đoạn ghi chú SmartScreen/Gatekeeper tương ứng.
