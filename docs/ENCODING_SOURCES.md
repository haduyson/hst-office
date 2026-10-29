# Nguồn bảng mã TCVN3 / VNI → Unicode

Bảng dùng trong `data/vietnamese/encoding-maps.json` (nạp bởi `hst_office/encoding.py`). Nguồn, hash và kiểm chéo ghi trong `data/vietnamese/provenance.json`; script dựng lại: `tests/fixtures/vietnamese/derive-encoding-data.py`.

## Nguồn

| Nguồn | Vai trò | Ghi chú |
|---|---|---|
| [Unicode & Vietnamese Legacy Character Encodings](https://vietunicode.sourceforge.net/charset/) (Vietnamese Unicode FAQ) | **Bảng chạy thật**: 74 byte đơn TCVN3 và 134 chuỗi VNI | SHA-256 của trang lúc lấy: xem `provenance.json` |
| [Wikipedia “VNI”](https://en.wikipedia.org/wiki/VNI) bảng *VNI “ANSI” Encoding (Windows/Unix)*, mô hình dấu kết hợp | **Kiểm chéo độc lập VNI** và xác nhận từng chuỗi VNI của vector | Trang này dẫn lại nguồn trên nhưng mô tả dạng *chữ cái + dấu kết hợp*, tạo ra kết quả bằng đường tính khác (NFC) |
| glibc `TCVN5712-1` (gói `locales`, đọc qua `iconv`) | **Kiểm chéo độc lập TCVN3** và bộ mã hóa cho vector TCVN3 | `/usr/share/i18n/charmaps/TCVN5712-1.gz`, phiên bản gói trong `provenance.json` |

Chỉ là ánh xạ mã ký tự (dữ kiện); không sao chép văn bản của nguồn. Cần rà soát pháp lý nếu phân phối rộng hơn.

## Phạm vi và quy ước

- Văn bản cũ vào Writer dưới dạng ký tự giải mã **Windows‑1252**; mỗi ký tự được đổi lại thành byte gốc rồi tra bảng. Ký tự trên U+00FF (đã là Unicode) và byte không có trong bảng được giữ nguyên và đếm riêng.
- **TCVN3 (ABC)**: 74 byte đơn (67 chữ thường có dấu/không dấu đặc biệt + `Ă Â Ê Ô Ơ Ư Đ`). Chữ **hoa có dấu** của TCVN3 nằm trong font `.Vn…H` (`.VnTimeH`, `.VnArialH`…) dùng *cùng mã với chữ thường*: bộ chuyển chỉ đổi chữ hoa khi font của đoạn văn bản có tên bắt đầu `.Vn` và kết thúc `H`; chữ ASCII không bị đổi. Bảng VN1 của glibc (chữ hoa ở 0x80–0x9F…) **không** dùng làm bảng chạy vì trùng với dấu câu cp1252 (ví dụ ‘ ’ “ ”).
- **VNI Windows**: chữ + byte dấu (ví dụ `a`+`ø` = à); `Đ đ Ơ ơ Ư ư Ĩ ĩ Ị ị Ỉ ỉ Ỵ ỵ` là byte đơn. Khớp theo chuỗi dài nhất; dấu chữ hoa (0xC0–0xDF) và chữ thường (0xE0–0xFF) không trộn.
- Văn bản có chữ Việt Unicode ngoài Latin‑1 (ví dụ `ộ`, `ệ`, `ơ`) được coi là *đã Unicode* và giữ nguyên cả đoạn (tránh làm hỏng). Từ chỉ chứa ký tự Latin‑1 (`hòa`) là mơ hồ: người dùng phải chọn bảng mã, xem trước, hoặc bỏ chọn.
- Nhận diện (`encoding_detect.suggest`) chỉ **gợi ý** kèm độ tin cậy (kiểm tra âm tiết tiếng Việt hợp lệ sau khi chuyển); không bao giờ tự áp dụng.
- Font cũ (`.Vn…`, `VNI-…`) được thay bằng font Unicode (`Times New Roman`/`Arial`) để kết quả đọc được.

## Vector chuẩn (golden vectors)

`tests/fixtures/vietnamese/encoding-vectors.json` (288 ca) **không** sinh bằng bộ chuyển đổi đang test:

1. Chữ cái VNI (134): chuỗi byte lấy từ nguồn vietunicode, được kiểm bằng cách dựng độc lập từ bảng Wikipedia (chữ cái hoặc ô tiền‑ghép + ô dấu kết hợp cùng kiểu hoa/thường → NFC → đúng chữ đó). Hai nguồn phải khớp 134/134, nếu không script dừng.
2. Chữ cái TCVN3 (74): byte → ký tự qua `iconv -f TCVN5712-1` của glibc; script yêu cầu 74/74 trùng bảng chạy.
3. Chữ hoa trong font `.Vn…H` (67): mã chữ thường + chữ hoa tương ứng do tên Unicode (`SMALL`→`CAPITAL`) và có mặt trong bảng glibc.
4. Câu mẫu (7 VNI, 6 TCVN3): mã hóa VNI từ bảng ngược của vietunicode đã kiểm; mã hóa TCVN3 bằng `iconv -t TCVN5712-1`. Kết quả mong đợi là chuỗi tiếng Việt viết tay trong script.

Chạy lại: `python3 tests/fixtures/vietnamese/derive-encoding-data.py --cache <thư mục> --write` (cần mạng; sửa mọi file đầu ra và `manifest.json` hash). Kiểm: `python3 -m unittest discover -s tests/unit -p 'test_encoding.py'`.

## Giới hạn đã biết

- Chưa có tài liệu TCVN3 thực tế do người dùng cung cấp để so sánh (UNVERIFIED với tài liệu thật).
- Chữ hoa có dấu TCVN3 chỉ chuyển đúng khi tên font còn lưu trong tài liệu; nếu font bị mất, người dùng cần tự chọn.
- Không hỗ trợ VNI Mac/DOS, VISCII, VPS, BK HCM, Unicode tổ hợp.
