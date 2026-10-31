# Khóa kiểm tra cập nhật cho quản trị viên

Từ v1.0.0-beta.4, cài đặt kiểm tra cập nhật nằm trong **lõi** HST Office, ở nút cấu hình
`/org.openoffice.Office.HSTUpdate` (schema `officecfg/.../Office/HSTUpdate.xcs`, thêm bằng
[`hst-update-config.patch`](../patches/libreoffice/hst-update-config.patch)). Nhờ vậy quản trị viên khóa được bằng các
cơ chế cấu hình chuẩn của LibreOffice: tệp `.xcd` trong `share/registry`, khóa registry chính sách trên Windows, hoặc hồ
sơ cấu hình (managed preferences) trên macOS. Thuộc tính có `finalized` thì người dùng không sửa được: hộp kiểm và mục
menu tương ứng bị làm mờ, và việc kiểm tra tuân theo giá trị bị khóa.

Cách kiểm tra cập nhật hoạt động: [UPDATE_CHECK](UPDATE_CHECK.md). Cài bản mới bằng "Cập nhật ngay":
[UPDATE_INSTALL](UPDATE_INSTALL.md).

## Các thuộc tính

| Thuộc tính | Kiểu | Mặc định | Ý nghĩa |
|---|---|---|---|
| `AutoCheck` | boolean | `true` | Tự kiểm tra khi khởi động |
| `ManualCheck` | boolean | `true` | Cho phép mục menu "Kiểm tra cập nhật…". `false`: mục menu bị làm mờ, HST Office không bao giờ liên hệ máy chủ cập nhật |
| `CheckIntervalHours` | int | `24` | Khoảng cách tối thiểu giữa hai lần tự kiểm tra, tính bằng giờ (1–8760) |
| `AllowInstall` | boolean | `true` | Hiện nút "Cập nhật ngay". `false`: chỉ còn "Tải về" thủ công |
| `Channel` | string | rỗng | Kênh phát hành. Rỗng: theo bản đang cài (bản beta thấy beta và chính thức). `stable`: chỉ bản chính thức. `beta`: cả beta |
| `LastCheck`, `SkippedVersion` | long, string | `0`, rỗng | Trạng thái riêng của từng người dùng; không cần khóa |

Muốn tắt hẳn mọi kết nối tới máy chủ cập nhật, khóa cả `AutoCheck = false` và `ManualCheck = false`.

Thứ tự ưu tiên khi nhiều nơi cùng đặt một giá trị: giá trị bị khóa trong lõi (`.xcd`, registry Windows, extension dùng
chung) > hồ sơ macOS > giá trị bị khóa bằng gói chính sách cũ `hst-update-policy.oxt` > giá trị người dùng/mặc định.

## Linux và macOS: tệp `.xcd`

Tạo tệp, ví dụ `hst-update-policy.xcd` (tên bất kỳ, đuôi `.xcd`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<oor:data xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xmlns:oor="http://openoffice.org/2001/registry">
  <dependency file="main"/>
  <oor:component-data oor:name="HSTUpdate" oor:package="org.openoffice.Office">
    <prop oor:name="AutoCheck" oor:finalized="true"><value>false</value></prop>
    <prop oor:name="ManualCheck" oor:finalized="true"><value>false</value></prop>
    <prop oor:name="AllowInstall" oor:finalized="true"><value>false</value></prop>
  </oor:component-data>
</oor:data>
```

Có thể sinh tệp này bằng `python3 scripts/release/build-update-policy-oxt.py --xcd hst-update-policy.xcd [--no-install] [--no-manual-check] [--enable]`. Chỉ giữ những dòng `prop` muốn khóa. Ví dụ chỉ giãn tần suất xuống một tuần và giữ kênh chính thức:

```xml
    <prop oor:name="CheckIntervalHours" oor:finalized="true"><value>168</value></prop>
    <prop oor:name="Channel" oor:finalized="true"><value>stable</value></prop>
```

Đặt tệp vào thư mục `share/registry` của bản cài (quyền root/quản trị viên), rồi khởi động lại HST Office:

| Hệ điều hành | Thư mục |
|---|---|
| Linux (`.deb`) | `/opt/hst-office1.0/share/registry/` |
| Windows | `share\registry\` trong thư mục cài (thường là `C:\Program Files\HST Office\share\registry\`); có thể dùng thay cho registry |
| macOS | `HST Office.app/Contents/Resources/registry/` — **làm hỏng chữ ký ứng dụng**, nên trên macOS hãy dùng hồ sơ cấu hình bên dưới |

```sh
sudo install -m 644 hst-update-policy.xcd /opt/hst-office1.0/share/registry/
```

Gói `.deb` không sở hữu tệp này nên nó được giữ nguyên khi nâng cấp HST Office. Gỡ khóa: xóa tệp.

## Windows: registry chính sách

HST Office đọc khóa chính sách giống LibreOffice, dưới `HKEY_LOCAL_MACHINE\SOFTWARE\Policies\LibreOffice` (cho cả máy)
hoặc `HKEY_CURRENT_USER\Software\Policies\LibreOffice` (cho một người dùng). Mỗi thuộc tính là một khóa con, có giá trị
chuỗi `Value` và DWORD `Final` = 1 để khóa:

```reg
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\SOFTWARE\Policies\LibreOffice\org.openoffice.Office.HSTUpdate\AutoCheck]
"Value"="false"
"Final"=dword:00000001

