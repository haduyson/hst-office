# License & trademark audit — HST Office trên LibreOffice

> Trạng thái: **bằng chứng kỹ thuật đã thu thập; CHƯA được người có thẩm quyền pháp lý duyệt.** Không phải ý kiến pháp lý.
> Ngày: 2026-10-29. Nguồn: LibreOffice 26.8.1.1 — [lock](../upstream/libreoffice-lock.json). Audit ONLYOFFICE trước đó: git `577f620` và nhánh `archive/onlyoffice-plugin-first` (không còn áp dụng, [ADR 0002](ADR/0002-libreoffice-standalone.md)).

## 1. Văn bản đã lưu nguyên văn

| File | Nguồn trong tarball | Ghi chú |
|---|---|---|
| `LICENSES/upstream/libreoffice/COPYING.MPL` | `COPYING.MPL` | Mozilla Public License 2.0 — giấy phép chính của LibreOffice |
| `LICENSES/upstream/libreoffice/COPYING.LGPL` | `COPYING.LGPL` | LGPLv3 (mã thừa hưởng từ OpenOffice.org theo Apache/LGPL) |
| `LICENSES/upstream/libreoffice/COPYING` | `COPYING` | GPLv3 (một số thành phần) |
| `LICENSES/upstream/libreoffice/license.xml`, `NOTICE` | `readlicense_oo/license/` | Danh sách giấy phép bên thứ ba được ship trong sản phẩm |
| `LICENSES/upstream/libreoffice-dictionary-vi/LICENSES-{en,vi}.txt` | `dictionaries/vi/` | Từ điển chính tả tiếng Việt v1.0.45 — **GPLv2** (Ivan Garcia, Nguyễn Xuân Minh, dựa trên danh sách của GS. Hồ Ngọc Đức) |

Hash từng file: `LICENSES/upstream/libreoffice/provenance.json`. Tarball nguồn kiểm chữ ký GPG khóa `C2839ECA…AEA3` ("LibreOffice Build Team (CODE SIGNING KEY)") — "Good signature"; khóa chưa được xác thực qua web of trust.

> Lưu ý: GitHub hiển thị `LibreOffice/core` là "GPL-3.0" vì file `COPYING`; giấy phép thực tế của phần lớn mã là MPL-2.0 (xem header từng file và `license.xml`).

## 2. Phân chia giấy phép cho HST Office

| Thành phần | Giấy phép | Nghĩa vụ |
|---|---|---|
| File LibreOffice HST sửa (patch trong `patches/libreoffice/`) | Giữ nguyên giấy phép của file (MPL-2.0, hoặc dual MPL/LGPL theo header) | Công bố source file đã sửa (repo public + tarball source tương ứng) |
| Mã HST mới, file riêng (extension, script build, generator) | AGPL-3.0 (quyết định chủ dự án) | MPL-2.0 §3.3 cho phép kết hợp với GNU licenses khi file không đánh dấu "Incompatible With Secondary Licenses" — **cần legal xác nhận** (LEG-06) |
| Mẫu văn bản (`templates/`) | CC BY 4.0 | Ghi công |
| Asset thương hiệu HST | Không cấp phép (thương hiệu HASON TECH) | — |
| Từ điển `vi` | GPLv2 (tác giả gốc) | Kèm license, source = file `.dic/.aff` |
| Thư viện bên ngoài do LibreOffice bundle | theo `license.xml` | Giữ `license.xml`/`NOTICE` trong gói cài |

## 3. Thương hiệu

- Nhãn hiệu TDF: tên "The Document Foundation", "LibreOffice", logo kẹp giấy, tên miền libreoffice.org/documentfoundation.org. Văn bản chính sách lưu tại [`LICENSES/upstream/libreoffice/TDF-trademark-policy.txt`](../LICENSES/upstream/libreoffice/TDF-trademark-policy.txt) (bản lưu trữ, sửa lần cuối 2020-05-14; wiki trực tiếp chặn truy cập tự động).
- Chính sách yêu cầu dùng nhãn hiệu **không gây nhầm lẫn**: phần mềm không do TDF làm thì không được ngụ ý là của TDF. Ghi "derivative of"/"based on LibreOffice" là **được phép (Permitted Use 4), không bắt buộc**. Không có điều khoản nào buộc hiển thị LibreOffice trong giao diện, About, splash hay bộ cài.
- Hệ quả: càng ít hiển thị LibreOffice trong nhận diện sản phẩm, rủi ro nhãn hiệu càng thấp. Tên nhãn hiệu chỉ cần xuất hiện ở văn bản pháp lý (giấy phép, bản quyền, thông báo bên thứ ba).

