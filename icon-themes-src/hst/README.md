# Bộ biểu tượng ribbon HST — hướng A

**Hai kiểu biểu tượng (1.0.0):** Tùy chọn ▸ HST Office ▸ Giao diện cho chọn giữa
- **Hiện đại (nhiều màu)**, tùy chọn: `hst_modern` / `hst_modern_dark`, vẽ từ mẫu gốc trong
  `../hst-modern/`. Mực nét lấy từ `../hst-modern/metadata/ink.json` lúc dựng (sáng `#1D2F42`, tối
  `#EEF4F9`), và ở 16 px nét 1 px được làm dày thành 2 px khi glyph còn chỗ
  (`scripts/brand/hst_icon_weight.py`: không lấp khe 1 px, không bít lỗ chữ, không chạm nét khác,
  vùng màu còn thấy). Mẫu gốc không đổi nên các đợt vẽ mới cũng được xử lý giống vậy.
- **Cổ điển**, mặc định (từ 08/11/2026): `hst_classic` / `hst_classic_dark` là bộ Colibre SVG của LibreOffice, chồng thêm
  glyph HST (thư mục này, theo màu mực của Colibre) cho những lệnh Colibre không có, như các lệnh
  `org.hst.office.vi:*` hay hộp thoại thống kê. Gói chỉ chứa phần glyph HST đó; phần còn lại VCL lấy
  từ `colibre_svg` / `colibre_dark_svg` (`patches/libreoffice/hst-icon-theme-classic-colibre.patch`).
  Danh sách lệnh được tính từ chính cây LibreOffice lúc dựng (`--tree`, hoặc `--lo-tree` khi dùng `--out`).
  Hồ sơ cũ còn ghi `hst` / `hst_dark` vẫn mở ra kiểu Cổ điển này. Bộ `hst` / `hst_dark` vẫn được
  cài, làm lớp dự phòng cho kiểu Hiện đại.

**Bắt điểm ảnh (1.0.0):** gói sản phẩm không còn xuất nguyên hình học lưới 24 cho mọi cỡ.
`scripts/brand/hst_icon_snap.py` bắt từng glyph theo cỡ raster: nét 1,65 đơn vị thành
**1 px ở 16, 2 px ở 24, 3 px ở 32** (nét đậm hơn giữ tỉ lệ), tâm nét lẻ nằm giữa điểm ảnh, nét chẵn
nằm trên mép điểm ảnh; transform của nhóm được trải phẳng. `hst_icon_outline.py` vẽ nét thành vùng tô
vì VCL dịch nét (không dịch vùng tô) nửa điểm ảnh thiết bị, nên chỉ vùng tô sắc nét được ở cả 1x và 2x.
78 họ Home/truy cập nhanh có bản 16 px vẽ tay trong `glyphs/stage-1-16/` (viewBox 16, nét nguyên
điểm ảnh); các cỡ và họ khác được bắt tự động. Kiểm tra bằng chính bộ dựng hình của VCL:
`tests/runtime/check-hst-icon-sharpness.py` (`rasterise` cho cả gói, `cache` đọc bộ đệm biểu tượng
khi chạy giao diện ở GDK_SCALE 1 và 2). Mẫu gốc lưới 24 vẫn là nguồn chỉnh sửa.

**Cập nhật tích hợp 1.0.0-beta.5:** dùng `scripts/brand/build-hst-icon-theme.py`
để tạo hai gói SVG-only cho sản phẩm; không cần chạy renderer PNG. Báo cáo và
ảnh chạy thật: [INTEGRATION.md](../../docs/design/ribbon-look/INTEGRATION.md).
Giữ 440 mẫu gốc, sửa nét `xlinecolor` từ chữ A sang bút/đường để đúng nghĩa màu nét;
recipe trong `stage2.py` được cập nhật cùng SVG. `glyphs/integration/` bổ sung sáu mẫu để sửa các yêu cầu
subtype/overflow quan sát được lúc chạy. `metadata/integration-map.json` giữ các
alias tương ứng. `themes/`, sheet PNG và các bảng xuất của `generate.py` đã được
.gitignore vì tái tạo được. Phần bên dưới là hồ sơ bàn giao **trước tích hợp**;
các nhận xét “chưa chạy trong sản phẩm” ở đó mô tả thời điểm của hồ sơ gốc.

