# Icon ứng dụng HST Office (bản gốc)

Thiết kế "Tile": ô vuông bo góc theo màu module, glyph trắng lớn, dấu HST (tam giác cắt chữ S) màu trắng ở góc trên phải. Icon chính là ô xanh thương hiệu chứa nguyên dấu HST.

| File | Ứng dụng | Màu | Glyph |
|---|---|---|---|
| `hst-office` | HST Office (Start Center) | `#0072BB` | dấu HST |
| `hst-writer` | Văn bản | `#2F5BD3` | dòng chữ |
| `hst-sheets` | Bảng tính | `#1E8E3E` | ô bảng |
| `hst-slides` | Trình chiếu | `#E8590C` | màn chiếu |
| `hst-draw` | Vẽ | `#F2A900` | tròn + tam giác (glyph nâu `#44300D`) |
| `hst-math` | Công thức | `#0F8A8A` | dấu căn |
| `hst-base` | Cơ sở dữ liệu | `#7B3FC4` | trụ dữ liệu |

`<tên>.svg` là bản gốc thiết kế: lưới 1024, thân ô 100–924, SVG 1.1 thuần, không ảnh nhúng, không chữ. `<tên>.png` là bản 1024×1024 RGBA render từ SVG và được commit.

## Sinh lại

```bash
python3 scripts/brand/render-app-icon-masters.py          # SVG -> PNG 1024 (cần rsvg-convert)
python3 scripts/brand/render-app-icon-masters.py --check
python3 scripts/generate-brand-assets.py                  # mọi kích thước/định dạng, chỉ dùng Pillow
```

Generator chỉ đọc PNG gốc nên `--check` trên CI không phụ thuộc phiên bản librsvg. Từ 64 px trở xuống, ảnh được cắt về hộp `smallCropBox` để ô vuông lấp đầy icon nhỏ. Thông số nằm trong `appIcons` của [brand-spec.json](../../../assets/brand/brand-spec.json).

Đầu ra:
- `assets/brand/icons/<tên>-{16…1024}.png` và `<tên>.svg`: hicolor Linux qua `hst-packaging-sysui.patch`; bộ icon app và tài liệu macOS qua `scripts/macos/stage-macos-icons.py`.
- `branding/windows/app-icons/*.ico` (16–256): `soffice.ico` và `*_app.ico`, được `scripts/brand/apply-icon-overrides.py` chép vào cây nguồn.
- `branding/icon-themes/mainapp-{16,24,32,48}.{png,svg}`: icon cửa sổ/Start Center của mọi icon theme.
- `branding/windows/hst-office.ico`; `branding/macos/hst-office.icns` (icon volume dmg) và `hst-<module>.icns`.

## Nguồn gốc

- Thiết kế bằng Codex CLI 0.165.0, model `gpt-6-astra`, chạy `codex exec` ngày 2026-10-30. Codex viết tay SVG theo brief; ảnh tham khảo do công cụ sinh ảnh tích hợp tạo ra chỉ dùng để định hướng và không nằm trong icon.
- Brief: [vòng 1](provenance/brief-round1.md) (3 hướng thiết kế, yêu cầu bắt buộc) và [vòng 2](provenance/brief-round2.md). Vòng 2 thay tam giác góc chung chung bằng dấu HST giản lược và vẽ lại dấu căn để không bị đọc thành dấu tick.
- Dấu HST được dựng lại dạng vector từ `assets/brand/hst-office-mark.png`, IoU 0,990 so với ảnh gốc.
- Chủ dự án chọn phương án 1 (Tile) ngày 2026-10-30, giữ nguyên thiết kế. Bảng xem trước: [preview-sheet.png](provenance/preview-sheet.png).
- Tiêu đề trong SVG được đổi thành tên sản phẩm. Mọi hình vẽ giữ nguyên như Codex tạo.
