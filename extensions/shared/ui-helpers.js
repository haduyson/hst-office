// Small DOM/i18n helpers shared by every HST plugin UI. Translations come from
// translations/<lang>.json, loaded by the ONLYOFFICE bridge into Asc.plugin.tr.

/** Translate an English source string through the plugin bridge (falls back to source). */
export function t(text) {
  const asc = globalThis.Asc;
  return asc && asc.plugin && typeof asc.plugin.tr === 'function' ? asc.plugin.tr(text) : text;
}

/** Translate every element carrying data-i18n / data-i18n-placeholder / data-i18n-title. */
export function translatePage(root = document) {
  root.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  root.querySelectorAll('[data-i18n-title]').forEach((el) => { el.title = t(el.dataset.i18nTitle); });
}

export function byId(id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing-element:${id}`);
  return el;
}

/** Show a status line. kind: 'info' | 'success' | 'warning' | 'error'. */
export function showStatus(message, kind = 'info') {
  const el = byId('hst-status');
  el.textContent = message;
  el.className = `hst-status hst-status-${kind}`;
  el.setAttribute('role', kind === 'error' || kind === 'warning' ? 'alert' : 'status');
}

/** Human message for a bridge outcome from editor-bridge.runCommand. */
export function describeOutcome(outcome, successMessage) {
  switch (outcome.status) {
    case 'ok':
      return { message: successMessage, kind: 'success' };
    case 'unknown':
      return {
        message: t('The editor did not confirm in time. The document may already be changed — check it or use Undo (Ctrl+Z). Nothing will be retried.'),
        kind: 'warning',
      };
    case 'busy':
      return { message: t('Another operation is still running. Please wait.'), kind: 'warning' };
    default:
      return {
        message: `${outcome.partial
          ? t('The operation failed part-way. Part of the document may have changed — use Undo (Ctrl+Z) once to revert it.')
          : t('The operation failed. The document was not changed by HST.')} (${outcome.error || ''})`,
        kind: 'error',
      };
  }
}

/** Disable/enable a set of controls while an operation runs. */
export function setBusy(controls, busy) {
  controls.forEach((el) => { el.disabled = busy; });
  document.body.setAttribute('aria-busy', busy ? 'true' : 'false');
}
