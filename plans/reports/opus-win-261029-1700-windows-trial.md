# Thử nghiệm build Windows x64 trên GitHub-hosted runner (2026-10-29)

Trạng thái: configure đã chạy xong trên runner; lượt full-build đang chạy lúc viết (mục "Lượt full" sẽ được cập nhật khi có số đo).

## Runner đo được (windows-2022, image win22 20261026.347.1)
- CPU: AMD EPYC 9V45, 4 vCPU logic; RAM 16 GiB (còn trống ~13.6).
- Đĩa: C: 78 GiB trống (đã dùng 177); D: 220 GiB trống. Xóa Android SDK/Julia/Strawberry/ghcup/Rust/Temurin cache => C: 108 GiB. Build ở `D:\hst` (đường dẫn ngắn).
- VS 2022 Enterprise 17.14 (MSVC 14.44), Windows SDK 10.0.26100; có sẵn NASM qua choco 3.02, Cygwin cài mới (make 4.4.1, autoconf 2.73, perl 5...).

## Thời gian từng pha (lượt preflight xanh, run 40866921981, tổng ~11 phút)
| Pha | Giây |
|---|---|
| Probe + giải phóng đĩa | ~210 |
| Cygwin + make native + NASM + pkgconf | 95 (lần cài sau); lần đầu ~5 phút gồm tải gói |
| Tải 3 tarball + sha256 (600 MB) | 13-30 |
| Giải nén (src+translations+dictionaries) | 236 |
| Vá HST (9 patch) | 1 |
| Configure (`autogen.sh`) | 60 |
Đĩa trống sau giải nén: 143 GiB trên D:.

## Sự cố và cách sửa (9 lượt chạy đến lượt full)
1. Git Bash làm hỏng đường dẫn `/cygdrive/...` (đối số và biến môi trường): bỏ biến `HST_WORK`, dùng `MSYS2_ARG_CONV_EXCL=*`, gọi `C:/cygwin64/bin/bash.exe --login -c` và tự `cygpath` bên trong Cygwin.
2. `-Work D:\hst` mất dấu `\` khi không quote: quote tham số.
3. Checkout CRLF (`set: pipefail\r`): `core.autocrlf=false` trước checkout, `.gitattributes` eol=lf, bash `-o igncr`.
4. Giải nén thất bại không có thông báo: ba tarball (src, translations, dictionaries) cùng giải vào gốc `libreoffice-26.8.1.1/`, không phải vào thư mục con. Phát hiện bằng mô phỏng cục bộ sau khi thêm `preflight-local.sh`.
5. Configure: thiếu `pkgconf-2.4.3.exe` (dạng Windows): dùng pkgconfiglite đổi tên; thiếu perl `Font::TTF` (gói `perl-Font-TTF`); Cygwin `ccache` làm hỏng lệnh `cl.exe` (`odbc not found`): bỏ ccache, thêm `--disable-ccache`.
6. Make native `make-4.2.1-msvc.exe` cần đặt đầu PATH (trước `/usr/bin/make`); configure xác nhận dùng `D:/hst/bin/make.exe 4.2.1`.
Quy trình chặn lỗi lặp: `scripts/windows/preflight-local.sh` (shellcheck, actionlint pin sha256, CRLF, tùy chọn configure, mô phỏng giải nén/vá trên Linux) và `mode=preflight|full`.

## Lượt full (run 40868444852)
CẦN CẬP NHẬT: kết quả biên dịch (số bước `[build ...]`, module cuối, đĩa thấp nhất, RAM đỉnh, có MSI hay không) nằm trong artifact `windows-trial-<run_id>` (`metrics.json`, `build-tail.log`, `progress.jsonl`).

## Khuyến nghị (dự kiến, chưa kèm số đo build)
- Runner chuẩn 4 vCPU thường không đủ trong 6 giờ cho build LibreOffice đầy đủ trên Windows (cộng thêm tải ~100 tarball ngoài và đóng gói MSI); xác nhận bằng tiến độ ở lượt full.
- Hướng khả thi: runner lớn (Windows 16-32 vCPU, trả phí) hoặc self-hosted; build dài cần ccache tương thích MSVC (sccache) hoặc cache `workdir` giữa các lượt vì artifact/cache GitHub bị giới hạn.
- Cần: ký MSI (SIGN-01), kiểm GUI/cài đặt (QA-01).
