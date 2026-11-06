# Tích hợp diện mạo ribbon HST — 1.0.0-beta.5

Đã triển khai **hướng A, giai đoạn tài nguyên**: đóng gói theme HST sáng/tối, nối vào luồng build hiện có, thêm patch chọn mặc định và fallback, chỉnh nhỏ Home của Writer/Sheets/Slides. Không sửa mã vẽ VCL, không đổi thứ tự nhóm, không đổi lệnh hoặc cơ chế fold/contextual tab.

## Kết quả trên bản build thật

Đã build series hiện tại và kiểm tra dưới Xvfb (GTK3, vi_VN, profile mới). Chưa tạo lại installer `.deb`, `.msi`, `.dmg`; Windows và macOS chưa chạy.

- **Chọn theme:** Automatic mở `images_hst.zip` khi sáng, `images_hst_dark.zip` khi tối, kể cả theme GTK tối không đặt cờ prefer-dark. Theme chọn tường minh (Colibre, Breeze, `hst` trong chế độ tối) được giữ nguyên. `CppunitTest_vcl_app_test` đạt.
- **Chiều cao ribbon:** 164/164/203 px ở 100% và 200%; banner `(1112,46,360,107)` ở 1485 px, `(993,46,360,107)` ở 1366 px.
- **Home ở 1366 px (quyết định của chủ sản phẩm):** Sao chép định dạng và Xóa chỉ còn icon ở cả ba ứng dụng và ở mọi độ rộng, giữ tooltip và tên trợ năng. Ở cả 1366 và 1485 px, Sheets hiện Số, Slides hiện Đoạn văn. Kiểm tra bằng `tests/runtime/check-ribbon-home-fit.py`.
- **Cấu hình:** configure phải có `WITH_THEMES` gồm `hst hst_dark colibre colibre_dark`. Cây đang build chạy lại `autogen.sh`; chỉ `config_zxing.h` đổi nên không phải build lại toàn bộ.

Slides vẫn có thể abort khi đóng (`SlideSorterController::GetPageSelector`, qua atk-bridge) sau khi đã kiểm tra xong; chưa xác định nguyên nhân.

Ảnh chụp, bảng fallback và số đo của lượt preview trên bản cài cũ không được commit vì quá lớn. Số liệu dưới đây lấy từ lượt đó, trừ khi ghi khác.

## Đóng gói và chọn theme

[`build-hst-icon-theme.py`](../../../scripts/brand/build-hst-icon-theme.py) đọc trực tiếp SVG master và bảng tên trong `icon-themes-src/hst/`. Chỉ cần thư viện chuẩn Python 3, không cần CairoSVG/Pillow để build sản phẩm. Kết quả gồm:

```text
images_hst.zip
images_hst_dark.zip
  cmd/sc_*.svg       # viewport 16 × 16
  cmd/lc_*.svg       # viewport 24 × 24
  cmd/32/*.svg       # viewport 32 × 32
  res/mainapp_*.svg  # tài nguyên thương hiệu HST hiện có
  sfx2/res/chevron.svg
  links.txt         # bên trong từng ZIP, tại gốc archive
  COPYING.txt
  LICENSE-CC-BY-4.0.txt
```

`--out` còn xuất cây giải nén, gồm `hst/links.txt` và `hst_dark/links.txt`. `--tree` đặt tài nguyên và `images.zip` vào `icon-themes/hst{,_dark}/` của cây upstream. Thứ tự entry, thời gian ZIP 1980-01-01, quyền file và mức nén được cố định; ghi lại chỉ khi byte thay đổi. `--check` chỉ đọc và phát hiện thiếu file, file cũ, file thừa. Đã kiểm tra xuất hai lần, đảo thứ tự đầu vào ZIP, staging rồi kiểm tra lại, và kiểm CRC/alias.

**Không xuất PNG trùng SVG vào sản phẩm.** VCL ở commit pin tìm `.png` rồi `.svg` theo cùng tên gốc, đọc SVG ở tỷ lệ DPI thiết bị. PNG bị phóng bằng `BmpScaleFlag::Fast`; giữ SVG giúp nét HST rõ ở 200%. Ba viewport 16/24/32 vẫn cần: menu/nút nhỏ, ribbon/sidebar, và nút lớn. Không thêm các cỡ command 48/64/96 hay một bộ `_svg` thứ hai.

