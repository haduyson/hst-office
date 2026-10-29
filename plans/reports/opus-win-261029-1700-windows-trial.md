# Thử nghiệm build Windows x64 trên GitHub-hosted runner (2026-10-29)

Trạng thái: lượt full 40897969466 biên dịch xong, hỏng ở đóng gói MSI (thiếu perl IO::String, đã sửa); lượt kế tiếp đang chạy.

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

## Lượt full (run 40897969466, 2026-10-29)
- Biên dịch xong toàn bộ trên runner chuẩn 4 vCPU/16 GB: 20.653 bước `[build ...]`, 1.109 module (11.865 CXX, 296 LNK). Pha build 9.299 s (~2 giờ 35 phút); cả lượt ~3 giờ. Đĩa D: thấp nhất 113 GiB trống; RAM đỉnh 16 GiB (chạm trần).
- Hỏng ở bước cuối `instsetoo_native` (đóng gói MSI `en-US,vi`): `Can't locate IO/String.pm` (Font::TTF cần IO::String; Cygwin thiếu gói `perl-IO-String`). Chưa có `.msi`.
- Sửa: thêm `perl-IO-String` vào danh sách gói Cygwin (`scripts/build-windows.ps1`); pha `--tools` nạp thử Archive::Zip, Font::TTF::Font, IO::String, Digest::MD5 nên thiếu module sẽ hỏng ngay đầu lượt.
- Lỗi header Skia các lượt trước đã hết sau khi bỏ thư mục đánh dấu `src/` ở gốc cây nguồn.

## Khuyến nghị
- Runner chuẩn miễn phí (repo public) đủ trong giới hạn 6 giờ: ~3 giờ/lượt, chưa cần runner lớn để ra MSI thử nghiệm.
- RAM chạm 16 GiB: nếu link hỏng do thiếu bộ nhớ thì giảm song song (`--with-parallelism=3`) hoặc dùng self-hosted ≥32 GB.
- Muốn nhanh hơn: self-hosted Windows ≥16 vCPU/32 GB, giữ `workdir` giữa các lượt (build tăng dần).
- Cần: ký MSI (SIGN-01), kiểm GUI/cài đặt (QA-01).