Đã hoàn thành **78 họ Stage 1** trước khi dựng **362 họ Stage 2**. Tổng cộng
**440 SVG gốc trên lưới 24**, bao phủ **495 URL lệnh có phần icon tĩnh** trong
inventory của Writer, Sheets và Slides. Ba URL còn lại trong tập 498 là điều
khiển không có glyph tĩnh, được loại có căn cứ từ source upstream. Đây là bộ
tài nguyên, chưa tích hợp hoặc kiểm thử nạp theme trong ứng dụng.

Mọi đường nét là hình HST tự dựng, theo [bản A sáng](../../docs/design/ribbon-look/a-light.png)
và [proposal](../../docs/design/ribbon-look/PROPOSAL.md). Không dùng artwork
Microsoft, Colibre, Sifr, icon font hoặc hình của bên thứ ba. Chỉ đọc tên file,
alias và source controller tại commit LibreOffice đã khóa:
`bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1`.

| Phạm vi | SVG gốc / họ | URL được bao phủ | PNG xuất, hai theme × ba cỡ | SVG xuất, hai theme × ba cỡ |
|---|---:|---:|---:|---:|
| Stage 1 — Home và truy cập nhanh | 78 | 85 URL Home/QAT; cùng các họ này còn phục vụ 13 URL ở tab khác | 468 | 468 |
| Stage 2 — các họ còn lại | 362 | 397 URL bổ sung | 2.172 | 2.172 |
| Tổng | **440** | **495 URL duy nhất** | **2.640** | **2.640** |

Không cộng 85 với 397 rồi gọi đó là tổng toàn ribbon: còn 13 URL ngoài Home
đã dùng hình của Stage 1. Tổng là 85 + 13 + 397 = 495. Các bản xuất theo màu,
kích thước và alias không được tính là mẫu vẽ mới. Kiểm tra pixel hiện phân
biệt cả 440 mẫu ở từng cỡ 16, 24 và 32; không có hai file gốc cho raster giống hệt.

Inventory dự trù 441 họ = 419 họ tra được + 22 URL chưa tra được. Sau rà soát,
loại họ `linewidth` vì là ô số đo: còn 418 họ đã có tên upstream + 22 mẫu HST
mới = 440. `GrafMode` và `XLineStyle` cũng bị loại ở mức URL, nhưng họ hình của
chúng vẫn có lệnh tĩnh khác sử dụng (`GraphicDialog`, `LineStyle`). Mười controller
đã bị inventory loại từ đầu vẫn được ghi trong bảng ngoại lệ, không bị trừ lần
nữa khỏi 498.

**Xem hình ở kích thước thật**

| Giai đoạn | Sáng | Tối |
|---|---|---|
| Stage 1, 78 glyph | [PNG 100%](contact-sheets/stage-1-light.png) | [PNG 100%](contact-sheets/stage-1-dark.png) |
| Stage 2, 362 glyph | [PNG 100%](contact-sheets/stage-2-light.png) | [PNG 100%](contact-sheets/stage-2-dark.png) |

Mỗi ô có ba bản 16 / 24 / 32 px, ghép trực tiếp từ PNG đã xuất, không phóng to
hoặc thu nhỏ. Stage 1 là 1224 × 1092 px; Stage 2 là 1224 × 4932 px. Stage 2 còn
có bảy trang cho mỗi theme, tên `stage-2-{light,dark}-page-01.png` đến `07.png`,
để xem 100% thuận tiện. Mở file và chọn 100%; chế độ tự vừa cửa sổ của trình xem
có thể làm ảnh nhỏ hơn. Đã mở xem toàn bộ glyph ở kích thước thật qua hai sheet
Stage 1 và các trang Stage 2 sáng/tối.

