# Ghi chú biên soạn

Hướng dẫn chỉ sử dụng `facts.html`, `labels.md` và 17 ảnh chụp đã được xem trực tiếp trong `images/`. Ảnh được sao chép nguyên bản vào `out/images/`. Nhãn giao diện trong `labels.md` được ưu tiên khi bản nháp rút gọn tên lệnh.

## Thông tin chưa có và phần đã lược bỏ

- Chưa có ảnh hoặc mô tả chi tiết cách nhập dữ liệu vào ô, xác nhận dữ liệu và thêm, đổi tên, xóa trang tính. Trang làm quen chỉ giới thiệu hàng, cột, ô và thao tác nhập cơ bản; không bổ sung các lệnh hay phím tắt chưa được cung cấp.
- Chưa có hộp thoại sắp xếp hoặc lọc. Hướng dẫn chỉ nêu thẻ Dữ liệu và các nhãn Sắp xếp…, Lọc tự động; không suy đoán các bước chọn khóa, phạm vi hay thứ tự.
- Chưa có ảnh thẻ Chèn để xác định lệnh đánh số trang thông thường hoặc các bước chọn vị trí ảnh, kích thước bảng. Hướng dẫn dừng ở thẻ hoặc lệnh đã được xác nhận.
- Ảnh kiểu trang đang mở mục Chung, chưa thể hiện các ô đặt khổ giấy và lề. Hướng dẫn nêu đường dẫn đã xác nhận, không mô tả các điều khiển chưa thấy.
- Chưa có ảnh Tải/Lưu → Chung hoặc hộp thoại lưu tệp. Đường dẫn, trường Kiểu tập tin: và Luôn lưu thành: dựa trên nguồn chữ; ảnh options.png chỉ minh họa vị trí Tải/Lưu trong cây tùy chọn, không minh họa thiết lập Luôn lưu thành:.
- Chưa có ảnh bảng hiệu ứng trình chiếu hoặc quy trình cài phần mở rộng. Hướng dẫn chỉ dùng thao tác có trong nguồn chữ, không thêm tên hiệu ứng, thiết lập thời gian hay hộp thoại xác nhận.
- Chưa có bằng chứng về hàm hoặc phép tính ngoài SUM và phép nhân trong ví dụ nguồn. Trang công thức không mở rộng sang các hàm và phép tính khác.
- Chưa có nút kết thúc hộp thoại chọn nơi lưu PDF trong ảnh. Hướng dẫn chỉ mô tả phạm vi xuất và nút Xuất đã thấy.

## Lưu ý khi đóng gói

Brief yêu cầu giữ nguyên `../icons/hst-office-logo.png` và cho biết đường dẫn này hợp lệ trong sản phẩm. Bộ đầu vào hiện tại không có `icons/hst-office-logo.png`. Vì chỉ được ghi vào `out/`, không tạo hoặc thay thế tệp ở bên ngoài thư mục này. Đây là phụ thuộc tài nguyên còn thiếu khi xem bản bàn giao độc lập; bộ cài cần cung cấp logo tại đường dẫn đã quy định. Các ảnh minh họa của hướng dẫn nằm trong `out/images/`.

Không tạo trang giới thiệu riêng vì thông tin giới thiệu đã có ở trang chủ và trang liên hệ.

## Kiểm tra bản bàn giao

- Đã kiểm tra đủ 18 trang HTML, tiêu đề, mục lục, trang hiện tại, liên kết trước/sau và stylesheet dùng chung.
- Đã kiểm tra các liên kết nội bộ, đích neo, ảnh minh họa và kích thước ảnh. Ngoại lệ duy nhất là logo do bộ cài cung cấp, đã nêu ở trên.
- Đã đối chiếu ảnh sao chép với ảnh nguồn; kiểm tra Unicode NFC, các liên kết ngoài được phép và chính sách tên sản phẩm. Không có JavaScript, phông tải qua mạng hoặc tài nguyên nhúng base64.
- CSS có bố cục cho màn hình dưới 760 px, chế độ tối và bản in ẩn điều hướng. Chưa xác minh trực quan các chế độ này trong trình duyệt: tiến trình tự động hóa không khởi động được; thử Chromium trực tiếp bị môi trường chặn thao tác socket (`Operation not permitted`).
