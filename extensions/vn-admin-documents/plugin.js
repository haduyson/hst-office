// Entry point of the vn-admin-documents plugin (bundled to plugin.bundle.js).
// Flow: fill form → Preview (validates, renders text) → Insert (one editor
// command = one Undo step). Editing the form after preview disables Insert.
import { buildLayout } from './logic/nd30-layout.js';
import { PAGE_SIZE_MM, TYPOGRAPHY } from './logic/nd30-data.js';
import { validateFields, validateMargins } from './logic/nd30-validation.js';
import { insertLayoutCommand } from './insert-document.js';
import {
  describeErrors, layoutToPreviewText, populateTypes, readForm, syncTypeVisibility,
} from './admin-form.js';
import { closePlugin, runCommand } from '../shared/editor-bridge.js';
import {
  byId, describeOutcome, setBusy, showStatus, t, translatePage,
} from '../shared/ui-helpers.js';

let previewed = null; // last validated request; null = must preview again

function invalidatePreview() {
  previewed = null;
  byId('btn-insert').disabled = true;
}

function onPreview() {
  const request = readForm();
  const errors = [...validateFields(request.typeId, request.fields).errors];
  if (request.applyPageSetup) errors.push(...validateMargins(request.marginsMm).errors);
  if (errors.length) {
    invalidatePreview();
    showStatus(describeErrors(errors), 'error');
    return;
  }
  const layout = buildLayout(request.typeId, request.fields);
  byId('preview').textContent = layoutToPreviewText(layout);
  previewed = { layout, request };
  byId('btn-insert').disabled = false;
  const note = request.applyPageSetup
    ? t('Insert will also set A4 paper and the margins above for the whole document.')
    : t('Insert will not change page size or margins.');
  showStatus(note, 'info');
}

async function onInsert() {
  if (!previewed) return;
  const { layout, request } = previewed;
  const controls = [byId('btn-preview'), byId('btn-insert')];
  setBusy(controls, true);
  showStatus(t('Inserting…'), 'info');
  const outcome = await runCommand(insertLayoutCommand, {
    layout,
    fontFamily: TYPOGRAPHY.fontFamily,
    pageSetup: request.applyPageSetup ? { marginsMm: request.marginsMm, pageMm: PAGE_SIZE_MM } : null,
  });
  setBusy(controls, false);
  invalidatePreview();
  const { message, kind } = describeOutcome(outcome,
    t('Inserted. Use Undo (Ctrl+Z) once to remove it. Remember to save the document.'));
  showStatus(message, kind);
}

function bindUi() {
  populateTypes();
  byId('doc-type').addEventListener('change', syncTypeVisibility);
  byId('nd30-form').addEventListener('input', invalidatePreview);
  byId('nd30-form').addEventListener('change', invalidatePreview);
  byId('btn-preview').addEventListener('click', onPreview);
  byId('btn-insert').addEventListener('click', onInsert);
  byId('btn-close').addEventListener('click', closePlugin);
}

const asc = globalThis.Asc;
if (asc && asc.plugin) {
  asc.plugin.init = () => bindUi();
  asc.plugin.onTranslate = () => {
    translatePage();
    if (document.getElementById('doc-type')) populateTypes();
  };
  asc.plugin.button = () => closePlugin();
}
