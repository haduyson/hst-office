# CI của HST Office

Các workflow phục vụ bản HST Office độc lập dựa trên LibreOffice 26.8.1.1.
Kiểm tra cấu trúc hoặc tài nguyên đạt không phải bằng chứng bộ cài chạy đúng.
Có số đo thật cho build Windows thử nghiệm (xem dòng Windows và `plans/reports/opus-win-261029-1700-windows-trial.md`); chưa có bộ cài Windows/macOS được xác minh.

| Workflow | Khi chạy | Phạm vi và giới hạn |
|---|---|---|
| [Quality](../.github/workflows/quality.yml) | Push vào `main`, mọi pull request | Python 3.12, Node 22, kiểm tra mã và dữ liệu; tối đa 20 phút. |
| [Linux](../.github/workflows/desktop-linux.yml) | `workflow_dispatch`, input `mode` = `full` (mặc định) hoặc `preflight` | `ubuntu-24.04` (4 vCPU, 16 GiB). Build các gói `.deb`, ~2 giờ; tối đa 355 phút. Xem mục [Linux (.deb)](#linux-deb). |
| [Windows](../.github/workflows/desktop-windows.yml) | `workflow_dispatch`, input `mode` = `preflight` (mặc định) hoặc `full` | `windows-2022` (4 vCPU AMD EPYC, 16 GiB RAM, ổ D: ~220 GiB trống; build ở `D:\hst`). Preflight ~11 phút: Cygwin, make native, NASM, pkgconf, tải+sha256, giải nén, vá, cấu hình đến hết `autogen.sh`. Full: thêm `make` trong ngân sách 330 phút rồi dừng sạch và tải log/số đo; tối đa 355 phút. Kiểm tra cục bộ: `scripts/windows/preflight-local.sh`. |
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

```bash
gh workflow run desktop-linux.yml                 # full: build + gói .deb
gh workflow run desktop-linux.yml -f mode=preflight   # chỉ đến hết fetch, ~10 phút
```

Kết quả lượt xanh (run 41009617263): build 1 giờ 55 phút, cả lượt ~2 giờ 04 phút; đĩa trống ≥ 108 GiB,
RAM đỉnh ~4,4 GiB (lấy mẫu 30 giây). Artifact:

- `hst-office-linux-deb-<run_id>` (14 ngày): **một** tệp `HSTOffice_<version>_Linux_x86-64.deb` và
  `SHA256SUMS`, chỉ tải lên khi build thành công. `--package` gộp bộ 38 gói `.deb` do EPM sinh ra thành
  một gói `hst-office` bằng [make-single-deb.py](../scripts/linux/make-single-deb.py): App Center, GNOME
  Software, gdebi chỉ mở được một tệp và không tự tìm các gói anh em. Gói gộp: `Depends` = hợp các phụ thuộc
  ngoài (bỏ phụ thuộc nội bộ), `Conflicts`/`Replaces` mọi tên gói tách (nâng cấp từ bản beta 2 gỡ sạch bản
  tách, giữ nguyên hồ sơ người dùng), cùng script postinst/postrm cập nhật cơ sở dữ liệu desktop/MIME/icon,
  tệp `copyright`, AppStream metainfo; bỏ tệp menu Debian cũ `usr/lib/menu` và không đánh dấu conffile
  ngoài `/etc`. Không còn `.tar.gz` bộ tách. Lintian có override cho `dir-or-file-in-opt`,
  `embedded-library`, `shared-library-is-executable` (bộ cài nằm ở `/opt`, mang theo thư viện riêng).
- `linux-evidence-<run_id>` (7 ngày, luôn tải lên): thời gian từng pha, mẫu đĩa/RAM, log.

Phụ thuộc của gói `.deb` theo glibc/thư viện của Ubuntu 24.04 (runner). Kiểm cài đặt sạch:
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
Homebrew). Phiên bản HST lấy từ `/VERSION` (header, `openoffice.lst`, `CFBundleShortVersionString`).

