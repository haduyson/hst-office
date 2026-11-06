# Rà soát mẫu "Văn bản hành chính" khi văn bản dài nhiều trang

Ngày 06/11/2026 (giờ Asia/Saigon). Phạm vi: 68 mẫu Writer (37 hành chính NĐ30, 2 Thông tư NĐ78+187, 22 Đảng, 7 biểu mẫu văn thư) qua **hai đường**: tệp mẫu `.ott` và trình hướng dẫn "Văn bản hành chính" (`nd30_writer.insert_layout`); 5 sổ đăng ký Sheets (Phụ lục IV). Bản build dùng: bản chép `instdir` 26.8.1.1 (chép dưới `flock lo-make.lock`), headless, profile riêng, cổng 22087–22090/22093. Mọi tiến trình đã dừng.

## Cách đo

- Mỗi loại × 2 đường × 1, 2, 3, 5 trang: thêm đoạn văn tiếng Việt thật + danh sách đánh số (biểu mẫu kẻ bảng: thêm dòng) tới khi đủ số trang; xuất PDF, ODT, DOCX, DOC; mở lại ODT/DOCX/DOC và xuất PDF lại. Đo bằng PyMuPDF (hộp chữ, đường kẻ, số trang, phông, khoảng dòng), XML DOCX (`sectPr`, `pgMar`, `titlePg`, header) và UNO (kiểu trang từng trang, trang của khối chữ ký).
- Quét từng dòng qua ngắt trang đầu (45 bước) để bắt khối chữ ký bị tách, tiêu đề/"Nơi nhận" mồ côi, trang trắng cuối.
- Lần chạy trước sửa: 544 trường hợp + 122 lần quét; sau sửa: 532 + 122 (biểu mẫu một tờ chỉ 1 trang).
- Kết quả, PDF, DOCX: `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/template-audit/run/before`, `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/template-audit/run/after` (`results.json`), bảng: `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/template-audit/run/table.md`.

Mã kiểm tra: **1** lề/vùng chữ, **2** số trang, **3** khối đầu chỉ ở trang 1, **4** chữ ký/Nơi nhận/trang trắng, **5** bảng dài, **6** phông/cỡ/khoảng dòng, **7** bản DOCX/DOC/ODT mở lại không lệch.

## Kết quả chung (sau sửa)

| Kiểm tra | Kết quả |
|---|---|
| 1 Lề | Đạt mọi trang, cả 3 hồ sơ. Một kiểu trang, cùng hình học mọi trang (không đổi lề/hướng; văn bản kèm theo dùng bản sao cùng hình học). Vùng chữ đo được: NĐ30 trái ≥29,9 / phải ≥14,84 (đường kẻ 0,75 pt) / trên ≥20,16 / dưới ≥20,08 mm. DOCX: `w:top=1134 w:bottom=1134 w:left=1701 w:right=850 w:header=567 w:gutter=0` (20/20/30/15 mm, header 10 mm), không `mirrorMargins`. |
| 2 Số trang | Không có ở trang 1 (và trang đầu văn bản kèm theo); từ trang 2: chữ số Ả Rập, tâm x = 112,5 mm (giữa vùng chữ), đỉnh 10,2 mm, 14 pt (NĐ30, Đảng), 13 pt (Thông tư), liên tục. DOCX: `w:titlePg`, header "first" rỗng, header "default" có trường PAGE. Giống nhau ở PDF, ODT/DOCX/DOC mở lại. |
| 3 Khối đầu | Quốc hiệu/tiêu đề Đảng, cơ quan, số, ngày chỉ ở trang 1 (trừ trang đầu văn bản kèm theo, đúng mẫu 1.3/15). |
| 4 Chữ ký | Không lần quét nào tách khối chữ ký hay Nơi nhận; không tiêu đề mồ côi. Trang trắng cuối đã sửa (xem lỗi 1). |
| 5 Bảng | Biểu mẫu kẻ bảng lặp dòng tiêu đề mỗi trang, dòng không bị tách (`keep-together`), cột nằm trong lề. Sổ đăng ký: sửa lỗi in thiếu (lỗi 5). |
| 6 Phông | Chỉ Liberation Serif (thay thế đo-kích-thước của Times New Roman, máy không có TNR — quyết định cũ không đóng gói TNR), không phông dự phòng khác. Khoảng dòng giống nhau mọi trang: NĐ30/Thông tư 6,53 mm = 18,5 pt (1,15 dòng, cỡ 14), Đảng 7,06 mm = 20 pt "Exactly" (05-HD: 18–22 pt). Cách đoạn 6 pt. |
| 7 Bản sao | Sau sửa: bản DOCX/DOC giữ khoảng trên khối chữ ký, ngắt trang văn bản kèm theo, số trang. Còn lại xem "Tồn đọng". |

