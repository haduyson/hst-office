# Upstream baseline — LibreOffice

> Nguồn máy đọc: [`upstream/libreoffice-lock.json`](../upstream/libreoffice-lock.json). Baseline ONLYOFFICE cũ: [`upstream/onlyoffice-lock.json`](../upstream/onlyoffice-lock.json) (lịch sử).

| Mục | Giá trị |
|---|---|
| Phiên bản | LibreOffice **26.8.1.1** (nhánh fresh 26.8) |
| Git | tag `libreoffice-26.8.1.1`, commit `bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1` |
| Tarball | `libreoffice-26.8.1.1.tar.xz` SHA-256 `296ba78e…bfc`… (đầy đủ trong lock), kèm `translations` và `dictionaries` |
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

1. Tải tarball bản mới + `.asc`, kiểm chữ ký, cập nhật lock.
2. Áp lại `patches/libreoffice/series`; sửa patch xung đột.
3. Build lại, chạy toàn bộ QA runtime và đo độ trễ menu.