[HKEY_LOCAL_MACHINE\SOFTWARE\Policies\LibreOffice\org.openoffice.Office.HSTUpdate\ManualCheck]
"Value"="false"
"Final"=dword:00000001

[HKEY_LOCAL_MACHINE\SOFTWARE\Policies\LibreOffice\org.openoffice.Office.HSTUpdate\AllowInstall]
"Value"="false"
"Final"=dword:00000001

[HKEY_LOCAL_MACHINE\SOFTWARE\Policies\LibreOffice\org.openoffice.Office.HSTUpdate\CheckIntervalHours]
"Value"="168"
"Final"=dword:00000001
```

Với PowerShell (quyền quản trị viên):

```powershell
$k = 'HKLM:\SOFTWARE\Policies\LibreOffice\org.openoffice.Office.HSTUpdate\AutoCheck'
New-Item -Path $k -Force | Out-Null
Set-ItemProperty -Path $k -Name Value -Value 'false'
Set-ItemProperty -Path $k -Name Final -Value 1 -Type DWord
```

Triển khai hàng loạt bằng Group Policy Preferences (Registry) với đúng các khóa trên. `Value` luôn là chuỗi
(`true`/`false`, số, hoặc `stable`/`beta`). Gỡ khóa: xóa khóa con.

## macOS: hồ sơ cấu hình (managed preferences)

LibreOffice không có lớp cấu hình macOS riêng, nên extension HST đọc trực tiếp managed preferences của miền
`vn.hasontech.hstoffice` (mã gói của HST Office): từ điển `HSTUpdate`, cùng tên thuộc tính như trên. Mọi giá trị trong
hồ sơ đều được coi là đã khóa. Triển khai qua MDM (Jamf, Intune, Mosyle, Kandji…) bằng payload "Custom Settings"/
Application & Custom Settings với miền `vn.hasontech.hstoffice` và nội dung:

```xml
<key>HSTUpdate</key>
<dict>
  <key>AutoCheck</key><false/>
  <key>ManualCheck</key><false/>
  <key>AllowInstall</key><false/>
  <key>CheckIntervalHours</key><integer>168</integer>
  <key>Channel</key><string>stable</string>
</dict>
```

Hoặc một tệp `.mobileconfig` đầy đủ (thay các UUID bằng `uuidgen`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadType</key><string>Configuration</string>
  <key>PayloadVersion</key><integer>1</integer>
  <key>PayloadIdentifier</key><string>vn.hasontech.hstoffice.update-policy</string>
  <key>PayloadUUID</key><string>00000000-0000-0000-0000-000000000001</string>
  <key>PayloadDisplayName</key><string>HST Office — khóa kiểm tra cập nhật</string>
  <key>PayloadScope</key><string>System</string>
  <key>PayloadContent</key>
  <array>
    <dict>
      <key>PayloadType</key><string>vn.hasontech.hstoffice</string>
      <key>PayloadVersion</key><integer>1</integer>
      <key>PayloadIdentifier</key><string>vn.hasontech.hstoffice.update-policy.settings</string>
      <key>PayloadUUID</key><string>00000000-0000-0000-0000-000000000002</string>
      <key>HSTUpdate</key>
      <dict>
        <key>AutoCheck</key><false/>
        <key>AllowInstall</key><false/>
      </dict>
    </dict>
  </array>
</dict>
</plist>
```

macOS ghi hồ sơ ra `/Library/Managed Preferences/vn.hasontech.hstoffice.plist` (cả máy) hoặc
`/Library/Managed Preferences/<tên người dùng>/vn.hasontech.hstoffice.plist`; HST Office đọc hai tệp này (hồ sơ theo
người dùng ghi đè hồ sơ cả máy). `defaults write` vào `/Library/Preferences` **không** phải là khóa và bị bỏ qua.

## Tương thích với bản cũ

- Bản beta.2/beta.3 lưu cài đặt ở `/org.hasontech.hstoffice.UpdateCheck` (schema `update.xcs` của extension). Lần đầu
  chạy bản mới, các giá trị người dùng đã đổi ở đó (`AutoCheck`, `AllowInstall`, `LastCheck`, `SkippedVersion`) được
  chép **một lần** sang `/org.openoffice.Office.HSTUpdate` (cờ `LegacyMigrated`).
- Gói chính sách cũ `hst-update-policy.oxt` (cài bằng `unopkg add --shared`) vẫn có hiệu lực: giá trị nó khóa ở
  nút cũ vẫn được coi là khóa. Khi chuyển sang `.xcd`/registry, gỡ gói cũ bằng
  `unopkg remove --shared vn.hasontech.hst.update-policy`.
- Trên bản cài cũ chưa có schema lõi, tệp `.xcd`/registry ở trên không có tác dụng; dùng gói chính sách cũ.

## Kiểm tra

- Công cụ ▸ Tùy chọn ▸ HST Office/Nâng cao ▸ Trình soạn cấu hình chuyên gia, tìm `HSTUpdate`: thuộc tính bị khóa
  không sửa được.
- Hộp kiểm "Tự động kiểm tra cập nhật khi khởi động" trong hộp thoại kiểm tra cập nhật bị làm mờ khi `AutoCheck` bị
  khóa; mục menu "Kiểm tra cập nhật…" bị làm mờ khi `ManualCheck` = `false`.
- Kiểm thử tự động trên Linux: `tests/runtime/check-update-lock.py`.
