// Form <-> data mapping and text preview for the ND30 plugin UI.
import { COMMON_FIELDS, DEFAULT_MARGINS_MM, DOCUMENT_TYPES, getDocumentType } from './logic/nd30-data.js';
import { byId, t } from '../shared/ui-helpers.js';

const FIELD_IDS = [...COMMON_FIELDS, 'kinhGui'];
const MARGIN_IDS = { top: 'm-top', bottom: 'm-bottom', left: 'm-left', right: 'm-right' };

export function populateTypes() {
  const select = byId('doc-type');
  select.replaceChildren();
  DOCUMENT_TYPES.forEach((type) => {
    const option = document.createElement('option');
    option.value = type.id;
    option.textContent = type.typeName ? `${type.typeName} — ${t(type.label)}` : `CÔNG VĂN — ${t(type.label)}`;
    select.append(option);
  });
  Object.entries(MARGIN_IDS).forEach(([side, id]) => { byId(id).value = DEFAULT_MARGINS_MM[side]; });
  syncTypeVisibility();
}

/** Show the "Kính gửi" field only for types that use it (ND30 II.9b). */
export function syncTypeVisibility() {
  const type = getDocumentType(byId('doc-type').value);
  byId('kinhGui-group').hidden = !(type && type.kinhGui);
}

export function readForm() {
  const fields = {};
  FIELD_IDS.forEach((id) => { fields[id] = byId(id).value; });
  const type = getDocumentType(byId('doc-type').value);
  if (!type || !type.kinhGui) fields.kinhGui = '';
  const marginsMm = {};
  Object.entries(MARGIN_IDS).forEach(([side, id]) => { marginsMm[side] = Number(byId(id).value); });
  return {
    typeId: byId('doc-type').value,
    fields,
    applyPageSetup: byId('apply-page-setup').checked,
    marginsMm,
  };
}

/** Flatten layout blocks into readable preview lines (cells shown side by side as two sections). */
export function layoutToPreviewText(layout) {
  const out = [];
  const paraText = (p) => p.runs.map((r) => r.text).join('');
  layout.blocks.forEach((block) => {
    if (block.type === 'two-column') {
      out.push(`[${t('Left column')}]`, ...block.left.map(paraText).filter(Boolean));
      out.push(`[${t('Right column')}]`, ...block.right.map(paraText).filter(Boolean));
    } else {
      out.push(paraText(block));
    }
  });
  return out.join('\n');
}

const ERROR_TEXT = {
  'unknown-type': 'Unknown document type.',
  'not-text': 'Invalid value.',
  'too-long': 'Text is too long.',
  'number-digits-only': 'Number must contain digits only.',
  'symbol-no-space-or-slash': 'Symbol must not contain spaces or "/".',
  'invalid-date': 'Invalid date.',
  'margin-not-number': 'Margin must be a number.',
  'margin-out-of-range': 'Margin is outside the Decree 30 range.',
};

export function describeErrors(errors) {
  return errors.map((e) => `• ${e.field}: ${t(ERROR_TEXT[e.code] || e.code)}`).join('\n');
}
