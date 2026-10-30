# HST OFFICE — ghi chú bàn giao

## Thiết kế

- **Quảng bá:** nền trắng và xanh sáng; logo gốc ở đầu; tiêu đề nhấn “dành cho người Việt”; nhãn miễn phí màu cam; ba thẻ module với icon riêng; ba tính năng và nút tải miễn phí. Minh họa cửa sổ Văn bản, Bảng tính, Trình chiếu đặt bên phải.
- **Sắp ra mắt:** nền xanh đậm, ánh sáng hắt và ba tấm kính ứng dụng chìm một phần vào bóng tối; “SẮP RA MẮT” chiếm ưu thế. Logo gốc nằm trên nền trắng để giữ nguyên màu và dễ đọc.
- Giữ nguyên logo từ `hst-logo.svg`, không vẽ lại, không đổi màu, không làm méo. Tất cả nội dung tiếng Việt được dàn bằng phần tử `text`/`tspan` trong SVG, font **Noto Sans**, trọng lượng 400 và 700.
- Màu chủ đạo: **#0B6FC1**; chữ đậm **#322E2E**. Icon module lần lượt **#2F4FC4**, **#1E8E3E**, **#E8710A**. Chữ thẻ xanh lá/cam được dùng sắc đậm hơn để dễ đọc trên nền sáng.
- Các cửa sổ là minh họa cách điệu không chữ, không phải ảnh chụp giao diện sản phẩm.

## File và cách sử dụng

| File | Nội dung | Kích thước |
|---|---|---|
| `bg-quangba.png` | Nền quảng bá không chữ | 1910×1000 px |
| `bg-sapramat.png` | Nền teaser không chữ | 1910×1000 px |
| `banner-quangba.svg` | Bản nguồn quảng bá có chữ chỉnh sửa được | 1910×1000 px |
| `banner-quangba.png` | Banner quảng bá hoàn chỉnh | 1910×1000 px |
| `banner-sapramat.svg` | Bản nguồn teaser có chữ chỉnh sửa được | 1910×1000 px |
| `banner-sapramat.png` | Banner teaser hoàn chỉnh | 1910×1000 px |
| `NOTES.md` | Ghi chú, cách render và prompt đã dùng | — |

SVG tham chiếu ảnh nền và `hst-logo.svg` bằng **đường dẫn tương đối**. Khi di chuyển bản nguồn, giữ các file này trong cùng thư mục. PNG hoàn chỉnh có thể sử dụng độc lập. Máy render cần cài Noto Sans.

Hai nền được tạo bằng công cụ **image_gen tích hợp**, ảnh gốc 1734×907 px, sau đó chuẩn hóa bằng SVG và `rsvg-convert` về 1910×1000 px, giữ tỷ lệ và cắt mép rất nhỏ. Chữ và logo được ghép sau bằng SVG, không đưa vào prompt tạo ảnh.

Render lại từ thư mục này:

```bash
rsvg-convert -w 1910 -h 1000 banner-quangba.svg -o banner-quangba.png
rsvg-convert -w 1910 -h 1000 banner-sapramat.svg -o banner-sapramat.png
```

Đã kiểm tra trực quan bản 1910×1000 và bản xem thử 1200×628; kiểm tra nội dung tiếng Việt, dấu, đường dẫn ảnh, tỷ lệ logo và kích thước đầu ra. Bản xem thử là file tạm và đã được dọn sau kiểm tra.

## Sửa lần 1

- Thêm **“MIỄN PHÍ VĨNH VIỄN”** ngay dưới tiêu đề chính trên cả hai banner, bằng nhãn lớn với chữ Noto Sans đậm 54 px. Bản quảng bá dùng cam **#E8710A**; bản sắp ra mắt dùng vàng ấm **#FFC76A**, đặt sát dưới cụm “SẮP RA MẮT”. Chữ xanh đậm **#05162C** tạo tương phản rõ trên cả hai nhãn.
- Đặt dòng **“Dùng trọn đời · Không thu phí bản quyền”** ngay dưới nhãn, cỡ 30 px. Giữ tiêu đề chính lớn nhất và nhãn miễn phí là điểm nhấn thứ hai.
- Đổi nút quảng bá thành **“Tải miễn phí tại hasontech.vn”**, mở rộng nút và căn lại icon. Giữ đủ ba thẻ Văn bản, Bảng tính, Trình chiếu; bỏ dòng “Giao diện tiếng Việt thân thiện” để bố cục thoáng hơn, giữ ba điểm nổi bật còn lại.
- Giữ phong cách sáng của banner quảng bá và xanh đậm của banner sắp ra mắt. Không thay đổi ảnh nền, logo, màu hoặc tỷ lệ logo; đã đối chiếu SHA-256 của các tài sản gốc. Không tạo thêm ảnh nền hay prompt mới.
- Đã render lại hai PNG **1910×1000** bằng `rsvg-convert` và tự xem cả bản gốc lẫn bản thu nhỏ **1200×628**. Nhãn và dòng phụ đọc rõ, dấu tiếng Việt đầy đủ, không có chữ bị cắt hoặc chồng lên nhau, không có dấu “—” treo cuối dòng. Đã kiểm tra cấu trúc SVG, nội dung chữ, đường dẫn tương đối và kích thước PNG.