## Lỗi tìm thấy (trước sửa)

| # | Lỗi | Bằng chứng | Phạm vi |
|---|---|---|---|
| 1 | **Trang trắng cuối chỉ có số trang.** Đoạn trống Writer giữ sau bảng chữ ký (14 pt, 5,7 mm) tràn sang trang mới khi khối chữ ký vừa chạm đáy trang. | 179/544 PDF có trang chỉ chứa số trang (vd. `quyet-dinh` 2 trang: trang 2 chỉ có "2"); 93/122 lần quét gặp ở đúng 1 bước. | Mọi loại kết thúc bằng bảng chữ ký, cả mẫu và wizard; wizard cả loại kết thúc bằng đoạn văn (phụ lục, biểu mẫu). |
| 2 | **Khoảng 12 pt trên khối chữ ký mất khi lưu DOCX/DOC.** Khoảng này là lề trên của bảng; Word không có thuộc tính đó. | Văn bản mở lại lệch 4,3 mm ở 204/544 trường hợp (vd. `thong-bao` 1 trang: "[Họ và tên]" lệch 4,3 mm); `quyet-dinh-gian-tiep` 5 trang: DOCX còn 4 trang. | Mọi loại. |
| 3 | **.doc làm mất ngắt trang trước văn bản kèm theo** (ngắt gắn vào bảng đầu văn bản kèm theo). | `quyet-dinh-gian-tiep`, `thong-tu-ban-hanh`: PDF gốc 2 trang, .doc mở lại 1 trang, văn bản kèm theo chạy liền sau chữ ký. | 2 loại × 2 đường. |
| 4 | **Thông tin liên hệ của Công văn ở trang cuối**, NĐ30 PL I, Phần I, III.4 quy định "ở trang thứ nhất". | `cong-van` 2/3/5 trang: thông tin liên hệ ở trang 2/3/5; lần thử 3 trang có trang 3 chỉ chứa dòng này. | `cong-van` (mẫu; wizard khi có điền). |
| 5 | **Sổ đăng ký in thiếu**: vùng in cố định `A1:…32`. | Nhập 120 dòng: PDF chỉ in dòng 1–30 ở cả 5 sổ (`so-van-ban-den`, `so-van-ban-di`, `so-gui-buu-dien`, `so-su-dung-ban-luu`, `so-theo-doi-giai-quyet`); XLSX như vậy. | 5 sổ. |
| 6 | **Dấu đến của wizard trải hết bề ngang trang** (`HoriOrient=LEFT` bỏ qua `RightMargin`). | Khung từ x=29,9 tới 210,1 mm (vượt mép phải giấy), chữ "ĐẾN" ở x=198,6 mm; mẫu .ott đúng 50 mm. | `dau-den` wizard. |
| 7 | **Biên bản (wizard): "Nơi nhận:" mồ côi ở đáy trang**, danh sách sang trang sau, tách khỏi hai chữ ký. | `bien-ban` wizard 3 trang: tiêu đề Nơi nhận ở cuối trang 2, danh sách ở trang 3. | `bien-ban` (wizard; mẫu có cùng cấu trúc). |

## Sửa và commit (đã đẩy lên main)

| Commit | Nội dung |
|---|---|
| `a28a0fd` fix(templates) | `nd30_layout.portable_blocks()` dùng chung cho mẫu và wizard: khoảng trên/dưới bảng chuyển vào đoạn văn bên cạnh hoặc vào ô (lỗi 2); ngắt trang văn bản kèm theo đặt ở đoạn 1 pt (lỗi 3); đoạn cuối sau bảng chữ ký 1 pt, bảng chữ ký "giữ với đoạn sau" (dòng cuối giữ keepNext cho Word) (lỗi 1); biên bản giữ Nơi nhận với chữ ký (lỗi 7); sổ đăng ký bỏ vùng in cố định (lỗi 5); dấu đến wizard `LEFT_AND_WIDTH` 50 mm (lỗi 6). Có sẵn đường ống chân trang trang đầu (chưa bật). |
| `b9bbf2b` test(templates) | `tests/runtime/check-templates-multipage.py` (+ `templates_multipage_fill.py`, `templates_multipage_measure.py`), quy tắc `tests/fixtures/templates/multipage.json`, kiểm tra nhanh `tests/unit/test_templates_multipage.py`, mục mới trong `docs/TEMPLATES.md`. |
| `312d97e` fix(nd30) | Wizard: văn bản kết thúc bằng đoạn văn không còn sinh trang trắng (bỏ khoảng dưới của đoạn cuối). |
| `4a9bb2b` test(templates) | Tách phần sổ đăng ký thành `templates_multipage_registers.py` (giới hạn 199 dòng). |

