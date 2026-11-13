# Gói Linux: `.deb`, `.rpm`, AppImage

Từ 1.0.2, mỗi bản Linux có ba tệp tải, cùng một nội dung (cùng cây cài `/opt/hst-office1.0`, cùng biểu tượng, launcher,
loại tệp), build **một lần**:

| Tệp | Cho ai | Cài |
|---|---|---|
| `HSTOffice_<release>_Linux_x86-64.deb` | Ubuntu 22.04+, Debian 12/13, Linux Mint 21/22 | nhấn đúp, hoặc `sudo apt install ./<tệp>` |
| `HSTOffice_<release>_Linux_x86-64.rpm` | Fedora 40–42, openSUSE Leap 15.6 / Tumbleweed (RHEL/Rocky/Alma 9 **không**: glibc 2.34 quá cũ) | `sudo dnf install ./<tệp>` / `sudo zypper install --allow-unsigned-rpm ./<tệp>` |
| `HSTOffice_<release>_Linux_x86-64.AppImage` | mọi bản Linux x86-64 có glibc ≥ 2.35, libstdc++ của GCC ≥ 12 và GTK 3 | `chmod +x <tệp>` rồi chạy, không cần quyền quản trị |

`<release>` là mã bản phát hành của [data/hst/release.json](../data/hst/release.json) (ví dụ `1.0.2`, `1.0.2-beta.1`);
phiên bản lõi 26.8.1.1 không xuất hiện ở tên hay siêu dữ liệu gói.

## Cách tạo (không build lại)

`.deb` vẫn được tạo như trước (`scripts/linux/make-single-deb.py`). Sau đó **một bước đóng gói thêm** lấy đúng phần dữ
liệu của `.deb` đó:

```sh
bash scripts/linux/ci-build.sh --rpm-appimage      # CI và hàng đợi build: sau --package, ghi vào $HST_WORK/installer
sudo scripts/build-linux.sh --rpm-appimage         # máy build cục bộ: dist/linux/ (cần rpmbuild: apt-get install rpm)
```

- [scripts/linux/make-rpm.py](../scripts/linux/make-rpm.py) (+ [rpm_spec.py](../scripts/linux/rpm_spec.py)): `rpmbuild` của
  Ubuntu 22.04 (gói `rpm`, tự cài ở bước này, **không** thêm vào `--deps` để môi trường build `.deb` không đổi).
  `Name: hst-office`, `Version: <lõi>[~<pre-release>]` (`1.0.2`, `1.0.2~beta.1`; dấu `~` xếp bản thử trước bản chính
  thức), `Release: 1`, `Vendor: HASON TECH`, `License: MPL-2.0 AND AGPL-3.0-only`. `AutoReqProv: no`: `Requires` tính từ
  `readelf` — mọi `DT_NEEDED` mà gói không tự mang theo, kèm phiên bản ký hiệu (`libc.so.6(GLIBC_2.34)(64bit)`, như
  `elfdeps` của rpm); thư viện đi kèm trong `/opt` không bị đòi hỏi và **không** được khai báo `Provides`, nên gói không
  bao giờ "cung cấp" thư viện của bản phân phối hay kéo LibreOffice của bản phân phối. `Recommends`: `urw-base35-fonts`
  (phông Symbol tương thích số đo, như `fonts-urw-base35` của `.deb`), `desktop-file-utils`, `shared-mime-info`.
  Không strip, không build-id link (`/usr/lib/.build-id` có thể đụng gói khác), không chạy `brp-*`. `%post`/`%postun`
  làm mới cơ sở MIME, launcher, bộ đệm biểu tượng; gỡ hẳn (`$1 = 0`, không phải nâng cấp) thì xóa phần còn sót trong
  `/opt/hst-office1.0`, như `postrm` của `.deb`. Bỏ các tệp chỉ dành cho Debian (lintian, `changelog.Debian.gz`).
