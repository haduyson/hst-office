// Verify legal notices inside every built .plugin:
// - vendor/plugins.js and LICENSE-ONLYOFFICE.txt are byte-identical to the audited copies;
// - the AGPL header of the bridge and the Additional Terms are present;
// - HST LICENSE/NOTICE match the repo, About names ONLYOFFICE / Ascensio System SIA.
//   node scripts/check-notices.js [dist/plugins]
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { readEntry } from './plugin-archive.js';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const sha = (buf) => createHash('sha256').update(buf).digest('hex');
const provenance = JSON.parse(fs.readFileSync(path.join(ROOT, 'third_party/onlyoffice-plugin-sdk/provenance.json'), 'utf8'));

function checkPackage(file) {
  const errors = [];
  const bin = (name) => readEntry(file, name, 'buffer');
  if (sha(bin('vendor/plugins.js')) !== provenance.files['plugins.js']) errors.push('vendor/plugins.js differs from audited bridge');
  if (sha(bin('LICENSE-ONLYOFFICE.txt')) !== provenance.files['LICENSE.txt']) errors.push('LICENSE-ONLYOFFICE.txt differs');
  const bridge = bin('vendor/plugins.js').toString('utf8');
  if (!bridge.includes('Copyright Ascensio System SIA')) errors.push('bridge copyright header missing');
  if (!bin('LICENSE-ONLYOFFICE.txt').toString('utf8').includes('Additional Terms')) errors.push('Additional Terms missing');
  if (!bin('LICENSE').equals(fs.readFileSync(path.join(ROOT, 'LICENSE')))) errors.push('LICENSE differs from repo');
  if (!bin('NOTICE.txt').equals(fs.readFileSync(path.join(ROOT, 'NOTICE.md')))) errors.push('NOTICE.txt differs from NOTICE.md');
  const about = bin('about.html').toString('utf8');
  for (const needle of ['Ascensio System SIA', 'ONLYOFFICE', 'AGPL', 'LICENSE-ONLYOFFICE.txt', 'github.com/haduyson/hst-office', 'lienhe@hasontech.vn']) {
    if (!about.includes(needle)) errors.push(`about.html lacks "${needle}"`);
  }
  return errors;
}

const dir = process.argv[2] || 'dist/plugins';
const files = fs.readdirSync(dir).filter((f) => f.endsWith('.plugin')).sort();
if (!files.length) {
  console.error(`no .plugin files in ${dir}`);
  process.exit(1);
}
let failed = 0;
for (const f of files) {
  const errors = checkPackage(path.join(dir, f));
  console.log(`${errors.length ? 'FAIL' : 'ok  '} ${f}${errors.length ? `\n  - ${errors.join('\n  - ')}` : ''}`);
  failed += errors.length ? 1 : 0;
}
process.exit(failed ? 1 : 0);
