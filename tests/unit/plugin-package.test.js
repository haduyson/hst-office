// Builds real packages with the production builder, then checks structure,
// notices, offline rules and byte-for-byte reproducibility.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { checkPlugin, uiStrings } from '../../scripts/check-plugins.js';
import { scanPackage } from '../../scripts/check-offline-assets.js';
import { listEntries } from '../../scripts/plugin-archive.js';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../..');
const ID = 'vn-admin-documents';

function build(outDir) {
  execFileSync('node', [path.join(ROOT, 'scripts/build-plugins.js'), '--plugin', ID, '--out', outDir], { stdio: 'pipe' });
  return path.join(outDir, `${ID}.plugin`);
}

const sha = (file) => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hst-plugin-'));
const first = build(path.join(tmp, 'a'));

test('package passes the contract checker', () => {
  assert.deepEqual(checkPlugin(first).errors, []);
});

test('config.json at archive root, no wrapper folder', () => {
  const names = listEntries(first).map((e) => e.name);
  assert.ok(names.includes('config.json'));
  assert.ok(!names.some((n) => n.startsWith(`${ID}/`)));
});

test('no runtime network resources', () => {
  assert.deepEqual(scanPackage(first), []);
});

test('translation scan finds the UI strings', () => {
  const html = fs.readFileSync(path.join(ROOT, 'extensions', ID, 'index.html'), 'utf8');
  assert.ok(uiStrings(html, '').length > 20);
  assert.deepEqual(uiStrings('', "t('A b') t(\"C\") x.t('no')"), ['A b', 'C']);
});

test('two builds are byte-identical', () => {
  const second = build(path.join(tmp, 'b'));
  assert.equal(sha(first), sha(second));
});

test.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
