# Catalog giao diện riêng của HST Office

## Quyết định

Mỗi miền gettext có trong danh sách đóng gói của LibreOffice có một miền HST tương ứng, ví dụ
`hst-sfx` cho `sfx`. Khóa giữ nguyên cặp ngữ cảnh và văn bản nguồn, kể cả
khóa số nhiều. Cùng một nhãn ở hai mô-đun có thể có hai bản dịch khác nhau.

Nguồn bản dịch HST nằm trong `l10n/`. Build đọc catalog gốc và tạo cây trung
gian riêng dưới `hst/l10n/` trong cây build. Các tài nguyên dịch lúc build
(XCU, ULF và bộ cài) đọc bản ghép ở đó. PO và MO mang tên LibreOffice lấy nội
dung từ thượng nguồn. Với khóa HST, bản dịch tiếng Việt phải giữ cả dấu tổ
hợp, phím gợi nhớ, khoảng trắng và biến thay thế của bản phát hành.

Catalog tiếng Việt và tiếng Anh Mỹ cùng dùng bộ khóa trong `l10n/hst/templates`.
Các sửa đè có lý do vẫn do `l10n/vi-overrides.jsonl` quản lý. Khi áp series,
trình áp patch bỏ qua các hunk PO lịch sử đã chuyển sang catalog. CI kiểm tra
dấu vân tay của từng nhóm hunk đã nghỉ sử dụng và chặn mọi hunk mới nhắm vào
`translations/source`. Nhờ đó có thể bảo toàn các patch dùng chung với nhóm
ribbon trong khi nâng lõi mà không áp lại một hunk dịch nào.

## Tra cứu và đóng gói

GtkBuilder chọn một miền cho toàn bộ hộp thoại. Vì vậy catalog HST phục vụ
hộp thoại hỗn hợp chứa cả những khóa cần kế thừa từ mô-đun gốc. Thứ tự ưu
tiên khi tạo catalog là bản HST của khóa, bản dịch thượng nguồn cùng ngôn
ngữ, rồi văn bản nguồn. Danh sách miền lấy từ các khai báo AllLangMoTarget và MO_FILELIST_ALL_LANG. Cách này giữ nguyên cơ chế lấy văn bản nguồn cho mô-đun mà bộ cài gốc thiếu MO. VCL và GTK dùng cùng một miền của tài nguyên đã cài.
Việc gán miền trên bản .ui để đóng gói cho phép giữ nguyên các patch ribbon.
Translate::Create dùng miền tương ứng cho các TranslateId. Tiếng Anh Mỹ có
nguồn PO riêng cho khóa HST. Ngôn ngữ chẩn đoán qtz giữ cơ chế sinh mã của lõi.

Cài MO theo thư mục ngôn ngữ trong đường dẫn tài nguyên của LibreOffice.
gbuild biên dịch catalog theo mô hình AllLangMoTarget. Danh sách đóng gói phải
bao gồm tài nguyên HST trên MSI, deb và macOS trước khi ký. RPM và AppImage
lấy tài nguyên từ gói Linux. Build gia tăng cần nhận lại thay đổi của cả PO
thượng nguồn và lớp HST.

Nếu tái sử dụng cây build trước khi tách, đối chiếu các PO với
`l10n/hst/upstream-vi.sha256`. Khi phát hiện khác biệt, khôi phục
`translations/source/vi` từ tarball bản dịch đã khóa trước khi build.
Khi nâng lõi, sinh lại danh sách từ tarball mới đã xác thực bằng lệnh sau
trong thư mục `translations/source/vi`, rồi cập nhật danh sách cùng khóa nguồn.

```sh
find . -type f -name '*.po' -printf '%P\0' | LC_ALL=C sort -z | xargs -0 sha256sum
```

## Điều kiện nghiệm thu

Đối chiếu nguồn pristine với cây đã áp hết series để thống kê theo mô-đun,
tách riêng các hiệu chỉnh khóa thượng nguồn. So sánh bản cài Linux của hai
commit theo từng tài nguyên .ui và định danh .hrc trong cả hai ngôn ngữ.
Ghi riêng mọi trường hợp thiếu khóa tiếng Việt và truy nguyên từ bản gốc.
Kết quả thử nghiệm và mã bản build nằm trong báo cáo giao việc.