Đã dùng lại [`apply-icon-overrides.py`](../../../scripts/brand/apply-icon-overrides.py), sau phần override app/document icon. Hook này đã được gọi bởi:

- `scripts/build-linux.sh` và `scripts/linux/ci-build.sh`;
- `scripts/windows/trial-build.sh` (luồng Windows thật, khác wrapper chuẩn bị môi trường `build-windows.ps1`);
- `scripts/macos/trial-build.sh` (luồng thử build thật; `build-macos.sh` vẫn là wrapper có chặn TODO sẵn có).

Không thêm một đường cài theme riêng chỉ dành cho Linux. Patch [`hst-icon-theme.patch`](../../../patches/libreoffice/hst-icon-theme.patch) thêm `hst hst_dark` vào danh sách theme mặc định và danh sách tên được configure chấp nhận; cấu hình rút gọn có HST phải giữ `colibre colibre_dark`. Target ảnh HST lấy ZIP đã sinh; `postprocess/Package_images.mk` → `Repository.mk/ooo_images` → `scp2/InstallModule_ooo.mk` đưa hai file vào `share/config` trên cả ba nền tảng. Đã chạy target make lấy hai ZIP bằng chính makefile đã patch và so sánh byte; lượt make tiếp theo không làm lại.

Nguồn đã đọc đúng commit [`bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1`](../../../upstream/libreoffice-lock.json):

