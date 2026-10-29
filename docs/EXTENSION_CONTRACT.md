# Hợp đồng extension LibreOffice (HST)

Thay thế [PLUGIN_CONTRACT](PLUGIN_CONTRACT.md) (ONLYOFFICE) theo ADR 0002. Một extension Python‑UNO đi kèm: `extensions/hst-vietnamese-tools/` → `dist/extensions/hst-vietnamese-tools.oxt`.

## Gói và đăng ký

| Mục | Giá trị |
|---|---|
| Identifier / version | `vn.hasontech.hst.vietnamese-tools` / `1.0.0`, yêu cầu LibreOffice ≥ 7.5 (`LibreOffice-minimal-version`, namespace `http://libreoffice.org/extensions/description/2011`) |
| Component | `python/hst_office_component.py` (`application/vnd.sun.star.uno-component;type=Python`) đăng ký service `org.hst.office.vi.DispatchProvider` (`com.sun.star.frame.ProtocolHandler`) |
| Giao thức | `ProtocolHandler.xcu`: `org.hst.office.vi:*` — `Nd30Wizard`, `ConvertEncoding`, `FormatDate`, `FormatVnd`, `FormatPercent`, `ImportCsv` |
| Menu/toolbar | `Addons.xcu`: menu **HST** (Writer + Calc) và toolbar `org.hst.office.vi.toolbar` (nút chỉ có chữ). Nhãn vi/en phải khớp `locales/{vi,en}.json` → `menu` (`scripts/check-extensions.py` kiểm) |
| Dữ liệu trong gói | `data/{nd30,number-formats,encoding-maps,provenance}.json` sao từ `data/vietnamese/` lúc build; `license/LICENSE.txt` (AGPL‑3.0), `license/NOTICES.txt` |
| Triển khai đi kèm | `unopkg` **không** có `--bundled`. Extension đi kèm là **thư mục đã giải nén** `<install>/share/extensions/hst-vietnamese-tools/` (nội dung .oxt); office đăng ký ở lần chạy đầu của profile mới. Chỉ chép `.oxt` cạnh file chạy là không đủ. Ghép vào gói cài do Phase 07 |
| Không có | mạng, Node, iframe/web view, hạ macro security, thư viện ngoài (kiểm bằng `check-extensions.py`) |

## Hành vi lệnh

- **Văn bản NĐ 30** (Writer): hộp thoại gốc với 7 loại và mọi trường; trường trống → `[placeholder]`; xem trước không ghi; Hủy không ghi. Chèn tại con trỏ trong **một bước Undo**; từ chối trước khi ghi nếu có vùng chọn, con trỏ ngoài thân văn bản (bảng/khung/đầu‑chân trang/chú thích) hoặc tài liệu chỉ đọc. Tuỳ chọn áp A4 + lề NĐ 30 (kiểm khoảng 20–25/20–25/30–35/15–20 mm) và số trang giữa lề trên, ẩn trang 1.
  - **Giới hạn Undo (đã chứng minh trên 24.2; cùng mã nguồn ở 26.8)**: thay đổi *kiểu trang* qua UNO không undo được và, nếu bật Undo, **xoá toàn bộ lịch sử Undo** (`sw/source/core/unocore/unostyle.cxx`, “Fix i64460”). Extension khoá Undo khi sửa kiểu trang (lịch sử cũ giữ nguyên với chỉ lề) nhưng **tạo đầu trang** (số trang) dịch vị trí nút nên phải xoá lịch sử Undo trước; nhãn hộp thoại ghi rõ. Nội dung chèn luôn là đúng một bước Undo. Action Undo tuỳ biến cho kiểu trang làm Writer **crash** khi Redo nên không dùng.
  - Lề hiệu dụng: `TopMargin + HeaderHeight` = lề trên ND30; DOCX xuất `w:top` = 20 mm (kiểm trực tiếp trong `document.xml`).
- **Chuyển TCVN3/VNI → Unicode**: người dùng *phải* chọn bảng mã; gợi ý chỉ là văn bản. Xem trước gốc/kết quả. Áp dụng theo **từng phần văn bản (run)**: chèn văn bản mới ở cuối run (thừa hưởng định dạng) rồi xoá run cũ — `setString` sẽ mất đậm/nghiêng. Từ chối trước khi ghi: chỉ đọc, đang ghi/ có thay đổi theo dõi, không có/nhiều vùng chọn, vùng chọn không phải văn bản, phần được bảo vệ, nội dung đổi sau xem trước. Trường (số trang…), chú thích cuối, v.v. bị bỏ qua và đếm. Một Undo khôi phục văn bản + định dạng.
- **Định dạng Calc**: ngày, VND, phần trăm theo `number-formats.json`. Mã trong file dùng dấu phân cách **en‑US**; `addNewConverted(code, en-US → vi-VN)` đăng ký đúng khoá (nếu nạp thẳng mã đó cho vi‑VN thì hiển thị sai `1234567,000 ₫`). Không đổi giá trị/công thức; ô văn bản được báo số lượng. Từ chối khi trang tính bị bảo vệ.
- **Nhập CSV**: UTF‑8 chặt (BOM tùy chọn; UTF‑16/NUL/byte lỗi → lỗi rõ, không thay thế), dấu `, ; Tab` (gợi ý), xem trước 10 dòng, mặc định mọi ô là **văn bản** (định dạng `@`, giữ `00123`, `=…`, `+…`, `-…`, `@…`); chế độ “số nếu an toàn” chỉ chuyển số thập phân thường không số 0 đầu. Giới hạn: 10 MiB, 50 000 dòng, 200 cột, 32 767 ký tự/ô — vượt thì lỗi, không cắt âm thầm. Đích = ô đang chọn; đích không trống cần xác nhận ghi đè; vượt biên/trang tính bảo vệ bị từ chối trước khi ghi. Ghi từng ô bằng `setString` trong một bước Undo (`setDataArray` không được Undo hoàn tác đúng — đã kiểm). Tốc độ đo: ~0,25–0,3 ms/ô (5 000×3 ô ≈ 4–5 s).

## Bằng chứng (xem `plans/reports/opus-05-261029-1342-vietnamese-extensions.md`)

- `python3 -m unittest discover -s tests/unit -p 'test_*.py'` (logic thuần, không cần `uno`).
- `python3 scripts/build-extensions.py --output dist/extensions --verify-reproducible` và `python3 scripts/check-extensions.py --directory dist/extensions` (+ `--self-test`).
- `python3 tests/runtime/check-extensions.py --soffice <soffice> --extension dist/extensions/hst-vietnamese-tools.oxt --fixtures tests/fixtures/vietnamese/manifest.json --output tests/output/extensions [--mode user|bundled --allow-modify-install] [--display :99]`. Chạy thật trên **LibreOffice 24.2.7.2 (Ubuntu)**; hộp thoại modal cần `--display`. **LibreOffice 26.8.1 (HST) chưa kiểm — chờ bản build của coordinator.**
