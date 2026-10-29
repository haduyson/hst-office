// Validate built .plugin archives against docs/PLUGIN_CONTRACT.md.
//   node scripts/check-plugins.js [dist/plugins] [--expected N]
// Checks: config.json at root, contract GUID, unique GUIDs, no unsafe/odd
// entries, fixed timestamps, required files, translations cover every UI string.
import fs from 'node:fs';
import path from 'node:path';
import { listEntries, readEntry } from './plugin-archive.js';

export const CONTRACT_GUIDS = {
  'vn-admin-documents': 'asc.{535252E5-A2B9-475A-B273-33F549C3CC5D}',
  'vn-encoding-tools': 'asc.{8A4ECB32-A9A3-4DB7-BB6F-BBACC0C194DD}',
  'vn-spreadsheet-formats': 'asc.{2098C2B4-AB91-403E-8E41-1683744CD329}',
  'vn-templates': 'asc.{A1C9AB68-72D0-4FDB-AA96-F40C11AB8FDC}',
};
const REQUIRED = ['config.json', 'index.html', 'plugin.bundle.js', 'vendor/plugins.js', 'about.html', 'LICENSE',
  'LICENSE-ONLYOFFICE.txt', 'NOTICE.txt', 'build-info.json', 'translations/langs.json', 'translations/vi-VN.json',
  'resources/light/icon.png', 'resources/light/icon@2x.png', 'resources/dark/icon.png'];

/** UI strings that must be translated: data-i18n* attributes and t('…') literals. */
export function uiStrings(html, js) {
  const found = new Set();
  const decode = (s) => s.replace(/&amp;/g, '&').replace(/&quot;/g, '"');
  for (const m of html.matchAll(/data-i18n(?:-placeholder|-title)?="([^"]+)"/g)) found.add(decode(m[1]));
  for (const m of js.matchAll(/\bt\(\s*(['"])((?:\\.|(?!\1).)+)\1\s*\)/g)) found.add(m[2].replace(/\\(.)/g, '$1'));
  return [...found];
}

export function checkPlugin(file) {
  const errors = [];
  const id = path.basename(file, '.plugin');
  const entries = listEntries(file);
  const names = entries.map((e) => e.name);
  for (const e of entries) {
    if (e.name.startsWith('/') || e.name.split('/').includes('..') || e.name.endsWith('/')) errors.push(`unsafe entry ${e.name}`);
    if (e.time.join(',') !== '1980,1,1,0,0,0') errors.push(`non-fixed timestamp ${e.name}`);
    if ((e.mode & 0o170000) === 0o120000) errors.push(`symlink ${e.name}`);
  }
  for (const req of REQUIRED) if (!names.includes(req)) errors.push(`missing ${req}`);
  if (errors.length) return { id, errors };

  const config = JSON.parse(readEntry(file, 'config.json'));
  if (CONTRACT_GUIDS[id] && config.guid !== CONTRACT_GUIDS[id]) errors.push(`guid ${config.guid} != contract ${CONTRACT_GUIDS[id]}`);
  if (!/^asc\.\{[0-9A-F-]{36}\}$/.test(config.guid)) errors.push(`bad guid format ${config.guid}`);
  for (const v of config.variations) {
    if (!names.includes(v.url)) errors.push(`variation url ${v.url} missing`);
    for (const icon of [...(v.icons || []), ...(v.icons2 || []).flatMap((s) => Object.values(s).filter((x) => x.normal).map((x) => x.normal))]) {
      if (!names.includes(icon)) errors.push(`icon ${icon} missing`);
    }
  }
  const langs = JSON.parse(readEntry(file, 'translations/langs.json'));
  const vi = JSON.parse(readEntry(file, 'translations/vi-VN.json'));
  if (!langs.includes('vi-VN')) errors.push('langs.json lacks vi-VN');
  if (!config.nameLocale || !config.nameLocale.vi) errors.push('config.nameLocale.vi missing');
  const missing = uiStrings(readEntry(file, 'index.html'), readEntry(file, 'plugin.bundle.js')).filter((s) => !(s in vi));
  if (missing.length) errors.push(`untranslated: ${missing.join(' | ')}`);
  return { id, guid: config.guid, errors };
}

function main() {
  const args = process.argv.slice(2);
  const dir = args.find((a) => !a.startsWith('--') && !/^\d+$/.test(a)) || 'dist/plugins';
  const expectedIdx = args.indexOf('--expected');
  const expected = expectedIdx > -1 ? Number(args[expectedIdx + 1]) : null;
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.plugin')).sort().map((f) => path.join(dir, f));
  const results = files.map(checkPlugin);
  const guids = results.map((r) => r.guid).filter(Boolean);
  let failed = 0;
  if (new Set(guids).size !== guids.length) { console.error('duplicate GUIDs across plugins'); failed++; }
  if (expected !== null && files.length !== expected) { console.error(`expected ${expected} plugins, found ${files.length}`); failed++; }
  for (const r of results) {
    console.log(`${r.errors.length ? 'FAIL' : 'ok  '} ${r.id}${r.errors.length ? `\n  - ${r.errors.join('\n  - ')}` : ''}`);
    if (r.errors.length) failed++;
  }
  process.exit(failed ? 1 : 0);
}

if (import.meta.url === `file://${process.argv[1]}`) main();
