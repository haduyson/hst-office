// Input validation for the ND30 form. Returns machine-readable error codes;
// the UI maps codes to translated messages. Empty fields are allowed (they
// become explicit placeholders) — validation only rejects malformed input.
import { getDocumentType, MARGIN_RANGES_MM } from './nd30-data.js';

const MAX_FIELD_LENGTH = 2000;
const MAX_BODY_LENGTH = 100000;

/** True when an ISO date string names a real calendar day. */
export function isValidIsoDate(text) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (!match) return false;
  const [year, month, day] = match.slice(1).map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

/** @returns {{ ok: boolean, errors: {field: string, code: string}[] }} */
export function validateFields(typeId, fields = {}) {
  const errors = [];
  if (!getDocumentType(typeId)) return { ok: false, errors: [{ field: 'type', code: 'unknown-type' }] };

  for (const [field, raw] of Object.entries(fields)) {
    if (raw === undefined || raw === null) continue;
    if (typeof raw !== 'string') errors.push({ field, code: 'not-text' });
    else if (raw.length > (field === 'body' ? MAX_BODY_LENGTH : MAX_FIELD_LENGTH)) errors.push({ field, code: 'too-long' });
  }
  const number = (fields.number || '').trim();
  if (number && !/^\d{1,6}$/.test(number)) errors.push({ field: 'number', code: 'number-digits-only' });
  const symbol = (fields.symbol || '').trim();
  if (symbol && /[\s/]/.test(symbol)) errors.push({ field: 'symbol', code: 'symbol-no-space-or-slash' });
  const date = (fields.date || '').trim();
  if (date && !isValidIsoDate(date)) errors.push({ field: 'date', code: 'invalid-date' });
  return { ok: errors.length === 0, errors };
}

/** Margins must stay inside the ND30 ranges (Phụ lục I, I.3). */
export function validateMargins(marginsMm = {}) {
  const errors = [];
  for (const [side, [min, max]] of Object.entries(MARGIN_RANGES_MM)) {
    const valueMm = Number(marginsMm[side]);
    if (!Number.isFinite(valueMm)) errors.push({ field: side, code: 'margin-not-number' });
    else if (valueMm < min || valueMm > max) errors.push({ field: side, code: 'margin-out-of-range' });
  }
  return { ok: errors.length === 0, errors };
}
