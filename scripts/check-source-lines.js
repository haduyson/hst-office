// Enforce the project rule that authored code files stay below 200 lines.
// Verbatim third-party files and generated output are excluded.
//   node scripts/check-source-lines.js [--max 199]
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const SCAN = ['extensions', 'scripts', 'tests'];
const EXT = /\.(js|mjs|py|css|html|sh)$/;
const SKIP_DIRS = new Set(['node_modules', 'output', 'fixtures', '__pycache__']);
const maxIdx = process.argv.indexOf('--max');
const MAX = maxIdx > -1 ? Number(process.argv[maxIdx + 1]) : 199;

function walk(dir, out) {
  for (const name of fs.readdirSync(dir)) {
    const abs = path.join(dir, name);
    if (fs.statSync(abs).isDirectory()) {
      if (!SKIP_DIRS.has(name)) walk(abs, out);
    } else if (EXT.test(name)) {
      out.push(abs);
    }
  }
  return out;
}

const offenders = [];
for (const top of SCAN) {
  const dir = path.join(ROOT, top);
  if (!fs.existsSync(dir)) continue;
  for (const file of walk(dir, [])) {
    const lines = fs.readFileSync(file, 'utf8').split('\n').length - 1;
    if (lines > MAX) offenders.push(`${path.relative(ROOT, file)}: ${lines} lines`);
  }
}
if (offenders.length) {
  console.error(`Files over ${MAX} lines:\n  ${offenders.join('\n  ')}`);
  process.exit(1);
}
console.log(`ok: all authored files ≤ ${MAX} lines`);