Cổng: quality suite 90 lệnh, 0 lỗi; `check-access-keys --strict` = 0; `check-templates.py` PASS 84; không đổi patch lõi (không cần apply-patches). Runtime mới trên tập đại diện (quyết định, quyết định gián tiếp, biên bản, quyết định Đảng, mục lục văn bản, sổ văn bản đến, phụ lục, Thông tư; 1 và 3 trang; mẫu + wizard + quét) PASS, trừ lỗi 4 (chờ duyệt). GitHub Quality CI: thành công trên `4a9bb2b`.

Sổ đăng ký 120 dòng (trước → sau, số dòng in được): 30 → 120 ở cả 5 sổ, dòng tiêu đề và (1)…(n) lặp mọi trang.

## Bảng theo loại

Ô "x → y": mã lỗi trước → sau; "đạt": không lỗi; N/A: wizard của khối sao (khối bản sao được thêm dưới văn bản có sẵn, thiết lập trang là của văn bản đó). Bảng tính bằng harness "tới đúng lúc số trang tăng" (trạng thái khắt khe nhất); các ô "4,7" còn lại sau sửa là trạng thái mép dao ở bản DOCX/DOC mở lại bằng chính HST (xem Tồn đọng 1); `cong-van` sau sửa đo với bản chân trang đang chờ duyệt.

