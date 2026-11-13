# Gói Linux: `.deb`, `.rpm`, AppImage

Từ 1.0.2, mỗi bản Linux có ba tệp tải, cùng một nội dung (cùng cây cài `/opt/hst-office1.0`, cùng biểu tượng, launcher,
loại tệp), build **một lần**:

| Tệp | Cho ai | Cài |
|---|---|---|
| `HSTOffice_<release>_Linux_x86-64.deb` | Ubuntu 22.04+, Debian 12/13, Linux Mint 21/22 | nhấn đúp, hoặc `sudo apt install ./<tệp>` |
| `HSTOffice_<release>_Linux_x86-64.rpm` | Fedora 36+ (đã thử 40–42), openSUSE Leap 15.6 / Tumbleweed | `sudo rpm --import https://office.hasontech.vn/tai/RPM-GPG-KEY-hasontech`, rồi `sudo dnf install ./<tệp>` / `sudo zypper install ./<tệp>` |
| `HSTOffice_<release>_Linux_x86-64.AppImage` | mọi bản Linux x86-64 có glibc ≥ 2.35, libstdc++ của GCC ≥ 12 và GTK 3 | `chmod +x <tệp>` rồi chạy, không cần quyền quản trị |

**Tối thiểu (1.0.2): glibc 2.35 và libstdc++ của GCC 12** — Ubuntu 22.04+, Debian 12+, Fedora 36+, openSUSE Leap 15.6
và Tumbleweed (và các bản dựa trên chúng: Linux Mint 21+, ...). **RHEL / Rocky / Alma 9 không được hỗ trợ trong 1.0.2**
(glibc 2.34, GCC 11), xem [glibc và thư viện](#glibc-và-thư-viện).

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
  Không nhúng thông tin cập nhật/zsync; chữ ký GPG tách rời được thêm ở bước phát hành (xem [Ký số](#ký-số)).

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

## Ký số

Chủ sản phẩm quyết định (13/11/2026): **từ 1.0.2 gói Linux được ký GPG** bằng một khóa riêng cho việc đóng gói Linux.
Khóa không nằm trong kho mã; chỉ khóa công khai được commit.

**Khóa.** RSA 4096, chỉ để ký, không hết hạn, `HASON TECH Linux packages <lienhe@hasontech.vn>`. Đã thử cả RSA 4096 lẫn
Ed25519: rpm 4.14 (openSUSE Leap 15.6), 4.19 (Fedora 40) và 4.20 (Fedora 42, Tumbleweed) đều báo
`digests signatures OK`. Chọn RSA để hợp với nhiều công cụ nhất.

**Tạo khóa (chủ sản phẩm chạy, một lần):** `sudo bash setup-linux-signing-key.sh` (bản đưa riêng cho chủ sản phẩm,
không nằm trong kho mã):

- `GNUPGHOME` là `/root/.config/hst-office/linux-signing-gnupg` (quyền 0700), cạnh khóa ký manifest cập nhật
  ([UPDATE_CHECK.md](UPDATE_CHECK.md#khóa-ký)). Mật khẩu ngẫu nhiên nằm trong `passphrase` (0600). Chứng thư thu hồi
  nằm trong `openpgp-revocs.d/`.
- Khóa công khai được ghi ra `/root/.config/hst-office/RPM-GPG-KEY-hasontech`.
- Tạo GitHub environment **`linux-signing`**. Đặt secret `HST_LINUX_GPG_PRIVATE_KEY` và `HST_LINUX_GPG_PASSPHRASE`
  bằng `gh secret set` đọc từ tệp, không in ra; đặt biến `HST_LINUX_GPG_FINGERPRINT`.
- Script chỉ in dấu vân tay và các dòng OK/FAIL. Chạy lại thì dùng lại khóa đã có.

**Sau khi tạo khóa:**

1. Commit khóa công khai thành [data/hst/RPM-GPG-KEY-hasontech](../data/hst/) **trước khi build 1.0.2**.
   `make-rpm.py` chép tệp này vào `/opt/hst-office1.0/RPM-GPG-KEY-hasontech` để bộ cập nhật nhập khóa trước khi cài bản
   mới. `sign-linux-packages.sh` từ chối ký nếu tệp đã commit mang dấu vân tay khác.
2. Đăng tệp lên trang thành `/tai/RPM-GPG-KEY-hasontech`.
3. Sao lưu cả thư mục `linux-signing-gnupg` ngoại tuyến, có mã hóa, cùng chỗ với khóa manifest.

**CI.** Job `sign` của [desktop-linux.yml](../.github/workflows/desktop-linux.yml) chạy sau environment `linux-signing`.
Nó tải artifact chưa ký rồi chạy [scripts/linux/sign-linux-packages.sh](../scripts/linux/sign-linux-packages.sh):

- `rpmsign --addsign` cho `.rpm`, kiểm lại bằng `rpmkeys --checksig`;
- chữ ký tách rời `<tệp>.AppImage.asc` cho AppImage;
- danh sách `HSTOffice_<release>_Linux_x86-64.SHA256SUMS` kèm chữ ký `.SHA256SUMS.asc`. Bản phát hành giữ nguyên hai tệp
  này, vì `SHA256SUMS` chung của bản phát hành được tạo lại nên không mang chữ ký Linux được;
- khóa `RPM-GPG-KEY-hasontech`;
- `SHA256SUMS` của artifact được viết lại.

Job tải lên artifact `hst-office-linux-deb-signed-<run>`, và `collect-release-assets.sh` ưu tiên bộ đã ký. Khi chưa có
secret, bước cổng in `enabled=false` và mọi bước sau bỏ qua.

**Người dùng.**

- Cài `.rpm`: `sudo rpm --import https://office.hasontech.vn/tai/RPM-GPG-KEY-hasontech` một lần, rồi
  `dnf install` / `zypper install` như thường. **Không** dùng `--allow-unsigned-rpm`.
- Kiểm AppImage: `gpg --import RPM-GPG-KEY-hasontech && gpg --verify <tệp>.AppImage.asc <tệp>.AppImage`.
- Kiểm danh sách hash: `gpg --verify HSTOffice_<release>_Linux_x86-64.SHA256SUMS.asc` rồi
  `sha256sum -c --ignore-missing HSTOffice_<release>_Linux_x86-64.SHA256SUMS`.

**Bộ cập nhật (`.rpm`).** Khi tệp tải về đã ký (`rpm -qp` có key ID) và bản đang cài có
`/opt/hst-office1.0/RPM-GPG-KEY-hasontech`, bộ cập nhật chạy trong **cùng một** lệnh `pkexec`:
`rpm --import <khóa>` rồi `dnf` / `zypper` / `rpm -U`, **không** có `--allow-unsigned-rpm`. Gói chưa ký, hoặc bản cài
không có tệp khóa, mới đi đường cũ, có `--allow-unsigned-rpm` cho zypper. SHA-256 trong manifest đã ký Ed25519 vẫn được
kiểm trong mọi trường hợp.

**Ghi chú về dnf.** `dnf` 4/5 không kiểm GPG của tệp `.rpm` cục bộ (`localpkg_gpgcheck` mặc định tắt). dnf5 in
`skipped OpenPGP checks … @commandline`, nên `rpm -K` là cách kiểm.

AppImage nén zstd, không zsync, không chữ ký nhúng (quyết định 13/11/2026). Bộ cập nhật của HST tải nguyên tệp và kiểm
bằng manifest đã ký.

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