| Nguồn upstream | Hệ quả đã áp dụng |
|---|---|
| [IconThemeScanner.cxx](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/vcl/source/app/IconThemeScanner.cxx), [IconThemeInfo.cxx](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/vcl/source/app/IconThemeInfo.cxx) | Scanner nhận tên `images_*.zip`; thêm tên hiển thị **HST**, **HST (dark)**. Không cần sửa scanner. |
| [IconThemeSelector.cxx](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/vcl/source/app/IconThemeSelector.cxx), [settings.cxx](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/vcl/source/app/settings.cxx), `svtools/source/config/miscopt.cxx` | Giữ `SymbolStyle=auto`; chỉ nhánh Automatic ưu tiên HST theo cờ tối. Nhánh lựa chọn tường minh và ưu tiên high contrast giữ nguyên. |
| [ImplImageTree.cxx](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/vcl/source/image/ImplImageTree.cxx) | Alias trực tiếp, không có chuỗi/vòng; SVG nạp được qua yêu cầu `.png`. HST thiếu tài nguyên → Colibre; thêm nhánh HST Dark → Colibre Dark → Colibre. |
| `svx/inc/bitmaps.hlst`, `svx/source/tbxctrls/tbcontrl.cxx`, `colrctrl.cxx`, hồ sơ controller của bộ glyph | Giữ controller, UNO dispatch, thanh màu động và ô số đo. Có alias cho bốn nhãn chỉnh ảnh `res/sc10863`, `10864`, `10868`, `10869`. |
| [CustomTarget_images.mk](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/postprocess/CustomTarget_images.mk), [pack_images.py](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/solenv/bin/pack_images.py) | Packer hiện tại là Python, không phải `packimages.pl`. Dùng target riêng cho ZIP HST để giữ metadata ZIP tái lập, toàn bộ alias và thông báo giấy phép. Các theme cũ vẫn dùng packer cũ. |
| [postprocess/Rdb_services.mk](https://github.com/LibreOffice/core/blob/bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1/postprocess/Rdb_services.mk) | Chỉ đăng ký cơ sở dữ liệu UNO services; theme là tài nguyên, không thêm service/RDB. |

**Profile mới:** `auto` chọn HST sáng hoặc HST tối khi có đủ gói. **Profile cũ từng chọn Colibre, Breeze, Sifr… tường minh:** vẫn chọn đúng theme đó; không chạy migration và không viết lại profile. Profile cũ đang Automatic cũng đi theo mặc định HST mới. Người dùng chọn riêng `hst` hoặc `hst_dark` tường minh sẽ giữ biến thể đó, đúng quy ước của các theme hiện có. High contrast vẫn có quyền ưu tiên. Có test CppUnit trong patch cho Automatic sáng/tối, lựa chọn tường minh và cây thiếu HST.

## Glyph được dùng thật, fallback và giới hạn phạm vi

Giữ tập **440 master gốc / 495 URL tĩnh**. Khi mở sản phẩm mới thấy các controller hình tự chọn subtype sau khởi tạo. Ở 200%, một số nút vẫn là bitmap Colibre phóng lớn dù icon họ lệnh đã có HST. Đã sửa bằng:

- Bốn master bổ sung: hình thoi, mũi tên khối hai chiều, lưu trữ nội bộ trong lưu đồ, callout chữ nhật bo góc. Không ánh xạ chúng sang glyph họ khác nghĩa (ví dụ biểu tượng tài liệu lưu đồ hoặc mũi tên một chiều).
- Alias subtype mặt cười và sao năm cánh tới đúng glyph HST đã có.
- Glyph menu ba nét `res/notebookbar.svg` 16 px, tách khỏi glyph cửa sổ của lệnh Menubar; thêm glyph overflow `sfx2/res/chevron.svg` giữ nguyên **14 × 16 px logic**. Hai nét này trước đó quá tối trên nền tối của binary cũ.
- Sửa master `xlinecolor` và recipe `stage2.py`: bỏ chữ A dễ nhầm với màu chữ, dùng bút và đường cho màu nét. Sau sửa cuối này, ZIP chỉ đổi ba viewport của `xlinecolor`; chụp lại 12 ảnh Slides có nút đó, các tài nguyên đang hiện trong ảnh Writer/Sheets không đổi.

Như vậy gói tích hợp có **446 hình gốc**, không gọi các biến thể kích thước/màu là hình mới. Thẻ Phần mở rộng thêm **10 hình gốc** cho nút lớn của các lệnh extension HST (`org.hst.office.vi:*`): `hst_commands()` trong [drawing.py](../../../icon-themes-src/hst/drawing.py), đánh dấu `extension_tab` trong `families.json`, nên `verify.py` vẫn đếm 78/362 hình của inventory riêng. Ảnh của lệnh nằm ở `cmd/32/<tên lệnh viết thường>.svg`; `formatpercent` và `nd30wizard` là alias tới `numberformatpercent` và `insertdoc` cùng nghĩa. Tổng gói: **456 hình gốc**. [integration-map.json](../../../icon-themes-src/hst/metadata/integration-map.json) ghi các bổ sung; các SVG mới đều tự dựng bằng đường nét HST, không sao chép artwork Colibre. Các subtype khác trong popup hình vẫn có thể dùng fallback, nhất là sau khi người dùng chọn một hình khác.

**Fallback được xác nhận từ mã nguồn và quan sát sản phẩm, nhưng không phủ toàn bộ UI bằng HST.** Cache quan sát được khi chọn HST ở 200% có tài nguyên từ `colibre`, gồm các trạng thái tài liệu/zoom, bố cục xem trang, tạo/cập nhật kiểu và màu vùng. Bản build mở `images_colibre_dark.zip` khi dùng HST Dark, đúng chuỗi HST Dark → Colibre Dark → Colibre.

| Bề mặt | Người dùng còn nhìn thấy từ Colibre / native |
|---|---|
| Ribbon | Icon tạo/cập nhật kiểu, một số popup hình/subtype chưa vẽ, tài nguyên ngoài bộ lệnh của ba notebookbar chính. Mẫu nét, line width, combo chế độ ảnh, gallery và thanh màu là controller, không phải glyph tĩnh bị thiếu. |
| Sidebar | Nút mở deck như Styles/Gallery/Navigator, các mẫu bố cục slide, preset thụt lề, preview/hình gallery và error bar biểu đồ. Lệnh dùng chung khóa HST vẫn nhận HST. |
| Menu | Các lệnh ngoài inventory như tự sửa, một số kiểu ô, công cụ VBA/Draw/Base. Một menu có thể không hiện icon theo cấu hình native; không tự thêm icon cho mục vốn không có. |
| Menu ngữ cảnh | Các kiểu ô, lệnh Bézier/sắp xếp đối tượng và lệnh chuyên biệt không nằm trong set. Cut/Copy và các khóa đã có dùng HST khi menu hiện icon. |
| Hộp thoại | Icon media transport, bộ chỉnh dữ liệu biểu đồ, preview và biểu tượng stock. Nút chữ/checkbox/tab native không bị thay bằng ảnh. |
| Start Center | Folder, recent/remote documents, templates và biểu tượng loại tài liệu từ theme nền; các biểu tượng tài liệu đã được cơ chế branding HST hiện có override. Banner HST giữ nguyên. |

Danh sách fallback tĩnh có ví dụ file `.ui`; số đếm là kiểm kê mọi UI trong **bản cài**, gồm cả module ngoài ba ứng dụng và các mục đang ẩn. Đây không phải trace “đã hiện trên màn hình”. Giá trị `dynamic-or-missing` chỉ có nghĩa quy tắc tra khóa tĩnh không kết luận được; không đồng nghĩa sản phẩm thiếu hình. Các URL/menu alias có thể đi qua metadata/controller khác. Dùng script audit để xuất lại bảng đầy đủ vào `build/`, không commit bảng đầy đủ 1,8 MB.

## Ảnh và kích thước

Ma trận nghiệm thu gồm Writer (**Trang đầu, Chèn, Bố cục**), Sheets (**Trang đầu, Chèn, Dữ liệu**), Slides (**Trang đầu, Chèn, Thiết kế**), mỗi tab ở sáng/tối, scale 1/2, cả baseline và HST: **72 ảnh**. Cửa sổ là 1485 × 900 pixel logic; ảnh 200% là 2970 × 1800 pixel thiết bị. Chụp dưới GTK3/Adwaita, Xvfb, profile mới cho từng trường hợp, giao diện tiếng Việt. Không lấy zoom tài liệu 100% làm DPI 100%.

| Ứng dụng | Baseline / HST, 100% | Baseline / HST, 200% | Banner logic |
|---|---:|---:|---|
| Writer | 164 / 164 px | 328 / 328 px thiết bị | `(1112,46,360,107)` |
| Sheets | 164 / 164 px | 328 / 328 px thiết bị | `(1112,46,360,107)` |
| Slides | 203 / 203 px | 406 / 406 px thiết bị | `(1112,46,360,107)` |

AT-SPI trả tọa độ logic ở cả hai DPI. Ở 200%, slot banner tương ứng `(2224,92,720,214)` pixel thiết bị. Slides có thêm hàng công cụ vẽ dưới ribbon trong bản cài nên mốc thẻ tài liệu là 203, nhưng page Home/banner vẫn có cùng slot. Đã so sánh từng cặp baseline/HST cùng app, tab, theme và DPI; không trừ/bù số đo để đạt yêu cầu. Banner tự luân phiên, vài ảnh bắt đúng pha chuyển nên chữ quảng cáo chồng mờ; giữ nguyên ảnh chạy thật, không sửa banner hoặc tô lại ảnh.

Bản cài không trùng ba `.ui` tái tạo từ pin + series hiện tại. Số đo và ảnh ghi rõ là của bản cài với tài nguyên mới. `evidence.json` giữ hash cả `.ui` gốc, `.ui` preview, `.ui` nguồn sau patch, cùng binary gốc/preview. Không thay notebookbar của bản cài bằng cả notebookbar main: chỉ áp phép sửa Home bằng ID để giữ khác biệt contextual tab/fold của bản cài.

Trong lúc làm, binary tại `/opt/hst/program/libmergedlo.so` đã thay đổi ngoài hai bản sao dùng chụp. Chưa kết luận tiến trình nào thay file đó. Baseline và preview vẫn cùng SHA-256 `83914d601529086990eb8f41b1b63586ac81cefa66761e51a9e577cfcca775ce`; mọi ảnh so sánh chạy trên hai bản sao này. Vì vậy báo cáo dùng dấu vân tay **snapshot baseline**, không lấy binary `/opt/hst` cuối phiên làm nguồn cho ảnh đã chụp. Script preview tái tạo được sáu file tài nguyên; không khẳng định bản sao mới nhất có cùng binary với lượt chụp cũ.

Các ảnh bề mặt phụ: Writer có chữ được chọn (nút Copy/Paste bật), sidebar mở, menu ứng dụng, menu ngữ cảnh, hộp thoại Phông chữ và Start Center, ở sáng/tối 100%. Không gọi đó là kiểm thử mọi hộp thoại hoặc mọi lệnh của sản phẩm.

**Quan sát và giới hạn:** nét HST đọc được, các biểu tượng mới không làm tăng chiều cao; caption Home đứng và dấu tiếng Việt không bị cắt ở những ảnh đã xem. Các nút bị vô hiệu hóa dùng cách giảm tương phản của VCL/GTK; không đổi công thức paint toàn cục. Những icon và chữ disabled vốn rất nhạt vẫn khác mockup, cần lượt đánh giá trạng thái/native riêng. Gallery Kiểu và nhóm cuối vẫn có thể nằm trong overflow; không ép co chữ để lấy chỗ. Cảnh báo thiếu Times New Roman trên máy Linux hiện trong combo font của cả baseline và HST; không thay font tài liệu trong phạm vi công việc này.

Một lượt thử sớm và cả lượt baseline gặp abort khi đóng Slides (`SlideSorterController::GetPageSelector`, sau khi đã chụp), cùng một số timeout AT-SPI. Chưa xác định nguyên nhân abort; **không suy đoán là lỗi icon hoặc đã sửa lỗi đó**. Runner được sửa để dùng accessibility bus riêng, chọn tab qua interface Selection, bỏ duyệt toàn bộ ô Sheets và chọn đúng PID. Ảnh lỗi/nhầm tab không được đưa vào ma trận nghiệm thu. Không coi việc sửa harness là sửa binary.

## Phần tài nguyên của hướng A

[`hst-ribbon-look-ui.patch`](../../../patches/libreoffice/hst-ribbon-look-ui.patch) được sinh bằng [`generate-ribbon-look.py`](../../../scripts/patches/generate-ribbon-look.py), đặt **sau series hiện có**:

- Caption nhóm `lbHome*`: italic → normal, giữ scale 0,9, nội dung và khóa dịch.
- `bxHomeFormatPaintbrush`, `bxHomeResetAttributes`, `bxHomeSetDefaults`: `toolbar-style` chuyển sang `icons`; nhãn lệnh vẫn cho tooltip và tên trợ năng.
- Grid Home có cặp margin 3/3: chuyển thành 4/2, giữ tổng bề rộng margin. Column spacing đang là 3: tăng lên 4. Không tăng margin trên/dưới, row spacing, cỡ font hoặc canvas icon của widget.
- Giữ nguyên object, thứ tự nhóm, action-name, priority, accessible name, controller, overflow và cấu trúc tab. Không thêm wrapper/reparent group.

[`hst-ribbon-look-config.patch`](../../../patches/libreoffice/hst-ribbon-look-config.patch) dùng `Misc/NotebookbarColorTransparency=255`: bỏ pha màu module, lấy nền native trung tính. Đã cập nhật kỳ vọng kiểm thử default/panel tương ứng; lượt kiểm tra panel GTK3 của ba ứng dụng đạt cả sáu kiểm tra. Không gán các token đề xuất vào màu ứng dụng toàn cục vì sẽ đổi cả dialog/tài liệu ngoài ribbon. Nét icon sáng/tối dùng `#294159` / `#DBE7F1` trong tài nguyên.

Còn khác mockup A: tab và focus/hover/pressed native; hình dạng combo và viền; font UI hệ thống; đường phân nhóm; cỡ hiển thị Paste và hitbox; màu nền tối native thay vì đúng `#1C2B3B`; màu tab/module, khoảng cách phụ thuộc requisition, gallery trong overflow, disabled native. Không giả vờ đạt mockup bằng cách đổi VCL paint hoặc bỏ banner.

**Ước lượng, chưa đo bằng triển khai:** để sát mockup cần 6–10 ngày kỹ thuật VCL cho metric/token có phạm vi notebookbar, trạng thái tab/nút, combo/focus và overflow; thêm 5–8 ngày kiểm tra/sửa lỗi ba nền tảng, DPI/high contrast và contextual tab. Không nên đổi toàn bộ button/combobox VCL dùng chung. Các số này là dự trù, không phải cam kết hay số ngày đã làm.

## Dung lượng

Đơn vị MB dưới đây là 1.000.000 byte. `images_hst.zip` **710.632 B**, `images_hst_dark.zip` **711.292 B**, tổng **1.421.924 B = 1,422 MB**. Đây là phần tài nguyên icon mới trong cây cài đặt trên cả ba nền tảng; chưa cộng chênh lệch binary do patch C++.

| Gói | Phần icon mới trước nén installer | Chênh lệch file installer cuối |
|---|---:|---|
| `.deb` | +1,422 MB | Chưa đo bằng full build; mô hình tar + XZ cho riêng hai ZIP: **899.172 B**. Không gọi đây là số tăng chính xác của `.deb`. |
| `.msi` | +1,422 MB | Chưa có runner Windows/CAB. **Phỏng đoán 1,1–1,5 MB**, tùy nén và metadata; cần đo hai MSI cùng cấu hình. |
| `.dmg` | +1,422 MB | Chưa có macOS/UDZO. **Phỏng đoán 1,1–1,5 MB**, tùy filesystem/nén; cần đo hai DMG cùng cấu hình và ký. |

Mô hình tar + zlib cho riêng hai ZIP là **1.169.366 B**; đây không phải kết quả CAB hoặc DMG. Không ghi số kích thước tổng installer khi chưa build. Để đo chính xác, build baseline và patch cùng toolchain, cấu hình, tài nguyên, chữ ký và revision; so kích thước artifact cuối lẫn thành phần `share/config/images_hst*.zip` sau giải nén.

Đối chiếu các ZIP đang cài: Colibre sáng/tối **5,800 MB**, Breeze **4,097 MB**, Sifr **4,850 MB**; hai HST bằng khoảng **24,5%** cặp Colibre. Giữ các theme cũ để bảo toàn lựa chọn của người dùng. Nếu nén cả PNG lẫn SVG của 440 glyph ban đầu bằng cùng bộ ghi ZIP, hai gói là **3,088 MB**; bản tích hợp SVG-only, kể cả sáu mẫu bổ sung và giấy phép, còn **1,422 MB**. Không commit ZIP, cây theme xuất, PNG contact sheet hoặc các export size trùng lặp.

Toàn bộ nội dung file cần thêm/sửa trong working tree khoảng **14,45 MB** nếu merge cả nguồn icon và proposal đang untracked từ trước. Trong đó 84 ảnh lossless chiếm **11,457 MB**, thay cho **21,665 MB** PNG gốc; nguồn icon gồm các sửa/bổ sung là **0,787 MB**, proposal/inventory có sẵn là **1,842 MB**. Phần tích hợp gồm ảnh, báo cáo, script, patch và kiểm thử khoảng **11,82 MB**. Số byte và cách đếm ghi riêng các nhóm; đây là dung lượng nội dung file, chưa đo Git pack sau commit. Không cộng cây upstream, bản cài sao chép, cache hay PNG gốc trong `build/` vào dung lượng cần merge.

## Tái tạo và kiểm tra

Kết quả kiểm tra: bốn unit test tài nguyên đạt; ba patch áp sạch lên các file tái tạo sau series; patch Home sinh lại khớp byte và phép sửa idempotent trên cả ba app; target make tạo đúng hai ZIP; sáu file tài nguyên preview tái tạo khớp; sáu kiểm tra panel GTK3 đạt; đủ 72 trạng thái và số đo; 84 ảnh chuyển lossless khớp RGBA. Kiểm tra link nội bộ và cú pháp Python đạt. Installer ba nền tảng chưa chạy.

Từ gốc repository, build tài nguyên không cần upstream checkout:

```sh
python3 scripts/brand/build-hst-icon-theme.py --out build/hst-icons
python3 scripts/brand/build-hst-icon-theme.py --out build/hst-icons --check
python3 -m unittest tests/brand/test-hst-icon-theme.py -v
```

Với cây LibreOffice đúng source lock, dùng các luồng build hiện có; ví dụ thao tác tài nguyên chung:

```sh
HST_LO_SRC=/path/to/libreoffice bash scripts/apply-patches.sh
python3 scripts/brand/apply-icon-overrides.py --tree /path/to/libreoffice
python3 scripts/brand/apply-icon-overrides.py --tree /path/to/libreoffice --check
# Chạy lại configure/autogen cho cây incremental để WITH_THEMES có hst hst_dark.
# Tiếp tục make/build/package theo script Linux, Windows hoặc macOS hiện có.
# Trên cây đã build: make CppunitTest_vcl_app_test
```

Không cần ép `SymbolStyle=hst` trong default config: việc đó sẽ ngăn Automatic theo chế độ tối. Không ghi đè profile người dùng. Với `--with-theme` tự chỉ định, phải gồm ít nhất `hst hst_dark colibre colibre_dark` và các theme muốn giữ.

Preview bản cài cũ, không sửa `/opt/hst`:

```sh
python3 scripts/brand/prepare-hst-icon-preview.py \
  --installed /opt/hst --copy build/hst-preview
Xvfb :91 -screen 0 3000x1800x24 -nolisten tcp -ac
# Ở terminal khác; khi chạy root đặt HST_BUILD_USER thành tài khoản thường có sẵn.
HST_BUILD_USER=ubuntu /usr/bin/python3 tests/runtime/check-hst-icon-theme.py \
  --display :91 --instdir build/hst-preview \
  --out build/hst-shots --work build/hst-runtime \
  --variant hst --mode light --scale 1 --legacy-binary
```

Lặp `--mode light/dark`, `--scale 1/2`. Baseline dùng bản sao nguyên trạng `/opt/hst`, `--variant baseline`, bỏ `--legacy-binary`. Cần Python-UNO của bản cài, `python3-pyatspi`, Xvfb, dbus, xdotool, ImageMagick, locale và GTK SVG loader. Thêm `--apps writer --surfaces` để chụp các bề mặt phụ. Khi dùng binary đã build patch mới, **bỏ `--legacy-binary`**, kiểm tra Automatic và đổi light/dark lần nữa.

Sau khi đủ ma trận PNG, dùng `tests/runtime/summarize-hst-icon-theme.py --shots DIR --raw-cache build/raw-shots --installed /path/to/untouched-baseline-copy --preview build/hst-preview [--source-tree TREE]`. Script xác nhận đủ 72 trạng thái, tab được chọn, số đo, kích thước ảnh, binary baseline/preview giống nhau và chuyển lossless. Audit fallback: `scripts/brand/audit-hst-icon-coverage.py --installed /opt/hst --themes build/hst-icons --out build/hst-coverage`.

**Rebase với công việc contextual tab/fold:** bỏ riêng `hst-ribbon-look-ui.patch` khỏi cuối series trong bản sao làm việc, áp các patch khác của hai nhánh, rồi chạy:

```sh
python3 scripts/patches/generate-ribbon-look.py \
  --tree /path/to/tree-after-other-patches \
  --patch patches/libreoffice/hst-ribbon-look-ui.patch
```

Đặt patch sinh lại ở cuối series và đo lại runtime. Script chỉ đọc tree nguồn, tìm Home bằng ID, sửa dòng thuộc caption/grid Home, không serialize lại cả XML. Đã kiểm tra áp cả ba patch mới bằng `git apply --check` sau khi tái tạo các file liên quan từ pin + series trước đó. **Không tuyên bố đã kiểm tra toàn bộ series trên một checkout LibreOffice đầy đủ**: sandbox chỉ lấy các file nguồn cần đọc/tái tạo, không có build tree hoàn chỉnh.
