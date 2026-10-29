// Build every extensions/<id> that has a config.json into dist/plugins/<id>.plugin.
//   node scripts/build-plugins.js [--plugin <id>] [--out dist/plugins]
// Each package gets the bundled code, shared UI, the verbatim ONLYOFFICE SDK
// bridge, HST icons, licences/notices and build-info.json; then
// scripts/package-plugin.py writes a deterministic ZIP.
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { bundlePlugin } from './bundle-plugin.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ICON_SCALES = { '': 28, '@1.25x': 35, '@1.5x': 42, '@1.75x': 49, '@2x': 56 };

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : fallback;
}

function listPlugins() {
  const dir = path.join(ROOT, 'extensions');
  return fs.readdirSync(dir).filter((id) => fs.existsSync(path.join(dir, id, 'config.json'))).sort();
}

function copy(from, to) {
  fs.mkdirSync(path.dirname(to), { recursive: true });
  fs.copyFileSync(from, to);
}

function gitCommit() {
  try {
    return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    return 'unknown';
  }
}

function hashTree(dir) {
  const out = {};
  const walk = (rel) => {
    for (const name of fs.readdirSync(path.join(dir, rel)).sort()) {
      const relPath = rel ? `${rel}/${name}` : name;
      const abs = path.join(dir, relPath);
      if (fs.statSync(abs).isDirectory()) walk(relPath);
      else out[relPath] = createHash('sha256').update(fs.readFileSync(abs)).digest('hex');
    }
  };
  walk('');
  return out;
}

/** Copy plugin-declared extra files (e.g. generated template catalog); missing input is an error. */
function copyExtraFiles(src, stage) {
  const buildFile = path.join(src, 'build.json');
  if (!fs.existsSync(buildFile)) return;
  const { extraFiles = [] } = JSON.parse(fs.readFileSync(buildFile, 'utf8'));
  for (const { from, to } of extraFiles) {
    const abs = path.join(ROOT, from);
    if (!fs.existsSync(abs)) throw new Error(`Missing generated input ${from} (run the template pipeline first)`);
    if (to.includes('..') || path.isAbsolute(to)) throw new Error(`Unsafe package path ${to}`);
    if (fs.statSync(abs).isDirectory()) fs.cpSync(abs, path.join(stage, to), { recursive: true });
    else copy(abs, path.join(stage, to));
  }
}

async function buildOne(id, outDir) {
  const src = path.join(ROOT, 'extensions', id);
  const stage = path.join(ROOT, 'build', 'plugins', id);
  fs.rmSync(stage, { recursive: true, force: true });
  fs.mkdirSync(stage, { recursive: true });

  for (const name of ['config.json', 'index.html', 'styles.css']) copy(path.join(src, name), path.join(stage, name));
  fs.cpSync(path.join(src, 'translations'), path.join(stage, 'translations'), { recursive: true });
  await bundlePlugin(path.join(src, 'plugin.js'), path.join(stage, 'plugin.bundle.js'));

  copy(path.join(ROOT, 'extensions/shared/plugin-ui.css'), path.join(stage, 'shared/plugin-ui.css'));
  copy(path.join(ROOT, 'extensions/shared/about.html'), path.join(stage, 'about.html'));
  copy(path.join(ROOT, 'third_party/onlyoffice-plugin-sdk/plugins.js'), path.join(stage, 'vendor/plugins.js'));
  copy(path.join(ROOT, 'third_party/onlyoffice-plugin-sdk/LICENSE.txt'), path.join(stage, 'LICENSE-ONLYOFFICE.txt'));
  copy(path.join(ROOT, 'LICENSE'), path.join(stage, 'LICENSE'));
  copy(path.join(ROOT, 'NOTICE.md'), path.join(stage, 'NOTICE.txt'));
  copy(path.join(ROOT, 'assets/brand/hst-office-logo.png'), path.join(stage, 'resources/brand/hst-office-logo.png'));
  for (const style of ['light', 'dark']) {
    for (const [suffix, size] of Object.entries(ICON_SCALES)) {
      copy(path.join(ROOT, `assets/brand/icons/hst-office-icon-${size}.png`),
        path.join(stage, `resources/${style}/icon${suffix}.png`));
    }
  }
  copyExtraFiles(src, stage);

  const config = JSON.parse(fs.readFileSync(path.join(src, 'config.json'), 'utf8'));
  const info = {
    id, guid: config.guid, version: config.version, gitCommit: gitCommit(),
    testedWith: 'ONLYOFFICE Desktop Editors 10.0.0.169', files: hashTree(stage),
  };
  fs.writeFileSync(path.join(stage, 'build-info.json'), `${JSON.stringify(info, null, 2)}\n`);

  const outFile = path.join(outDir, `${id}.plugin`);
  execFileSync('python3', [path.join(ROOT, 'scripts/package-plugin.py'), stage, outFile], { stdio: 'inherit' });
  return outFile;
}

async function main() {
  const only = arg('--plugin', null);
  const outDir = path.resolve(ROOT, arg('--out', 'dist/plugins'));
  const ids = only ? [only] : listPlugins();
  for (const id of ids) {
    if (!listPlugins().includes(id)) throw new Error(`Unknown plugin ${id}`);
  }
  fs.mkdirSync(outDir, { recursive: true });
  for (const id of ids) console.log(`built ${path.relative(ROOT, await buildOne(id, outDir))}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
