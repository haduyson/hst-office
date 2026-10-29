# Compatibility matrix

Trạng thái: **PASS / FAIL / NOT RUN / BLOCKED**. Chỉ ghi PASS khi có evidence trong repo; không tuyên bố tương thích 100% với Microsoft Office.

## Nền tảng

| OS / arch | Build | Cài đặt | Chạy 3 module | Ghi chú |
|---|---|---|---|---|
| Ubuntu 24.04 x86_64 | đang build (26.8.1.1) | NOT RUN | NOT RUN | VPS dev |
| Debian 12 x86_64 | NOT RUN | NOT RUN | NOT RUN | dự kiến dùng cùng `.deb` |
| Windows 10/11 x64 | BLOCKED (OPS-01) | BLOCKED | BLOCKED | |
| macOS arm64 / x86_64 | BLOCKED (OPS-01) | BLOCKED | BLOCKED | MAC-01: độ trễ chuột phải |

## Định dạng (HST Office build Linux)

| Định dạng | Mở | Lưu | Mở lại | Evidence |
|---|---|---|---|---|
| ODT/ODS/ODP | NOT RUN | NOT RUN | NOT RUN | — |
| DOCX/XLSX/PPTX | NOT RUN | NOT RUN | NOT RUN | — |
| DOC/XLS/PPT, RTF, TXT, CSV UTF-8 | NOT RUN | NOT RUN | NOT RUN | — |
| PDF (xuất) | NOT RUN | — | — | — |

## Mẫu HST (kiểm trên LibreOffice 24.2 trước khi có bản build HST)

| Nhóm | Kết quả | Ghi chú |
|---|---|---|
| 7 mẫu Writer `.ott` | PASS (24.2) | PDF, DOCX (lề thân văn bản trong khoảng NĐ30), lưu/mở lại |
| 5 mẫu Slides `.otp` | PASS (24.2) | PDF, PPTX 16:9, lưu/mở lại |
| 6 mẫu Sheets `.ots` | **FAIL** (24.2) | PDF trắng sau khi lưu thành `.ods` rồi in — đang sửa generator |

## Microsoft Office round-trip

BLOCKED (QA-01): chưa có máy Microsoft Office hợp lệ.
