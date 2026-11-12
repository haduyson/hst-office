# Phiên bản trước và tự lưu khôi phục (từ 1.0.2)

Hai cơ chế giúp người dùng lấy lại công việc. Hướng dẫn cho người dùng:
[help/khoi-phuc-tai-lieu.html](../extensions/hst-vietnamese-tools/help/khoi-phuc-tai-lieu.html).

## Tự lưu thông tin khôi phục: 3 phút

[`RecoveryDefaults.xcu`](../extensions/hst-vietnamese-tools/RecoveryDefaults.xcu) của extension đi kèm đặt
`/org.openoffice.Office.Recovery/AutoSave/TimeIntervall` = `3` (mặc định gốc 10) và giữ `UserAutoSaveEnabled` =
`false`: chỉ bản khôi phục trong thư mục backup của hồ sơ được ghi 3 phút một lần, tệp của người dùng không bao giờ bị
tự lưu đè. Giá trị người dùng (Công cụ ▸ Tùy chọn ▸ Tải/Lưu ▸ Chung) hoặc quản trị viên đặt vẫn thắng giá trị mặc định này.

## Phiên bản trước

Mỗi lần lưu đè một tệp đã có trên đĩa (mọi định dạng), bản trên đĩa ngay trước khi ghi đè được cất vào
`<hồ sơ người dùng>/user/hst-versions/`. Lệnh `org.hst.office.vi:PreviousVersions` mở hộp thoại "Phiên bản trước"
(Mở xem: bản sao chỉ đọc; Khôi phục: cất bản hiện tại trước, đóng tài liệu, thay tệp, mở lại).

| Thành phần | Tệp |
|---|---|
| Kho (chép, trùng, giới hạn, dọn, khóa, chỉ mục hỏng) | `python/hst_office/version_store.py`, `version_files.py` |
| Thời điểm chép | `version_capture.py`, job `version_job.py` (`Jobs.xcu`: `OnModifyChanged`, `OnSave`, `OnUnload`) |
| Hộp thoại, khôi phục | `version_dialog.py`, `version_restore.py`, chuỗi `version_texts.py` |
| Cài đặt, khóa quản trị | `version_config.py`, schema `previousversions.xcs`, trang `dialogs/PreviousVersions.xdl` + `version_options.py` |
| Menu | `Addons.xcu` (`OfficeMenuBarMerging`: Tệp tin ▸ Phiên bản trước, sau "Phiên bản"), `FeatureSearch.xcu` |
| Bảng Tệp tin của giao diện theo thẻ | nút "Phiên bản trước" ở trang Thông tin: bản vá lõi `hst-backstage-previous-versions.patch` (chưa vào series lúc viết) |

### Kho

- Mỗi tệp một thư mục `sha1(đường dẫn đầy đủ đã chuẩn hóa)` (NFC; Windows không phân biệt hoa thường), nên hai tệp
  trùng tên khác thư mục không lẫn nhau. Bản cất: `<giờ UTC của nội dung>-<sha256[:8]><đuôi>`; `index.json` ghi đường
  dẫn gốc và, cho mỗi bản, giờ lưu nội dung, giờ cất, kích thước, SHA-256.
- Giới hạn (quyết định chủ dự án): tối đa 10 bản hoặc 30 ngày mỗi tệp; cả kho tối đa 2 GB, bản cũ nhất của bất kỳ tệp
  nào bị xóa trước. Không cất tệp > 100 MB; không cất khi nội dung trùng (SHA-256) bản mới nhất của chính tệp đó.
- Mọi thay đổi chỉ mục/bản cất diễn ra dưới một khóa hệ điều hành của cả kho (`store.lock`, `flock`/`msvcrt`, chờ tối đa
  5 giây) và ghi qua tệp tạm + đổi tên, nên hai tiến trình office hay một lần sập máy chỉ để lại trạng thái cũ hoặc mới.
  Chỉ mục hỏng được dựng lại từ các bản cất; bản cất chưa có trong chỉ mục được thêm lại, không bị xóa.

### Thời điểm chép (không làm treo giao diện)

`OnSave` được phát đồng bộ trên luồng giao diện ngay trước khi office ghi tệp (`SfxBaseModel::storeSelf`: `NotifyEvent`
đồng bộ rồi `Save_Impl`; job chạy đồng bộ qua `JobExecutor`). Chép trong `OnSave` thì đúng nội dung nhưng chặn giao
diện bằng đúng thời gian chép; chép ở luồng nền song song với lúc office ghi thì sai: trên Windows tệp được thay bằng
`osl::File::replace` (đổi tên), một handle đang đọc không có `FILE_SHARE_DELETE` làm việc thay thất bại, còn khi ghi đè
tại chỗ thì bản chép bị trộn.

