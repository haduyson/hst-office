# Giấy phép và nguồn gốc

Copyright © 2026 Công ty TNHH Công nghệ Hà Sơn (HASON TECH).

Các glyph SVG trong `glyphs/`, bản SVG/PNG xuất trong `themes/` và phần hình
biểu tượng trong contact sheet là **tác phẩm được dựng riêng cho HST**,
cấp phép **Creative Commons Attribution 4.0 International (CC-BY-4.0)** theo
yêu cầu của chủ dự án. Văn bản đầy đủ: [LICENSE-CC-BY-4.0.txt](LICENSE-CC-BY-4.0.txt).

Cách ghi công đề nghị: “HST Ribbon Icons — HASON TECH, 2026, CC BY 4.0”,
kèm liên kết đến bộ nguồn này và
[giấy phép CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Khi sửa hình, ghi rõ đã chỉnh sửa. Giấy phép artwork không cấp quyền thương hiệu.
Bộ glyph này không chứa logo HST, logo Microsoft hoặc logo LibreOffice.

Ngoại lệ trong gói `images_hst*.zip`: `res/mainapp_*` và nút “Giải pháp HASON TECH”
(`cmd/sc_showsolutions.svg`, `cmd/lc_showsolutions.svg`, `cmd/32/showsolutions.svg`)
dùng dấu HASON TECH. Nguồn của nút là
[hasontech-mark.svg](../../branding/icon-themes/hasontech-mark.svg), cùng hình dấu
trong `res/mainapp_*`, tô màu xanh thương hiệu. Đây là **nhãn hiệu của HASON TECH**,
không thuộc CC BY 4.0; `COPYING.txt` trong gói ghi rõ ngoại lệ này
(xem [NOTICE.md](../../NOTICE.md)).

Các script Python, cấu hình và bảng ánh xạ mới của HST dùng **AGPL-3.0-only**,
phù hợp quy ước cho mã mới/generator trong [NOTICE.md](../../NOTICE.md),
[kiểm kê giấy phép](../../docs/LICENSE_AUDIT.md) và [LICENSE](../../LICENSE).
Đường dẫn từ thư mục này đến gốc repo là `../../`.

Đường nét được dựng từ tọa độ, đường Bézier và các hình cơ bản. Một số motif
Stage 1 tiếp nối bản vẽ HST ở `docs/design/ribbon-look/render.py`, được proposal
xác nhận là hình HST tự dựng. Không tải, trace, nhúng hoặc chuyển đổi artwork
Microsoft, Colibre, Sifr hay bộ icon bên thứ ba. Các chữ/ký hiệu trong glyph
cũng là đường nét tự dựng; không chuyển outline từ font.

`metadata/upstream-paths.json` và `metadata/upstream-links.txt` chỉ lưu tên
tài nguyên và quan hệ alias của LibreOffice tại commit
`bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1`. Đây là dữ liệu đối chiếu upstream,
không được nhận là artwork HST hoặc được tái cấp phép như artwork HST.
Không có pixel/path SVG Colibre nào trong gói này. Các thông báo và giấy phép
LibreOffice vẫn theo [quy ước của repo](../../THIRD_PARTY_NOTICES.md).

| Công cụ/thành phần lúc tạo | Giấy phép/nguồn | Vai trò |
|---|---|---|
| CairoSVG 2.7.1 | LGPL-3.0-or-later; [CairoSVG](https://cairosvg.org/) | Render SVG thành PNG; không đóng gói thư viện |
| Pillow | HPND; [Pillow](https://python-pillow.org/) | Ghép contact sheet, kiểm tra pixel; không đóng gói thư viện |
| Be Vietnam Pro Regular | SIL OFL 1.1; [OFL có sẵn](../../extensions/hst-vietnamese-tools/banners/fonts/OFL.txt) | Chỉ chữ nhãn trên contact sheet; không dùng trong glyph |
| Văn bản CC BY 4.0 | [Creative Commons](https://creativecommons.org/licenses/by/4.0/legalcode); bản text từ SPDX | Văn bản giấy phép, URL và SHA-256 tại `metadata/licence-source.json` |

Thông báo này nằm trong thư mục đầu ra theo phạm vi được giao; không sửa
`THIRD_PARTY_NOTICES.md` ở gốc repo và không thay đổi giấy phép của thành phần cũ.
