# 01 — Asset HST Office

Status: pending. Owner: Claude brand. Dependencies: 00 asset audit. Priority: P0. Context: [brief §§0,1,7,10](../../docs/HST_OFFICE_IMPLEMENTATION_BRIEF.md), [index](plan.md).

## Requirements

Giữ nguyên pixel mark tam giác HS của logo owner; thay phần chữ `HASON TECH` bằng `HST OFFICE`. Không redraw/generative approximation. Nguồn 476×393 bất biến; không dùng asset ONLYOFFICE, không thay icon/splash/executable upstream. Owner đã cho phép tạo dẫn xuất; không cần hỏi lại thiết kế cơ bản.

## Files tạo / ownership

- `assets/brand/brand-spec.json`: crop rectangle mark, bố cục, màu, font và kích thước output.
- `assets/brand/hst-office-logo.png`, `assets/brand/hst-office-mark.png`, `assets/brand/hst-office-icon-28.png`, `assets/brand/hst-office-icon-56.png`.
- `scripts/generate-brand-assets.py`, `tests/brand/test-brand-assets.py`.
- `docs/BRAND.md`: source/hash, cách tái tạo, font license, quyền sử dụng, phạm vi branding.
- `plans/reports/brand-261029-hst-office.md`: before/after và kết quả pixel check.
- Chỉ đọc `assets/brand/source/hasontech-logo-original.png`; không sửa root manifest, plugin hay lock của 00. Không xóa file.

## Steps

1. Xem ảnh nguồn; đo ranh giới mark/text và ghi `brand-spec.json`; lưu SHA-256 nguồn. Khoảng trắng/text cũ loại khỏi bản dẫn xuất, mark không thay đổi.
2. Chọn font đã có và có quyền phân phối output; pin tên/version/hash font được dùng. Nếu cần vendoring font, 00 review provenance trước, cập nhật file inventory với Codex; không lấy Times New Roman thương mại để đóng gói.
3. Script Python dùng subprocess ImageMagick `convert`/`identify` đang có; tạo full logo ở native resolution, mark riêng và icon 28/56. Giữ crop mark native nguyên pixel; resize chỉ cho icon. Normalize metadata, không chứa ngày tạo ngẫu nhiên.
4. Pixel check crop output full logo với crop nguồn; visual review chữ mới, độ tương phản/light-dark. Không hứa vector SVG nếu chỉ có raster nguồn.
5. Ghi bộ lệnh và notices trong docs; assets sẽ được copy vào package bởi builder 02, không để plugin cần đọc ngoài archive.

## Validation commands

```bash
sha256sum assets/brand/source/hasontech-logo-original.png
python3 scripts/generate-brand-assets.py
python3 tests/brand/test-brand-assets.py
identify assets/brand/hst-office-logo.png assets/brand/hst-office-mark.png assets/brand/hst-office-icon-28.png assets/brand/hst-office-icon-56.png
python3 scripts/generate-brand-assets.py --check
```

`--check` render vào temp, so bytes/pixels theo contract và exit nonzero khi khác; không ghi đè source. Test có `unittest.main()`, xác nhận source hash, crop pixel, kích thước, repeatability; chạy trực tiếp vì unittest discovery bỏ qua tên file kebab-case. Reviewer nhìn chữ thay thành HST OFFICE.

## Acceptance / review

- [ ] Mark nguyên vẹn, đúng chữ, source không đổi; 4 assets thật, tái tạo được.
- [ ] Font/source/provenance ghi đủ; dẫn xuất chỉ phục vụ plugin/mẫu/docs.

## Parallel, risks, rollback

01 trước 02 để PoC dùng icon thật; không shared edits. Crop sai/anti-alias vào mark phải sửa spec, không tô lại mark. Nếu font không ổn định, pin resource có license trước khi pass reproducibility. Rollback chỉ assets sinh và script của phase; bảo toàn logo nguồn.
