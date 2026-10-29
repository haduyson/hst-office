// Safe wrapper around the ONLYOFFICE plugin bridge (window.Asc.plugin).
// - one mutation in flight at a time (callers must disable Apply while busy);
// - inputs are copied into Asc.scope as plain JSON (no closures cross over);
// - after dispatch, a timeout means "outcome unknown": we never retry, because
//   the editor may already have applied the change.

const DEFAULT_TIMEOUT_MS = 30000;
let inFlight = false;

export function isBusy() {
  return inFlight;
}

function plugin() {
  const asc = globalThis.Asc;
  if (!asc || !asc.plugin) throw new Error('bridge-unavailable');
  return asc.plugin;
}

/**
 * Commands must return a plain object: { ...data } on success or
 * { error, stage, modified } when they caught an exception. The editor invokes the
 * callback even when a command throws, with an undefined result, so an
 * absent result is "unknown" rather than success.
 */
export function classifyResult(result) {
  if (result && typeof result === 'object' && !Array.isArray(result)) {
    if (result.error) {
      // Assume partial change unless the command states it modified nothing.
      return { status: 'error', error: `${result.stage || 'command'}: ${result.error}`, partial: result.modified !== false };
    }
    return { status: 'ok', result };
  }
  return { status: 'unknown' };
}

/**
 * Run an editor command. Resolves to one of:
 *   { status: 'ok', result }      – editor confirmed completion
 *   { status: 'error', partial }  – command reported a caught exception; it may have changed part of the document
 *   { status: 'unknown' }         – dispatched but no confirmation (timeout or no result)
 *   { status: 'busy' }            – another mutation is still running (nothing sent)
 *   { status: 'error', error }    – failed before or during dispatch
 */
export function runCommand(command, scopeData, { timeoutMs = DEFAULT_TIMEOUT_MS, recalc = true } = {}) {
  if (inFlight) return Promise.resolve({ status: 'busy' });
  let p;
  try {
    p = plugin();
    // JSON round-trip guarantees only serialisable data reaches the editor.
    const copy = JSON.parse(JSON.stringify(scopeData || {}));
    Object.keys(copy).forEach((key) => { globalThis.Asc.scope[key] = copy[key]; });
  } catch (error) {
    return Promise.resolve({ status: 'error', error: String(error.message || error) });
  }
  inFlight = true;
  return new Promise((resolve) => {
    let settled = false;
    const finish = (outcome) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      inFlight = false;
      resolve(outcome);
    };
    const timer = setTimeout(() => finish({ status: 'unknown' }), timeoutMs);
    try {
      p.callCommand(command, false, recalc, (result) => finish(classifyResult(result)));
    } catch (error) {
      finish({ status: 'error', error: String(error.message || error) });
    }
  });
}

/** Promise wrapper for read-only executeMethod calls (e.g. GetSelectedText). */
export function executeMethod(name, args = [], { timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve({ status: 'unknown' }), timeoutMs);
    try {
      plugin().executeMethod(name, args, (result) => {
        clearTimeout(timer);
        resolve({ status: 'ok', result });
      });
    } catch (error) {
      clearTimeout(timer);
      resolve({ status: 'error', error: String(error.message || error) });
    }
  });
}

/** Close the plugin window (modal/visual plugins). */
export function closePlugin() {
  try {
    plugin().executeCommand('close', '');
  } catch { /* window already gone */ }
}
