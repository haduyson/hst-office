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
| `assets/brand/icons/hst-office-icon-{28,35,42,49,56}.png` | Icon plugin cũ (5 mức scale); giữ để tương thích |
| `assets/brand/icons/hst-office-{16,24,32,48,64,128,256,512}.png` | Icon ứng dụng (biểu tượng, nền trong suốt, đệm 8%) |
| `assets/brand/icons/hst-{writer,sheets,slides}-{16…512}.png` | Icon module: biểu tượng + huy hiệu tròn viền trắng. Writer `#2F4FC4` (dòng chữ), Sheets `#1E8E3E` (lưới), Slides `#E8710A` (màn hình) |
| `branding/libreoffice/` | Đầu vào cho `configure --with-branding` (bảng dưới) |
| `branding/windows/hst-office.ico`, `branding/macos/hst-office.icns` | Container 16–256 px / 16–512 px do Pillow ghi; **chưa kiểm thử trên Windows/macOS** |
| `branding/linux/hst-{office,writer,sheets,slides}.desktop` | Launcher Linux (viết tay, `desktop-file-validate` đạt) |
| `branding/credits.html`, `branding/help/index.html` | Trang ghi nhận nguồn mở & trợ giúp ngoại tuyến (viết tay) |
| `branding/brand-audit-allowlist.json` | Ngoại lệ cho quét chuỗi “LibreOffice/Document Foundation” (chỉ văn bản pháp lý) |

`branding/libreoffice/` (tên file do `configure.ac:15571` bắt buộc; thiếu file → configure chỉ cảnh báo và dùng ảnh upstream):

| File | Kích thước | Dùng ở |
|---|---|---|
| `intro.png` / `intro-highres.png` | 644×199 / 1288×398 | Splash (`desktop/source/splash/splash.cxx`); highres chưa được C++ đọc ở bản pin nhưng configure vẫn đòi |
| `logo.svg`, `logo_inverted.svg` | lockup ngang (mark nguyên pixel + chữ) | About (`cui/source/dialogs/about.cxx:106`), nền sáng/tối |
| `logo-sc.svg`, `logo-sc_inverted.svg` | như trên | Start Center (`sfx2/source/dialog/backingwindow.cxx:119`) |
| `about.svg` | logo dọc trên nền trắng bo góc | Nền About (`about.cxx:117`), What's New, `appmisc.cxx:216` |
| `donate1.png`, `donate2.png` | 200×200 / 150×150 | Banner quyên góp (`backingwindow.cxx:274,286`); nên tắt `Misc/ShowDonation` |
| `progress.conf` | shell, được `source` | `PROGRESS*` → `ProgressBarColor/Size/Position/FrameColor/TextColor/TextBaseline` (`common_brand.scp:368-422`), tọa độ theo `intro.png` |

SVG chỉ nhúng PNG do chính generator sinh (data URI); không có artwork LibreOffice/TDF. LibreOffice 24.2 hệ thống đọc được các SVG này (đã kiểm tra bằng GraphicProvider).

Launcher Linux dùng `hst-office --writer|--calc|--impress %U` làm **placeholder**: bước đóng gói chốt tên executable thật, `StartupWMClass` và đường dẫn icon (`hst-office`, `hst-writer`, `hst-sheets`, `hst-slides` theo tên file trong `assets/brand/icons/`).

Thông số: [`assets/brand/brand-spec.json`](../assets/brand/brand-spec.json).

```bash
python3 scripts/generate-brand-assets.py          # sinh lại
python3 scripts/generate-brand-assets.py --check  # CI: báo lỗi nếu asset lệch
python3 tests/brand/test-brand-assets.py
python3 tests/brand/test-check-branding.py
python3 scripts/check-branding.py                 # kiểm tra asset
python3 scripts/check-branding.py --install-root upstream/libreoffice/instdir \
        --allowlist branding/brand-audit-allowlist.json   # quét chuỗi còn sót
```

Quét chuỗi chỉ xem file văn bản/cấu hình/`.mo`; **không phát hiện logo TDF nhúng trong ảnh hay chuỗi trong file nhị phân** — cần xem ảnh chụp màn hình. Không thêm cả thư mục UI vào allowlist.

## Font

Chữ “HST OFFICE” được raster hóa bằng **Liberation Sans Bold Italic** (SIL OFL 1.1, gói `fonts-liberation`). Font không được phân phối kèm. Font gốc của chữ “HASON TECH” không xác định được, nên chữ mới không trùng font gốc; khi có font chính thức của HASON TECH, cập nhật `brand-spec.json` rồi sinh lại.

## Phạm vi sử dụng

- Dùng cho splash/About/Start Center, icon ứng dụng, launcher, mẫu tài liệu (khi phù hợp), tài liệu và README của HST Office (engine LibreOffice).
- About/credits phải nêu đúng nguồn: “dựa trên LibreOffice”, kèm giấy phép và mã nguồn; không dùng logo TDF/LibreOffice hay ONLYOFFICE trong asset HST.
- Giấy phép AGPL của mã nguồn **không** cấp quyền dùng thương hiệu HASON TECH.