Đã sửa các điểm thấy ở bản render: giản lược lưới tự định dạng và gộp ô; làm rõ
hàng/cột được chọn; thu badge vào khung; nắn đầu mũi tên, dây liên kết và đũa phép;
tách dấu tiến/lùi một lớp; làm rõ nhập slide từ file, chế độ zoom và thuộc tính
trang. Kiểm tra vùng vẽ mở rộng còn phát hiện đầu mũi tên `SearchDialog` vượt
khung; đã sửa lại glyph Stage 1 này và render lại cả hai theme.

**Quy tắc hình học và màu**

Tất cả master có `viewBox="0 0 24 24"`, nền trong suốt, nét cơ sở **1,65 đơn vị**,
đầu và nối nét bo tròn. Các motif thu nhỏ để ghép badge được bù độ rộng nét,
giữ cùng bút vẽ. Chữ B đậm dùng nét quang học 2,4; vạch trạng thái dùng 2,5.
Không có chữ phụ thuộc font trong glyph. Light/dark và cả ba kích thước dùng
cùng hình học; chỉ đổi màu, viewport và kích thước raster.

| Thành phần | Sáng | Tối |
|---|---|---|
| Nét icon | `#294159` | `#DBE7F1` |
| Nền contact sheet, theo mặt ribbon | `#FFFFFF` | `#1C2B3B` |
| Chữ trên sheet | `#172D47` | `#E8F0F7` |
| Đường chia sheet | `#DCE6F0` | `#35485C` |
| Mẫu vạch màu chữ | `#B65A62` | `#B65A62` |
| Mẫu vạch tô sáng | `#E2B741` | `#E2B741` |

Hai vạch cuối lấy từ bản vẽ A trong `render.py`, gắn `data-state="font-color"`
và `data-state="highlight"` trong SVG gốc. Đây là mẫu trạng thái ban đầu; controller
ứng dụng phải cập nhật màu thực tế theo lựa chọn người dùng. Tài nguyên tĩnh không
tự theo dõi màu tài liệu. Không tô xanh toàn bộ glyph và không đổi màu nội dung ảnh.

**Cấu trúc và tái tạo**

- `glyphs/stage-1/`, `glyphs/stage-2/`: SVG gốc có thể chỉnh trực tiếp.
- `themes/hst/`, `themes/hst_dark/`: theme sáng/tối. Mỗi theme có 1.320 PNG,
  1.320 SVG xuất và `links.txt` chứa **644 alias**, gồm 322 alias PNG và 322 alias SVG.
- `cmd/sc_<tên>.png/.svg`: 16 px; `cmd/lc_<tên>.png/.svg`: 24 px;
  `cmd/32/<tên>.png/.svg`: 32 px. Các đường dẫn này nằm bên trong từng theme.
- `manifest.csv`: **7.008 dòng dữ liệu** cho 440 master, 5.280 file xuất và
  1.288 alias của hai theme; ghi lệnh, nguồn glyph, stage, cỡ, theme, đích alias và SHA-256.
  Alias là khóa trong `links.txt`, không phải một file vật lý khác.
- `command-coverage.csv`: từng URL, ứng dụng, khóa inventory, glyph và trạng thái.
- `metadata/families.json`: quan hệ họ/URL, khóa icon, alias controller và phân stage.
- `metadata/naming-audit.json`: từng khóa xuất đối chiếu với tên/alias ở commit pin.
  `upstream-paths.json` lưu cây tên; `upstream-links.txt` lưu bảng alias gốc, không có artwork.

Từ gốc repo, cần Python 3, CairoSVG và Pillow. Font nhãn sheet là Be Vietnam Pro
Regular có sẵn trong repo; không cần cài font vào hệ thống. Môi trường đã kiểm tra:
CairoSVG 2.7.1. Xuất và kiểm tra bằng:

```sh
python3 icon-themes-src/hst/generate.py --through-stage 2
python3 icon-themes-src/hst/verify.py
```

