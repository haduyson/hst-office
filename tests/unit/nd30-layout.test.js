import assert from 'node:assert/strict';
import test from 'node:test';
import { buildLayout, formatIssueDate, formatNumber } from '../../extensions/vn-admin-documents/logic/nd30-layout.js';
import { DOCUMENT_TYPES, PLACEHOLDERS } from '../../extensions/vn-admin-documents/logic/nd30-data.js';

const textOf = (layout) => JSON.stringify(layout);
const paragraphs = (layout) => layout.blocks.flatMap((b) => (b.type === 'two-column' ? [...b.left, ...b.right] : [b]));
const lineTexts = (layout) => paragraphs(layout).map((p) => p.runs.map((r) => r.text).join(''));

test('number < 10 is zero padded (II.3c)', () => {
  assert.equal(formatNumber('5'), '05');
  assert.equal(formatNumber('12'), '12');
  assert.equal(formatNumber(''), '');
});

test('dates pad day < 10 and months 1–2 only (II.4b)', () => {
  assert.equal(formatIssueDate('2026-02-05'), 'ngày 05 tháng 02 năm 2026');
  assert.equal(formatIssueDate('2026-03-09'), 'ngày 09 tháng 3 năm 2026');
  assert.equal(formatIssueDate('2026-12-25'), 'ngày 25 tháng 12 năm 2026');
  assert.equal(formatIssueDate('05/02/2026'), null);
});

test('every type builds a header and signature block', () => {
  for (const type of DOCUMENT_TYPES) {
    const layout = buildLayout(type.id, {});
    assert.equal(layout.blocks[0].type, 'two-column', type.id);
    assert.equal(layout.blocks.at(-1).type, 'two-column', type.id);
    assert.ok(textOf(layout).includes('CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM'));
    assert.ok(textOf(layout).includes('Độc lập - Tự do - Hạnh phúc'));
  }
});

test('empty fields become explicit placeholders, never invented values', () => {
  const lines = lineTexts(buildLayout('quyet-dinh', {}));
  assert.ok(lines.includes(PLACEHOLDERS.agency));
  assert.ok(lines.includes(PLACEHOLDERS.signerName));
  assert.ok(lines.some((l) => l.startsWith(`Số: ${PLACEHOLDERS.number}/`)));
});

test('công văn: V/v under number, no type name; quyết định: type name block', () => {
  const cv = lineTexts(buildLayout('cong-van', { summary: 'mua sắm' }));
  assert.ok(cv.includes('V/v mua sắm'));
  assert.ok(!cv.includes('QUYẾT ĐỊNH'));
  const qd = lineTexts(buildLayout('quyet-dinh', { summary: 'phê duyệt' }));
  assert.ok(qd.includes('QUYẾT ĐỊNH'));
  assert.ok(qd.includes('phê duyệt'));
});

test('agency upper-cased and bold; place/date italic', () => {
  const layout = buildLayout('thong-bao', { agency: 'Sở kiểm thử', place: 'Huế', date: '2026-01-01' });
  const paras = paragraphs(layout);
  const agency = paras.find((p) => p.runs[0].text === 'SỞ KIỂM THỬ');
  assert.ok(agency && agency.runs[0].bold && agency.ruleWidthMm);
  const date = paras.find((p) => p.runs[0].text === 'Huế, ngày 01 tháng 01 năm 2026');
  assert.ok(date && date.runs[0].italic);
});

test('Kính gửi: single target inline, multiple targets as dash list', () => {
  const one = lineTexts(buildLayout('to-trinh', { kinhGui: 'Đơn vị A' }));
  assert.ok(one.includes('Kính gửi: Đơn vị A.'));
  const many = lineTexts(buildLayout('bao-cao', { kinhGui: 'Đơn vị A\nĐơn vị B' }));
  assert.ok(many.includes('Kính gửi:') && many.includes('- Đơn vị A;') && many.includes('- Đơn vị B.'));
  assert.ok(!lineTexts(buildLayout('quyet-dinh', { kinhGui: 'X' })).some((l) => l.startsWith('Kính gửi')));
});

test('recipients: dash list, ";" endings, final "Lưu" line ends with "."', () => {
  const lines = lineTexts(buildLayout('cong-van', { recipients: 'Như trên;\n- Sở A' }));
  const start = lines.indexOf('Nơi nhận:');
  assert.deepEqual(lines.slice(start + 1, start + 4), ['- Như trên;', '- Sở A;', '- Lưu: VT, [đơn vị soạn thảo].']);
  const custom = lineTexts(buildLayout('cong-van', { recipients: 'Như trên\nLưu: VT, VP.' }));
  assert.equal(custom.filter((l) => l.includes('Lưu')).length, 1);
});

test('body paragraphs: justified, first-line indent, one per line', () => {
  const layout = buildLayout('bien-ban', { body: 'Một.\n\nHai.' });
  const body = layout.blocks.filter((b) => b.type === 'paragraph' && b.align === 'justify');
  assert.deepEqual(body.map((b) => b.runs[0].text), ['Một.', 'Hai.']);
  assert.ok(body.every((b) => b.indentFirstMm > 0 && b.spacingAfterPt >= 6));
});

test('unknown type throws', () => {
  assert.throws(() => buildLayout('x', {}), /unknown-type/);
});

test('Vietnamese text is preserved verbatim (NFC input stays NFC)', () => {
  const s = 'Đoạn có dấu: ăâđêôơư ÁÀẢÃẠ';
  assert.ok(lineTexts(buildLayout('thong-bao', { body: s })).includes(s));
});
