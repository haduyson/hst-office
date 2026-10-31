# "Cập nhật ngay": tải và cài bản mới bằng một cú nhấp

Mở rộng của [kiểm tra phiên bản mới](UPDATE_CHECK.md). Không bao giờ cài ngầm: chỉ tải khi người dùng bấm
**Cập nhật ngay**, chỉ cài sau khi họ trả lời "Cập nhật ngay" cho câu hỏi "Đóng HST Office để cập nhật?".
Nút "Tải về" (tải thủ công bằng trình duyệt), "Xem điểm mới" và "Bỏ qua phiên bản này" vẫn còn. Chữ hiển thị theo
ngôn ngữ giao diện (vi/en), như phần kiểm tra cập nhật.

## Luồng

1. Nút có trên thanh thông tin và hộp thoại HST ▸ Kiểm tra cập nhật… khi manifest có bộ cài cho hệ điều hành này
   (`windows`, `linux`, `macos-arm`, `macos-intel`) và quản trị viên không tắt `AllowInstall`.
2. Bấm: luồng nền tải lại manifest và **kiểm lại chữ ký Ed25519**, chọn bộ cài, tải về thư mục cache của người dùng
   (Windows `%LOCALAPPDATA%\HSTOffice\update`, macOS `~/Library/Caches/HSTOffice/update`, Linux
   `$XDG_CACHE_HOME/hst-office/update`) kèm hộp thoại tiến độ có nút Hủy. Tệp chỉ đổi tên từ `.part` sau khi **kích thước
   và SHA256 khớp** giá trị trong manifest đã ký. Lỗi bất kỳ (mạng, kích thước, hash, chữ ký, chuyển hướng sang máy lạ):
   báo rõ và đưa nút "Tải về".
3. Hỏi "Đã tải xong HST Office X. Đóng HST Office để cập nhật?" [Cập nhật ngay] [Để sau]. "Để sau" giữ tệp; lần bấm
   sau dùng lại tệp **sau khi kiểm lại** (không tải lại). Tệp cũ khác tên bị dọn; `update.log` được giữ.
4. Đồng ý: ghi tệp trợ giúp nhỏ vào cache, chạy tách rời, rồi đóng HST Office bằng đường terminate thông thường
   (tài liệu đã sửa vẫn hiện hộp hỏi lưu; chọn Hủy thì hủy cập nhật và dừng trợ giúp). Trợ giúp đợi tiến trình soffice
   thoát, **kiểm lại SHA256 ngay trước khi cài**, chạy bộ cài, xóa tệp nếu thành công, rồi mở lại HST Office (cả khi cài
   lỗi: mở bản cũ). Nhật ký ở `update.log` trong thư mục cache.

| Hệ điều hành | Cách cài |
|---|---|
| Windows | `powershell` chạy `msiexec /i <msi> /passive /norestart` nâng quyền qua UAC (MSI nâng cấp bản cũ) |
| Linux | `.deb` đơn: `pkexec env DEBIAN_FRONTEND=noninteractive apt-get install -y <deb>`, hoặc `pkcon install-local` (hỏi mật khẩu quản trị). Thiếu cả hai: báo rõ trước khi đóng, dùng "Tải về" |
| macOS | gắn dmg, `codesign --verify --deep --strict`, `spctl --assess`, Team ID phải là `74AT34P945`; chép bản mới cạnh bản cũ, kiểm lại, đổi tên bản cũ sang `.hst-old`, đưa bản mới vào chỗ, rồi mới xóa bản cũ (hỏng thì khôi phục); quyền quản trị qua `osascript ... with administrator privileges` khi thư mục không ghi được; mở lại bằng `open` |

Linux chỉ hỗ trợ bộ cài là **một tệp `.deb`** (`HSTOffice_<ver>_Linux_x86-64.deb`); bản phát hành cũ dạng
`.deb.tar.gz` chỉ có "Tải về".

## Manifest schema 2

`https://office.hasontech.vn/update/latest-2.json` (+ `.sig`) là schema 1 cộng khóa `installers` cho mỗi bản:

```json
"installers": {"windows": {"url": "https://github.com/haduyson/hst-office/releases/download/v1.0.0-beta.4/HSTOffice_1.0.0_Win_x86-64_en-US_vi.msi",
                           "sha256": "<64 hex thường>", "size": 222650368}}
```

- `url`: https tới `hasontech.vn` hoặc `github.com/haduyson/hst-office/releases/download/...`; đuôi `.msi`/`.dmg`/`.deb` đúng
  nền tảng. Chuyển hướng chỉ được tới `github.com`, `*.githubusercontent.com`, `hasontech.vn`.
- Ứng dụng chấp nhận schema 1 và 2 (schema 1: không có `installers`, chỉ "Tải về").
- **`latest.json` giữ schema 1** cho các bản đã cài (beta.2, beta.3 chỉ chấp nhận `schema == 1`; đổi thẳng sang 2 sẽ làm
  họ không còn nhận thông báo). Bản mới đọc `latest-2.json`, nếu lỗi mạng thì rơi về `latest.json`.

## Phát hành

```sh
python3 scripts/release/generate-update-manifest.py --tag v1.0.0-beta.4 --sums SHA256SUMS --assets-dir <thư mục collect-release-assets>
#  hoặc: --gh-tag v1.0.0-beta.4 (đọc kích thước từ GitHub Release)
python3 scripts/release/sign-update-manifest.py website/office.hasontech.vn/update/latest-2.json
python3 scripts/release/sign-update-manifest.py website/office.hasontech.vn/update/latest.json
```

Bộ sinh điền `sha256`/`size`/URL từ `SHA256SUMS` của bản phát hành, giữ kênh còn lại, tự kiểm bằng bộ đọc của ứng dụng
và không bao giờ đọc khóa ký (cách ký không đổi). Tải **cả hai** cặp tệp lên `update/`.

## Quản trị viên

`AllowInstall=false` chỉ để lại "Tải về". Đọc qua `update_config` (lớp cấu hình lõi, khóa bằng `.xcd`/registry/profile
macOS; tài liệu quản trị do phần khóa cấu hình cập nhật nắm) và vẫn nhận lớp cũ: gói
`python3 scripts/release/build-update-policy-oxt.py --no-install --keep-autocheck` (`unopkg add --shared`).

## Kiểm thử

- Unit: `tests/unit/test_update_installer.py` (schema 2, hash/kích thước, chọn nền tảng, bộ sinh manifest),
  `test_update_prepare.py` (tải, kiểm, dùng lại, hủy, chính sách), `test_update_helper.py` (dòng lệnh trợ giúp mỗi hệ
  điều hành; chạy thật tập lệnh sh với công cụ giả).
- Runtime Linux: `python3 tests/runtime/check-update-install.py` (máy chủ cục bộ, .deb giả, bước cài chạy dry-run).
- Windows: `tests/runtime/check-update-install-smoke.py` trong [windows-smoke.yml](../.github/workflows/windows-smoke.yml).
- Chưa chạy thật trên Windows/macOS (không có máy); chưa thử cài `.deb` thật.
