# Build matrix

| Artifact | Nơi build | Công cụ | Trạng thái |
|---|---|---|---|
| HST Office Linux x86_64 (`instdir`, `.deb`) | VPS dev (Ubuntu 24.04, 32 vCPU) | LibreOffice 26.8.1.1 gbuild + EPM, `scripts/build-linux.sh` | **Đang làm** — số đo ở `build/metrics/linux-build.json`, tóm tắt trong báo cáo Phase 01 |
| Extension `hst-vietnamese-tools.oxt` | VPS / GitHub `ubuntu-latest` | Python 3.12 zipfile | Đang làm |
| Mẫu `.ott/.ots/.otp` | VPS / GitHub `ubuntu-latest` | Python stdlib, ODF xác định | Đang làm |
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

- `scripts/build-linux.sh --package` chạy `make`, từ chối kết quả `*_witherror`, rồi gộp 38 file `.deb` (bộ `HSTOffice` + `HSTOffice_languagepack` vi) thành **một** `HSTOffice_<release>_Linux_x86-64.deb` (gói `hst-office`, `scripts/linux/make-single-deb.py`) cùng `SHA256SUMS` trong `dist/linux/` (~192 MiB). Trình cài đồ họa (nhấn đúp) chỉ mở được một tệp.
- Phiên bản sản phẩm lấy từ [`VERSION`](../VERSION) (`1.0.0`; lõi LibreOffice vẫn 26.8.1.1). Tên gói `hst-office1.0*`, `hst-officebasis1.0-*` (phiên bản gói `1.0.0`); cài tại `/opt/hst-office1.0`; lệnh `/usr/bin/hst-office` và `/usr/bin/hst-office1.0`; tên tải `HSTOffice_<release>_*` (mã đầy đủ như `1.0.0-beta.4.1`); Maintainer `HASON TECH`. Không gói/tệp nào mang tên `libreoffice*`/`libobasis*` ngoài `/opt/hst-office1.0`, không `Conflicts/Replaces` với LibreOffice của distro.
- Cơ chế phiên bản: `scripts/build-linux.sh` xuất `HST_VERSION_MAJOR/MINOR/MICRO` (từ `scripts/write-hst-version.py`) vào môi trường `make`, ghi `include/hst_version.h` (chỉ khi đổi) và thay `@HST_VERSION_*@` trong `openoffice.lst` sau `config.status`; `sysui/productlist.mk` báo lỗi nếu thiếu biến. Đổi `VERSION` xong gbuild không tự theo dõi scp2/sysui: xoá `workdir/CustomTarget/sysui/deb/hst_office` và `workdir/CustomTarget/sysui/share/hst_office` rồi `--build`, `--package`. Windows/macOS gọi cùng `write-hst-version.py`.
- Extension `hst-vietnamese-tools` đi kèm trong gói lõi (`/opt/hst-office1.0/share/extensions/hst-vietnamese-tools`, đăng ký tự động cho mọi người dùng, không gỡ được trong Extension Manager): `dictionaries/ExtensionPackage_hst-vietnamese-tools.mk` dựng `.oxt` từ `extensions/` bằng `scripts/build-extensions.py` (không commit nhị phân) và `scp2` liệt kê trong module brand (`hst-version.patch`).
- Patch: `hst-packaging.patch` (openoffice.lst.in), `hst-packaging-sysui.patch` (sysui: product `hst_office`, launcher "HST Writer/Sheets/Slides", icon HST), `hst-packaging-installer.patch` (đường dẫn có dấu cách), `hst-packaging-vendor.patch` (Maintainer + phụ thuộc thư viện hệ thống Ubuntu 24.04), `hst-packaging-scp2.patch` (LibreLogo với Python hệ thống).
- Kiểm thử vòng đời trong container sạch (`IMAGE=` ubuntu:22.04, 24.04, 26.04, debian:13; `INSTALL_MODE=` apt, pkcon, upgrade): `tests/runtime/check-deb-install.sh dist/linux/HSTOffice_<release>_Linux_x86-64.deb` (cài → chuyển đổi tài liệu bằng user thường → gỡ → purge → tài liệu/profile còn → cài lại). Cần mạng trong container để `apt` kéo thư viện phụ thuộc.
- Sau khi sửa `.scp`/`.mk` của scp2, xoá `workdir/ScpPreprocessTarget/.../*.pre` tương ứng (gbuild không theo dõi `InstallModule_*.mk`); sau khi sửa `sysui/desktop/share/create_tree.sh`, xoá `workdir/CustomTarget/sysui/deb/hst_office` để không còn tệp cũ trong cây gói.

## Phiên bản hiển thị theo hệ điều hành