| Loại (id) | Đường | 1 tr. | 2 tr. | 3 tr. | 5 tr. |
|---|---|---|---|---|---|
| ban-ghi-nho | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| ban-ghi-nho | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| ban-sao-dien-tu | mẫu | đạt | đạt | đạt | đạt |
| ban-sao-dien-tu | wizard | N/A | N/A | N/A | N/A |
| ban-thoa-thuan | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| ban-thoa-thuan | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| bao-cao | mẫu | 7 → đạt | 4,7 → đạt | đạt | đạt |
| bao-cao | wizard | 7 → đạt | 4,7 → đạt | đạt | đạt |
| bi-van-ban | mẫu | đạt | — | — | — |
| bi-van-ban | wizard | đạt | — | — | — |
| bien-ban | mẫu | 4,7 → đạt | 4,7 | 7 → 4,7 | 7 → 4,7 |
| bien-ban | wizard | 4,7 → đạt | 4,7 | 4,7 | 4,7 |
| bien-ban-giao-nhan | mẫu | đạt | đạt | đạt | 4,7 → đạt |
| bien-ban-giao-nhan | wizard | đạt | đạt | đạt | đạt |
| chi-thi | mẫu | 4,7 → đạt | đạt | đạt | đạt |
| chi-thi | wizard | 4,7 → đạt | đạt | đạt | đạt |
| chuong-trinh | mẫu | 4,7 → đạt | đạt | đạt | đạt |
| chuong-trinh | wizard | 4,7 → đạt | đạt | đạt | đạt |
| cong-dien | mẫu | 7 → đạt | đạt | đạt | đạt |
| cong-dien | wizard | 7 → đạt | đạt | 4,7 | 4,7 |
| cong-van | mẫu | 7 | 7 | 4,7 | 4,7 |
| cong-van | wizard | 7 → đạt | đạt | 4,7 | 4,7 |
| dang-ban-sao | mẫu | 7 → đạt | 4,7 → đạt | đạt | 4,7 → đạt |
| dang-ban-sao | wizard | N/A | N/A | N/A | N/A |
| dang-bao-cao | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-bao-cao | wizard | 7 → đạt | đạt | 4,7 → đạt | đạt |
| dang-bien-ban | mẫu | 7 → đạt | 4,7 → đạt | đạt | 4,7 → đạt |
| dang-bien-ban | wizard | 7 → đạt | 4,7 → đạt | đạt | đạt |
| dang-chi-thi | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| dang-chi-thi | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-chuong-trinh | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| dang-chuong-trinh | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-cong-van | mẫu | 7 → đạt | đạt | 4,7 → đạt | đạt |
| dang-cong-van | wizard | 7 → đạt | đạt | 4,7 → đạt | đạt |
| dang-de-an | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| dang-de-an | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-giay-gioi-thieu | mẫu | 7 → đạt | 4,7 → đạt | đạt | 4,7 → đạt |
| dang-giay-gioi-thieu | wizard | 7 → đạt | 4,7 → đạt | đạt | đạt |
| dang-giay-moi | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-giay-moi | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-huong-dan | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| dang-huong-dan | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-ke-hoach | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| dang-ke-hoach | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-ket-luan | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| dang-ket-luan | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-nghi-quyet | mẫu | 7 → đạt | 4,7 → đạt | đạt | đạt |
| dang-nghi-quyet | wizard | 7 → đạt | 4,7 → đạt | đạt | đạt |
| dang-phu-luc | mẫu | đạt | đạt | đạt | đạt |
| dang-phu-luc | wizard | đạt | đạt | đạt | 4,7 → đạt |
| dang-phuong-an | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| dang-phuong-an | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-quy-che | mẫu | 7 → đạt | 4,7 → đạt | đạt | 4,7 → đạt |
| dang-quy-che | wizard | 7 → đạt | 4,7 → đạt | đạt | đạt |
| dang-quy-dinh | mẫu | 7 → đạt | 4,7 → đạt | đạt | 4,7 → đạt |
| dang-quy-dinh | wizard | 7 → đạt | 4,7 → đạt | đạt | đạt |
| dang-quyet-dinh | mẫu | 7 → đạt | 4,7 → đạt | đạt | đạt |
| dang-quyet-dinh | wizard | 7 → đạt | 4,7 → đạt | đạt | đạt |
| dang-thong-bao | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-thong-bao | wizard | 7 → đạt | đạt | 4,7 → đạt | đạt |
| dang-thong-cao | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-thong-cao | wizard | 7 → đạt | đạt | 4,7 → đạt | đạt |
| dang-thong-tri | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| dang-thong-tri | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | đạt |
| dang-to-trinh | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| dang-to-trinh | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| danh-muc-ho-so | mẫu | 7 | 7 | 7 | 7 |
| danh-muc-ho-so | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| dau-den | mẫu | 7 | — | — | — |
| dau-den | wizard | 1,7 → đạt | — | — | — |
| de-an | mẫu | 4,7 → đạt | đạt | đạt | đạt |
| de-an | wizard | 4,7 → đạt | đạt | đạt | đạt |
| du-an | mẫu | 4,7 → đạt | đạt | đạt | đạt |
| du-an | wizard | 4,7 → đạt | đạt | đạt | đạt |
| giay-gioi-thieu | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| giay-gioi-thieu | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| giay-moi | mẫu | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| giay-moi | wizard | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| giay-nghi-phep | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| giay-nghi-phep | wizard | 7 → đạt | 4,7 → đạt | đạt | đạt |
| giay-uy-quyen | mẫu | 7 → đạt | 4,7 → đạt | 4,7 | 4,7 |
| giay-uy-quyen | wizard | 7 → đạt | 4,7 → đạt | 4,7 | 4,7 |
| hop-dong | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| hop-dong | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| huong-dan | mẫu | 7 → đạt | đạt | đạt | đạt |
| huong-dan | wizard | 7 → đạt | đạt | 4,7 | 4,7 |
| ke-hoach | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| ke-hoach | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| muc-luc-ho-so | mẫu | 7 → đạt | 7 → đạt | 7 → đạt | 7 → đạt |
| muc-luc-ho-so | wizard | 7 → đạt | 7 → đạt | 4,7 → đạt | 4,7 → đạt |
| muc-luc-van-ban | mẫu | đạt | đạt | đạt | đạt |
| muc-luc-van-ban | wizard | đạt | đạt | đạt | đạt |
| nghi-quyet | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| nghi-quyet | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| phieu-bao | mẫu | 7 → đạt | 4,7 → đạt | 4,7 | 4,7 |
| phieu-bao | wizard | 7 → đạt | 4,7 → đạt | 4,7 | 4,7 |
| phieu-chuyen | mẫu | 4,7 → đạt | đạt | đạt | đạt |
| phieu-chuyen | wizard | 4,7 → đạt | đạt | đạt | đạt |
| phieu-giai-quyet | mẫu | đạt | đạt | đạt | đạt |
| phieu-giai-quyet | wizard | đạt | 4,7 | 4,7 → đạt | 4,7 → đạt |
| phieu-gui | mẫu | 4,7 → đạt | đạt | đạt | đạt |
| phieu-gui | wizard | 4,7 → đạt | đạt | đạt | đạt |
| phu-luc-dien-tu | mẫu | đạt | đạt | đạt | đạt |
| phu-luc-dien-tu | wizard | đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| phu-luc-giay | mẫu | đạt | đạt | đạt | đạt |
| phu-luc-giay | wizard | đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| phuong-an | mẫu | 4,7 → đạt | đạt | đạt | đạt |
| phuong-an | wizard | 4,7 → đạt | đạt | đạt | đạt |
| quy-che | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| quy-che | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| quy-dinh | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| quy-dinh | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| quyet-dinh | mẫu | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| quyet-dinh | wizard | 7 → đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| quyet-dinh-gian-tiep | mẫu | 7 → đạt | 7 → đạt | 7 → đạt | 2,7 → đạt |
| quyet-dinh-gian-tiep | wizard | 7 → đạt | 7 → đạt | 7 → đạt | 2,7 → đạt |
| sao-luc | mẫu | đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| sao-luc | wizard | N/A | N/A | N/A | N/A |
| sao-y | mẫu | đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| sao-y | wizard | N/A | N/A | N/A | N/A |
| thong-bao | mẫu | 7 → đạt | đạt | đạt | đạt |
| thong-bao | wizard | 7 → đạt | đạt | 4,7 | 4,7 |
| thong-cao | mẫu | 7 → đạt | đạt | đạt | đạt |
| thong-cao | wizard | 7 → đạt | đạt | 4,7 | 4,7 |
| thong-tu | mẫu | 7 → đạt | đạt | 4,7 → đạt | 4,7 → đạt |
| thong-tu | wizard | 7 → đạt | đạt | 4,7 → đạt | 4,7 → đạt |
| thong-tu-ban-hanh | mẫu | 7 → đạt | 7 → đạt | 7 → đạt | 2,7 → đạt |
| thong-tu-ban-hanh | wizard | 7 → đạt | 7 → đạt | 7 → đạt | 2,7 → đạt |
| thu-cong | mẫu | 7 → đạt | đạt | đạt | đạt |
| thu-cong | wizard | 7 → đạt | đạt | đạt | đạt |
| to-trinh | mẫu | 7 → đạt | 4,7 → đạt | đạt | đạt |
| to-trinh | wizard | 7 → đạt | 4,7 → đạt | đạt | đạt |
| trich-sao | mẫu | đạt | 4,7 → đạt | 4,7 → đạt | 4,7 → đạt |
| trich-sao | wizard | N/A | N/A | N/A | N/A |
| van-ban-kem-theo-qd-dien-tu | mẫu | đạt | đạt | đạt | đạt |
| van-ban-kem-theo-qd-dien-tu | wizard | đạt | đạt | đạt | đạt |

