# Brand report — Phase 01

- Source SHA-256 khớp spec; không ghi đè source.
- Đo bằng Pillow theo kênh alpha: vùng biểu tượng rows 38–270, cols 94–362, màu chủ đạo `#0072BB`; vùng chữ rows 304–352, cols 26–430, màu `#322E2E`.
- Sinh 7 file; `--check` chạy lại trong cùng toolchain → byte-identical.
- `tests/brand/test-brand-assets.py`: 5/5 OK (hash nguồn, vùng biểu tượng giống từng pixel bằng `ImageChops.difference`, không có pixel ngoài 2 vùng, kích thước icon, tái tạo).
- Review trực quan: logo trên nền trắng và icon 56 px phóng 4× — chữ đọc đúng “HST OFFICE”, biểu tượng nguyên vẹn.

Hạn chế: Pillow resize LANCZOS có thể cho byte khác nếu Pillow đổi major version → pin Pillow trong lock; CI chạy `--check`.

## Unresolved questions

- Font chính thức của wordmark HASON TECH (nếu có) để thay Liberation Sans Bold Italic.
