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
| Báo người nhận bản thực thi cách lấy mã nguồn | MPL-2.0 §3.2(a) | Câu "Mã nguồn: github.com/haduyson/hst-office" trong About và tệp giấy phép |
| Không xóa/sửa thông báo giấy phép, bản quyền trong file nguồn | MPL-2.0 §3.4 | Patch không đụng header; repo công bố file đã sửa |
| Giấy phép + thông báo của thư viện bên thứ ba (LGPL, BSD, MIT, Apache NOTICE…) | Từng giấy phép trong `license.xml` | Giữ nguyên danh sách thông báo bên thứ ba trong tệp giấy phép |
| Từ điển `vi` GPLv2: kèm giấy phép, cung cấp nguồn | GPLv2 §1, §3 | `LICENSES-vi.txt` trong extension từ điển (bản thân `.dic/.aff` là nguồn) |

Trong các văn bản trên, chữ "LibreOffice"/"The Document Foundation" xuất hiện vì là **chủ thể bản quyền**; giữ nguyên.

### 3.2 Không bắt buộc — HST gỡ hoặc thay

| Vị trí | Hiện trạng 26.8.1.1 | Xử lý |
|---|---|---|
| About: "%PRODUCTNAME có nguồn gốc từ LibreOffice…", dòng "Bản quyền © … cộng tác viên LibreOffice", nút Credits, "dựa trên LibreOffice 26.8.1.1" cạnh số phiên bản | Đang hiện | Gỡ; thay bằng "Mã nguồn mở theo MPL-2.0 — xem Thông tin giấy phép" + link mã nguồn |
| `soffice --version` | "HST Office 1.0.0 (LibreOffice 26.8.1.1)" | Chỉ "HST Office 1.0.0" + build id |
| Chuỗi giao diện nhắc LibreOffice (Cộng đồng LibreOffice, Quyên góp, Impress Remote, LibreOffice Basic…) | 17 chuỗi vi | Thay bằng %PRODUCTNAME hoặc tên trung tính; menu/hộp thoại "tham gia/quyên góp" ẩn |
| Liên kết tới libreoffice.org / documentfoundation.org (get-involved, FAQ, portable, accessibility, volunteer support, chứng nhận) | Hardcode trong mã + officecfg | Trỏ về hasontech.vn hoặc ẩn mục |
| Trợ giúp F1 (build `--without-help` → mở help.libreoffice.org) | Mở site LibreOffice | Chủ dự án chọn (2026-10-29): trỏ trang hướng dẫn HST trên hasontech.vn |
| Trang extension (extensions.libreoffice.org) | Mở site LibreOffice | Chủ dự án chọn (2026-10-29): giữ kho LibreOffice (chỉ mở khi người dùng bấm) |
| Tên tệp/gói nội bộ (`libreofficekit`, `libreoffice.soc`, `Libreoffice.theme`) | Không hiện tên công ty, một số hiện tên bảng màu/chủ đề | Đổi tên hiển thị bảng màu/chủ đề; tên tệp kỹ thuật giữ |

Phiên bản engine 26.8.1.1 vẫn dùng **nội bộ** cho kiểm tra tương thích extension, không hiển thị.

## 4. Kết luận

| Phạm vi | Trạng thái |
|---|---|
| Build nội bộ, kiểm thử | Cho phép |
| Phát hành công khai `.deb` HST Office | **Chờ duyệt** LEG-03/06/07 + QA |
| Windows/macOS installer | BLOCKED (OPS-01, SIGN-01) |