Sổ đăng ký: 5/5 sổ "5: in 30/120 dòng" → đạt (120/120, tiêu đề lặp mọi trang).

## Chờ chủ dự án duyệt

1. **Thông tin liên hệ Công văn → chân trang trang 1** (lỗi 4; thay đổi giao diện). Đã gửi coordinator. Dải 10 mm trong lề dưới trang 1, kẻ ngang hết vùng chữ, 11 pt; thân văn bản vẫn kết thúc ở 20 mm mọi trang; Word đặt dòng này thấp hơn ~4 mm trong cùng dải (Word neo chân trang theo mép dưới). Chưa commit; code sẵn sàng. Ảnh:
   - `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/template-audit/review/cong-van-2trang-truoc.png` / `cong-van-2trang-sau.png` (+ PDF cùng tên)
   - `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/template-audit/review/cong-van-1trang-truoc.png` / `cong-van-1trang-sau.png`
2. **Trang chữ ký đứng riêng** (câu hỏi của coordinator): không có quy tắc trong NĐ30 PL I (II.7–II.9, tr.26–28 bản ký) hay 05-HD/VPTW; khối chữ ký là một bảng không tách (~60 mm) nên đi nguyên khối sang trang sau, trang trước có thể trống tới ~60 mm. Giữ nguyên thiết kế; tùy chọn "giữ 2 dòng cuối thân văn bản với chữ ký" làm được trong `portable_blocks` nếu chủ dự án muốn.
3. Ảnh từng loại, trang 1–3 với khung lề đỏ: trước `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/template-audit/review/contact-before/`, sau `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/template-audit/review/contact-after/` (`template-<id>.png`, `wizard-<id>.png`). Ngoài Công văn, các sửa không đổi giao diện (chỉ bỏ trang trắng và giữ nguyên khoảng cách trong DOCX/DOC).

## Tồn đọng (không sửa, báo cáo)

