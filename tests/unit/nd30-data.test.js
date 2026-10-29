import assert from 'node:assert/strict';
import test from 'node:test';
import {
  DEFAULT_MARGINS_MM, DOCUMENT_TYPES, getDocumentType, MARGIN_RANGES_MM, PAGE_SIZE_MM, TYPOGRAPHY,
} from '../../extensions/vn-admin-documents/logic/nd30-data.js';

test('margin ranges match Phụ lục I, I.3', () => {
  assert.deepEqual(MARGIN_RANGES_MM, { top: [20, 25], bottom: [20, 25], left: [30, 35], right: [15, 20] });
});

test('default margins sit inside the allowed ranges', () => {
  for (const [side, [min, max]] of Object.entries(MARGIN_RANGES_MM)) {
    assert.ok(DEFAULT_MARGINS_MM[side] >= min && DEFAULT_MARGINS_MM[side] <= max, side);
  }
});

test('A4 portrait and Times New Roman', () => {
  assert.deepEqual(PAGE_SIZE_MM, { width: 210, height: 297 });
  assert.equal(TYPOGRAPHY.fontFamily, 'Times New Roman');
});

test('font sizes stay inside the ND30 ranges', () => {
  const ranges = {
    nationalTitle: [12, 13], motto: [13, 14], agency: [12, 13], parentAgency: [12, 13], number: [13, 13],
    placeDate: [13, 14], typeName: [13, 14], summary: [13, 14], summaryOfficialLetter: [12, 13], body: [13, 14],
    signerAuthority: [13, 14], signerName: [13, 14], recipientsHeading: [12, 12], recipientsList: [11, 11], kinhGui: [13, 14],
  };
  for (const [key, [min, max]] of Object.entries(ranges)) {
    assert.ok(TYPOGRAPHY[key] >= min && TYPOGRAPHY[key] <= max, `${key}=${TYPOGRAPHY[key]}`);
  }
  assert.ok([10, 12.7].includes(TYPOGRAPHY.bodyFirstLineIndentMm));
  assert.ok(TYPOGRAPHY.paragraphSpacingPt >= 6);
  assert.ok(TYPOGRAPHY.lineSpacing >= 1 && TYPOGRAPHY.lineSpacing <= 1.5);
});

test('seven document types with unique ids', () => {
  const ids = DOCUMENT_TYPES.map((t) => t.id);
  assert.deepEqual(ids, ['cong-van', 'thong-bao', 'quyet-dinh', 'to-trinh', 'bao-cao', 'giay-moi', 'bien-ban']);
  assert.equal(new Set(ids).size, 7);
  assert.equal(getDocumentType('cong-van').officialLetter, true);
  assert.equal(getDocumentType('nope'), null);
});

test('Kính gửi only for công văn, tờ trình, báo cáo (II.9b)', () => {
  const withKinhGui = DOCUMENT_TYPES.filter((t) => t.kinhGui).map((t) => t.id);
  assert.deepEqual(withKinhGui, ['cong-van', 'to-trinh', 'bao-cao']);
});

test('data is JSON-serialisable for the template exporter', () => {
  const copy = JSON.parse(JSON.stringify({ DOCUMENT_TYPES, TYPOGRAPHY, MARGIN_RANGES_MM }));
  assert.equal(copy.DOCUMENT_TYPES.length, 7);
});