### 3.1 Bắt buộc giữ (giấy phép)

| Nghĩa vụ | Căn cứ | Cách HST đáp ứng |
|---|---|---|
| Văn bản giấy phép MPL-2.0 đi kèm bản phân phối | MPL-2.0 §3.1/§3.2 | `license.html`/`LICENSE` trong thư mục cài (Trợ giúp → Thông tin giấy phép) |
| Báo người nhận bản thực thi cách lấy mã nguồn | MPL-2.0 §3.2(a) | Mục "HST Office" ở đầu tài liệu giấy phép (hộp thoại Trợ giúp → Thông tin giấy phép và `LICENSE.html`/`LICENSE`), song ngữ Việt–Anh: cách nhận bản sao mã nguồn tương ứng qua liên hệ HASON TECH (lienhe@hasontech.vn). Không có URL kho mã trong sản phẩm (kho có thể đổi chỗ); About chỉ có câu ngắn "Phần mềm nguồn mở — xem Trợ giúp → Thông tin giấy phép." |
| Không xóa/sửa thông báo giấy phép, bản quyền trong file nguồn | MPL-2.0 §3.4 | Patch không đụng header; repo công bố file đã sửa |
| Giấy phép + thông báo của thư viện bên thứ ba (LGPL, BSD, MIT, Apache NOTICE…) | Từng giấy phép trong `license.xml` | Giữ nguyên danh sách thông báo bên thứ ba trong tệp giấy phép |
| Từ điển `vi` GPLv2: kèm giấy phép, cung cấp nguồn | GPLv2 §1, §3 | `LICENSES-vi.txt` trong extension từ điển (bản thân `.dic/.aff` là nguồn) |

Trong các văn bản trên, chữ "LibreOffice"/"The Document Foundation" xuất hiện vì là **chủ thể bản quyền**; giữ nguyên.

### 3.2 Không bắt buộc — HST gỡ hoặc thay