1. Mép dao 1 pt: khi khối chữ ký kết thúc trong khoảng ~0,4 mm cuối trang, bản DOCX/DOC **mở lại bằng HST** vẫn có thể có trang trắng (bộ nhập DOCX của LibreOffice bỏ "keep with next" của bảng). DOCX có `w:keepNext` ở dòng cuối bảng nên Word giữ bảng với đoạn sau. Trước sửa vùng này là 5,7 mm.
2. LibreOffice tự chèn một trang trống trước văn bản kèm theo khi trang bắt đầu lại số 1 rơi vào trang chẵn (`sw/source/core/layout/pagechg.cxx`): PDF bỏ trang này, nhưng in ra giấy thì có (tùy chọn in "trang trống tự chèn" mặc định bật). Hành vi lõi, liên quan in hai mặt; sửa cần patch lõi — cần quyết định.
3. Sổ đăng ký XLSX: số trang khác (vd. 9 → 8) vì XLSX không có "chiều cao dòng tối thiểu"; đủ 120 dòng.
4. Dấu đến wizard cao 32 mm (mẫu .ott 35 mm theo PL IV.V); bề ngang đã đúng 50 mm.
5. Khối sao (sao y/sao lục/trích sao/bản sao Đảng/bản sao điện tử) tạo bằng wizard trên tài liệu trống dùng trang mặc định (lề 2 cm, không số trang): theo thiết kế khối này ghép dưới văn bản có sẵn.
6. Mẫu Sheets (bảng lương…) vẫn có vùng in cố định tới dòng TỔNG; người dùng chèn dòng thì vùng in tự giãn.
7. Bảng biểu mẫu: chữ trong ô xuống dòng khác ~1,4 mm giữa ODT và DOCX ở các dòng thêm (đệm ô), không lệch lề.
8. Times New Roman không cài trên máy đo: mọi số đo là với Liberation Serif (cùng kích thước ký tự).

## Nguồn

- Nghị định 30/2020/NĐ-CP, Phụ lục I, Phần I: I.1–I.7 (A4; lề 20–25/20–25/30–35/15–20; TNR; số trang 13–14, giữa lề trên, không hiện trang 1), II.7–II.9 (chữ ký, Nơi nhận), III.4 (thông tin liên hệ "ở trang thứ nhất", 11–12, dưới đường kẻ hết vùng chữ). Bản ký chinhphu.vn: https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/03/30.signed.pdf (sha256 be2514460c95…9178), trang PDF 21, 26–28, 30.
- Nghị định 78/2025/NĐ-CP sửa bởi NĐ 187/2025/NĐ-CP, Phụ lục I (Thông tư: lề trên/dưới/phải 15–20, trái 30–35, số trang 13): https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/7/187-ndcp.signed.pdf (theo `data/vietnamese/qppl.json`).
- Hướng dẫn 05-HD/VPTW ngày 27/5/2026, Phần II.IV.3–5 (A4; lề 20/20/30/15, mặt sau in hai mặt 20/20/15/30; số trang giữa, cách mép trên 10 mm, không hiện trang 1, phụ lục đánh số riêng), II.6.2.2 (cách đoạn ≥6 pt, dòng 18–22 pt Exactly), II.6 (thông tin liên hệ **trang cuối**), Phụ lục 2 (số trang 14). https://www.sav.gov.vn/Files/Others/761e611b-48d7-4b86-a5a2-4c17bac0f753/05.HD.VPTW.pdf (sha256 dba6843ce82a…3cd7). Phần III.1: thay thế **Hướng dẫn 36-HD/VPTW ngày 04/3/2018**; giá trị lề và số trang của 36-HD giống 05-HD (theo trích dẫn tại thuvienphapluat.vn: https://thuvienphapluat.vn/hoi-dap-phap-luat/phong-chu-kho-giay-dinh-le-trang-van-ban-so-trang-va-phu-luc-van-ban-cua-dang-265851.html; bản gốc 36-HD trên thuvienphapluat bị chặn Cloudflare, chưa đọc trực tiếp).
- Lựa chọn còn để nguyên (luật cho phép): lề 20/20/30/15 (cận dưới), giãn dòng 1,15, cỡ thân 14, số trang 14; Đảng in hai mặt không dùng lề đối xứng (05-HD 4.2 chỉ áp dụng khi in hai mặt).

## Câu hỏi còn mở

1. Duyệt thông tin liên hệ Công văn ở chân trang 1?
2. Có muốn giữ 2 dòng cuối thân văn bản cùng trang chữ ký (không phải quy tắc)?
3. Trang trống LibreOffice tự chèn trước văn bản kèm theo khi in: chấp nhận hay patch lõi?
4. Văn bản Đảng in hai mặt: thêm tùy chọn lề đối xứng (15/30 mặt sau)?

## Bổ sung 06/11/2026 tối (theo trả lời của chủ dự án 20:59)

### 1. Thông tin liên hệ Công văn ở chân trang 1 — đã áp dụng

