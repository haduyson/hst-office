// Fail if a built plugin would load anything from the network at runtime.
// Allowed: plain <a href="https://…"> attribution/licence links and URLs that
// only appear inside comments of the verbatim upstream bridge.
//   node scripts/check-offline-assets.js [dist/plugins]
import fs from 'node:fs';
import path from 'node:path';
import { listEntries, readEntry } from './plugin-archive.js';

const REMOTE = 'https?:)?//';
const RULES = [
  { ext: /\.html?$/, re: new RegExp(`<(script|link|img|iframe|source|video|audio)\\b[^>]*\\b(src|href)\\s*=\\s*["'](${REMOTE}`, 'gi'), what: 'remote resource tag' },
  { ext: /\.css$/, re: new RegExp(`(@import|url\\()\\s*["']?(${REMOTE}`, 'gi'), what: 'remote CSS import/url' },
  { ext: /\.js$/, re: /\b(fetch|importScripts|WebSocket|EventSource|sendBeacon)\s*\(/g, what: 'network API call' },
  { ext: /\.js$/, re: /XMLHttpRequest/g, what: 'XMLHttpRequest' },
  { ext: /\.js$/, re: new RegExp(`["'\`](${REMOTE}[^"'\`]+["'\`]`, 'g'), what: 'remote URL literal' },
];

function stripComments(js) {
  return js.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:\\])\/\/[^\n]*/g, '$1');
}

export function scanPackage(file) {
  const findings = [];
  for (const { name } of listEntries(file)) {
    if (name === 'vendor/plugins.js') continue; // verbatim upstream bridge, audited separately
    const rules = RULES.filter((r) => r.ext.test(name));
    if (!rules.length) continue;
    let text = readEntry(file, name);
    if (name.endsWith('.js')) text = stripComments(text);
    for (const rule of rules) {
      for (const m of text.matchAll(rule.re)) findings.push(`${name}: ${rule.what}: ${m[0].slice(0, 80)}`);
    }
  }
  return findings;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const dir = process.argv[2] || 'dist/plugins';
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.plugin')).sort();
  let failed = 0;
  for (const f of files) {
    const findings = scanPackage(path.join(dir, f));
    console.log(`${findings.length ? 'FAIL' : 'ok  '} ${f}${findings.length ? `\n  - ${findings.join('\n  - ')}` : ''}`);
    failed += findings.length ? 1 : 0;
  }
  if (!files.length) console.error(`no .plugin files in ${dir}`);
  process.exit(failed || !files.length ? 1 : 0);
}