Generator chạy offline, đọc SVG master và kiểm SHA-256 của các đầu vào inventory,
proposal, ảnh A và source lock. Nó tái tạo hoàn toàn `themes/`, `contact-sheets/`
và các bảng xuất trong thư mục này. Không đặt file tự sửa trong hai thư mục sinh
tự động. `--through-stage 1` chỉ xuất Stage 1; chạy lại với `2` để phục hồi bộ đầy đủ.

`drawing.py` và `stage2.py` giữ công thức dựng ban đầu. Chỉ khi muốn ghi lại master
từ công thức mới chạy `drawing.py --stage 1`, rồi `drawing.py --stage 2`; các lệnh
này ghi đè master tương ứng. `generate.py` không sửa master đã được chỉnh bằng tay.

**Ngoại lệ và fallback**

[unmapped-and-fallbacks.csv](unmapped-and-fallbacks.csv) liệt kê đủ 35 URL cần chú ý:
22 tên tài nguyên mới, ba controller động và mười controller ngoài tập đếm gốc.
Không còn URL tĩnh thiếu glyph trong phạm vi đã chọn. Không chèn icon bên thứ ba
làm fallback. Chưa chạy trong sản phẩm nên không khẳng định runtime không fallback.

Ba URL bỏ qua là `.uno:LineWidth` (ô số đo), `.uno:XLineStyle` (mẫu nét do controller
vẽ) và `.uno:GrafMode` (combo chế độ ảnh). Bằng chứng, dòng source và hash nằm trong
[controller-audit.json](metadata/controller-audit.json). Bốn lệnh `GrafLuminance`,
`GrafContrast`, `GrafGamma`, `GrafTransparence` chỉ nhận icon nhãn tĩnh; số đo vẫn
thuộc controller. Đã thêm alias `res/sc10863.png`, `sc10864.png`, `sc10868.png`,
`sc10869.png` đến glyph 16 px, theo `svx/inc/bitmaps.hlst` tại commit pin.

22 URL vốn chưa tra được trong inventory được vẽ và xuất theo quy ước tên UNO,
gồm cả `ClearContents`. Riêng `ImportSlideFromFile` có thêm alias `ImportFromFile`
theo `TargetURL`. Sáu alias TargetURL khác của nhóm slide cũng được bổ sung.
Các khóa mới đều có SVG/PNG và ánh xạ cụ thể, nhưng còn cần xác nhận nạp icon khi
tích hợp. Menu riêng, popup tự sinh, sidebar/hộp thoại ngoài inventory, media
transport và lệnh chỉ có ở bản cài khác baseline không thuộc tuyên bố bao phủ này.

**Xác minh và giấy phép**

[verification.json](verification.json) xác nhận đủ ánh xạ ở ba cỡ cho hai theme,
không alias treo/vòng lặp, không file thừa so với manifest, không nét bị cắt khi
render vùng mở rộng, không raster trùng nhau và alpha sáng/tối giống hệt. Báo cáo
kiểm tra không thay thế đánh giá người dùng hoặc kiểm thử trong LibreOffice.
[visual-review.json](metadata/visual-review.json) lưu các ảnh đã xem và SHA-256.
[reproducibility.json](metadata/reproducibility.json) ghi phép xuất đầy đủ → chỉ
Stage 1 → đầy đủ: 5.301 file tài nguyên, alias, sheet và manifest giống từng byte.
[provenance.json](metadata/provenance.json) ghi blob SHA-1 của bảng alias đã đối
chiếu trực tiếp với cây Colibre tại commit pin, cùng nguồn gốc hình học HST.

Artwork HST dùng **CC-BY-4.0**; script/config mới dùng **AGPL-3.0-only** theo quy
ước repo. Xem [LICENSE.md](LICENSE.md) và [văn bản CC BY 4.0](LICENSE-CC-BY-4.0.txt).
Đã đối chiếu `NOTICE.md`, `docs/LICENSE_AUDIT.md` và `THIRD_PARTY_NOTICES.md`.

Toàn bộ đầu ra nằm trong `icon-themes-src/hst/`. Giữ nhánh `codex/ribbon-look`,
không sửa mã sản phẩm, không sửa tài liệu proposal có sẵn, không commit và không push.