Commit `a541bdc` fix(templates): thông tin liên hệ thành chân trang riêng của trang 1 (dải 10 mm trong lề dưới, kẻ ngang hết vùng chữ, 11 pt); thân văn bản vẫn kết thúc ở 20 mm mọi trang; các trang sau không có. Hàm `portable_blocks` chuyển sang mô-đun mới `nd30_portable.py` (giới hạn 199 dòng). Kiểm chứng: `check-templates.py` PASS 84; runtime `check-templates.py` PASS (cong-van, thong-bao, bien-ban); `check-templates-multipage.py` PASS 40/40 trường hợp (cong-van, thong-bao, bien-ban, quyet-dinh-gian-tiep; 1–5 trang; mẫu + wizard + quét); quality suite 91 lệnh, 0 lỗi. Wizard có điền thông tin liên hệ: chân trang đầu có nội dung, thân không còn dòng đó, DOCX `w:footer=567 w:bottom=1134` (đo trực tiếp).

### 2. "Giữ 2 dòng cuối nội dung cùng khối chữ ký" — chưa áp dụng, có ảnh minh họa

Ảnh: `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/ribbon-shots/img/keep-with-signature.png` (mẫu Công văn thật, nội dung chỉnh để khối chữ ký vừa rơi sang trang 2). Trái "HIỆN NAY": nội dung hết ở trang 1, trang 2 chỉ có Nơi nhận và khối chữ ký. Phải "NẾU ÁP DỤNG QUY TẮC": đoạn cuối của nội dung sang trang 2 cùng khối chữ ký.

Lưu ý kỹ thuật: Writer thực hiện "giữ với đoạn sau" bằng cách chuyển **cả đoạn cuối** (trong ảnh là 4 dòng), không cắt đúng 2 dòng; Word cho phép tách đoạn và chỉ chuyển 2 dòng cuối (có kiểm soát dòng mồ côi). Muốn đúng "2 dòng" trên Writer phải dùng cách khác (tách đoạn), không làm trong beta.5.

NĐ30 nói gì: Phụ lục I, Phần I, II.7 (thẩm quyền, chức vụ, họ tên, chữ ký), II.8 (dấu, chữ ký số cơ quan), II.9 (nơi nhận) — trang PDF 26–28 của bản ký — **không có điều khoản nào** yêu cầu trang chữ ký phải có nội dung văn bản hay cấm khối chữ ký đứng riêng một trang. Hướng dẫn 05-HD/VPTW cũng không có. Đây là thói quen trình bày (tránh ký vào trang không có nội dung), không phải quy tắc pháp lý.

### 3. Trang trống tự động chèn khi in — khuyến nghị TẮT, đã chuẩn bị, chưa commit

- **Vì sao Writer chèn:** (a) đánh số trang bắt đầu lại ở số lẻ mà rơi vào trang chẵn: Writer chèn một trang trống để trang "số 1" là trang phải (`sw/source/core/layout/pagechg.cxx`, `sw::IsRightPageByNumber`), kể cả khi kiểu trang dùng "trái và phải"; (b) kiểu trang chỉ trang phải/chỉ trang trái (ví dụ bộ nhập DOCX biến ngắt phần "Odd page"/"Even page" thành kiểu trang chỉ phải/chỉ trái, `sw/source/writerfilter/dmapper/PropertyMap.cxx` `CreateEvenOddPageStyleCopy`). Tùy chọn `/org.openoffice.Office.Writer/Print/EmptyPages` ("In trang trống tự động chèn") mặc định **bật**; xuất PDF thì mặc định bỏ các trang này (`IsSkipEmptyPages=true`) nên PDF và bản in khác nhau.
- **Word:** không chèn trang khi đánh số lại (`w:pgNumType w:start`); chỉ ngắt phần "Odd/Even page" mới tạo trang trống, và Word in trang đó.
- **Mẫu HST bị ảnh hưởng:** 2 loại có văn bản kèm theo đánh số lại từ 1: `quyet-dinh-gian-tiep` (mẫu 1.3), `thong-tu-ban-hanh` (mẫu 15): khi phần chính có số trang lẻ, Writer có 3 trang (1 trống), PDF 2 trang. In thử (in ra tệp, đo bằng pdfinfo): **bật = 3 tờ, tắt = 2 tờ**. 66 loại còn lại không sinh trang trống. Với .docx thường gặp trong hành chính (phụ lục/văn bản kèm theo đánh số riêng) cũng xảy ra như vậy khi mở bằng HST.
- **In hai mặt:** tắt thì tài liệu có ngắt "Odd page" thật (sách, báo cáo dàn trang hai mặt — ít gặp trong văn bản hành chính) mất tờ trống, phần đó bắt đầu ở mặt sau và các mặt trước/sau lệch từ đó; bật (như hiện nay) thì văn bản kèm theo/phụ lục bị chèn tờ trắng mà Word không có. Đặt lại được ở hộp thoại In (trang Writer) hoặc Công cụ ▸ Tùy chọn ▸ Writer ▸ In.
- **Khuyến nghị:** TẮT mặc định — đúng với Word và với trường hợp phổ biến của văn bản hành chính; ghi chú ở trợ giúp. Cách triệt để hơn cho 1.0.0: patch lõi chỉ bỏ trang trống do đánh số lại khi kiểu trang là "trái và phải" (giữ trang trống của ngắt Odd/Even như Word).
- **Đã chuẩn bị (không phải patch lõi):** `extensions/hst-vietnamese-tools/PrintDefaults.xcu` (lớp cấu hình của phần mở rộng, người dùng ghi đè được) + dòng trong `META-INF/manifest.xml`: `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/template-audit/print-blank-pages-off.patch` (áp dụng sạch trên main). Đã thử: cài vào bản office thử, giá trị đọc được = false, in `quyet-dinh-gian-tiep` ra 2 tờ. **Chưa commit** — chờ xác nhận.

