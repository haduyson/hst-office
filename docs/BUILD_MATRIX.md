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

## Hàng đợi build cục bộ (agent tự dùng)

Agent tự build `.deb` (máy dev) hoặc `.msi` (HST4/HST5) qua hàng đợi
[`scripts/build-queue.sh`](../scripts/build-queue.sh), không cần qua S0. Bản phát hành chính thức vẫn lấy từ CI.

```bash
scripts/build-queue.sh submit --platform linux   --ref rc/1.0.2-batch4             # in ra mã job
scripts/build-queue.sh submit --platform windows --ref feat/x --priority 10        # Windows là nền tảng ưu tiên
scripts/build-queue.sh submit --platform linux   --ref feat/x --modules sc,sw      # bản vá nhanh, CHỈ ĐỂ THỬ
scripts/build-queue.sh submit --platform linux   --ref feat/x --no-package         # chỉ make, không .deb
scripts/build-queue.sh wait   <id>          # chờ; in đường dẫn .deb/.msi/overlay (thoát 0) hoặc đuôi log (thoát 1)
scripts/build-queue.sh status <id>          # trạng thái, slot/máy, đầu ra, log
scripts/build-queue.sh list [--all]         # job đang chờ/chạy + 10 job xong gần nhất
scripts/build-queue.sh cancel <id>          # job chờ bị bỏ ngay; job đang chạy được dispatcher dừng
```

- `--ref` là nhánh, tag hoặc sha (lấy từ `origin`, `origin/<ref>` thắng nhánh local); commit được ghim ngay lúc
  submit. Job cùng nền tảng + commit + tuỳ chọn mà đang chờ/chạy hoặc đã xong và còn đầu ra thì `submit` trả lại mã
  job cũ (dedupe), `wait` trả kết quả ngay. Thứ tự: `--priority` (-100…100, cao trước), rồi đến trước làm trước;
  job ưu tiên cao đang chờ thì job thấp hơn cùng nền tảng không được chen.
- Dữ liệu dưới `/data/hst-build-queue/`: `jobs/<id>.json`, `logs/<id>.log`, `out/<id>/` (`.deb`/`.msi`/overlay +
  `SHA256SUMS`), `config.json` (ghi đè mặc định trong `build-queue.py`: số đầu ra giữ lại, danh sách slot Windows).
  Giữ `retention_per_branch` (3) đầu ra mới nhất cho mỗi nền tảng + nhánh; đầu ra cũ hơn bị xoá (job vẫn còn,
  đánh dấu `output_deleted`). Job Windows ghi máy đã build (`host`, `slot`).
- Dispatcher là dịch vụ systemd `hst-build-queue` ([unit](../scripts/linux/hst-build-queue.service), `Restart=on-failure`,
  `Nice=10`, I/O idle; `journalctl -u hst-build-queue`), chạy từ bản triển khai `/data/hst-build/infra-current`
  (symlink tới `infra-<sha>`, không bao giờ từ worktree đang sửa). Cập nhật bằng
  [`build-infra-deploy.sh <commit>`](../scripts/linux/build-infra-deploy.sh): tạo `infra-<sha>` mới, đổi symlink bằng
  một lần rename (nguyên tử), khởi động lại dispatcher; job đang chạy giữ phiên bản lúc nó bắt đầu, phiên bản cũ bị
  xoá khi không còn tiến trình nào dùng. Công cụ Windows chỉ được chép sang máy khi máy đó không có build nào chạy.
  Job hỏng vì hạ tầng (script đổi giữa chừng, slot bận, mount, mạng/SSH/SSL, task Windows biến mất…) được tự đưa lại
  vào hàng đợi, tối đa 2 lần (`infra_retries` trong job); lỗi build thật (lỗi make) thì không. Job Linux chạy `local-build.sh --slot N` trên slot rảnh mà bộ
  điều phối cho vào; job Windows chạy trên các slot trong `windows_slots` (HST4, HST5): dispatcher tự chép công cụ
  (`D:\hst-build\tools\scripts`) khi chúng đổi, chạy build thành scheduled task qua
  [`hst-queue-remote.ps1`](../scripts/windows/hst-queue-remote.ps1), kéo MSI về `out/<id>/` rồi xoá bản trên máy
  Windows. Slot có `build.lock` do người khác giữ (ví dụ một lượt `hst4-build.ps1` chạy tay) bị bỏ qua tới khi rảnh.