## Prompt ảnh quảng bá — nguyên văn

```text
Use case: ads-marketing.
Asset type: text-free background illustration for a Vietnamese office-software advertising banner. Create one wide landscape image, approximately 1910 by 1000 pixels, aspect ratio 1.91:1.
Composition: LEFT 54% of the whole canvas is completely empty clean warm-white to very pale ice-blue negative space, quiet and bright for later typesetting. On the RIGHT 46%, compose a beautiful large sculptural cluster of three floating office application panels, all comfortably inside the frame. Main panel at right-center: an elegant white document sheet inside a thick frosted-glass application window, using only blue and grey horizontal rules of varying lengths to suggest paragraphs, and one simple blue rectangular block. Behind it upper-right: translucent spreadsheet window with an unlabeled clean grid, tiny green cells and a simple green bar chart. In front lower-right: smaller slide window containing only an orange circle, rectangle and a geometric orange rising bar graph. Every panel looks like a designed abstract object, not an actual screenshot. Three layers overlap with clear depth and one cohesive perspective, elevated slightly above a satin white surface. Keep all panels fully within x=1060..1840 and y=180..850 on the target canvas. Let a broad subtle blue architectural arc frame the group at far right, softly cropped beyond the top/right edge.
Style: premium 3D product visualization, crisp precise beveled edges, ceramic white and optical frosted glass, minimal, editorial, refined enterprise software campaign. Not cute or toy-like. Rich but restrained HST blue #0B6FC1 plus document blue #2F4FC4, spreadsheet green #1E8E3E and presentation orange #E8710A only as small meaningful accents. Soft daylight, delicate ambient occlusion, elegant realistic shadows, luminous blue depth on the right. High production finish.
Text: NONE.
Strict constraints: ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO GLYPHS, NO TYPOGRAPHY, NO LOGOS, NO WATERMARKS anywhere, including application panels. No company marks, no Microsoft or LibreOffice resemblance, no recognizable software chrome or branded UI. No human, laptop, keyboard, mouse, plants, desk props, badges, buttons, symbols floating in the empty left half. No glitter, no visual clutter. The empty left half is crucial. Background only; logo and Vietnamese type will be added later in SVG.
```

## Prompt ảnh sắp ra mắt — nguyên văn

```text
Use case: ads-marketing.
Asset type: text-free background for a premium office-software launch teaser. One wide landscape image approximately 1910 by 1000 pixels, aspect ratio 1.91:1.
Scene: a deep midnight navy architectural studio, sophisticated and quiet, with a dramatic restrained cobalt and sky-blue backlight. The LEFT 57% is uncluttered uninterrupted dark navy negative space for large typography to be added later, especially the upper left and middle left. The RIGHT 43% contains a mysterious group of three premium floating translucent software application panels, resting just above a barely visible satin dark-blue stage. Panels are only partially revealed: the edges and upper halves catch blue rim light, the lower halves dissolve into a broad translucent midnight-blue veil and soft shadow. Main tall document window in front has only a few short horizontal blue rules; a spreadsheet behind contains a faint empty geometric grid and a few green cells; a slide panel at right has one dim orange circle and rectangular geometric blocks. The panels must be abstract sculptural glass objects, no recognizable real software interface. Clear 3D perspective and premium engineered beveled edges.
A single narrow diagonal wash of soft sky-blue light from the upper-right grazes the group and creates an elegant halo behind the concealed objects. A subtle low arc of reflected cobalt on the floor guides the eye toward the product. Composition is spacious, cinematic, controlled and expensive, with very dark navy on the left and a concentrated blue reveal on the right. Objects stay between x=1120..1820 and y=180..840 of target canvas, with safe margins. Do not place a bright light behind the left text area.
Palette: midnight #05162C, deep navy #06294B, HST blue #0B6FC1 and restrained icy blue edge highlights; only tiny muted green #1E8E3E and orange #E8710A accents within the panels. Matte and optical glass materials. High-fidelity 3D advertising illustration.
Text: NONE.
Strict constraints: ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO GLYPHS, NO TYPOGRAPHY, NO LOGOS, NO WATERMARKS. No question marks, no countdown, no labels, no button. No recognizable Microsoft or LibreOffice interface. No humans, laptop, desk accessories, starfield, particles, glitter, cyberpunk, matrix code, circuitry or crowded decoration. Leave the left 57% visually calm. This is the background only; original logo and Vietnamese type will be composited separately.
```

