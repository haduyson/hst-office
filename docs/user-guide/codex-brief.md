# Brief: offline Vietnamese user guide for HST Office (level A)

You are writing the built-in, offline user guide of **HST Office**, a free office suite for Vietnamese
users (documents, spreadsheets, presentations) published by HASON TECH. The guide opens in the
system browser when the user presses F1 or chooses Trợ giúp → Trợ giúp HST Office. It ships inside
the product, so it must work from local files with no Internet.

Work only inside this folder. Inputs:

- `facts.html`: the approved fact sheet (a one-page draft guide). **Every statement you write must be
  supported by `facts.html`, `labels.md` or a screenshot in `images/`.** Do not invent features,
  menu paths, buttons, shortcuts or behaviour. If a page needs a fact you do not have, leave it out.
- `labels.md`: the exact Vietnamese UI labels of the product. Use them verbatim (same spelling,
  diacritics, capitalisation) when you name a tab, menu, command, dialog or button. Write menu paths
  as `<span class="menu">Tập tin → Lưu thành…</span>`.
- `images/*.png` and `images/README.md`: real screenshots of HST Office in Vietnamese, with a
  description of each. Look at them. Use each where it helps (most pages one or two images); do not
  describe anything in an image that you cannot see in it.

Output: write the finished pages into `out/` (create it). Nothing else in the folder may change.

## Audience and tone

Vietnamese office workers, teachers and civil servants; many are switching from Microsoft Office or
from old TCVN3/VNI documents; not technical. Write natural, polite, concise Vietnamese ("bạn"), with
full and correct diacritics (Unicode NFC). Short paragraphs, numbered steps for procedures, one idea
per sentence. No marketing fluff apart from the positioning line below. No English UI terms unless
the product shows them (file extensions such as .docx are fine).

## Product policy (mandatory)

- Never write "LibreOffice", "OpenOffice", "The Document Foundation", "GitHub" or any URL of them.
- The only external links allowed: `https://hasontech.vn/?utm_source=hst-office&utm_medium=help&utm_campaign=hst-office-1-0`
  (the HASON TECH website) and `mailto:lienhe@hasontech.vn`. Contact: lienhe@hasontech.vn,
  phone (0236) 3.507.507, address 300 Xô Viết Nghệ Tĩnh, phường Cẩm Lệ, TP. Đà Nẵng.
- Positioning: HST Office is **"Miễn phí vĩnh viễn"** (free forever); say it on the home page and
  the contact page. No "donate", no prices, no comparisons naming competitors other than saying files
  from Word, Excel, PowerPoint open and save.
- Do not promise 100 % Microsoft Office compatibility, legal validity of documents, or support
  hours. Keep the responsibility note for third-party extensions (see facts).
- The ND30 tool is a presentation helper per Nghị định 30/2020/NĐ-CP; it does not check legal
  validity (keep that warning).

## Pages (file names fixed; 18 pages)

| File | Title | Content |
|---|---|---|
| index.html | Hướng dẫn sử dụng HST Office | welcome, "Miễn phí vĩnh viễn", the 3 apps, grouped table of contents linking every page, F1 tip |
| bat-dau.html | Bắt đầu | Trang bắt đầu, create/open files, defaults (A4, Times New Roman), Vietnamese UI and spell check, no account/Internet/data collection |
| giao-dien.html | Giao diện theo thẻ | tabs, Thanh bên, switching to classic menus via Xem → Giao diện người dùng… |
| van-ban-soan-thao.html | Văn bản: soạn thảo và định dạng | text, character formatting, paragraph dialog, paragraph styles |
| van-ban-bang-hinh.html | Văn bản: bảng, hình ảnh, tìm kiếm | insert table, images, find & replace, spelling |
| van-ban-trang-in.html | Văn bản: trang, in và PDF | page style, margins, header/footer/page numbers, print, export PDF |
| bang-tinh-co-ban.html | Bảng tính: làm quen | sheets, rows, columns, cells, entering data |
| bang-tinh-cong-thuc.html | Bảng tính: công thức | =, SUM and the Tổng button, simple arithmetic (only what facts give) |
| bang-tinh-dinh-dang.html | Bảng tính: định dạng và sắp xếp | Định dạng ô…, HST VND/date/percent commands, sorting |
| bang-tinh-csv.html | Bảng tính: nhập CSV (UTF-8) | the HST CSV import |
| trinh-chieu.html | Trình chiếu | new slides, layouts, content, running the show (F5, Shift+F5, Esc), transitions |
| nd30.html | Văn bản hành chính theo NĐ 30 | the wizard step by step, live preview, insert, Undo, page options, warning |
| chuyen-ma.html | Chuyển TCVN3/VNI sang Unicode | steps, what is kept, Undo |
| dinh-dang-office.html | Lưu tệp Word, Excel, PowerPoint | open, Lưu thành…, Kiểu tập tin, always-save-as option, compatibility note |
| phan-mo-rong.html | Cài phần mở rộng từ tệp | Công cụ → Phần mở rộng…, Thêm…, Gỡ bỏ, responsibility note |
| phim-tat.html | Phím tắt thường dùng | the shortcut table from facts (+ macOS ⌘ note) |
| meo-hay.html | Mẹo và câu hỏi thường gặp | short Q&A built only from facts (e.g. document from old font, file from Word looks different, where is the HST menu) |
| lien-he.html | Hỗ trợ và liên hệ | HASON TECH, Miễn phí vĩnh viễn, contact, how to report a problem |

(That is 18 content pages plus `style.css`; add `gioi-thieu.html` "Giới thiệu HST Office" only if
it adds value without repeating index.html.)

## HTML/CSS structure

- One shared stylesheet `out/style.css`; each page links `style.css`. No JavaScript, no web fonts,
  no external resources, no inline base64 images. HTML5, `<html lang="vi">`, `<meta charset="utf-8">`,
  `<meta name="viewport" content="width=device-width, initial-scale=1">`, `<title>… · Hướng dẫn HST Office</title>`.
- Layout: a top header with the logo `<img src="../icons/hst-office-logo.png" alt="HST OFFICE">`
  (this path is valid in the product; keep it exactly), the guide title linking to `index.html`,
  and the badge `<span class="badge">MIỄN PHÍ VĨNH VIỄN</span>`; a left navigation listing
  all pages grouped (Bắt đầu · Văn bản · Bảng tính · Trình chiếu · Công cụ HST · Khác) with the
  current page marked `aria-current="page"`; the main article; "← Trang trước | Trang sau →" links at
  the bottom; a footer "HST Office · HASON TECH · Hướng dẫn ngoại tuyến".
- Responsive: at < 760 px the navigation moves above the article. Support
  `prefers-color-scheme: dark` and print (hide navigation).
- Colours: brand blue `#0072BB`, text `#322E2E`, badge "MIỄN PHÍ VĨNH VIỄN" white text on dark green `#0E7A36` (owner decision), warnings red `#C8102E`.
  Follow the look of `facts.html` (cards for the three apps, `kbd` keys, note boxes `.note`,
  warning boxes `.note.warn`).
- Images: `<figure><img src="images/NAME.png" alt="…" loading="lazy" width="W" height="H"><figcaption>…</figcaption></figure>`
  with the real pixel size from `images/README.md`; CSS makes them `max-width: 100%; height: auto`
  with a thin border.
- Relative links only between pages; every page must be reachable from index.html.

## Done when

All 18 pages and style.css exist in `out/`, every link and image path resolves, the policy above
holds (search your output for the forbidden names), and you have listed in `out/NOTES.md` any fact
you wanted but did not have.