- `preflight`: probe runner, giải phóng đĩa nếu còn dưới 80 GiB, tải+sha256, giải nén, vá, cấu hình, `make fetch`.
- `full`: thêm `make` với ngân sách 315 phút (dừng sạch), ccache lưu qua `actions/cache` kể cả khi dừng
  giữa chừng để lượt sau chạy tiếp, rồi đóng gói lại dmg bằng [build-dmg.sh](../scripts/macos/build-dmg.sh)
  (dmgbuild, [dmg-settings.py](../scripts/macos/dmg-settings.py)): nền HST tiếng Việt
  ([make-dmg-background.py](../scripts/macos/make-dmg-background.py)), biểu tượng volume HST, không có hộp
  thoại giấy phép. Icon ứng dụng và tài liệu (`main.icns`, `generic-*`, `oasis-*`) do
  [stage-macos-icons.py](../scripts/macos/stage-macos-icons.py) dựng từ ảnh HST. Bước `--verify` gắn dmg,
  kiểm tên `HST Office.app`, bundle ID `vn.hasontech.hstoffice`, kiến trúc, icon, bố cục, chuỗi Info.plist
  và catalog `.mo` tiếng Việt.
- Artifact: `macos-build-<arch>-<run_id>` (log/số đo, luôn tải, 7 ngày) và
  `hst-office-macos-<arch>-dmg-<run_id>` (`HSTOffice_<version>_macOS_<arch>.dmg` + `SHA256SUMS`, chỉ khi
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
[macos-signature-probe.yml](../.github/workflows/macos-signature-probe.yml) (input `tag`).

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

[sign-notarize.sh](../scripts/macos/sign-notarize.sh) nhập chứng chỉ vào keychain tạm (luôn xóa ở bước
cuối, kể cả khi lỗi), ký app bằng chính script upstream `solenv/bin/macosx-codesign-app-bundle` với
hardened runtime và entitlement do configure sinh (`hardened_runtime.xcent`, launch constraint) — đúng
những gì `--enable-macosx-code-signing` chạy lúc đóng gói, nhưng tách khỏi job build để secret không vào
build. Sau đó dựng lại dmg cùng bố cục, ký dmg, `notarytool submit --wait`, `stapler staple`, kiểm tra
`spctl -a -t open --context context:primary-signature -v` và `codesign --verify --deep --strict`.
Artifact: `hst-office-macos-<arch>-dmg-signed-<run_id>`. `check-workflows.py` chỉ cho phép secret trong
job này, ở bước `gate` hoặc bước có điều kiện `steps.gate.outputs.enabled == 'true'`.

## Phát hành (Release)

Workflow `release.yml` (chạy tay) tạo **một** GitHub Release chứa bộ cài Windows (`.msi`),
Linux (một tệp `.deb`) và macOS (`.dmg` arm64 + x86_64) của **cùng một commit** trên
`main`; người dùng tải không cần đăng nhập. Không build lại: `scripts/release/collect-release-assets.sh`
tìm lượt build thành công mới nhất của từng nền tảng tại commit đó (hoặc dùng run id được ghim),
kiểm `SHA256SUMS` từng artifact, ưu tiên `.dmg` đã ký + notarize nếu có, gộp một `SHA256SUMS`,
rồi tạo tag tại commit đó. Thiếu bản build của nền tảng nào thì dừng với hướng dẫn. Ghi chú phát
hành lấy từ `docs/releases/<tag>.md` (thiếu thì dừng).

Quy trình: chạy `desktop-windows.yml`, `desktop-linux.yml`, `desktop-macos.yml` (`mode=full`)
trên cùng commit; khi cả ba xanh:

```bash
gh workflow run release.yml -f tag=v1.0.0-beta.2 -f prerelease=true
# tùy chọn: -f platforms="windows linux" -f commit=<sha> -f windows_run_id=<id> ...
```

Phát hành từng phần: tạo bản phát hành với `-f platforms="windows linux"`, rồi khi macOS build
xong (cùng commit) chạy lại với `-f platforms=macos -f append=true` — workflow lấy commit của tag,
không ghi đè bộ cài đã có, gộp `SHA256SUMS` theo tên tệp.

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
