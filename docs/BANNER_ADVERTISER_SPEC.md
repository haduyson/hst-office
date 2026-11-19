# Quy định banner quảng cáo "Bảng tin HST" (từ HST Office 1.0.3)

Tài liệu dành cho nhà quảng cáo và người thiết kế banner hiển thị trên thanh công cụ (ribbon) của HST Writer,
HST Sheets, HST Slides và HST Draw. Quy định do chủ sở hữu chốt ngày 17/11/2026. Hợp đồng kỹ thuật của tệp
`banners.json` nằm ở [BANNERS.md](BANNERS.md#manifest-contract-schemaversion-1).

## 1. Kích thước chuẩn

Banner **không co giãn theo màn hình**. Mỗi chiến dịch nộp đủ **3 kích thước chuẩn**, mỗi kích thước có
bản thường (1×) và bản cho màn hình mật độ cao (2×, ví dụ Retina, màn hình 4K):

| Kích thước | Bản 1× (px) | Bản 2× (px) | Dùng khi chỗ trống trên ribbon |
|---|---|---|---|
| Nhỏ | 360 × 96 | 720 × 192 | từ 360 đến dưới 640 px |
| Vừa | 640 × 96 | 1280 × 192 | từ 640 đến dưới 960 px |
| Lớn | 960 × 96 | 1920 × 192 | từ 960 px trở lên |

- Ứng dụng tự chọn **kích thước chuẩn lớn nhất vừa chỗ trống**. Ảnh **không bao giờ bị kéo giãn, bóp méo hay
  cắt**; phần ribbon dư ra (nếu có) để trống hoặc tô nền.
- Banner không bao giờ hẹp hơn 360 px và không rộng quá 960 px. Trên màn hình hẹp, ribbon thu gọn các nhóm
  nút trước để giữ chỗ cho banner 360 px.
- Kích thước 2× phải đúng gấp đôi bản 1×, cùng bố cục (chỉ sắc nét hơn), không phải ảnh khác.

## 2. Vùng an toàn 360 px bên trái

- **Logo và thông điệp chính phải nằm trọn trong 360 px bên trái** (720 px ở bản 2×) của **mọi** kích thước.
- Bản 640 và 960 chỉ mở rộng thêm sang phải: hình minh họa, nền, thông tin phụ. Người xem bản 360 px vẫn
  phải hiểu đủ thông điệp.
- Chiều cao 96 px: chữ quan trọng không sát mép trên/dưới, nên chừa tối thiểu 8 px (16 px ở bản 2×).
- Cỡ chữ tối thiểu 12 px ở bản 1× (24 px ở bản 2×) để chữ tiếng Việt có dấu đọc rõ; độ tương phản chữ/nền
  tối thiểu 4,5 : 1.

## 3. Định dạng và dung lượng

- Định dạng: **PNG** (khuyến nghị, nhất là có chữ hoặc logo) hoặc **JPG**. Không nhận WebP, GIF, SVG hay ảnh
  động (APNG). Nên dùng JPG hệ màu RGB.
- Dung lượng: **tối đa 300 KB mỗi tệp** (300 × 1024 = 307.200 byte).
- Hệ màu sRGB. Không cần nền trong suốt; nếu có, nền phía sau là màu nền ribbon (sáng hoặc tối tùy giao diện),
  nên tránh logo chỉ đọc được trên một nền.

## 4. Tên tệp khi nộp

Mỗi chiến dịch có một mã (`id`) gồm chữ thường không dấu, số và dấu gạch ngang, ví dụ `acme-tet-2027`.
Nộp đủ 6 tệp:

```
acme-tet-2027-360x96@1x.png    acme-tet-2027-360x96@2x.png
acme-tet-2027-640x96@1x.png    acme-tet-2027-640x96@2x.png
acme-tet-2027-960x96@1x.png    acme-tet-2027-960x96@2x.png
```

Kèm theo: tên sản phẩm (tối đa 80 ký tự), câu giới thiệu ngắn (tối đa 160 ký tự, dùng cho trình đọc màn hình),
địa chỉ trang đích khi người dùng bấm (HTTPS), thời gian bắt đầu/kết thúc chiến dịch nếu có.

## 5. Kiểm tra trước khi nộp

HASON TECH kiểm mọi bộ banner bằng công cụ của kho mã nguồn:

```sh
python3 scripts/brand/validate-banner-manifest.py --campaign <thư mục> --id <mã chiến dịch>
```

Công cụ báo thiếu tệp, sai kích thước điểm ảnh, sai định dạng, quá 300 KB. Vùng an toàn và độ dễ đọc do người
duyệt kiểm bằng mắt trên ribbon thật ở cả 3 kích thước.

## 6. Tương thích với HST Office 1.0.2 trở về trước

Các bản 1.0.2 trở về trước vẫn hiển thị banner cũ 360 × 104 (1×, 2×, 3×). Trong giai đoạn chuyển tiếp, mỗi mục
trong `banners.json` giữ trường cũ `image` (và `imageCompact` nếu có) và thêm trường mới `sizes` cho 3 kích thước
chuẩn; bản cũ bỏ qua trường mới. Nhà quảng cáo cần nộp thêm bản 360 × 104 (1×, 2×, 3×) cho tới khi HASON TECH
thông báo ngừng hỗ trợ bản cũ.

Kiểm tệp `banners.json` trước khi xuất bản:

```sh
python3 scripts/brand/validate-banner-manifest.py banners.json --assets <thư mục ảnh> --require-sizes
```

Lưu ý: toàn bộ `banners.json` tối đa 64 KB và 24 mục. Với đủ trường cũ, `imageCompact` và 6 tệp mới mỗi mục,
tệp viết gọn (không thụt dòng) chứa được 24 mục; nếu thụt dòng thì khoảng 18 mục.