Cách làm: khi tài liệu chuyển sang trạng thái đã sửa (`OnModifyChanged`), tệp trên đĩa chính là tệp lần lưu kế tiếp
sẽ ghi đè, nên một luồng nền chép nó vào tệp tạm trong kho (băm SHA-256 trong lúc chép, bỏ nếu tệp đổi trong lúc
chép). Tại `OnSave` chỉ còn so kích thước + thời gian sửa của tệp với bản đã chép rồi đổi tên bản đó vào kho
(một `rename` và một chỉ mục nhỏ). Chỉ khi không có bản dùng được (lưu mà không sửa, tệp bị chương trình khác đổi,
bản chép chưa xong) thì `OnSave` mới chờ/chép, tối đa `WAIT_SECONDS` = 3 giây; quá hạn thì bỏ phiên bản đó, ghi nhật ký,
và việc lưu vẫn tiếp tục. Lỗi chép không bao giờ chặn việc lưu. `OnUnload` xóa bản chép không dùng đến.

Đo bằng `version_store` trên máy build Linux (SSD, tệp vừa ghi nên còn trong bộ đệm; trung vị 3 lần):

| Tệp | Chép nền (`stage`) | `OnSave` khi đã có bản chép | `OnSave` phải tự chép |
|---|---|---|---|
| 1 MB | 0,009 s | 0,002 s | 0,012 s |
| 10 MB | 0,10 s | 0,003 s | 0,10 s |
| 100 MB | 0,91 s | 0,003 s | 0,92 s |

Trên ổ mạng hay USB chậm (ví dụ 5 MB/s), tự chép 10 MB mất khoảng 2 giây và 100 MB khoảng 20 giây; vì vậy việc chép đặt
ở luồng nền và `OnSave` không bao giờ chờ quá 3 giây. Giới hạn 2 GB của cả kho cần đọc mọi chỉ mục (0,19 s với 1 000
tệp trên SSD), nên chạy ở luồng nền sau mỗi lần cất; lúc lưu chỉ áp giới hạn của chính tệp đó (0,002 s với 1 000 tệp).

### Không bảo vệ

Lần lưu đầu của tệp mới; "Lưu thành" đè lên một tệp khác đã có (đích của Lưu thành không có trong sự kiện
`OnSaveAs`); thay đổi do chương trình khác giữa hai lần lưu; tệp bị xóa/đổi tên/di chuyển bên ngoài; tệp > 100 MB;
tài liệu không nằm trên ổ đĩa (URL không phải `file:`); lưu trên ổ quá chậm để chép trong 3 giây ngay sau khi sửa.

### Quyền riêng tư

Bản cất chỉ nằm trong hồ sơ người dùng trên máy, không bao giờ gửi đi ([PRIVACY](PRIVACY.md)). Nhật ký cục bộ chỉ ghi
kết quả (`stored`, `timeout`…) và thời gian, không ghi đường dẫn hay tên tệp.

## Khóa cho quản trị viên

Thuộc tính `/org.hasontech.hstoffice.PreviousVersions/Enabled` (boolean, mặc định `true`) nằm trong schema của extension.
Lớp chính sách HKLM của lõi được đọc trước khi extension đi kèm đăng ký schema nên lõi bỏ qua giá trị đó; vì vậy
`version_config.py` tự đọc. Thứ tự ưu tiên: chính sách Windows > hồ sơ macOS > giá trị `finalized` trong cấu hình >
giá trị người dùng. Khi bị khóa, ô "Lưu phiên bản trước khi ghi đè tệp" bị làm mờ. Nút "Xóa toàn bộ phiên bản đã lưu"
vẫn dùng được (bản cất là dữ liệu của người dùng).

Windows (cả máy; `HKEY_CURRENT_USER\Software\Policies\...` cho một người dùng), cùng định dạng khóa cập nhật
([UPDATE_ADMIN](UPDATE_ADMIN.md)):

```reg
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\SOFTWARE\Policies\HASON TECH\HST Office\org.hasontech.hstoffice.PreviousVersions\Enabled]
"Value"="false"
"Final"=dword:00000001
```

macOS: từ điển `PreviousVersions` trong managed preferences của miền `vn.hasontech.hstoffice` (cùng hồ sơ cấu hình với
`HSTUpdate`):

```xml
<key>PreviousVersions</key>
<dict>
  <key>Enabled</key><false/>
</dict>
```

Linux (và mọi hệ điều hành): một extension chính sách cài chung (`unopkg add --shared`) chứa tệp `.xcu` sau (khai báo
trong `META-INF/manifest.xml` với kiểu `application/vnd.sun.star.configuration-data`). Tệp `.xcd` trong
`share/registry` **không** dùng được cho thuộc tính này, vì lớp đó được đọc trước schema của extension.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<oor:component-data xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema"
                    oor:name="PreviousVersions" oor:package="org.hasontech.hstoffice">
  <prop oor:name="Enabled" oor:finalized="true"><value>false</value></prop>
</oor:component-data>
```

## Kiểm tra

- `tests/unit/test_version_store.py`, `test_version_capture.py`, `test_version_config.py`, `test_version_restore.py`.
- Cần kiểm GUI trên Windows, macOS, Linux trước khi phát hành: mục menu và nút trên trang Thông tin, hộp thoại, Mở xem,
  Khôi phục (đóng/mở lại tài liệu, tệp đang bị khóa trên Windows), trang Tùy chọn, khóa registry/hồ sơ macOS, lưu trên
  ổ mạng/USB chậm.