Nguồn: `VERSION` (`1.0.0`) + `data/hst/release.json` (mã đầy đủ, ví dụ `1.0.0-beta.4.1`). `scripts/write-hst-version.py`
suy ra số build đơn điệu cho trường số thứ tư: `beta.N[.M]` thành `N*100+M` (`beta.4` = 400, `beta.4.1` = 401),
`rc.N[.M]` thành `5000+N*100+M`, bản chính thức `10000`. Mã ngoài quy tắc này làm build dừng với thông báo rõ.

| | Tên tệp tải | Phiên bản hiển thị |
|---|---|---|
| Mọi OS | `HSTOffice_<release>_<nền tảng>` | About và `soffice --version`: `1.0.0-beta.4.1 (<arch>)` (macro `HST_RELEASE`, `hst-version.patch`) |
| Windows | `HSTOffice_1.0.0-beta.4.1_Win_x86-64_en-US_vi.msi` (workflow đổi tên tệp do installer đặt) | MSI `ProductVersion` `1.0.0.401` (`trial-build.sh` đặt `PACKAGEVERSION` bốn thành phần; Programs and Features hiện số này). `soffice.exe`/DLL: `FileVersion` `1.0.0.401`, `ProductVersion` `1.0.0-beta.4.1` (`hst-copyright.patch`, `include/default.rc`) |
| Linux | `HSTOffice_1.0.0-beta.4.1_Linux_x86-64.deb` | `Version: 1:1.0.0~beta.4.1-1`; AppStream `<release version="1.0.0-beta.4.1" type="development">` |
| macOS | `HSTOffice_1.0.0-beta.4.1_macOS_arm64.dmg`, `..._macOS_x86_64.dmg` | `CFBundleShortVersionString` `1.0.0`, `CFBundleVersion` `401` (Finder: "1.0.0 (401)"), `CFBundleGetInfoString` `HST Office 1.0.0-beta.4.1`; ghi vào `Info.plist` ở bước configure, trước khi ký |

Thứ tự phiên bản Debian: epoch `1:` và dấu `~` cho bản thử. Không có epoch thì `1.0.0~beta4.1-1` nhỏ hơn
`1.0.0-2` (gói beta.4 đã phát hành) và apt không bao giờ nâng cấp lên nó. Với epoch:
`1.0.0-2 < 1:1.0.0~beta.4.1-1 < 1:1.0.0~beta.5-1 < 1:1.0.0~rc.1-1 < 1:1.0.0-1 < 1:1.0.1-1`.
Epoch không thể bỏ đi nữa; bản chính thức phải là `1:1.0.0-1` (`scripts/linux/make-single-deb.py`, `deb_version`).

## Mã MSI trên Windows (UpgradeCode)

UpgradeCode của HST Office là **`{A1751BCB-2603-4428-A5DE-419B438ECFBC}`**. **Không bao giờ đổi mã này**: mọi bộ cài
HST về sau nhận ra và thay bản đang cài nhờ nó; đổi mã thì bản cũ không được gỡ và Programs and Features có hai mục.
Mã nằm trong `codes_hst.txt` do [`hst-msi-upgradecode.patch`](../patches/libreoffice/hst-msi-upgradecode.patch) thêm
(`CODEFILENAME` của sản phẩm HSTOffice). ProductCode thì installer tạo mới mỗi lần build, nên mỗi bản phát hành là
một major upgrade như upstream.

- Đến beta.4, MSI dùng UpgradeCode của LibreOffice (`{4B17E523-5D91-4E69-BD96-7FD81CFA81BB}`, ProductVersion
  `1.0.0.1`). Windows Installer vì vậy coi mọi LibreOffice đã cài là "HST Office mới hơn" và không cho cài; cài
  LibreOffice sau đó cũng gỡ mất HST Office.
- Từ beta.5, bảng Upgrade có thêm một dòng trên mã của LibreOffice chỉ để **gỡ** các bản beta cũ đó: phiên bản
  `1.0.0.0` (gồm) đến `1.0.1.0` (không gồm), thuộc tính 257, `OLDPRODUCTS`. Windows Installer chỉ so ba trường đầu
  của phiên bản, và LibreOffice cho Windows bắt đầu từ 3.3, nên dòng này không bao giờ khớp một bản LibreOffice.
  Dòng phát hiện bản mới hơn (`NEWPRODUCTS`) chỉ dùng mã của HST.
- Kiểm tra: `scripts/check-msi-upgrade.py` (Quality CI, đọc patch) và `scripts/check-msi-upgrade.py --msi <tệp>`
  (đọc bảng Upgrade và Property của MSI đã build; workflow Windows smoke chạy bước này và thử cài cạnh LibreOffice,
  nâng cấp từ beta.4).
