# Kiểu trích dẫn của HST Writer

Mỗi tệp `styles/<id>.json` là một kiểu trích dẫn do HST soạn từ chính các hướng dẫn gốc (sổ tay APA, IEEE, NLM/ICMJE, AMA, Chicago, MLA, Cite Them Right, ISO 690/TCVN 10256 và hướng dẫn trình bày luận văn, luận án của các trường Việt Nam ghi trong khóa `source`). Không tệp nào chép hay chuyển thể từ tệp `.csl` hoặc locale của dự án CSL (giấy phép CC BY-SA 3.0), nên các tệp kiểu theo giấy phép AGPL-3.0-only như phần còn lại của mã HST. Lúc build, `scripts/build-extensions.py` chép thư mục này vào gói ở `data/citation-styles/`; `scripts/check-extensions.py` báo lỗi khi bản trong gói khác bản ở đây.

| id | Kiểu | Lớp |
|---|---|---|
| `vn-so` | Luận văn Việt Nam – số thứ tự `[1]` | numeric |
| `vn-tac-gia-nam` | Luận văn Việt Nam – tác giả, năm `(Nguyễn Văn An, 2010)` | author-date |
| `apa-7` | APA 7 | author-date |
| `ieee` | IEEE | numeric |
| `vancouver` | Vancouver (ICMJE/NLM) | numeric |
| `ama-11` | AMA 11 (số mũ) | numeric |
| `harvard` | Harvard (Cite Them Right) | author-date |
| `chicago-tac-gia-nam` | Chicago 18 – tác giả, năm | author-date |
| `chicago-chu-thich` | Chicago 18 – chú thích cuối trang | note |
| `mla-9` | MLA 9 | author-date (tác giả, trang) |
| `iso-690-so` | ISO 690 – số thứ tự | numeric |
| `iso-690-tac-gia-nam` | ISO 690 – tác giả, năm | author-date |

## Cấu trúc một tệp kiểu

- `id`, `name` (tên người dùng thấy), `class` (`numeric`, `author-date`, `note`), `description`, `source`.
- `options`: giá trị của **mọi** tùy chọn khai báo trong `extensions/hst-vietnamese-tools/python/hst_office/citation_style_options.py` (thứ tự danh mục, nhóm theo ngôn ngữ, khóa xếp tên Việt, cách viết tên Việt và tên nước ngoài, "và cộng sự"/"et al.", ngưỡng rút gọn, dấu ngoặc, gộp dải số, nhãn trang "tr."…). Khác biệt giữa các trường là tùy chọn, không phải kiểu mới.
- `presets`: bộ tùy chọn có tên cho các biến thể đã gặp (ví dụ `thu-tu-trich` của `vn-so` cho ĐH Hồng Đức, `mot-danh-muc-theo-ho` của `vn-tac-gia-nam` cho ĐH Kinh tế Quốc dân).
- `layouts`: với mỗi kiểu tài liệu CSL (`book`, `chapter`, `article-journal`, `paper-conference`, `thesis`, `report`, `legislation`, `webpage`, `article-newspaper`, `default`), danh sách phần tử mẫu; `alias` trỏ kiểu khác vào một layout; `macros` là các danh sách dùng lại.
- `notes` (chỉ kiểu `note`): layout của chú thích đầy đủ theo kiểu tài liệu và `short` cho chú thích rút gọn.
- `terms`: thay thuật ngữ mặc định (`citation_terms.py`) cho riêng kiểu này, ví dụ `"en": {"editor": ["Ed.", "Eds."]}`.

Ngôn ngữ của phần tử mẫu (khóa, điều kiện, chuỗi `@tùy-chọn`, chuỗi theo ngôn ngữ `{"vi": …, "other": …}`) mô tả ở đầu `citation_style_check.py`; lỗi trong tệp kiểu được báo kèm tên tệp và khóa.

## Thêm hoặc sửa một kiểu

1. Sửa hoặc thêm `styles/<id>.json` (id chữ thường, số, gạch ngang); ghi nguồn hướng dẫn vào `source`.
2. Thêm ca kiểm thử vào `CASES` của `tests/unit/citation_golden.py`, sinh mẫu chuẩn rồi **đọc lại từng dòng** đối chiếu với hướng dẫn gốc:
   `HST_UPDATE_CITATION_GOLDEN=1 PYTHONPATH=tests/unit python3 -m unittest tests/unit/test_citation_golden_styles.py`
3. Chạy `PYTHONPATH=tests/unit python3 -m unittest discover -s tests/unit -p 'test_citation_*.py'`, build và `scripts/check-extensions.py`.

Kiểu riêng của người dùng ("Kiểu của tôi" = một kiểu ở đây cộng các tùy chọn đã đổi, và tệp `.csl` người dùng tự nhập) nằm trong hồ sơ người dùng, `hst-citations/styles/`, không nằm trong gói.
