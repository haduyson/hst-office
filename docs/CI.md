# CI của HST Office

Các workflow phục vụ bản HST Office độc lập dựa trên LibreOffice 26.8.1.1.
Kiểm tra cấu trúc hoặc tài nguyên đạt không phải bằng chứng bộ cài chạy đúng.
Có số đo thật cho build Windows thử nghiệm (xem dòng Windows và `plans/reports/opus-win-261029-1700-windows-trial.md`); chưa có bộ cài Windows/macOS được xác minh.

| Workflow | Khi chạy | Phạm vi và giới hạn |
|---|---|---|
| [Quality](../.github/workflows/quality.yml) | Push vào `main`, mọi pull request | Python 3.12, Node 22, kiểm tra mã và dữ liệu; tối đa 20 phút. |
| [Linux](../.github/workflows/desktop-linux.yml) | `workflow_dispatch`, input `mode` = `full` (mặc định) hoặc `preflight` | `ubuntu-24.04` (4 vCPU, 16 GiB), build trong container Ubuntu 22.04. Build một gói `.deb`, ~2 giờ; tối đa 355 phút. Xem mục [Linux (.deb)](#linux-deb). |
| [Windows](../.github/workflows/desktop-windows.yml) | `workflow_dispatch`, input `mode` = `preflight` (mặc định) hoặc `full` | `windows-2022` (4 vCPU AMD EPYC, 16 GiB RAM, ổ D: ~220 GiB trống; build ở `D:\hst`). Preflight ~11 phút: Cygwin, make native, NASM, pkgconf, tải+sha256, giải nén, vá, cấu hình đến hết `autogen.sh`. Full: thêm `make` trong ngân sách 330 phút rồi dừng sạch và tải log/số đo; tối đa 355 phút. Kiểm tra cục bộ: `scripts/windows/preflight-local.sh`. |
| [Windows smoke](../.github/workflows/windows-smoke.yml) | `workflow_dispatch`; inputs `release_tag` (mặc định bản phát hành mới nhất đã ghi), `overlay_extension` | `windows-2022`. Tải MSI của bản phát hành, kiểm tra sha256 theo `SHA256SUMS`, cài `msiexec /qn`, rồi `tests/runtime/check-windows-smoke.py` chạy bằng `python.exe` đóng gói: nạp mọi mô-đun phần mở rộng HST, gửi từng lệnh HST (NĐ 30, chuyển mã, giải pháp, cập nhật, CSV, định dạng), chụp màn hình các hộp thoại, đo kích thước so với màn hình. `overlay_extension` thay phần mở rộng đóng gói bằng bản dựng từ commit để thử bản sửa mà không build 2 giờ. Nhật ký/ảnh tải lên artifact. Tối đa 70 phút mỗi kịch bản. Input `install_paths` (mặc định bật; cần MSI từ beta.5) thêm ba kịch bản vào ma trận `scenario`, mỗi kịch bản một runner mới: kiểm bảng Upgrade/Property bằng `scripts/check-msi-upgrade.py --msi` và bảng Registry bằng `scripts/check-msi-coexist.py --msi` (không App Paths, scheme `vnd.libreoffice.*`, ProgID, CLSID phần mở rộng Explorer hay khóa `Software\LibreOffice` của LibreOffice), rồi (a) cài LibreOffice 26.8.2 chính thức (URL và SHA256 ghim trong workflow) trước HST Office, hoặc (a') HST Office trước: cả hai còn cài, giữ ProgID, lệnh mở `.odt`/`.docx` và `UNO\InstallPath` riêng, đều mở được; gỡ bộ cài sau thì bộ còn lại giữ nguyên, kể cả App Paths, scheme `vnd.libreoffice.command`, CLSID phần mở rộng Explorer và ProgID cũ của LibreOffice ([smoke-coexist-registry.ps1](../scripts/windows/smoke-coexist-registry.ps1)); (b) cài HST beta.4 rồi MSI mới, beta.4 được thay và Programs and Features chỉ còn một mục HST Office (`scripts/windows/smoke-install-paths.ps1`); (c) `upgrade-from-1.0.1`: cài 1.0.1 (URL và SHA256 ghim trong workflow; đưa assembly CLI-UNO vào GAC) rồi MSI mới: không còn `cli_*` trong GAC hay thư mục cài, một mục HST Office, không lỗi 1304, macro VBA chạy headless trong Sheets và Writer (`scripts/windows/probe-upgrade-no-gac.ps1`). Bảng File/MsiAssembly kiểm bằng `scripts/check-msi-no-cli.py --msi` (cũng chạy trong Desktop Windows sau khi build). |
| [macOS](../.github/workflows/desktop-macos.yml) | `workflow_dispatch`, input `mode` = `preflight` (mặc định) hoặc `full` | Ma trận `macos-15` (arm64) và `macos-15-intel` (x86_64), dmg **chưa ký**; job ký/notarize tùy chọn. Xem mục [macOS](#macos). |

Mọi workflow chỉ có quyền `contents: read`, action ghim bằng SHA đầy đủ và có
concurrency. Quality hủy lượt cũ cùng ref; desktop tuần tự, không hủy build đang
chạy. Checkout không giữ thông tin xác thực. Artifact chỉ chứa log/số đo thực tế,
lưu 7 ngày và lỗi nếu không có tệp. Chưa có workflow phát hành công khai.
SHA action do coordinator cung cấp; cần **re-verify pins** khi có kết nối mạng.

## Quality chạy những gì

[ci-quality.sh](../scripts/ci-quality.sh) tìm mã kiểm tra tại thời điểm chạy:

- Mọi tệp `test*.py` dưới `tests/unit` và `tests/brand`, kể cả tên có dấu gạch nối.
- `generate-brand-assets.py --check`, `check-doc-links.py`, `check-workflows.py`
  là bắt buộc; thiếu tệp hoặc thư mục test rỗng làm lượt chạy thất bại.
- Khi đã có, chạy `build-extensions` và `generate-templates` trước các kiểm tra
  cấu trúc. Các script `scripts/check-*` có đuôi `.py`, `.sh`, `.js`, `.mjs`
  được phát hiện và thực thi, gồm `check-templates`, `check-extensions`, kiểm tra
  nguồn/giấy phép nếu chủ sở hữu đã tích hợp chúng. Lệnh dùng tham số mặc định
  của script; thêm giao diện bắt buộc mới phải cập nhật bộ điều phối quality.
- Thu thập lỗi của từng lệnh, tiếp tục các kiểm tra độc lập, rồi trả mã khác 0
  nếu bất kỳ lệnh nào lỗi. Không đổi thiếu đầu vào thành PASS.

Workflow cài dependency bằng `pip --require-hashes -r requirements-templates.lock`
và `fonts-liberation` trên Ubuntu 24.04. Lock thuộc coordinator; thiếu lock là lỗi
thiết lập. Không cài LibreOffice của bản phân phối để gọi đó là runtime HST.
Nếu script sinh mẫu cần HST/UNO mà chưa được cấp, lỗi đó vẫn làm quality đỏ;
chủ sở hữu mẫu cần công bố rõ giao diện kiểm tra cấu trúc và runtime.

[check-workflows.py](../scripts/check-workflows.py) dùng PyYAML với khóa `on`
đúng kiểu chuỗi, từ chối khóa YAML trùng, trigger sai, quyền ghi, pin không đúng,
timeout thiếu, guard có thể bỏ qua và tham chiếu script không tồn tại. Chỉ
`scripts/build-linux.sh` do coordinator quản lý được miễn kiểm tra tồn tại.
Đây là kiểm tra hợp đồng YAML, không thay thế trình thực thi GitHub Actions.

[check-doc-links.py](../scripts/check-doc-links.py) được chuyển từ nhánh archive
ONLYOFFICE tại commit `e0517d71c813535087c401b2683bec0784d71fd8`. Nó kiểm tra
đường dẫn tệp Markdown cục bộ trong README, NOTICE, THIRD_PARTY_NOTICES, docs và
plans; không truy cập mạng hoặc xác minh anchor. Liên kết cũ bị hỏng vẫn báo lỗi.

## Tài nguyên Linux và các điều kiện còn chặn

[probe-runner.py](../scripts/probe-runner.py) ghi CPU khả dụng, RAM tổng/khả dụng,
dung lượng đĩa, filesystem, phiên bản công cụ, SHA cấu hình, SHA Git và thời gian
UTC vào `build/metrics/runner-probe.json`. Probe chỉ đọc tài nguyên, không tải
source hoặc chạy build. Quota/billing của tài khoản luôn ghi `UNVERIFIED` cho đến
khi chủ tài khoản xác minh riêng.

Ngưỡng sàn là **40 GiB đĩa trống**, **16 GiB RAM khả dụng** và dự trữ **10 GiB**.
Probe đọc `--with-parallelism` trong `build-config/linux-x86_64.conf` làm yêu cầu
CPU. Coordinator có thể bổ sung comment `# min_free_gib=...`, `# min_ram_gib=...`,
`# min_cpu=...`, `# reserve_gib=...` để tăng ngưỡng sau khi có số đo. Tham số
`--min-free-gib` không thể hạ sàn 40 GiB. Khi chưa có metadata, sàn là giả định
thận trọng của nhiệm vụ, **không phải peak đã đo của một build hoàn chỉnh**.

Probe và `scripts/measure-job.py` dành cho máy build cục bộ (`scripts/build-linux.sh`); workflow
Linux trên GitHub dùng ngưỡng riêng (mục [Linux (.deb)](#linux-deb)). Thiếu tài nguyên trả
`BLOCKED (OPS-01)` và mã 1, vẫn giữ JSON. Build/package đạt chưa chứng minh GUI, độ trễ hoặc
tương thích Office.

| Mã | Điều kiện mở | Chủ sở hữu |
|---|---|---|
| OPS-01 | Cấp runner phù hợp; Linux đo đủ dung lượng/RAM; Windows/macOS ít nhất 100 GB đĩa trống và toolchain bản địa. | Quản trị môi trường + coordinator |
| SIGN-01 | Cấp chứng chỉ Windows, Apple signing/notarization qua kho bí mật được bảo vệ; xác định luồng phát hành đã duyệt. | Chủ dự án / người phụ trách phát hành |
| QA-01 | Có máy Windows, Mac arm64/x86_64, phiên GUI và quy trình cài đặt, nâng cấp, gỡ, mở/lưu tài liệu, đo độ trễ. | Chủ dự án + QA |

## Linux (.deb)

[desktop-linux.yml](../.github/workflows/desktop-linux.yml) build trên `ubuntu-24.04` bằng
[ci-build.sh](../scripts/linux/ci-build.sh): `--deps` (`apt-get build-dep libreoffice` + ninja, Pillow),
tải tarball đã ghim và kiểm sha256 (`fetch-sources.py`), `--extract`, `--patch` (patch HST, lớp dịch
tiếng Việt, icon HST), `--configure` (`linux-x86_64.conf`, thay branding và `--with-parallelism` theo
runner), `--fetch`, `--build` (một `make`, gồm cả bộ cài `.deb`), `--package`.
[free-runner-disk.sh](../scripts/linux/free-runner-disk.sh) xóa toolchain không dùng trước khi build
ở `/mnt/hst`. `--build` dừng make và báo lỗi khi tới hạn 330 phút kể từ đầu job hoặc đĩa trống dưới 3 GiB.
Sau `--package`, [check-coexistence.sh](../scripts/linux/check-coexistence.sh) cài gói cạnh LibreOffice của
Ubuntu 24.04 trong container và kiểm hai bộ chạy song song (log trong artifact `linux-evidence-<run_id>/coexistence/`).

```bash
gh workflow run desktop-linux.yml                 # full: build + gói .deb
gh workflow run desktop-linux.yml -f mode=preflight   # chỉ đến hết fetch, ~10 phút
```

Kết quả lượt xanh (run 41009617263): build 1 giờ 55 phút, cả lượt ~2 giờ 04 phút; đĩa trống ≥ 108 GiB,
RAM đỉnh ~4,4 GiB (lấy mẫu 30 giây). Artifact:

- `hst-office-linux-deb-<run_id>` (14 ngày): **một** tệp `HSTOffice_<release>_Linux_x86-64.deb` và
  `SHA256SUMS`, chỉ tải lên khi build thành công. `--package` gộp bộ 38 gói `.deb` do EPM sinh ra thành
  một gói `hst-office` bằng [make-single-deb.py](../scripts/linux/make-single-deb.py): App Center, GNOME
  Software, gdebi chỉ mở được một tệp và không tự tìm các gói anh em. Gói gộp: `Depends` = hợp các phụ thuộc
  ngoài (bỏ phụ thuộc nội bộ), `Conflicts`/`Replaces` mọi tên gói tách (nâng cấp từ bản beta 2 gỡ sạch bản
  tách, giữ nguyên hồ sơ người dùng), cùng script postinst/postrm cập nhật cơ sở dữ liệu desktop/MIME/icon,
  tệp `copyright`, AppStream metainfo; bỏ tệp menu Debian cũ `usr/lib/menu` và không đánh dấu conffile
  ngoài `/etc`. Không còn `.tar.gz` bộ tách. Lintian có override cho `dir-or-file-in-opt`,
  `embedded-library`, `shared-library-is-executable` (bộ cài nằm ở `/opt`, mang theo thư viện riêng).
- `linux-evidence-<run_id>` (7 ngày, luôn tải lên): thời gian từng pha, mẫu đĩa/RAM, log.

**Một gói cho nhiều bản phân phối.** Job chạy trên `ubuntu-24.04` nhưng mọi pha của
[ci-build.sh](../scripts/linux/ci-build.sh) chạy trong container `ubuntu:22.04` (ghim digest, biến
`HST_CONTAINER`; [run-in-container.sh](../scripts/linux/run-in-container.sh)). Gói liên kết với
glibc 2.35 nên cài được trên Ubuntu 22.04 (Mint 21) và mọi bản mới hơn: Ubuntu 24.04, 26.04, Debian 13.
Ba điểm khác với bản trước:

- **Trình biên dịch:** LibreOffice 26.8 cần GCC 13 hoặc Clang 18; Ubuntu 22.04 không có. Dùng
  Clang 20 từ `apt.llvm.org` (`HST_CLANG=20`, vân tay khóa được kiểm), biên dịch với header
  libstdc++ 12 của chính Ubuntu 22.04 nên gói không đòi libstdc++ mới hơn khi chạy.
- **Python:** `--enable-python=internal` (Python 3.13 đi kèm trong `/opt/hst-office1.0`), nên không còn phụ thuộc
  `libpython3.12t64`; macro Python, pyuno và phần mở rộng HST chạy bằng Python đóng gói.
- **Phụ thuộc thư viện:** `make-single-deb.py` thêm phương án `libX | libXt64` cho mọi thư viện (Ubuntu 24.04+/Debian 13
  đổi tên `libglib2.0-0t64`, `libcups2t64`, ...).

Bản phân phối hỗ trợ (đã kiểm bằng `check-deb-install.sh` trong Docker): Ubuntu 22.04, 24.04, 26.04, Debian 13 (và dẫn xuất:
Mint 21/22). Phiên bản gói `1.0.0-2` (> `1.0.0-1` của beta 3, nên nâng cấp được); tăng `HST_DEB_REVISION` khi dựng lại cùng `VERSION`. Kiểm cài đặt sạch:
`tests/runtime/check-deb-install.sh [tệp.deb]` (mặc định `INSTALL_MODE=apt`: `apt-get install ./tệp.deb`,
cùng đường với trình cài đồ họa; `INSTALL_MODE=pkcon`: PackageKit `pkcon install-local`;
`INSTALL_MODE=upgrade OLD_SPLIT_DIR=<thư-mục-bản-tách>`: nâng cấp đè lên bản tách của beta 2;
`IMAGE=debian:13` đổi bản phân phối). Kiểm cục bộ trước khi đẩy:
`scripts/linux/preflight-local.sh` (shellcheck, actionlint; chạy trong `ci-quality.sh`).

## Entrypoint Windows và macOS

[build-windows.ps1](../scripts/build-windows.ps1) chỉ chuẩn bị runner (probe, giải phóng đĩa,
Cygwin, make native, NASM, pkgconf). Các bước build nằm trong
[trial-build.sh](../scripts/windows/trial-build.sh) chạy bằng bash của Cygwin
(`--extract|--tools|--options|--patch|--configure|--build`), tải/kiểm sha256 bằng
[fetch-sources.py](../scripts/windows/fetch-sources.py), tổng hợp số đo bằng
[summarize-trial.py](../scripts/windows/summarize-trial.py). Cấu hình ở
[windows-x86_64.conf](../build-config/windows-x86_64.conf). Phần Cygwin/MSVC chỉ
xác minh được trên runner Windows; [preflight-local.sh](../scripts/windows/preflight-local.sh)
chạy trong `ci-quality.sh` (shellcheck, actionlint, CRLF, mô phỏng giải nén/vá/tùy chọn trên Linux).

### Build Windows cục bộ trên HST4/HST5 (bản thử, không phải bản phát hành)

Máy thử HST4 (28 luồng, 32 GB RAM) build MSI để phát triển và thử nghiệm. Bản phát hành chính thức
vẫn lấy từ CI. Máy này đi theo đúng các bước của workflow: dùng `trial-build.sh` của chính commit
được build, cùng gói Cygwin, ghim flex, make native, pkgconf, NASM, Python 3.12 + Pillow 10.4.0 và
cùng cách đổi tên MSI/`SHA256SUMS`. Toàn bộ nằm trên ổ D:, trong đường dẫn không có dấu cách vì
ổ D: tắt tên 8.3. Bộ công cụ được cài một lần bằng
[hst4-setup.ps1](../scripts/windows/hst4-setup.ps1) gồm: VS 2022 Build Tools tại `D:\VS2022BT`
với đúng các thành phần mà `configure.log` của CI dùng (MSVC v143, ATL kể cả Spectre, clang-cl,
merge module MSVC, CMake/Ninja, Windows SDK 10.0.26100, .NET Framework 4.8.1 SDK), Cygwin tại
`D:\cygwin64` (qua `build-windows.ps1 -CygwinRoot`), cùng ngoại lệ Defender cho `D:\hst-build` và
`D:\cygwin64`. Windows SDK và trình cài VS luôn nằm trên C:, và C: phải còn trống ít nhất 3 GB.

[hst4-build.ps1](../scripts/windows/hst4-build.ps1) build một nhánh hoặc commit vào `D:\hst-build`
(thư mục `repo`, `lo`, `dl`, `branding`, `logs`, `metrics`, `out`). MSI cùng `SHA256SUMS` và
`build-info.json` (thời gian từng bước, sha, kích thước) được ghi vào
`D:\hst-build\out\<nhánh>-<sha7>\`. Mặc định script dùng mọi luồng, ưu tiên Normal; có thể đổi
bằng `-Jobs N` và `-Priority BelowNormal`. Lần sau build tăng dần nhờ
[hst4-tree.sh](../scripts/windows/hst4-tree.sh). Bản giải nén gốc được giữ trong `pristine\<khóa>\`,
với khóa tính từ sha256 của tarball và `trial-build.sh`. `stage\` giữ cây đã vá của lần chạy
trước. Mỗi lần chạy, script đưa những tệp và thư mục mà lần vá trước đã đổi, tạo hay xóa về lại bản
gốc, rồi vá lại bằng `trial-build.sh --patch` của commit đang build. Những gì vừa đổi được nhận ra
bằng ctime và danh sách tệp, và chỉ những tệp có nội dung khác mới được chép sang `lo\`, nên make
chỉ build lại phần mà commit thay đổi. Nếu đổi tarball, `trial-build.sh` hoặc dùng `-Clean`, cây
được dựng lại đầy đủ. Khi đổi tarball, tệp upstream cũ có thể còn sót trong `lo\`; lúc đó nên dùng
`-Clean`. Thêm `-VerifyTree` để so `stage\` và `lo\` với một cây vừa giải nén và vá mới (mất thêm
khoảng 13 phút). `lo\` chỉ được phép khác ở `configure`, `aclocal.m4` và `openoffice.lst`, là
những tệp do bước configure ghi lại. Build dài phải chạy tách khỏi phiên SSH bằng
[hst4-detach.ps1](../scripts/windows/hst4-detach.ps1). Script này tạo task `hst-build-<tên>`
chạy dưới tài khoản `kiemtra` (S4U, ưu tiên Normal) và tự xóa task khi xong.

```powershell
# một lần: chép script ra ngoài checkout (checkout bị đổi sang commit cần build)
Copy-Item scripts\build-windows.ps1 D:\hst-build\tools\scripts\; Copy-Item scripts\windows\hst4-* D:\hst-build\tools\scripts\windows\
powershell -File D:\hst-build\tools\scripts\windows\hst4-detach.ps1 -Name build -Script D:\hst-build\tools\scripts\windows\hst4-build.ps1 -ScriptArgs '-Ref rc/1.0.2-batch1'
powershell -File D:\hst-build\tools\scripts\windows\hst4-build.ps1 -Status   # bước hiện tại, số bước [build], đuôi build.log, dung lượng trống
```

Dùng `-ExpectSha <sha>` để build dừng ngay khi nhánh không còn ở đúng commit đã được báo. Số đo
lần đầu (13/11/2026, `rc/1.0.2-batch2` cac9177, 28 luồng): toàn bộ quy trình mất 86 phút, riêng
make 71 phút. Trước đó cây đã được build sẵn khoảng 11 phút, xong phần lớn các thư viện ngoài. Để
so sánh, bước build trên runner CI mất 157 phút. Phần OpenSSL do nmake build chạy một luồng nên
kéo dài khoảng 30 phút. MSI cuối cùng nặng khoảng 224 MiB. Một lần build tăng dần mất khoảng 17
phút. Riêng bước cây mất 5,5 phút (trước khi có bộ đệm `pristine\` là 14 phút): đưa tệp về bản gốc
5 giây, vá lại 5 phút, quét và chép 8 giây. Sau đó configure 1 phút, make và đóng gói MSI 10 phút.
Lần đầu dùng một khóa tarball mới phải giải nén thêm khoảng 5 phút. Ổ D: cần khoảng 45 GB cho cây
build, `pristine\` và `stage\`.

#### Nhiều máy, nhiều slot và hàng đợi (HST4, HST5)

Agent không gọi `hst4-build.ps1` bằng tay nữa mà gửi job vào hàng đợi
(`scripts/build-queue.sh submit --platform windows --ref <nhánh|sha> [--priority N] [--modules a,b]`, xem
[BUILD_MATRIX.md](BUILD_MATRIX.md#hàng-đợi-build-cục-bộ-agent-tự-dùng)). Dispatcher trên máy dev coi các slot trong
`windows_slots` của `/data/hst-build-queue/config.json` là một bể chung: mỗi slot là một máy + một thư mục gốc
(`-Root`) với `repo\`, `lo\`, `stage\`, `pristine\`, `out\` và `build.lock` riêng; Cygwin, VS, Python và `bin\` dùng
chung dưới `-ToolsRoot` (`D:\hst-build`). Với mỗi job, dispatcher:

1. chép công cụ (`hst4-*.ps1`, `hst4-tree.sh`, `hst4-make-targets.sh`, `build-windows.ps1`,
   `apply-build-overlay.ps1`) vào `D:\hst-build\tools\scripts\` của máy khi chúng đổi;
2. chạy [hst-queue-remote.ps1](../scripts/windows/hst-queue-remote.ps1) qua `tests/realwin/remote.py <máy> ps`:
   `Probe` (slot bận nếu `build.lock` đang bị giữ, kể cả bởi một lượt chạy tay), `Start` (task
   `hst-build-q-<job>` qua `hst4-detach.ps1`, `hst4-build.ps1 -Ref <sha> -OutName q-<job>`), `Status` mỗi phút,
   `Cancel` (dừng task và đúng cây tiến trình của nó);
3. kéo `out\q-<job>\` (MSI + `SHA256SUMS` + `build-info.json`, kiểm `sha256sum -c`) về
   `/data/hst-build-queue/out/<job>/`, ghi máy đã build vào job, rồi xoá bản trên máy Windows.

`-Modules sc,sw` (chỉ để thử) chạy `make udkapi.build offapi.build oovbaapi.build` rồi `make sc.build sw.build` với
cùng môi trường như `trial-build.sh --build` ([hst4-make-targets.sh](../scripts/windows/hst4-make-targets.sh)), và
xuất `HSTOffice-overlay-<sha>-<module>.zip` (tệp trong `instdir` mà lượt make đó ghi lại) để chép đè lên ảnh cài
quản trị (`msiexec /a`) của một MSI tham chiếu. Slot phải đã build đủ một lần.

HST5 được dựng giống HST4 bằng `hst4-setup.ps1` (13/11/2026): bước mới `Prereqs` cài Chocolatey (script cài
chính thức, kiểm chữ ký Authenticode) và Git for Windows nếu thiếu; VS Build Tools 17.14.37906.3 (MSVC 14.44.35207,
clang-cl 19.1.5, SDK 10.0.26100, .NET 4.8.1), Cygwin, NASM 3.02, pkgconfiglite, Python 3.12.10 + Pillow giống hệt
HST4; ngoại lệ Defender cho `D:\hst-build` và `D:\cygwin64`. Chủ máy đã tắt Smart App Control trên HST5 (không
bật lại được nếu không cài lại Windows; ghi ở `C:\hst-test\hst5-sac-change.txt`). Kho chứng chỉ gốc của Windows trên HST5
thiếu chuỗi của máy chủ tải tarball (`CERTIFICATE_VERIFY_FAILED` với Python NuGet). Không đổi kho chứng chỉ của máy:
bước `Python` của `hst4-setup.ps1` cài `certifi` ghim phiên bản và hash (`pip --require-hashes`), và `hst4-build.ps1`
chỉ đặt `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` tới bộ CA đó trong lúc chạy `fetch-sources.py` của task build; tarball vẫn
được kiểm sha256 theo lock. Trên Windows 11 bản 26200 (HST5),
`expand.exe` báo `0x80070005` khi bộ đóng gói MSI bung merge module VC vào thư mục do Cygwin tạo dưới `/tmp` (thư mục
thuộc người build, không cấp quyền cho Administrators) bên trong task S4U nâng quyền; bước `TmpAcl` của
`hst4-setup.ps1` cấp toàn quyền kế thừa cho Administrators và SYSTEM trên `D:\cygwin64\tmp` (đã áp trên HST5).

Số slot (đo 13/11/2026, giữ ổ còn trống ≥ 15 GB và RAM không quá tải):

| Máy | Slot (`-Root`) | Lý do |
|---|---|---|
| HST4 (28 luồng, 32 GB) | 1: `D:\hst-build` | Mỗi cây ~40 GB (`lo` 33 + `stage` 3,5 + `pristine` 3,5); D: chỉ còn ~37 GB trống, C: dao động 10–56 GB vì việc khác nên không đặt cây thứ hai ở C:; các ứng dụng sẵn có trên máy đã chiếm ~15 GB RAM. |
| HST5 (Xeon E5-2680 v4, 28 luồng, 32 GB) | 2: `D:\hst-build`, `D:\hst-build-s2` | D: 130 GB: hai cây (~80 GB) vẫn để ~37 GB trống, cây thứ ba thì không. Một build `-j28` lên đỉnh ~21 GB commit (gồm ~8 GB nền); build thứ hai trên cùng máy chạy `-j14`. |

Bản dịch tiếng Việt trong build tăng dần: `make` của LibreOffice không dựng lại `.mo`, `registry_vi.xcd` hay
`XcuResTarget/*/vi` khi `.po` đổi ([SHARED_BUILD_SLOTS.md](SHARED_BUILD_SLOTS.md#incremental-build-gaps)), nên trước
13/11/2026 MSI build tăng dần trên HST4/HST5 mang catalogue của lần build đủ đầu tiên của slot (nhãn ribbon, gợi ý tìm
kiếm còn tiếng Anh). Nay `hst4-tree.sh` xoá các tệp đó cho mọi ngôn ngữ có `.po` mới hơn `.mo` cũ nhất của nó, và
`hst4-build.ps1` chạy [check-mo-fresh.py](../scripts/l10n/check-mo-fresh.py) sau make: dịch lại từng `.po` như gbuild
(`msguniq | msgfmt`) và so từng mục với `.mo` trong `instdir`; lệch là job hỏng, không ra MSI. Build Linux cục bộ kiểm
cùng cách trước khi đóng gói.

Khi máy có hai slot, lưu ý: `trial-build.sh --build` (script của CI, giữ nguyên) khi chạm hạn 3 ngày
(`HST_BUILD_DEADLINE`) chạy `taskkill /IM make.exe|cl.exe|link.exe` cho **cả máy**, nên sẽ dừng luôn build của slot
kia; chỉ xảy ra khi một build chạy quá 3 ngày. Đổi công cụ trên một máy luôn bận: `scripts/build-queue.sh drain <máy>`.

`-Jobs` của job mới = luồng của slot chia cho (số build đang chạy trên máy đó + 1): một mình 28, cạnh một build khác
14. Tarball ghim nằm chung ở `D:\hst-build\dl` (`-ToolsRoot`). Slot mới build đủ lần đầu khi được dùng lần đầu; trước đó thư mục gốc của nó phải có ngoại lệ Defender
(`hst4-setup.ps1 -Step Defender -ExtraRoots D:\hst-build-s2`), nếu không configure của LibreOffice dừng.

Số đo: HST4 build tăng dần qua hàng đợi `rc/1.0.2-batch4` (d071caa): 18 phút (cây 332 s, configure 66 s,
make + MSI 666 s) và thêm khoảng 1 phút kéo MSI về. HST5 build đủ lần đầu: cây 20 phút (giải nén + vá),
fetch 10,5 phút, configure 2 phút, make 80,5 phút (chậm hơn HST4 vì CPU 2,4 GHz). Ổ D: của HST5 cần ~45 GB cho một
slot mới.

[build-macos.sh](../scripts/build-macos.sh) (chỉ kiểm kê, không dùng trong CI; CI dùng `scripts/macos/`, xem mục [macOS](#macos)) nhận `--arch arm64|x86_64`, in lệnh từ
[arm64](../build-config/macos-arm64.conf) hoặc [x86_64](../build-config/macos-x86_64.conf).
Script kiểm tra host đúng kiến trúc, Xcode từ 14.3, SDK từ 13.3 và công cụ đóng
gói; từ chối Xcode 15.0 với target macOS 11 theo `configure.ac` đã ghim. Cấu hình
dùng tên HST Office, bundle ID `vn.hasontech.hstoffice`, phiên bản số `26.8.1.1`
và định dạng `dmg`. Luồng `.pkg`, signing và notarization còn phải xác minh.

Cả hai entrypoint **chỉ kiểm kê và in lệnh, luôn kết thúc khác 0**: thiếu
toolchain bị chặn sớm; đủ công cụ vẫn báo thiếu tích hợp patch, signing và QA.
Chúng không chỉnh source, gọi configure, tạo bộ cài hay tuyên bố build thành công.
Khi có máy thật, coordinator phải thay guard bằng build và kiểm thử bản địa thực,
phân biệt bản thử nội bộ không ký với bản phát hành công khai đã ký.

## macOS

[desktop-macos.yml](../.github/workflows/desktop-macos.yml) build bản địa trên runner GitHub, mỗi kiến
trúc một job (`macos-15`: Apple M1 ảo 3 vCPU/7 GiB; `macos-15-intel`: i7-8700B 4 vCPU/14 GiB; Xcode 16.4,
SDK 15.5, target tối thiểu macOS 11.0). Các bước nằm trong [trial-build.sh](../scripts/macos/trial-build.sh)
(`--probe|--free-disk|--tools|--extract|--patch|--configure|--fetch|--build|--collect|--verify`), cấu hình ở
[macos-arm64.conf](../build-config/macos-arm64.conf) / [macos-x86_64.conf](../build-config/macos-x86_64.conf).
Công cụ lấy từ Homebrew nhưng chỉ symlink từng công cụ vào `~/hst/bin` (PATH tối thiểu, không lộ thư viện
Homebrew). Phiên bản HST lấy từ `/VERSION` và `data/hst/release.json` (header, `openoffice.lst`, `CFBundleShortVersionString` = `1.0.0`, `CFBundleVersion` = số build, `CFBundleGetInfoString` = mã bản phát hành; tên dmg mang mã đầy đủ).

- `preflight`: probe runner, giải phóng đĩa nếu còn dưới 80 GiB, tải+sha256, giải nén, vá, cấu hình, `make fetch`.
- `full`: thêm `make` với ngân sách 315 phút (dừng sạch), ccache lưu qua `actions/cache` kể cả khi dừng
  giữa chừng để lượt sau chạy tiếp, rồi đóng gói lại dmg bằng [build-dmg.sh](../scripts/macos/build-dmg.sh)
  (dmgbuild, [dmg-settings.py](../scripts/macos/dmg-settings.py)): nền HST tiếng Việt
  ([make-dmg-background.py](../scripts/macos/make-dmg-background.py)), biểu tượng volume HST, không có hộp
  thoại giấy phép. Icon ứng dụng và tài liệu (`main.icns`, `generic-*`, `oasis-*`) do
  [stage-macos-icons.py](../scripts/macos/stage-macos-icons.py) dựng từ ảnh HST. Bước `--verify` gắn dmg,
  kiểm tên `HST Office.app`, bundle ID `vn.hasontech.hstoffice`, kiến trúc, icon, bố cục, chuỗi Info.plist
  và catalog `.mo` tiếng Việt, và bằng [check-coexist-plists.py](../scripts/macos/check-coexist-plists.py)
  rằng bundle không khai báo gì trùng LibreOffice (không export UTI của bộ khác, không URL scheme
  `vnd.libreoffice.*`/`vnd.sun.star.*`, plug-in Spotlight/Quick Look mang id HST).
- Sau khi tải dmg lên, job arm64 chạy [coexist-probe.sh](../scripts/macos/coexist-probe.sh): cài LibreOffice
  chính thức (dmg ghim URL và SHA-256) rồi HST vào `/Applications`, ghi ứng dụng mặc định (`duti -x`,
  LaunchServices) khi cài/gỡ HST (scheme riêng của LibreOffice phải giữ nguyên; loại tệp cả hai cùng nhận,
  như ODF với hạng Owner và OOXML, chỉ báo WARN vì LaunchServices tự chọn một), hai ứng dụng chạy cùng lúc (`lsappinfo`, cửa sổ), `open -a`
  mở tệp đúng ứng dụng được chọn, profile riêng, gỡ bên nào bên kia vẫn chạy. Kết quả trong
  `macos-build-arm64-<run_id>/coexist/summary.md`; lỗi làm job đỏ (dmg chưa ký vẫn được tải lên).
- Artifact: `macos-build-<arch>-<run_id>` (log/số đo, luôn tải, 7 ngày) và
  `hst-office-macos-<arch>-dmg-<run_id>` (`HSTOffice_<release>_macOS_<arch>.dmg` + `SHA256SUMS`, chỉ khi
  thành công, 14 ngày). Kiểm tra cục bộ: [preflight-local.sh](../scripts/macos/preflight-local.sh) (trong `ci-quality.sh`).
- Số đo (2026-10-30, run 41026070593): arm64 xanh trong 3 giờ 01 phút (make 9934 giây, 17 830 bước,
  RAM tối đa 4,7 GiB, đĩa trống thấp nhất 82 GiB), dmg 279,6 MB. Intel chậm hơn khoảng 3,3 lần: hết ngân sách
  315 phút ở 12 677/≈17 830 bước (71 %), RAM tối đa 8,0 GiB; **một job không đủ**. ccache được lưu khi dừng
  ngân sách, nên lượt `full` kế tiếp **cùng commit** chạy tiếp; cần 2 (có thể 3) lượt cho x86_64. Đổi file
  dùng chung (ví dụ `officecfg/.../Common.xcs`) làm phần lớn cache mất hiệu lực.

**Bản chưa ký Developer ID.** Bản build upstream không có identity chỉ mang chữ ký ad-hoc của linker trên
từng tệp Mach-O; bundle (Info.plist, tài nguyên) không được niêm phong, và HST còn sửa bundle sau đó (gói
tiếng Việt, icon). Trên Apple Silicon, bundle bị cách ly (quarantine) như vậy bị báo **"bị hỏng"**. Vì vậy
`--collect` ký lại ad-hoc toàn bộ app sau thay đổi cuối cùng bằng [adhoc-sign.sh](../scripts/macos/adhoc-sign.sh)
(từ trong ra ngoài như `macosx-codesign-app-bundle`) và chặn build nếu `codesign --verify --deep --strict`
lỗi; `--verify` kiểm lại trên dmg. Có thể kiểm một dmg đã phát hành bằng
[macos-signature-probe.yml](../.github/workflows/macos-signature-probe.yml) (input `tag`); với `sign=true`
workflow này chạy luôn đường ký Developer ID + notarize trên app đó (environment `macos-signing`, cần duyệt) và
tải dmg đã ký lên artifact `macos-signing-probe-arm64-dmg-signed-<run_id>` (3 ngày).

**Bundle không được tự sửa khi chạy.** Người dùng admin kéo app vào `/Applications` (thư mục ghi được), nên
mọi tệp app ghi vào chính bundle sẽ phá niêm phong chữ ký. Python từng ghi `__pycache__/*.pyc` vào bundle
(upstream chép framework Python bằng `cp -R` nên mọi `.pyc` kèm theo đều cũ so với `.py`). Hai lớp chặn:
[hst-python-no-bytecode.patch](../patches/libreoffice/hst-python-no-bytecode.patch) đặt
`PYTHONDONTWRITEBYTECODE=1` trước `Py_Initialize()` trên macOS (tiến trình con dùng python3 đóng gói cũng thừa
hưởng; trên Windows và Linux bản vá đặt `PYTHONPYCACHEPREFIX=<hồ sơ người dùng>/cache/python` thay vào đó: bộ cài
không kèm bytecode, nên nếu không có bộ nhớ đệm này mỗi lần mở đều biên dịch lại mọi mô-đun Python trong lúc màn
hình chờ hiện — xem [Startup timing](../.github/workflows/startup-timing.yml)), và
`--collect` chạy [precompile-python.sh](../scripts/macos/precompile-python.sh) trước khi ký (bytecode
unchecked-hash hợp lệ cho thư viện chuẩn, mô-đun của office và phần mở rộng). Kiểm tra:
[macos-bundle-seal-probe.yml](../.github/workflows/macos-bundle-seal-probe.yml) (input `tag` hoặc `run_id`,
`baseline=required` mặc định: sau một phiên Writer + Kiểm tra cập nhật + trình hướng dẫn Văn bản hành chính,
danh sách tệp trong bundle không đổi và `codesign --verify --deep --strict` vẫn đạt; dmg trước bản sửa dùng
`informational`); trên Linux `tests/runtime/check-python-no-bytecode.py` (instdir: không có bytecode trong
bản cài, bytecode của phần mở rộng HST nằm trong `cache/python` của hồ sơ).

Người dùng macOS 15: mở app → hộp "Apple không thể xác minh…" → **Xong** → **Cài đặt hệ thống ▸ Quyền riêng
tư & Bảo mật ▸ Vẫn mở** (*Open Anyway*) → xác nhận mật khẩu → mở lại, chọn **Vẫn mở**. Dự phòng:
`xattr -dr com.apple.quarantine "/Applications/HST Office.app"`.

### Ký và notarize (tùy chọn)

Job `sign` chạy sau `build` ở chế độ `full`, trong environment `macos-signing` (chủ dự án có thể đặt người
duyệt). Bước `gate` kiểm tra đủ secret; thiếu bất kỳ secret nào thì mọi bước sau bị bỏ qua và job vẫn xanh.
Secret (repository hoặc environment `macos-signing`):

| Secret | Nội dung |
|---|---|
| `MACOS_DEVELOPER_ID_P12_BASE64` | Chứng chỉ "Developer ID Application" xuất `.p12`, mã hóa base64 (`base64 -i cert.p12`) |
| `MACOS_DEVELOPER_ID_P12_PASSWORD` | Mật khẩu của `.p12` |
| `MACOS_SIGNING_IDENTITY` | Ví dụ `Developer ID Application: HASON TECH (TEAMID)` |
| `APPLE_TEAM_ID` | Team ID 10 ký tự |
| `APPLE_API_KEY_P8_BASE64`, `APPLE_API_KEY_ID`, `APPLE_API_ISSUER_ID` | Khóa App Store Connect API (`.p8` base64, Key ID, Issuer ID) cho `xcrun notarytool` |

Bộ ký ([make-signing-kit.sh](../scripts/macos/make-signing-kit.sh)) giữ script upstream và **mẫu** `.in` của
entitlement/launch constraint; lúc ký mới điền bundle ID và `APPLE_TEAM_ID` (configure không ký để trống team ID,
helper ký xong sẽ không chạy được). Trước script upstream, mọi tệp Mach-O được ký Developer ID với hardened runtime
và timestamp; sau đó kiểm từng tệp có chữ ký Developer ID kèm timestamp trước khi gửi notarize.
[sign-notarize.sh](../scripts/macos/sign-notarize.sh) nhập chứng chỉ vào keychain tạm (luôn xóa ở bước
cuối, kể cả khi lỗi), ký app bằng chính script upstream `solenv/bin/macosx-codesign-app-bundle` với
hardened runtime và entitlement do configure sinh (`hardened_runtime.xcent`, launch constraint) — đúng
những gì `--enable-macosx-code-signing` chạy lúc đóng gói, nhưng tách khỏi job build để secret không vào
build. Sau đó dựng lại dmg cùng bố cục, ký dmg, `notarytool submit --wait`, `stapler staple`, kiểm tra
`spctl -a -t open --context context:primary-signature -v` và `codesign --verify --deep --strict`.
Artifact: `hst-office-macos-<arch>-dmg-signed-<run_id>`. `check-workflows.py` chỉ cho phép secret trong
job này, ở bước `gate` hoặc bước có điều kiện `steps.gate.outputs.enabled == 'true'`.

## Đo thời gian khởi động

Workflow [startup-timing.yml](../.github/workflows/startup-timing.yml) (chạy tay; input `windows_run_id`,
`windows_baseline_run_id` (bản build cũ đo trên cùng runner để so trước/sau), `macos_run_id`, `linux_run_id`,
`variants`, `starts` (chuỗi lần mở), `overlay_extension`) cài bộ cài của các lần build đó trên runner Windows,
macOS và Ubuntu rồi đo từ lúc mở đến khi màn hình chờ hiện, tắt và cửa sổ Start Center đầu tiên hiện: lần đầu với
hồ sơ mới, các lần sau và một lần sau khi xóa bộ nhớ đệm tệp của hệ điều hành (như vừa khởi động lại máy). Các biến
thể tách thời gian: bộ theo dõi Python (`scripts/perf/startup_trace/sitecustomize.py`: import, biên dịch, job HST,
kết nối mạng và luồng của chúng), bỏ phần mở rộng HST, phần mở rộng dựng từ commit đang chạy, bytecode, quét thời
gian thực của Windows và LibreOffice gốc cùng phiên bản trên cùng runner. Kịch bản:
`scripts/perf/startup-timing-{windows,macos,linux}.sh`; kết quả: artifact `startup-timing-<os>-<run_id>`
(`summary.md`, JSON từng lần mở, ảnh màn hình chờ). Chỉ là bằng chứng: workflow chỉ lỗi khi không cài được.

## Phát hành (Release)

Workflow `release.yml` (chạy tay) tạo **một** GitHub Release chứa bộ cài Windows (`.msi`),
Linux (một tệp `.deb`) và macOS (`.dmg` arm64 + x86_64) của **cùng một commit** trên
`main`; người dùng tải không cần đăng nhập. Không build lại: `scripts/release/collect-release-assets.sh`
tìm lượt build thành công mới nhất của từng nền tảng tại commit đó (hoặc dùng run id được ghim),
kiểm `SHA256SUMS` từng artifact, ưu tiên `.dmg` đã ký + notarize nếu có, gộp một `SHA256SUMS`,
rồi tạo tag tại commit đó. Thiếu bản build của nền tảng nào thì dừng với hướng dẫn. Ghi chú phát
hành lấy từ `docs/releases/<tag>.md` (thiếu thì dừng). Tên tệp tải mang mã bản phát hành đầy đủ
(`HSTOffice_1.0.0-beta.4.1_Win_x86-64_en-US_vi.msi`, `..._Linux_x86-64.deb`, `..._macOS_arm64.dmg`,
`..._macOS_x86_64.dmg`); `collect-release-assets.sh` chọn tệp theo đuôi nên không phụ thuộc phần phiên
bản, còn `generate-update-manifest.py` nhận diện nền tảng từ tên và dừng nếu mã trong tên khác tag
(tên cũ `HSTOffice_1.0.0_*` của các bản đến beta.4 vẫn được chấp nhận).

Quy trình: chạy `desktop-windows.yml`, `desktop-linux.yml`, `desktop-macos.yml` (`mode=full`)
trên cùng commit; khi cả ba xanh:

```bash
gh workflow run release.yml -f tag=v1.0.0-beta.2 -f prerelease=true
# tùy chọn: -f platforms="windows linux" -f commit=<sha> -f windows_run_id=<id> ...
```

Phát hành từng phần: tạo bản phát hành với `-f platforms="windows linux"`, rồi khi macOS build
xong (cùng commit) chạy lại với `-f platforms=macos -f append=true` — workflow lấy commit của tag,
không ghi đè bộ cài đã có, gộp `SHA256SUMS` theo tên tệp.

**macOS từ commit sau (chỉ sửa đóng gói macOS).** Input `macos_commit` cho phép lấy `.dmg` từ một commit
sau commit phát hành, chỉ khi commit đó là hậu duệ của commit phát hành và `git diff` giữa hai commit chỉ
chạm `scripts/macos/**`, `scripts/release/**`, `.github/workflows/**`, `scripts/check-workflows.py`, `docs/**`, `plans/**`,
`tests/**`, `website/**` (không có gì mà bộ cài Windows/Linux được build từ đó). Kiểm tra nằm ở
[macos-commit-paths.sh](../scripts/release/macos-commit-paths.sh) (gọi qua GitHub compare API); sai thì dừng.
Ghi chú phát hành và tóm tắt run ghi cả hai commit. Ví dụ:

```bash
gh workflow run release.yml -f tag=v1.0.0-beta.3 -f platforms=macos -f append=true -f macos_commit=<sha>
```

Chỉ job `publish` của workflow này có quyền ghi (`contents: write`, `actions: read`);
`scripts/check-workflows.py` từ chối quyền ghi ở mọi nơi khác. Artifact hết hạn sau 14 ngày nên
phải phát hành trong thời hạn đó. Liên kết `releases/latest` không trỏ tới bản pre-release.

### Báo bản mới cho người dùng (manifest cập nhật)

Sau khi Release đã công bố và `/tai/*` của trang đã trỏ tới bản mới:

1. Sửa `website/office.hasontech.vn/update/latest.json` (kênh `beta` hoặc `stable`: `version`, `date`, `notes`, `downloads`).
2. Ký: `python3 scripts/release/sign-update-manifest.py` (khóa ngoài kho mã, quyền 600); kiểm: `--verify`.
3. Commit, rồi tải `latest.json` và `latest.json.sig` lên `public_html/update/` của office.hasontech.vn.

Các bản đã cài sẽ thấy thông báo trong vòng 24 giờ. Chi tiết, khóa ký và chính sách quản trị:
[UPDATE_CHECK](UPDATE_CHECK.md); ghi chú phát hành: [docs/releases](releases/), workflow: [release.yml](../.github/workflows/release.yml).

## Chạy cục bộ

Từ gốc repo, dùng Python 3.12 có dependency theo lock và font đã ghim:

```bash
.venv/bin/python scripts/check-workflows.py
python3 -m unittest tests/unit/test_check_workflows.py
bash scripts/ci-quality.sh
python3 scripts/probe-runner.py --output build/metrics/runner-probe.json
bash scripts/build-macos.sh --arch arm64
pwsh -File scripts/build-windows.ps1
```

Quality ưu tiên biến `PYTHON`, rồi `.venv/bin/python`, rồi `python3`. Dùng
`PYTHON=python3 bash scripts/ci-quality.sh` khi hệ thống đã có đủ phiên bản.
Lệnh probe chỉ chứng minh tài nguyên tại thời điểm đo; hai lệnh native dự kiến
trả lỗi khi blocker chưa được giải quyết. Báo cáo tác giả nằm trong
[báo cáo Phase 09](../plans/reports/codex-09-261029-1342-ci.md); kết quả GitHub và
URL lượt chạy chỉ bổ sung sau khi thực sự chạy được.
