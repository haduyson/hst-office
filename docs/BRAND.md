# Thương hiệu HST Office

![HST Office](../assets/brand/hst-office-logo.png)

## Nguồn

- `assets/brand/source/hasontech-logo-original.png` — logo HASON TECH do chủ dự án cung cấp ngày 2026-10-29 (476×393 PNG RGBA), SHA-256 `2f77a5fce52a515d52333cca3879a0aec18e582628a7111c00a05714b1c4d2ef`. **Không sửa file này.**
- Theo brief §0: giữ nguyên hình biểu tượng, thay dòng chữ “HASON TECH” bằng “HST OFFICE”.

## Asset dẫn xuất (sinh tự động)

| File | Mô tả |
|---|---|
| `assets/brand/hst-office-logo.png` | 476×393; biểu tượng copy nguyên pixel (vùng `[94,38,363,271]`), chữ mới vẽ vừa đúng khung chữ cũ `[26,304,431,353]`, màu `#322E2E` |
| `assets/brand/hst-office-mark.png` | Chỉ biểu tượng, 269×233 |
| `assets/brand/icons/hst-office-icon-{28,35,42,49,56}.png` | Icon plugin theo 5 mức scale 100–200% của ONLYOFFICE |

Thông số: [`assets/brand/brand-spec.json`](../assets/brand/brand-spec.json).

```bash
python3 scripts/generate-brand-assets.py          # sinh lại
python3 scripts/generate-brand-assets.py --check  # CI: báo lỗi nếu asset lệch
python3 tests/brand/test-brand-assets.py
```

## Font

Chữ “HST OFFICE” được raster hóa bằng **Liberation Sans Bold Italic** (SIL OFL 1.1, gói `fonts-liberation`). Font không được phân phối kèm. Font gốc của chữ “HASON TECH” không xác định được, nên chữ mới không trùng font gốc; khi có font chính thức của HASON TECH, cập nhật `brand-spec.json` rồi sinh lại.

## Phạm vi sử dụng

- Dùng cho icon/About của plugin HST, mẫu tài liệu (chỉ khi phù hợp), tài liệu và README.
- **Không** thay icon, splash, tên executable hay About của ONLYOFFICE (đường B đang BLOCKED).
- Không dùng logo/trademark ONLYOFFICE trong bất kỳ asset HST nào.
- Giấy phép AGPL của mã nguồn **không** cấp quyền dùng thương hiệu HASON TECH.