### 4. Văn bản Đảng in hai mặt — chỉ nghiên cứu

- **Quy tắc hiện hành:** Hướng dẫn 05-HD/VPTW ngày 27/5/2026 (thay 36-HD/VPTW ngày 04/3/2018, Phần III.1), Phần II, IV.4: "4.1. Văn bản của Đảng trình bày theo chiều dọc… Lề trên 20 mm, lề dưới 20 mm, lề trái 30 mm, lề phải 15 mm. 4.2. **Trường hợp văn bản in hai mặt**, mặt sau vùng trình bày như sau: lề trên 20 mm, lề dưới 20 mm, lề trái 15 mm, lề phải 30 mm." IV.5.1: số trang giữa, cách mép trên 10 mm, không hiện ở trang 1. 36-HD/VPTW có cùng giá trị (theo trích dẫn tại thuvienphapluat.vn: "Với văn bản in hai mặt, lề trái của mặt sau là 15 mm").
- **Kết luận:** quy định **không bắt buộc in hai mặt**; chỉ quy định lề mặt sau *nếu* in hai mặt (lề đối xứng: gáy 30 mm). Lề đối xứng mà in một mặt thì các trang chẵn có lề trái 15 mm — sai 4.1. Vì vậy lề đối xứng phải đi cùng việc chọn in hai mặt.
- **Mặc định in hai mặt theo mẫu:** LibreOffice không có thuộc tính "in hai mặt" trong ODF/DOCX. Chế độ hai mặt nằm trong JobSetup của máy in (`PrinterSetup` trong `settings.xml`, gắn tên và driver máy in): máy khác hoặc máy in khác thì bị bỏ qua; `com.sun.star.view.PrintOptions` và `PrinterDescriptor` cũng không có thuộc tính hai mặt. Không mang được mặc định hai mặt theo mẫu một cách khả chuyển. Lề đối xứng thì mang được: ODF `style:page-usage="mirrored"`, DOCX `w:mirrorMargins`.
- **Đề xuất cho 1.0.0 (không làm bây giờ):** kiểu trang Đảng đối xứng (trong 30 / ngoài 15) bật khi người dùng chọn "In hai mặt" trong phần HST (một bước hỏi lúc in hoặc lệnh riêng), còn chế độ hai mặt của máy in do hộp thoại In/driver quyết định.

### Commit bổ sung

| Commit | Nội dung |
|---|---|
| `a541bdc` | Thông tin liên hệ Công văn ở chân trang 1 (đã duyệt) |
| (chưa commit) | `/tmp/claude-0/-home-office/9b7a3a59-b584-43cf-95a7-4b248497ec7a/scratchpad/template-audit/print-blank-pages-off.patch` — tắt in trang trống tự chèn, chờ xác nhận |

### Quyết định của chủ dự án (06/11/2026, 21:4x)

1. Trang trống tự động chèn khi in: **giữ như hiện nay** (vẫn in). Không commit `print-blank-pages-off.patch`.
2. Giữ đoạn cuối nội dung cùng khối chữ ký: **không áp dụng**. Lý do: trang 1 để trống một khoảng lớn khiến người đọc tưởng văn bản đã hết.
3. Văn bản Đảng in hai mặt: làm ở **1.0.0** theo đề xuất trên: chỉ dùng lề đối xứng khi người dùng chọn in hai mặt.

beta.5 không có thay đổi nào khác từ đợt rà soát này.
