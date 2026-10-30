# Build matrix

| Artifact | Nơi build | Công cụ | Trạng thái |
|---|---|---|---|
| HST Office Linux x86_64 (`instdir`, `.deb`) | VPS dev (Ubuntu 24.04, 32 vCPU) | LibreOffice 26.8.1.1 gbuild + EPM, `scripts/build-linux.sh` | **Đang làm** — số đo ở `build/metrics/linux-build.json`, tóm tắt trong báo cáo Phase 01 |
| Extension `hst-vietnamese-tools.oxt` | VPS / GitHub `ubuntu-latest` | Python 3.12 zipfile | Đang làm |
| 18 mẫu `.ott/.ots/.otp` | VPS / GitHub `ubuntu-latest` | Python stdlib, ODF xác định | Đang làm |
| HST Office Linux trên GitHub-hosted runner | `ubuntu-latest` | như trên | **Dự kiến không đủ** ổ (~14 GB trống) — `desktop-linux.yml` thăm dò và fail rõ ràng (OPS-01) |
| Windows x64 `.msi` | `windows-2022` hosted (4 vCPU/16 GiB/ổ D: 220 GiB); configure đạt (preflight ~11 phút); biên dịch đầy đủ: xem báo cáo thử nghiệm | `scripts/build-windows.ps1` + `scripts/windows/trial-build.sh` | **TRIAL** (configure xác minh trên runner; build/MSI chưa xác minh; SIGN-01, QA-01 còn mở) |
| macOS arm64/x86_64 `.dmg` | Mac ≥100 GB, Xcode | `scripts/build-macos.sh` | **BLOCKED** (OPS-01, SIGN-01, MAC-01) |

## Ngân sách đĩa (Linux)

Ước lượng ban đầu (giới hạn để kiểm tra, không phải dự đoán): dependency 4 GB, source + tarball 7 GB, workdir ~20 GB, cài đặt/đóng gói 6 GB, ccache 4 GB, log 1 GB. `scripts/measure-job.py` cảnh báo ở 15 GiB trống, dừng job ở 12 GiB và không bao giờ cho phép xuống dưới 10 GiB.

## Lệnh

```bash
scripts/build-linux.sh --preflight        # kiểm tra tuỳ chọn configure theo configure.ac
scripts/apply-patches.sh --check          # patch HST áp sạch?
scripts/build-linux.sh --configure
python3 scripts/measure-job.py --json build/metrics/linux-build.json -- scripts/build-linux.sh --build
scripts/build-linux.sh --package          # .deb (EPM)
```

## Đóng gói `.deb` (Linux x86_64)

- `scripts/build-linux.sh --package` chạy `make`, từ chối kết quả `*_witherror`, rồi gộp 38 file `.deb` (bộ `HSTOffice` + `HSTOffice_languagepack` vi) thành **một** `HSTOffice_<version>_Linux_x86-64.deb` (gói `hst-office`, `scripts/linux/make-single-deb.py`) cùng `SHA256SUMS` trong `dist/linux/` (~192 MiB). Trình cài đồ họa (nhấn đúp) chỉ mở được một tệp.
- Phiên bản sản phẩm lấy từ [`VERSION`](../VERSION) (`1.0.0`; lõi LibreOffice vẫn 26.8.1.1). Tên gói `hst-office1.0*`, `hst-officebasis1.0-*` (phiên bản gói `1.0.0`); cài tại `/opt/hst-office1.0`; lệnh `/usr/bin/hst-office` và `/usr/bin/hst-office1.0`; tên tải `HSTOffice_1.0.0_*`; Maintainer `HASON TECH`. Không gói/tệp nào mang tên `libreoffice*`/`libobasis*` ngoài `/opt/hst-office1.0`, không `Conflicts/Replaces` với LibreOffice của distro.
- Cơ chế phiên bản: `scripts/build-linux.sh` xuất `HST_VERSION_MAJOR/MINOR/MICRO` (từ `scripts/write-hst-version.py`) vào môi trường `make`, ghi `include/hst_version.h` (chỉ khi đổi) và thay `@HST_VERSION_*@` trong `openoffice.lst` sau `config.status`; `sysui/productlist.mk` báo lỗi nếu thiếu biến. Đổi `VERSION` xong gbuild không tự theo dõi scp2/sysui: xoá `workdir/CustomTarget/sysui/deb/hst_office` và `workdir/CustomTarget/sysui/share/hst_office` rồi `--build`, `--package`. Windows/macOS gọi cùng `write-hst-version.py`.
- Extension `hst-vietnamese-tools` đi kèm trong gói lõi (`/opt/hst-office1.0/share/extensions/hst-vietnamese-tools`, đăng ký tự động cho mọi người dùng, không gỡ được trong Extension Manager): `dictionaries/ExtensionPackage_hst-vietnamese-tools.mk` dựng `.oxt` từ `extensions/` bằng `scripts/build-extensions.py` (không commit nhị phân) và `scp2` liệt kê trong module brand (`hst-version.patch`).
- Patch: `hst-packaging.patch` (openoffice.lst.in), `hst-packaging-sysui.patch` (sysui: product `hst_office`, launcher "HST Writer/Sheets/Slides", icon HST), `hst-packaging-installer.patch` (đường dẫn có dấu cách), `hst-packaging-vendor.patch` (Maintainer + phụ thuộc thư viện hệ thống Ubuntu 24.04), `hst-packaging-scp2.patch` (LibreLogo với Python hệ thống).
- Kiểm thử vòng đời trong container Ubuntu 24.04 sạch: `tests/runtime/check-deb-install.sh dist/linux/HSTOffice_<version>_Linux_x86-64.deb` (cài → chuyển đổi tài liệu bằng user thường → gỡ → purge → tài liệu/profile còn → cài lại). Cần mạng trong container để `apt` kéo thư viện phụ thuộc.
- Sau khi sửa `.scp`/`.mk` của scp2, xoá `workdir/ScpPreprocessTarget/.../*.pre` tương ứng (gbuild không theo dõi `InstallModule_*.mk`); sau khi sửa `sysui/desktop/share/create_tree.sh`, xoá `workdir/CustomTarget/sysui/deb/hst_office` để không còn tệp cũ trong cây gói.
