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

- "LibreOffice" và logo thuộc The Document Foundation (TDF). Bản phái sinh **phải đổi tên và gỡ logo** khỏi nhận diện sản phẩm; được phép ghi trung thực "dựa trên LibreOffice". Chính sách: <https://www.libreoffice.org/about-us/trademark-policy/> — **nội dung chưa được lưu nguyên văn** (LEG-07).
- HST gỡ: tên sản phẩm (configure `--with-product-name`), splash/About/Start Center (`--with-branding`), icon/desktop file, URL trỏ về libreoffice.org cho update/donate/get-involved (patch + cấu hình). Kiểm tra bằng `scripts/check-branding.py` trên `instdir`.
- Giữ: văn bản giấy phép, credits, thông báo bản quyền trong mã nguồn.

## 4. Kết luận

| Phạm vi | Trạng thái |
|---|---|
| Build nội bộ, kiểm thử | Cho phép |
| Phát hành công khai `.deb` HST Office | **Chờ duyệt** LEG-03/06/07 + QA |
| Windows/macOS installer | BLOCKED (OPS-01, SIGN-01) |
