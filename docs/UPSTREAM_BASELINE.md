# Upstream baseline — LibreOffice

> Nguồn máy đọc: [`upstream/libreoffice-lock.json`](../upstream/libreoffice-lock.json). Baseline ONLYOFFICE cũ: [`upstream/onlyoffice-lock.json`](../upstream/onlyoffice-lock.json) (lịch sử).

| Mục | Giá trị |
|---|---|
| Phiên bản | LibreOffice **26.8.3.1** (nhánh fresh 26.8) |
| Git | tag `libreoffice-26.8.3.1`, commit `861effc5289d539f15c4c18d1ba8579ffd78728b` |
| Tarball | `libreoffice-26.8.3.1.tar.xz` SHA-256 `83006a81…de28`… (đầy đủ trong lock), kèm `translations`, `dictionaries` và `help` |
| Chữ ký | GPG "Good signature", khóa `C2839ECAD9408FBE9531C3E9F434A1EFAFEEAEA3` |
| Thư mục | `upstream/libreoffice/` (gitignored, sở hữu bởi user build `hstbuild`) |
| Phương án so sánh | 26.2.6.3 (`8221e31b…`) — không chọn vì hết hỗ trợ 2026-11-30 |

## Cấu hình build

[`build-config/linux-x86_64.conf`](../build-config/linux-x86_64.conf); mọi tuỳ chọn được `scripts/build-linux.sh --preflight` đối chiếu với `configure.ac` tại commit pin (dạng `AC_ARG_*` hoặc `libo_FUZZ_ARG_*`).

## Ghi chú môi trường (2026-10-29)

- Ubuntu 24.04.4, 32 vCPU, 47 GiB RAM (~19 GiB khả dụng), ổ còn ~47 GB khi bắt đầu build.
- `apt-get build-dep libreoffice` cần bật `deb-src` trong `/etc/apt/sources.list.d/ubuntu.sources` (bản gốc được backup ở `build/ubuntu.sources.bak`).
- Build chạy bằng user hệ thống `hstbuild`, không chạy bằng root.

## Cập nhật baseline

1. Tải tarball bản mới + `.asc`, kiểm SHA-256 công bố và chữ ký bằng khóa ghim, cập nhật lock. Chạy `python3 scripts/check-source-lock.py --tarballs <thư-mục-tarball> --remote`.
2. Áp lại `patches/libreoffice/series`; sửa patch xung đột. Kiểm thêm mọi patch `external/*/...patch*` mà series tạo hoặc sửa: lấy tarball theo `download.lst`, xác minh SHA-256 rồi dry-run và áp từng patch với `--fuzz=0` theo thứ tự trong `UnpackedTarball_*.mk`, kể cả patch upstream đứng trước. Kiểm series trên cây LibreOffice chưa kiểm được lớp patch tarball này.
3. Build lại, chạy toàn bộ QA runtime và đo độ trễ menu.

Chạy `scripts/apply-patches.sh --check` trên cây sạch trước overlay tiếng Việt.
Phép nhận diện patch đã áp chưa hỗ trợ đầy đủ cây sau overlay: các `msgstr` rỗng
trong patch ribbon được điền bản dịch, làm kiểm tra vá ngược không khớp. Khi nâng
lõi, kiểm tra và áp series từ nguồn pristine rồi mới chạy overlay và kiểm UI.

## Đường lấy nguồn theo nền tảng

- Linux VM103: hàng đợi gọi `scripts/linux/local-build.sh`; tarball được xác minh theo lock của SHA đã gửi. Hash lock đổi làm cache pristine được giải nén lại bằng `scripts/linux/ci-build.sh`.
- Windows HST4: `scripts/windows/hst4-build.ps1` tải theo lock của checkout; `hst4-tree.sh` dùng hash tarball và script `trial-build.sh` làm khóa cache.
- macOS: `desktop-macos.yml` tải qua `scripts/windows/fetch-sources.py` theo lock của nhánh, rồi `scripts/macos/trial-build.sh` giải nén trên cả arm64 và x86_64.
- Khi nâng lõi, cập nhật cả lock và tên tarball trong các script giải nén; kiểm tra lock đối chiếu các điểm ghim này. Các phiên bản trong hồ sơ kiểm thử/lịch sử phát hành được giữ theo nguồn đã đo.
