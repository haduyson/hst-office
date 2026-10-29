// Builds an editor-independent layout (paragraph / two-column blocks) for an
// ND30 administrative document. The Writer adapter renders these blocks with
// the Office JS API; the template generator renders them with python-docx.
import {
  getDocumentType, MOTTO, NATIONAL_TITLE, PLACEHOLDERS, TYPOGRAPHY as T,
} from './nd30-data.js';

/** Approximate widths of horizontal rules drawn under headings (mm). */
export const RULE_WIDTH_MM = Object.freeze({ agency: 25, motto: 62, title: 30 });

const run = (text, size, extra = {}) => ({ text, size, bold: false, italic: false, ...extra });
const para = (runs, align = 'center', extra = {}) => ({ type: 'paragraph', align, runs, ...extra });

function value(fields, key) {
  const raw = typeof fields[key] === 'string' ? fields[key].trim() : '';
  return raw || PLACEHOLDERS[key];
}

function lines(text) {
  return String(text || '').split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
}

/** ND30 II.3c/II.4b: pad numbers below 10; months 1–2 are padded, 3–12 are not. */
export function formatNumber(number) {
  const n = String(number || '').trim();
  return /^\d$/.test(n) ? `0${n}` : n;
}

export function formatIssueDate(isoDate) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(isoDate || ''));
  if (!match) return null;
  const [, year, month, day] = match;
  const m = Number(month);
  const monthText = m <= 2 ? month : String(m);
  return `ngày ${day} tháng ${monthText} năm ${year}`;
}

function placeDateLine(fields) {
  const place = value(fields, 'place');
  const date = formatIssueDate(fields.date) || PLACEHOLDERS.date;
  return `${place}, ${date}`;
}

function headerBlock(type, fields) {
  const left = [];
  if (fields.parentAgency && fields.parentAgency.trim()) {
    left.push(para([run(fields.parentAgency.trim().toUpperCase(), T.parentAgency)]));
  }
  left.push(para([run(value(fields, 'agency').toUpperCase(), T.agency, { bold: true })], 'center',
    { ruleWidthMm: RULE_WIDTH_MM.agency }));
  const number = formatNumber(fields.number) || PLACEHOLDERS.number;
  left.push(para([run(`Số: ${number}/${value(fields, 'symbol')}`, T.number)]));
  if (type.officialLetter) {
    left.push(para([run(`V/v ${value(fields, 'summary')}`, T.summaryOfficialLetter)], 'center',
      { spacingBeforePt: 6 }));
  }
  const right = [
    para([run(NATIONAL_TITLE, T.nationalTitle, { bold: true })]),
    para([run(MOTTO, T.motto, { bold: true })], 'center', { ruleWidthMm: RULE_WIDTH_MM.motto }),
    para([run(placeDateLine(fields), T.placeDate, { italic: true })], 'center', { spacingBeforePt: 6 }),
  ];
  return { type: 'two-column', widthsPct: [35, 65], left, right };
}

function titleBlocks(type, fields) {
  if (type.officialLetter) return [];
  return [
    para([run(type.typeName, T.typeName, { bold: true })], 'center', { spacingBeforePt: 12 }),
    para([run(value(fields, 'summary'), T.summary, { bold: true })], 'center',
      { ruleWidthMm: RULE_WIDTH_MM.title }),
  ];
}

function kinhGuiBlocks(type, fields) {
  if (!type.kinhGui) return [];
  const targets = lines(fields.kinhGui);
  if (targets.length <= 1) {
    const target = targets[0] || PLACEHOLDERS.kinhGui;
    return [para([run(`Kính gửi: ${target}.`, T.kinhGui)], 'center', { spacingBeforePt: 12 })];
  }
  return [
    para([run('Kính gửi:', T.kinhGui)], 'center', { spacingBeforePt: 12 }),
    ...targets.map((t, i) => para([run(`- ${t}${i === targets.length - 1 ? '.' : ';'}`, T.kinhGui)], 'center')),
  ];
}

function bodyBlocks(fields) {
  const paragraphs = lines(fields.body);
  const texts = paragraphs.length ? paragraphs : [PLACEHOLDERS.body];
  return texts.map((text) => para([run(text, T.body)], 'justify', {
    indentFirstMm: T.bodyFirstLineIndentMm,
    spacingAfterPt: T.paragraphSpacingPt,
    lineSpacing: T.lineSpacing,
  }));
}

function recipientParagraphs(fields) {
  const items = lines(fields.recipients).map((l) => l.replace(/^[-–]\s*/, '').replace(/[;.]$/, ''));
  if (!items.some((l) => /^Lưu\b/i.test(l))) items.push('Lưu: VT, [đơn vị soạn thảo]');
  return items.map((item, i) => para([run(`- ${item}${i === items.length - 1 ? '.' : ';'}`, T.recipientsList)], 'left'));
}

function signatureBlock(fields) {
  const left = [
    para([run('Nơi nhận:', T.recipientsHeading, { bold: true, italic: true })], 'left'),
    ...recipientParagraphs(fields),
  ];
  const right = [para([run(value(fields, 'signerAuthority').toUpperCase(), T.signerAuthority, { bold: true })])];
  if (fields.signerTitle && fields.signerTitle.trim()) {
    right.push(para([run(fields.signerTitle.trim().toUpperCase(), T.signerAuthority, { bold: true })]));
  }
  right.push(para([run('', T.signerName)], 'center', { spacingAfterPt: 60 }));
  right.push(para([run(value(fields, 'signerName'), T.signerName, { bold: true })]));
  return { type: 'two-column', widthsPct: [50, 50], left, right, spacingBeforePt: 12 };
}

/** @returns {{ typeId: string, blocks: object[] }} JSON-serialisable layout. */
export function buildLayout(typeId, fields = {}) {
  const type = getDocumentType(typeId);
  if (!type) throw new Error('unknown-type');
  return {
    typeId,
    blocks: [
      headerBlock(type, fields),
      ...titleBlocks(type, fields),
      ...kinhGuiBlocks(type, fields),
      ...bodyBlocks(fields),
      signatureBlock(fields),
    ],
  };
}