- [scripts/linux/make-appimage.py](../scripts/linux/make-appimage.py): AppDir = dữ liệu `.deb` (bỏ `usr/bin`, vốn là
  liên kết tuyệt đối tới `/opt`) + [AppRun](../scripts/linux/appimage/AppRun) +
  [appimage_desktop_integration.py](../scripts/linux/appimage/appimage_desktop_integration.py) + launcher/biểu tượng Start
  Center ở gốc. Đóng bằng **appimagetool 1.9.1** với **runtime type-2 `20251108`** (bản tĩnh, có sẵn FUSE 3: **không cần
  `libfuse2`**), nén zstd; cả hai được ghim SHA-256 trong script và tải vào `$HST_DL/appimage-tools` (sai hash là lỗi).
  Không nhúng thông tin cập nhật/zsync, không ký (xem [Ký số](#ký-số-quyết-định-của-chủ-sản-phẩm)).

`SHA256SUMS` cạnh các gói có cả ba dòng; `collect-release-assets.sh` đưa `.rpm`, `.AppImage` (và `.AppImage.asc`,
`RPM-GPG-KEY-hasontech` khi đã ký) vào bản phát hành. Workflow [desktop-linux.yml](../.github/workflows/desktop-linux.yml)
chạy `--package` rồi `--rpm-appimage` trong cùng bước, tải lên cùng artifact `hst-office-linux-deb-<run>`.

**Hàng đợi build cục bộ** (`scripts/linux/local-build.sh`, nhánh hạ tầng build): cần gọi thêm
`ci --rpm-appimage` sau `ci --package` và chép `*.rpm *.AppImage` cùng `.deb`; nên cài sẵn gói `rpm` vào chroot gốc cùng
`ccache`. Cho tới khi có thay đổi đó, chạy `make-rpm.py`/`make-appimage.py` trên `.deb` hàng đợi trả về.

## glibc và thư viện

Build trong Ubuntu 22.04 (glibc 2.35, libstdc++ của GCC 12). Phiên bản ký hiệu cao nhất mà các tệp ELF cần:
**`GLIBC_2.35`** (từ `libm`; `libc` chỉ cần 2.34) và **`GLIBCXX_3.4.30`** / `CXXABI_1.3.13` (libstdc++ GCC 12) —
`make-rpm.py` in cả hai sau mỗi lần đóng gói. Chạy được: Ubuntu 22.04+, Debian 12+, Fedora 36+, openSUSE Leap 15.6 và
Tumbleweed, Arch. **Không** chạy: RHEL/Rocky/Alma 9 (glibc 2.34, GCC 11) — `dnf` báo rõ `nothing provides
libm.so.6(GLIBC_2.35)(64bit)` vì `.rpm` ghi các phiên bản này thành `Requires` (đã thử trên `rockylinux:9`); AppImage trên
máy như vậy không khởi động (thử trên `rockylinux:9`: thiếu `GLIBCXX_3.4.30`). AppImage **không**
mang theo thư viện hệ thống: máy cần GTK 3, NSS, CUPS, GStreamer base, X11/xcb — một máy để bàn bình thường đã có
(container tối giản thì phải cài, xem `tests/runtime/check-appimage-inside.sh`).

## Cài song song LibreOffice

Như `.deb`: cây `/opt/hst-office1.0`, lệnh `hst-office`, launcher/biểu tượng/`StartupWMClass` `vn.hasontech.hstoffice-*`,
tệp MIME `hst-office1.0.xml`; không có `Conflicts`/`Obsoletes`/`Provides` nào nhắm tới LibreOffice. Đã kiểm trên Fedora 42
với `libreoffice-writer`/`calc` của bản phân phối: không tệp chung, chạy cùng lúc, gỡ HST xong LibreOffice vẫn chạy.

## AppImage: FUSE, tích hợp menu, gỡ

- **FUSE:** runtime tĩnh tự gắn bằng FUSE 3, chỉ cần lệnh `fusermount3` (gói `fuse3`, có sẵn trên Ubuntu 22.04+, Fedora,
  Debian 12, Arch). Máy không có FUSE: runtime báo `No suitable fusermount binary found`; chạy
  `./HSTOffice_<release>_Linux_x86-64.AppImage --appimage-extract-and-run` (hoặc đặt `APPIMAGE_EXTRACT_AND_RUN=1`).
- **Lần chạy đầu** (và mỗi khi tệp AppImage đổi chỗ/đổi tên): AppRun chạy python đi kèm để ghi vào `$XDG_DATA_HOME`
  (mặc định `~/.local/share`) các launcher `vn.hasontech.hstoffice-*.desktop` (lệnh `Exec` trỏ tới chính tệp AppImage,
  đã trích dẫn theo đặc tả), biểu tượng `icons/hicolor`, gói MIME `mime/packages/vn.hasontech.hstoffice-appimage.xml`, rồi
  làm mới `update-mime-database`/`update-desktop-database`/`gtk-update-icon-cache` nếu có, và báo một lần bằng
  `notify-send`. Không cần quyền quản trị. Trạng thái: `~/.local/share/hst-office/appimage-integration.{json,state}`.
  Launcher dùng cùng id với gói hệ thống nên `StartupWMClass`, app_id Wayland và câu hỏi "ứng dụng mặc định" của HST
  hoạt động như nhau. Đã cài `.deb`/`.rpm` (có `/usr/share/applications/vn.hasontech.hstoffice-startcenter.desktop`):
  không tự tích hợp (tránh che launcher hệ thống); muốn thì chạy với `--install-desktop-integration`.
- **Gỡ khỏi menu:** chuột phải biểu tượng HST Office → **Gỡ khỏi menu ứng dụng**, hoặc
  `<tệp>.AppImage --remove-desktop-integration`. Chỉ xóa đúng các tệp đã ghi (nằm trong `$XDG_DATA_HOME`), và ghi nhớ
  lựa chọn: lần chạy sau không tự thêm lại. `HST_APPIMAGE_NO_INTEGRATION=1` tắt việc tự tích hợp (máy dùng chung).
  Gỡ hẳn = gỡ khỏi menu rồi xóa tệp AppImage; hồ sơ người dùng (`~/.config/hstoffice`) giữ nguyên như các gói khác.

## Cập nhật trong ứng dụng

Xem [UPDATE_INSTALL.md](UPDATE_INSTALL.md): ứng dụng tự nhận ra mình được cài bằng `.deb` (dpkg sở hữu
`program/soffice`), `.rpm` (rpm sở hữu) hay chạy từ AppImage (`$APPIMAGE`, chương trình nằm trong `$APPDIR`), rồi lấy
đúng bộ cài `linux`, `linux-rpm` hay `linux-appimage` từ `latest-3.json` đã ký.

## Ký số (quyết định của chủ sản phẩm)

Hiện tại `.rpm` và `.AppImage` **chưa ký GPG**. Tính toàn vẹn được bảo đảm bằng `SHA256SUMS` trên trang tải và, với cập
nhật trong ứng dụng, bằng SHA-256 + kích thước nằm trong manifest **đã ký Ed25519** (kiểm khi tải và kiểm lại ngay trước
khi cài). Hệ quả với người dùng: `dnf` (4 và 5) cài tệp `.rpm` cục bộ chưa ký không hỏi gì (`localpkg_gpgcheck` mặc định
tắt); `zypper` từ chối ("Package header is not signed!") nếu không có `--allow-unsigned-rpm` — hướng dẫn trên trang tải
và bộ cập nhật đều dùng cờ này.

Khi chủ sản phẩm quyết định ký (không tạo, không lưu khóa trong kho mã):

1. Tạo khóa ký riêng cho gói Linux trên máy tin cậy (ví dụ `gpg --quick-gen-key "HASON TECH Linux packages
   <lienhe@hasontech.vn>" rsa4096 sign 3y`), sao lưu ngoại tuyến, ghi lại dấu vân tay 40 ký tự.
2. GitHub: tạo environment **`linux-signing`** (nên bật người duyệt), thêm secret `HST_LINUX_GPG_PRIVATE_KEY`
   (`gpg --armor --export-secret-keys <vân tay>`), `HST_LINUX_GPG_PASSPHRASE`, và biến `HST_LINUX_GPG_FINGERPRINT`.
3. Job `sign` của `desktop-linux.yml` tự bật: tải artifact chưa ký, chạy
   [scripts/linux/sign-linux-packages.sh](../scripts/linux/sign-linux-packages.sh) (`rpmsign --addsign`, kiểm bằng
   `rpmkeys --checksig`; chữ ký tách rời `<tệp>.AppImage.asc`; xuất khóa công khai `RPM-GPG-KEY-hasontech`; viết lại
   `SHA256SUMS`), tải lên `hst-office-linux-deb-signed-<run>`; `collect-release-assets.sh` ưu tiên bộ đã ký. Không có
   secret: bước cổng in `enabled=false`, mọi bước sau bỏ qua, job vẫn xanh.
4. Đăng `RPM-GPG-KEY-hasontech` lên trang (ví dụ `/tai/RPM-GPG-KEY-hasontech`) và thêm vào hướng dẫn:
   `sudo rpm --import https://office.hasontech.vn/tai/RPM-GPG-KEY-hasontech`; khi đó bỏ `--allow-unsigned-rpm` ở
   hướng dẫn zypper và ở `update_helper_scripts_linux.py`.
5. AppImage: chữ ký `.asc` tách rời (kiểm: `gpg --verify <tệp>.asc <tệp>`). Chữ ký nhúng (`appimagetool --sign`) và cập nhật
   delta zsync (`appimagetool -u "zsync|https://office.hasontech.vn/tai/HSTOffice-latest-x86_64.AppImage.zsync"`, cần
   phục vụ tệp `.zsync` ổn định trên trang) là các lựa chọn thêm, chưa bật: bộ cập nhật của HST đã tải nguyên tệp và
   kiểm bằng manifest đã ký.

## Kiểm thử

```sh
# .rpm: cài (dnf/zypper, tệp chưa ký), launcher/biểu tượng/MIME, mở-lưu .docx/.xlsx tiếng Việt, GUI dưới Xvfb, rpm -U, gỡ
IMAGE=fedora:42 tests/runtime/check-rpm-install.sh dist/linux/HSTOffice_<release>_Linux_x86-64.rpm
IMAGE=fedora:42 COEXIST=1 tests/runtime/check-rpm-install.sh ...   # + LibreOffice của Fedora cùng lúc
# AppImage: không FUSE / chỉ fuse3 (không libfuse2), tích hợp menu, đổi chỗ, gỡ, mở-lưu, GUI
IMAGE=ubuntu:22.04 tests/runtime/check-appimage.sh dist/linux/HSTOffice_<release>_Linux_x86-64.AppImage
```

`IMAGE` đã chạy: rpm — `fedora:40`, `fedora:41`, `fedora:42`, `opensuse/leap:15.6`, `opensuse/tumbleweed`; AppImage —
`ubuntu:22.04`, `ubuntu:24.04`, `debian:12`, `fedora:41`, `archlinux:latest` (bước GUI tự bỏ qua trong container Arch: bộ
nạp ảnh glycin của GTK cần namespace của `bwrap` mà docker không cho, một chương trình GTK 3 bất kỳ cũng lỗi y hệt).
Cập nhật trong ứng dụng, bước cài thật: `tests/runtime/check-linux-package-update.sh rpm|appimage <cũ> <mới> [image]`
(Fedora 42 qua dnf5, Tumbleweed qua zypper, AppImage trên Ubuntu 24.04). Unit: `tests/unit/test_linux_rpm_appimage_packaging.py`.
