// Formatting rules from Nghị định 30/2020/NĐ-CP, Phụ lục I, Phần I
// (official PDF sha256 be2514460c95…9178, pages cited per constant).
// Pure data: shared by the Writer plugin and the template generator.

/** Allowed page margins in millimetres (Phụ lục I, I.3 — PDF p.21). */
export const MARGIN_RANGES_MM = Object.freeze({
  top: [20, 25],
  bottom: [20, 25],
  left: [30, 35],
  right: [15, 20],
});

/** HST default: smallest value of each allowed range. */
export const DEFAULT_MARGINS_MM = Object.freeze({ top: 20, bottom: 20, left: 30, right: 15 });

/** A4 portrait (I.1 — p.21). */
export const PAGE_SIZE_MM = Object.freeze({ width: 210, height: 297 });

/** Font sizes (pt) chosen inside the ranges allowed by section II (pp.21–28). */
export const TYPOGRAPHY = Object.freeze({
  fontFamily: 'Times New Roman', // I.4
  nationalTitle: 12, // II.1a: 12–13, upper case, bold (12 keeps it on one line)
  motto: 14, // II.1b: 13–14, bold
  parentAgency: 13, // II.2b: 12–13, upper case
  agency: 13, // II.2b: 12–13, upper case, bold
  number: 13, // II.3c: 13
  placeDate: 14, // II.4c: 13–14, italic
  typeName: 14, // II.5b: 13–14, upper case, bold
  summary: 14, // II.5b: 13–14, bold
  summaryOfficialLetter: 13, // II.5b công văn "V/v": 12–13
  body: 14, // II.6e: 13–14
  bodyFirstLineIndentMm: 12.7, // II.6e: 1 cm or 1.27 cm
  paragraphSpacingPt: 6, // II.6e: >= 6pt
  lineSpacing: 1.15, // II.6e: single .. 1.5 lines
  signerAuthority: 14, // II.7đ: 13–14, upper case, bold
  signerName: 14, // II.7đ: 13–14, bold
  recipientsHeading: 12, // II.9d: "Nơi nhận:" 12, italic bold
  recipientsList: 11, // II.9d: 11
  kinhGui: 14, // II.9d: 13–14
});

export const NATIONAL_TITLE = 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM';
export const MOTTO = 'Độc lập - Tự do - Hạnh phúc';

/** Common user-entered fields. Labels are UI strings (English source, translated). */
export const COMMON_FIELDS = Object.freeze([
  'parentAgency', 'agency', 'number', 'symbol', 'place', 'date',
  'summary', 'body', 'signerAuthority', 'signerTitle', 'signerName', 'recipients',
]);

/**
 * Seven supported document types. `typeName` is printed in upper case;
 * `officialLetter` (công văn) has no type name and puts "V/v" under the number;
 * `kinhGui` adds the "Kính gửi:" line (II.9b: công văn, tờ trình, báo cáo).
 */
export const DOCUMENT_TYPES = Object.freeze([
  { id: 'cong-van', label: 'Official letter', typeName: '', officialLetter: true, kinhGui: true },
  { id: 'thong-bao', label: 'Notice', typeName: 'THÔNG BÁO', officialLetter: false, kinhGui: false },
  { id: 'quyet-dinh', label: 'Decision', typeName: 'QUYẾT ĐỊNH', officialLetter: false, kinhGui: false },
  { id: 'to-trinh', label: 'Submission', typeName: 'TỜ TRÌNH', officialLetter: false, kinhGui: true },
  { id: 'bao-cao', label: 'Report', typeName: 'BÁO CÁO', officialLetter: false, kinhGui: true },
  { id: 'giay-moi', label: 'Invitation', typeName: 'GIẤY MỜI', officialLetter: false, kinhGui: false },
  { id: 'bien-ban', label: 'Minutes', typeName: 'BIÊN BẢN', officialLetter: false, kinhGui: false },
]);

/** Placeholder shown when the user leaves a field empty — never invented data. */
export const PLACEHOLDERS = Object.freeze({
  parentAgency: '[TÊN CƠ QUAN CHỦ QUẢN]',
  agency: '[TÊN CƠ QUAN BAN HÀNH]',
  number: '[số]',
  symbol: '[KÝ HIỆU]',
  place: '[Địa danh]',
  date: '[ngày] tháng [tháng] năm [năm]',
  summary: '[Trích yếu nội dung văn bản]',
  body: '[Nội dung văn bản]',
  signerAuthority: '[QUYỀN HẠN, CHỨC VỤ NGƯỜI KÝ]',
  signerTitle: '',
  signerName: '[Họ và tên]',
  recipients: '[Nơi nhận]',
  kinhGui: '[Cơ quan, tổ chức nhận văn bản]',
});

export function getDocumentType(typeId) {
  return DOCUMENT_TYPES.find((type) => type.id === typeId) || null;
}
