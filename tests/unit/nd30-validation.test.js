import assert from 'node:assert/strict';
import test from 'node:test';
import { isValidIsoDate, validateFields, validateMargins } from '../../extensions/vn-admin-documents/logic/nd30-validation.js';

const codes = (result) => result.errors.map((e) => `${e.field}:${e.code}`);

test('empty form is valid (placeholders are inserted)', () => {
  assert.deepEqual(validateFields('cong-van', {}), { ok: true, errors: [] });
});

test('unknown type', () => {
  assert.deepEqual(codes(validateFields('zzz', {})), ['type:unknown-type']);
});

test('number digits only, symbol without spaces or slash', () => {
  assert.deepEqual(codes(validateFields('cong-van', { number: '12a', symbol: 'UB ND/VP' })),
    ['number:number-digits-only', 'symbol:symbol-no-space-or-slash']);
  assert.ok(validateFields('cong-van', { number: '007', symbol: 'QĐ-UBND' }).ok);
});

test('calendar date validation', () => {
  assert.ok(isValidIsoDate('2024-02-29'));
  assert.ok(!isValidIsoDate('2026-02-29'));
  assert.ok(!isValidIsoDate('2026-13-01'));
  assert.deepEqual(codes(validateFields('thong-bao', { date: '2026-02-30' })), ['date:invalid-date']);
});

test('length limits and non-text values', () => {
  assert.deepEqual(codes(validateFields('thong-bao', { agency: 'x'.repeat(2001) })), ['agency:too-long']);
  assert.ok(validateFields('thong-bao', { body: 'x'.repeat(50000) }).ok);
  assert.deepEqual(codes(validateFields('thong-bao', { agency: 5 })), ['agency:not-text']);
});

test('margins must stay in ND30 ranges', () => {
  assert.ok(validateMargins({ top: 20, bottom: 25, left: 30, right: 15 }).ok);
  assert.deepEqual(codes(validateMargins({ top: 19, bottom: 20, left: 36, right: 'x' })),
    ['top:margin-out-of-range', 'left:margin-out-of-range', 'right:margin-not-number']);
});