### `--modules`: bản vá nhanh để thử (không dùng cho batch)

`--modules sc,sw` chỉ chạy `make udkapi.build offapi.build oovbaapi.build` rồi `make sc.build sw.build` (tên có `.`
hoặc `_` được dùng nguyên là target make, ví dụ `Library_merged` khi sửa vcl/sfx2/svx) trên một slot đã từng build
đủ, và cho ra **overlay**: các tệp trong `instdir` mà lượt make đó ghi lại (thư viện, `uiconfig`, registry…), cùng
`FILES`, `SHA256SUMS`, `README.txt` và script áp:

- Linux: `HSTOffice-overlay-<nhánh>-<sha>-<module>.tar.gz`;
  `dpkg-deb -x HSTOffice_<release>_Linux_x86-64.deb ref/ && ./apply-build-overlay.sh ref/`
  ([script](../scripts/overlay/apply-build-overlay.sh), tìm `program/soffice.bin` rồi chép đè).
- Windows: `HSTOffice-overlay-<sha>-<module>.zip`; `msiexec /a <MSI tham chiếu> /qn TARGETDIR=C:\hst-test\ref` rồi
  `powershell -File apply-build-overlay.ps1 -Image C:\hst-test\ref` ([script](../scripts/overlay/apply-build-overlay.ps1)).