| Vị trí | Hiện trạng 26.8.1.1 | Xử lý |
|---|---|---|
| About: "%PRODUCTNAME có nguồn gốc từ LibreOffice…", dòng "Bản quyền © … cộng tác viên LibreOffice", nút Credits, "dựa trên LibreOffice 26.8.1.1" cạnh số phiên bản | Đang hiện | **Đã xử lý** (`hst-about.patch`): gỡ cả 3 dòng/nút, không hiện EXTRA_BUILDID và liên kết build id; thay bằng một câu "Phần mềm nguồn mở — xem Trợ giúp → Thông tin giấy phép." (không URL; nút Release Notes cũng ẩn) + khối liên hệ HASON TECH. Dòng `Engine:` chỉ có trong "Sao chép thông tin phiên bản". Tuỳ chọn `--with-extra-buildid` đã gỡ khỏi `build-config/*.conf` (cây Linux hiện tại giữ giá trị cũ trong `config_buildid.h` đến lần `--configure` sạch kế tiếp; mã không còn đọc nó) |
| `soffice --version` | "HST Office 1.0.0 (LibreOffice 26.8.1.1)" | **Đã xử lý** (`hst-version.patch`): "HST Office 1.0.0 <build id>" |
| Chuỗi giao diện nhắc LibreOffice (Cộng đồng LibreOffice, Quyên góp, Impress Remote, LibreOffice Basic…) | 17 chuỗi vi | **Đã xử lý**: `l10n/vi-overrides.jsonl` (13 dòng) do `scripts/l10n/apply-overrides.py` áp lúc `--build`: About, báo cáo sự cố, "%PRODUCTNAME _Basic" (nhãn tuỳ chọn xuất HTML, không phải định danh macro), thư viện Basic bảo vệ mật khẩu, gói Windows, tooltip Impress Remote (liên kết ẩn), Quyên góp (đã ẩn), "yêu cầu phiên bản engine tối thiểu". **Giữ** (văn bản pháp lý): hộp thoại Giấy phép (`licensedialog`) và tài liệu readme/credits. Chuỗi tiếng Anh (en-US) nhắc LibreOffice chưa đổi vì đổi msgid làm mất bản dịch |
| Liên kết tới libreoffice.org / documentfoundation.org (get-involved, FAQ, portable, accessibility, volunteer support, chứng nhận) | Hardcode trong mã + officecfg | **Đã xử lý** (`hst-debrand.patch`, `hst-defaults.patch`): menu Trợ giúp/Start Center trỏ hasontech.vn (`utm_medium=menu`); "Gửi phản hồi", "Tham gia đóng góp", Release Notes và Credits **ẩn** (URL cấu hình để trống, `hst-remove-donation.patch`, `hst-about.patch`) — không còn URL GitHub/kho mã nào trong sản phẩm; URL mở nguyên văn không kèm `LOversion/LOlocale`; mẹo trong ngày: bỏ 6 mẹo quyên góp/cộng đồng/chứng nhận/bản portable/tài liệu LibreOffice, liên kết help.libreoffice.org mở trang trợ giúp HST, liên kết wiki/trang TDF khác ẩn; nút "Tải ứng dụng" Impress Remote ẩn. Kho extension trực tuyến không còn được liên kết (chỉ cài từ tệp `.oxt` do người dùng chọn, `hst-extensions.patch`). Chi tiết từng URL: báo cáo `plans/reports/opus-debrand-261029-1945-remove-libreoffice-ui.md` |
| Trợ giúp F1 (build `--without-help` → mở help.libreoffice.org) | Mở site LibreOffice | **Đã xử lý**: F1, menu Trợ giúp, nút Trợ giúp của hộp thoại mở một URL duy nhất `Office.Common/Help/HelpRootURL` (`officecfg/.../Common.xcs`): Hướng dẫn sử dụng tiếng Việt ngoại tuyến `help/index.html` trong extension HST đi kèm (`vnd.sun.star.expand:$BUNDLED_EXTENSIONS/...`, mở bằng trình duyệt hệ thống; `hst-offline-help.patch`); đổi sang trang web chỉ cần sửa giá trị này. Hộp thoại "chưa cài trợ giúp" tắt mặc định |
| Trang extension (extensions.libreoffice.org, hub.libreoffice.org/extensions) | Mở site LibreOffice | **Đã xử lý** (`hst-extensions.patch`, `hst-defaults.patch`, `hst-start-center-banner.patch`; chủ dự án 2026-10-29): không còn liên kết/đường dẫn tới kho extension hay danh mục trực tuyến nào. Nút Phần mở rộng ở Start Center mở Extension Manager; liên kết "Get more extensions online", nút/mục "Update", cập nhật extension qua mạng, hộp thoại danh mục trực tuyến (mẫu, từ điển, giao diện, biểu tượng, bảng màu, thư viện ảnh) và các mẹo dẫn tới site extension đều bị gỡ/ẩn. Người dùng chỉ cài extension từ tệp `.oxt` tự chọn (Add…, nhấp đúp `.oxt`, `soffice tệp.oxt`); mọi trường hợp đều hiện hộp thoại "Cài đặt tiện ích mở rộng" nêu HASON TECH không kiểm duyệt bên thứ ba, người dùng tự chịu trách nhiệm, nút Tiếp tục/Hủy. Extension HST đi kèm (bundled) không đổi. Liên kết trang chủ tác giả trong metadata các extension từ điển bên thứ ba vẫn còn (đã gỡ link thư viện extension khỏi từ điển `en`) |
| Tên tệp/gói nội bộ (`libreofficekit`, `libreoffice.soc`, `Libreoffice.theme`) | Không hiện tên công ty, một số hiện tên bảng màu/chủ đề | **Đã xử lý**: bảng màu `libreoffice.soc` hiển thị "HST Office", tên màu "(Main Color)". Chủ đề `Libreoffice.theme` **giữ tên** vì mã tra cứu theo tên "LibreOffice" (ColorSets.cxx, xuất PPTX); tên tệp kỹ thuật giữ |

Phiên bản engine 26.8.1.1 vẫn dùng **nội bộ** cho kiểm tra tương thích extension, không hiển thị.

## 4. Kết luận

| Phạm vi | Trạng thái |
|---|---|
| Build nội bộ, kiểm thử | Cho phép |
| Phát hành công khai `.deb` HST Office | **Chờ duyệt** LEG-03/06/07 + QA |
| Windows/macOS installer | BLOCKED (OPS-01, SIGN-01) |
