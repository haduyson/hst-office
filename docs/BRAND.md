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
| `branding/icons/app/hst-{office,writer,sheets,slides,draw,math,base}.{svg,png}` | **Bản gốc icon ứng dụng** (thiết kế Tile, SVG + PNG 1024). Nguồn gốc, bảng màu, cách sinh lại: [README](../branding/icons/app/README.md) |
| `assets/brand/icons/hst-{office,writer,sheets,slides,draw,math,base}-{16…1024}.png`, `….svg` | Icon ứng dụng sinh từ bản gốc. Hicolor Linux (PNG + scalable) và iconset macOS |
| `branding/libreoffice/` | Đầu vào cho `configure --with-branding` (bảng dưới) |
| `branding/windows/hst-office.ico`, `branding/macos/hst-{office,writer,sheets,slides,draw,math,base}.icns` | Container 16–256 px / 16–1024 px do Pillow ghi; `hst-office.icns` là icon volume dmg |
| `branding/windows/app-icons/{soffice,*_app}.ico`, `branding/icon-themes/mainapp-*` | `.ico` 16–256 cho từng module và icon cửa sổ/Start Center. `scripts/brand/apply-icon-overrides.py` chép vào cây nguồn |
| `branding/linux/hst-{office,writer,sheets,slides}.desktop` | Launcher Linux (viết tay, `desktop-file-validate` đạt) |
| `branding/credits.html` | Trang ghi nhận nguồn mở (viết tay); trợ giúp ngoại tuyến: `docs/user-guide/` |
| `branding/brand-audit-allowlist.json` | Ngoại lệ cho quét chuỗi “LibreOffice/Document Foundation” (chỉ văn bản pháp lý) |

`branding/libreoffice/` (tên file do `configure.ac:15571` bắt buộc; thiếu file → configure chỉ cảnh báo và dùng ảnh upstream):

| File | Kích thước | Dùng ở |
|---|---|---|
| `intro.png` / `intro-highres.png` | 644×199 / 1288×398 | Splash (`desktop/source/splash/splash.cxx`); highres chưa được C++ đọc ở bản pin nhưng configure vẫn đòi |
| `logo.svg`, `logo_inverted.svg` | lockup ngang (mark nguyên pixel + chữ) | About (`cui/source/dialogs/about.cxx:106`), nền sáng/tối |
| `logo-sc.svg`, `logo-sc_inverted.svg` | như trên | Start Center (`sfx2/source/dialog/backingwindow.cxx:119`) |
| `about.svg` | logo dọc trên nền trắng bo góc | Nền About (`about.cxx:117`), What's New, `appmisc.cxx:216` |
| `donate1.png`, `donate2.png` | 200×200 / 150×150 | `donate1.png` là ảnh nền banner Start Center (xem mục Banner Start Center); `donate2.png` không còn được dùng |
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

## Banner Start Center

[`branding/libreoffice/hst-banner.png`](../branding/libreoffice/hst-banner.png) là nền thẻ của banner Start Center: biểu tượng HS gốc (chỉ thu nhỏ) và dòng “Giải pháp chuyển đổi số từ HASON TECH”. Ảnh RGBA cao **160 px**, hiển thị ở nửa kích thước (HiDPI 2×), rộng vừa nội dung, có nền thẻ trắng đục bo góc để giữ độ tương phản trên cả giao diện sáng và tối. **Tên giải pháp không nằm trong ảnh**: AIOS, eChatbot, Zalo Mini App, HST SEO, HST Post và AI Dễ Lắm là sáu nút thật (xếp lưới 3×2 bên phải ảnh, focus được bằng Tab, tooltip là khẩu hiệu), mỗi nút mở URL riêng trong [solutions.json](../data/hst/solutions.json) kèm `utm_source=hst-office&utm_medium=start-center&utm_campaign=hst-office-1-0`. Dưới lưới có liên kết chữ “Xem thêm các giải pháp khác →” mở https://hasontech.vn với cùng UTM (luôn tiếng Việt). Cửa sổ rộng dưới 1100 px: ẩn ảnh, giữ sáu nút và liên kết. Bảng giải pháp trong mã C++ phản chiếu `solutions.json`; `tests/runtime/check-start-center-banner.py` kiểm tra khớp và bấm thử từng nút.

Xem trước đúng kích thước hiển thị: [nền trắng](../branding/libreoffice/hst-banner-preview-light.png) và [nền tối](../branding/libreoffice/hst-banner-preview-dark.png). Font **Liberation Sans Regular/Bold** (SIL OFL 1.1) bao phủ toàn bộ chữ tiếng Việt và ký tự mũi tên. Đường dẫn và SHA-256 được khóa trong mục `startCenterBanner` của [brand-spec.json](../assets/brand/brand-spec.json); generator từ chối font sai hash. Không phân phối file font.

Module [start_center_banner.py](../scripts/brand/start_center_banner.py) được gọi từ generator chung; PNG không có timestamp, `--check` so sánh chính xác từng byte:

```bash
.venv/bin/python scripts/generate-brand-assets.py
.venv/bin/python scripts/generate-brand-assets.py --check
.venv/bin/python tests/brand/test-brand-assets.py
```

## Phạm vi sử dụng

- Dùng cho splash/About/Start Center, icon ứng dụng, launcher, mẫu tài liệu (khi phù hợp), tài liệu và README của HST Office (engine LibreOffice).
- About chỉ có một câu "Phần mềm nguồn mở — xem Trợ giúp → Thông tin giấy phép." (không URL nào trỏ tới kho mã/GitHub/kho extension: kho có thể đổi chỗ; cách nhận mã nguồn nằm ở đầu tài liệu giấy phép, liên hệ lienhe@hasontech.vn), không nêu tên/bản quyền LibreOffice (tên chỉ nằm trong văn bản pháp lý: Trợ giúp → Thông tin giấy phép; xem [LICENSE_AUDIT](LICENSE_AUDIT.md) §3); không dùng logo TDF/LibreOffice hay ONLYOFFICE trong asset HST.
- Giấy phép AGPL của mã nguồn **không** cấp quyền dùng thương hiệu HASON TECH.