Overlay **chỉ để thử**: nó chỉ chứa module đã chọn, cây của slot có thể mang thay đổi của commit khác ở module
không build lại, và `.mo`/registry dịch không được dựng lại (khoảng hở ở
[SHARED_BUILD_SLOTS.md](SHARED_BUILD_SLOTS.md#incremental-build-gaps)). Bản giao cho batch, QA hay người dùng luôn
phải là bản build đủ (`.deb`/`.msi`).

## Build cục bộ giống CI (Linux `.deb`): slot song song

[`scripts/linux/local-build.sh`](../scripts/linux/local-build.sh) (hàng đợi gọi script này) build `.deb` bằng đúng các
pha của `desktop-linux.yml` (`ci-build.sh` của chính nhánh được build: `--deps`, `--extract`, `--patch`,
`--configure`, `--fetch`, `--package`), tăng dần, trong một trong các **slot** song song dưới `/data/hst-build`:

```bash
sudo scripts/linux/local-build.sh rc/1.0.2-batch4                 # slot rảnh đầu tiên mà bộ điều phối cho vào
sudo scripts/linux/local-build.sh --slot 2 -j 8 /home/wt-my-fix   # worktree, kể cả thay đổi chưa commit ("-dirty")
sudo scripts/linux/local-build.sh --slot 3 --modules sc feat/x    # overlay thử (xem trên)
sudo scripts/linux/local-build.sh --umount --slot 2               # gỡ mount sau một lượt bị giết
python3 scripts/linux/build-slots.py status                       # slot đang chạy, -j, ngân sách, RAM/đĩa
```

- Bố trí: `chroot/` (root file system của image container CI, cùng digest, clang theo `HST_CLANG`, thêm ccache; dùng
  chung, chỉ đọc: mỗi slot gắn overlayfs `slots/<N>/root` = `chroot/` + `chroot-upper/`), `ccache/` (dùng chung, tối
  đa 30 GB), `external-tarballs/`, `out/<nhánh>-<sha>/` (lượt chạy tay), `locks/`, `slots/<N>/` (`checkout/`, `src/`
  = `HST_WORK` với `lo/`, `dl/`, `pristine.git`; `logs/<giờ>-<nhãn>/`: `wrapper.log`, `build.log`, `timings.tsv`,
  `memory.tsv`). Trong chroot của mọi slot, cây được gắn ở **cùng đường dẫn** `/data/hst-office-build/{src,checkout,
  ccache,logs}`: cây LibreOffice không di chuyển được, nên cây sao chép sang slot khác vẫn hợp lệ (không build lại) và
  ccache trúng giữa các slot. Đường `/data/hst-office-build` trên máy chủ chỉ còn `src` → slot 1 (cho các script
  kiểm cú pháp đọc header) và một tệp `ccache` để `local-build.sh` cũ (một cây) dừng ngay thay vì dựng cây mới.
- Tạo slot: [`build-slots-setup.sh`](../scripts/linux/build-slots-setup.sh) `migrate` (cây cũ thành slot 1, chỉ di
  chuyển), `clone N` (chép cây ấm của slot 1; tarball, `pristine.git` là hard link), `plan` (còn chứa được mấy slot:
  mỗi slot thêm ~13 GB; luôn chừa 15 GB trống + phần ccache còn lớn được + 5 GB đầu ra).
- Đồng bộ patch: mỗi lượt đưa các tệp mà series đã sửa/thêm về trạng thái tarball gốc (`pristine.git`, nằm ngoài cây để
  LibreOffice không coi là git build), áp lại như CI, rồi trả mtime cũ cho tệp không đổi nội dung, nên đổi nhánh luôn
  sạch mà `make` chỉ build lại phần đổi. Configure chỉ chạy lại khi tệp mà `Makefile.in` theo dõi, `autogen.input` hoặc
  phiên bản HST đổi (`--reconfigure` để ép). `.po` đổi thì xoá `.mo`/`registry_<lang>.xcd` tương ứng (khoảng hở ở
  [SHARED_BUILD_SLOTS.md](SHARED_BUILD_SLOTS.md#incremental-build-gaps)). `--fresh` giải nén lại (build lại toàn bộ).
  Khi `do_deps` của nhánh hoặc image đổi, `chroot/` được cập nhật một lần, sau khi mọi slot khác dừng (khoá
  `locks/chroot.lock`: slot giữ khoá chia sẻ, cập nhật giữ khoá độc quyền).
- **Bộ điều phối** ([`build-slots.py`](../scripts/linux/build-slots.py), trạng thái `locks/slots.json` dưới flock): slot
  chỉ bắt đầu `make` khi tổng job ≤ 28 và `MemAvailable` trừ phần ngân sách đã giữ mà chưa dùng ≥ ngân sách slot + 8 GB,
  và `/data` còn ≥ 17 GB. `-j` chia theo kiểu rót nước: một slot một mình được tối đa 20 (`-j`/`--jobs` là trần), nhiều
  slot thì chia đều 28 (tối thiểu 4); khi slot khác vào/ra, `make` được khởi động lại với `-j` mới (giảm ngay, tăng khi
  thêm ≥ 6). Ngân sách = `clamp(4 + 0,4 × jobs, 6, 12)` GB là `MemoryMax` của scope systemd (`MemoryHigh` 90 %,
  `MemorySwapMax=0`, `CPUQuota` = jobs × 100 %), `nice 19`, `ionice -c3`. Hàng đợi cho job `--modules` trần 6 job
  (ngân sách 6,4 GB) để ba job nhỏ chạy cạnh nhau. Xong `make`, slot trả ngân sách ngay (đóng gói `.deb`/overlay nhẹ).
- Bảo vệ: chung cho cả máy, `MemAvailable` < 6 GB hoặc swap tăng > 1 GB (so với lần nhận/thả gần nhất) thì chỉ slot
  vào **sau cùng** bị đóng băng (`cgroup.freeze`), áp lực còn thì slot kế tiếp; trong mỗi slot giữ cơ chế cũ: rã đông ở
  8 GB, lần dừng thứ hai hoặc do swap thì chạy lại `make` với nửa số job (tối thiểu 2), quá 30 phút thì dừng; scope bị
  giết vì chạm `MemoryMax` thì thử lại với nửa số job; mỗi slot chỉ một lần link nặng (≥ 1 GB) cùng lúc; đĩa dưới 5 GB
  thì dừng.
- Khác CI nhưng không đổi thứ được biên dịch: chroot thay cho docker, ccache, `-j` do bộ điều phối quyết. Không chạy
  `check-coexistence.sh`. Cần root (chroot, mount).

## Đóng gói `.deb` (Linux x86_64)

- `scripts/build-linux.sh --package` chạy `make`, từ chối kết quả `*_witherror`, rồi gộp 38 file `.deb` (bộ `HSTOffice` + `HSTOffice_languagepack` vi) thành **một** `HSTOffice_<release>_Linux_x86-64.deb` (gói `hst-office`, `scripts/linux/make-single-deb.py`) cùng `SHA256SUMS` trong `dist/linux/` (~192 MiB). Trình cài đồ họa (nhấn đúp) chỉ mở được một tệp.
- Phiên bản sản phẩm lấy từ [`VERSION`](../VERSION) (`1.0.0`; lõi LibreOffice vẫn 26.8.1.1). Tên gói `hst-office1.0*`, `hst-officebasis1.0-*` (phiên bản gói `1.0.0`); cài tại `/opt/hst-office1.0`; lệnh `/usr/bin/hst-office` và `/usr/bin/hst-office1.0`; tên tải `HSTOffice_<release>_*` (mã đầy đủ như `1.0.0-beta.4.1`); Maintainer `HASON TECH`. Không gói/tệp nào mang tên `libreoffice*`/`libobasis*` ngoài `/opt/hst-office1.0`, không `Conflicts/Replaces` với LibreOffice của distro.
- Cơ chế phiên bản: `scripts/build-linux.sh` xuất `HST_VERSION_MAJOR/MINOR/MICRO` (từ `scripts/write-hst-version.py`) vào môi trường `make`, ghi `include/hst_version.h` (chỉ khi đổi) và thay `@HST_VERSION_*@` trong `openoffice.lst` sau `config.status`; `sysui/productlist.mk` báo lỗi nếu thiếu biến. Đổi `VERSION` xong gbuild không tự theo dõi scp2/sysui: xoá `workdir/CustomTarget/sysui/deb/hst_office` và `workdir/CustomTarget/sysui/share/hst_office` rồi `--build`, `--package`. Windows/macOS gọi cùng `write-hst-version.py`.
- Extension `hst-vietnamese-tools` đi kèm trong gói lõi (`/opt/hst-office1.0/share/extensions/hst-vietnamese-tools`, đăng ký tự động cho mọi người dùng, không gỡ được trong Extension Manager): `dictionaries/ExtensionPackage_hst-vietnamese-tools.mk` dựng `.oxt` từ `extensions/` bằng `scripts/build-extensions.py` (không commit nhị phân) và `scp2` liệt kê trong module brand (`hst-version.patch`).
- Patch: `hst-packaging.patch` (openoffice.lst.in), `hst-packaging-sysui.patch` (sysui: product `hst_office`, launcher "HST Writer/Sheets/Slides", icon HST), `hst-packaging-installer.patch` (đường dẫn có dấu cách), `hst-packaging-vendor.patch` (Maintainer + phụ thuộc thư viện hệ thống Ubuntu 24.04), `hst-packaging-scp2.patch` (LibreLogo với Python hệ thống).
- Kiểm thử vòng đời trong container sạch (`IMAGE=` ubuntu:22.04, 24.04, 26.04, debian:13; `INSTALL_MODE=` apt, pkcon, upgrade): `tests/runtime/check-deb-install.sh dist/linux/HSTOffice_<release>_Linux_x86-64.deb` (cài → chuyển đổi tài liệu bằng user thường → gỡ → purge → tài liệu/profile còn → cài lại). Cần mạng trong container để `apt` kéo thư viện phụ thuộc.
- Cài và chạy song song với LibreOffice (của distro, của TDF, Flatpak): launcher, biểu tượng ứng dụng, `WM_CLASS` và app_id Wayland đều là `vn.hasontech.hstoffice-<module>` (`DESKTOPID.hst_office` trong `sysui/productlist.mk`, `hst-linux-desktop-ids.patch`). `update-desktop-database` xếp ứng dụng xử lý mỗi loại tệp theo id; khi người dùng chưa chọn mặc định, GLib và `xdg-mime` mở bằng ứng dụng đầu tiên, nên id này (xếp sau mọi `libreoffice*`) không giành mặc định của LibreOffice; HST vẫn có trong "Mở bằng". Lần chạy đầu không tìm/chép profile của LibreOffice/OpenOffice cũ (`hst-no-other-suite-profile-migration.patch`). `scripts/linux/check-desktop-entries.py` kiểm `StartupWMClass` = id launcher khi đóng gói; `scripts/linux/check-coexistence.sh <deb>` cài `libreoffice-writer/calc/impress` của Ubuntu 24.04 rồi gói HST trong container, kiểm không trùng tệp, mặc định không đổi, chạy cùng lúc dưới Xvfb (tiến trình, cửa sổ, `WM_CLASS` riêng), không đọc `~/.config/libreoffice`, gỡ bên nào bên kia vẫn chạy (cũng chạy trong `desktop-linux.yml` sau bước đóng gói).
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
- **Beta 1–4 phải được gỡ trước khi cài beta.5** (quyết định của chủ dự án). Beta 1–4 đóng dấu các tệp .exe/.dll của
  HST là 26.8.1.1, cao hơn `1.0.0.500` của beta.5; MSI ghi đúng phiên bản thật. Cài đè lên beta 1–4 thì Windows Installer
  bỏ qua các component có tệp khóa (key file) trên máy mang phiên bản cao hơn, bất kể GUID, rồi `RemoveExistingProducts`
  xóa bản của beta.4: khoảng 170 tệp (gồm `soffice.bin`, `soffice.com`) bị thiếu. Bộ cài không chặn việc này; ghi chú
  phát hành hướng dẫn gỡ bản cũ trước, và bản Windows không có trong nguồn cập nhật. Windows smoke có kịch bản
  `uninstall-beta4-then-install` (bắt buộc đạt) và `upgrade-from-beta4` (chỉ để ghi nhận, liệt kê mọi tệp bị thiếu).
  [`hst-msi-component-guids.patch`](../patches/libreoffice/hst-msi-component-guids.patch) (GUID component mới, hạt
  `COMPONENTGUIDSEED`) vẫn giữ nhưng không thay đổi điều này.
- ProgID riêng và đường dẫn UNO riêng ([`hst-windows-own-progids.patch`](../patches/libreoffice/hst-windows-own-progids.patch)):
  ProgID loại tệp là `HSTOffice.*` (ví dụ `HSTOffice.WriterDocument.1`, `HSTOffice.Docx`), đường dẫn cài cho UNO ở
  `HKLM\Software\HASON TECH\HST Office\UNO\InstallPath`. Custom action `LookForRegisteredExtensions` chỉ nhận định dạng
  Office chưa ai giữ, của WordPad hoặc của chính HST, không lấy của LibreOffice. Giữ nguyên: AppUserModelID, CLSID OLE
  và tên kiểu lưu trữ OLE ghi vào tài liệu. Mặc định `.odt`/`.ods`/`.odp` vẫn là của bộ cài sau cùng, và gỡ một bộ sẽ xóa
  giá trị mặc định đó (ProgID và lệnh mở của bộ còn lại không bị ảnh hưởng).
- Tên khác cũng tách khỏi LibreOffice (đều là patch nối cuối series, kiểm tra bằng
  [`test_windows_coexist_registry.py`](../tests/unit/test_windows_coexist_registry.py) và
  [`smoke-coexist-registry.ps1`](../scripts/windows/smoke-coexist-registry.ps1) trong windows-smoke):
  - ProgID định dạng cũ StarOffice 6/OpenOffice.org 1 là `HSTOffice.Star*` thay cho `soffice.Star*`
    ([`hst-windows-own-legacy-progids.patch`](../patches/libreoffice/hst-windows-own-legacy-progids.patch)).
  - Không ghi `App Paths\soffice.exe`, `swriter.exe`, `scalc.exe`, `simpress.exe`, `sdraw.exe`, `smath.exe`,
    `sbase.exe`, `unopkg.exe` (cùng tên chương trình với LibreOffice; không đổi tên tệp .exe)
    ([`hst-windows-no-app-paths.patch`](../patches/libreoffice/hst-windows-no-app-paths.patch)).
  - Không đăng ký URI scheme `vnd.libreoffice.command` với Windows; dòng lệnh của office vẫn hiểu nó. Các scheme
    `ms-word`/`ms-excel`/… trong Capabilities trỏ tới ProgID `HSTOffice.OfficeURI` (không phải scheme)
    ([`hst-windows-no-libreoffice-uri-scheme.patch`](../patches/libreoffice/hst-windows-no-libreoffice-uri-scheme.patch)).
  - Phần mở rộng Explorer (infotip, cột, trang thuộc tính, ảnh thu nhỏ, property handler, IFilter và persistent
    handler) có CLSID riêng, trong mã và trong scp2; infotip và ảnh thu nhỏ gắn vào ProgID `HSTOffice.*` thay vì khóa
    `.odt`/`.ods`/… dùng chung. Persistent handler và property handler Windows chỉ đọc theo phần mở rộng, nên vẫn là
    của bộ cài sau cùng (như mặc định `.odt`)
    ([`hst-windows-own-shell-extension-clsids.patch`](../patches/libreoffice/hst-windows-own-shell-extension-clsids.patch)).
    **CLSID của server nhúng OLE giữ nguyên**: tài liệu lưu CLSID đó, đổi sẽ làm đối tượng nhúng trong tài liệu cũ
    (và tài liệu tạo bằng ứng dụng khác) không mở được.
  - Khóa `Software\LibreOffice\…` (Layers, URE, Path) chuyển sang `Software\HASON TECH\…`; khóa gỡ cài đặt cũ ghi
    nhà phát hành HASON TECH ([`hst-windows-own-registry-keys.patch`](../patches/libreoffice/hst-windows-own-registry-keys.patch)).
    Custom action `MigrateInstallPath` vẫn đọc khóa Layers cũ để giữ thư mục cài của beta 1–4.
  - ProgID của gói phần mở rộng `.oxt` là `HSTOffice.Extension.1` thay cho `office.Extension.1`
    ([`hst-windows-own-extension-progid.patch`](../patches/libreoffice/hst-windows-own-extension-progid.patch)).
  - Giữ nguyên có chủ đích (tên API tự động hóa mà script bên ngoài gọi): `com.sun.star.ServiceManager`,
    `Writer.Application`, `Calc.Application`, `AppID\soffice.exe` và CLSID tương ứng; bộ cài sau cùng phục vụ chúng.
- Beta 1–4 ghi ProgID `LibreOffice.*` và `Software\LibreOffice\UNO\InstallPath`, trùng LibreOffice. Gỡ bản beta (kể cả
  khi cài beta.5 lên) xóa các khóa đó, nên LibreOffice cài cùng máy mất lệnh mở tệp cho tới khi chạy Repair LibreOffice
  (ghi trong ghi chú phát hành beta.5).
- Kiểm tra: `scripts/check-msi-upgrade.py` (Quality CI, đọc patch) và `scripts/check-msi-upgrade.py --msi <tệp>`
  (đọc bảng Upgrade và Property của MSI đã build; workflow Windows smoke chạy bước này và thử cài cạnh LibreOffice,
  nâng cấp từ beta.4).
- Không có cầu nối CLI-UNO (.NET Framework) cũ, không ghi gì vào GAC (từ 1.0.2; quyết định của chủ dự án): bản Windows
  cấu hình `--disable-cli` (cùng `--without-dotnet`) và
  [`hst-windows-no-cli-uno.patch`](../patches/libreoffice/hst-windows-no-cli-uno.patch) chỉ đưa các mục ASSEMBLY của scp2
  vào gói khi có `ENABLE_CLI`, nên MSI không còn `cli_ure.dll`, `cli_basetypes.dll`, `cli_uretypes.dll`,
  `cli_cppuhelper.dll`, `cli_oootypes.dll`, `cli_uno.dll`, các `policy.1.0.cli_*.dll`/`cli_*.config` và không còn dòng
  `MsiAssembly`. 1.0.0/1.0.1 cài chúng vào GAC, bước đó lỗi trên một số máy (lỗi 1304 khi ghi `cli_uretypes.dll`, Smart
  App Control chặn `policy.1.0.cli_cppuhelper.dll` chưa ký). Basic, macro VBA, cầu nối OLE/COM (`HSTOffice.*`), Python
  và phần mở rộng HST không dùng chúng; chỉ chương trình .NET viết cho binding CLI cũ mới cần. Nâng cấp từ 1.0.0/1.0.1:
  `RemoveExistingProducts` (675) chạy trước `InstallInitialize` (700), gỡ bản cũ, kể cả assembly trong GAC, trước khi
  cài bản mới. Ngoại lệ đã biết: bản gỡ của 1.0.0/1.0.1 (và của LibreOffice x64) để lại một tệp
  `GAC_64\cli_cppuhelper\v4.0_1.0.23.0__ce2cb7e279207b9e\cli_cppuhelper.dll` (scp2 khai báo `x86`, assembly thực là
  AMD64 nên Fusion không tìm thấy tên `x86` khi gỡ); MSI mới không sửa được bước gỡ của bản cũ, tệp không được nạp.
  Kiểm tra: `scripts/check-msi-no-cli.py` (Quality CI: tùy chọn configure và series) và
  `scripts/check-msi-no-cli.py --msi <tệp>` (bảng File, MsiAssembly, MsiAssemblyName, InstallExecuteSequence; chạy trong
  Desktop Windows sau khi build và trong Windows smoke); kịch bản smoke `upgrade-from-1.0.1`
  ([`probe-upgrade-no-gac.ps1`](../scripts/windows/probe-upgrade-no-gac.ps1)) cài 1.0.1 rồi MSI mới, kiểm GAC sạch và
  chạy macro VBA headless trong Sheets và Writer.
