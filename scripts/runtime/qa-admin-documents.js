// Runtime QA for vn-admin-documents on real ONLYOFFICE Desktop Editors.
//   node scripts/runtime/qa-admin-documents.js [--out tests/output/runtime-qa/admin]
// Run under scripts/runtime/run-offline.sh to prove it works without network.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { APP_DIR, ROOT, startDesktop } from './desktop-session.js';
import { createEvidence } from './evidence.js';
import { sleep } from './cdp-client.js';

const GUID = 'asc.{535252E5-A2B9-475A-B273-33F549C3CC5D}';
const outArg = process.argv.indexOf('--out');
const OUT = path.resolve(ROOT, outArg > -1 ? process.argv[outArg + 1] : 'tests/output/runtime-qa/admin');
const PLUGIN = path.join(ROOT, 'dist/plugins/vn-admin-documents.plugin');
const DOC = path.join(OUT, 'files/cong-van.docx');
const MARKER = 'Đoạn kiểm thử HST có dấu: ăâđêôơư ÁÀẢÃẠ';
// Synthetic, clearly-labelled test values — no real agency or person.
const FORM = {
  agency: 'Cơ quan kiểm thử HST', number: '5', symbol: 'KT-HST', place: 'Đà Nẵng', date: '2026-02-05',
  summary: 'kiểm thử chèn văn bản', kinhGui: 'Đơn vị kiểm thử', body: `${MARKER}.\nĐoạn thứ hai.`,
  signerAuthority: 'KT. THỦ TRƯỞNG', signerName: '', recipients: 'Như trên',
};

const ev = createEvidence({ suite: 'vn-admin-documents runtime', app: 'ONLYOFFICE Desktop Editors', offline: !!process.env.HST_OFFLINE });
const has = (html) => html.includes(MARKER);

async function fillAndPreview(s) {
  await s.evalPlugin(GUID, `const v = ${JSON.stringify(FORM)};
    for (const [id, value] of Object.entries(v)) { const e = d.getElementById(id); e.value = value; e.dispatchEvent(new w.Event('input', { bubbles: true })); }
    d.getElementById('btn-preview').click(); return true;`);
  await sleep(300);
  return s.evalPlugin(GUID, "return { preview: d.getElementById('preview').textContent, insertDisabled: d.getElementById('btn-insert').disabled };");
}

async function insert(s) {
  await s.evalPlugin(GUID, "d.getElementById('btn-insert').click(); return true;");
  for (let i = 0; i < 80; i++) {
    await sleep(250);
    const st = await s.evalPlugin(GUID, "const e = d.getElementById('hst-status'); return { text: e.textContent, cls: e.className };");
    if (!/Đang chèn|Inserting/.test(st.text)) return st;
  }
  return { text: 'timeout', cls: '' };
}

async function main() {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(DOC), { recursive: true });
  fs.copyFileSync(path.join(APP_DIR, 'converter/empty/default/new.docx'), DOC);
  const blankHash = execFileSync('sha256sum', [DOC], { encoding: 'utf8' }).split(' ')[0];

  let s = await startDesktop({ home: path.join(OUT, 'home'), file: DOC, plugins: [PLUGIN] });
  try {
    ev.note('editor-version', await s.version());
    ev.check('plugin-installed', 'GUID listed by AscDesktopEditor.GetInstallPlugins', (await s.installedPluginNames()).includes(GUID), s.guids);
    await s.openPlugin(GUID);
    await s.screenshot(path.join(OUT, 'plugin-open.png'));

    const undoBefore = await s.evalEditor('return a.asc_getCanUndo();');
    const preview = await fillAndPreview(s);
    ev.check('preview-renders', 'preview contains padded number and marker', preview.preview.includes('Số: 05/KT-HST') && preview.preview.includes(MARKER), preview.preview.slice(0, 200));
    // GetFileHTML is not byte-stable between calls, so "no write" = no new undo history and no marker.
    const undoAfter = await s.evalEditor('return a.asc_getCanUndo();');
    ev.check('preview-no-write', 'no undo history and no content after preview', undoBefore === false && undoAfter === false && !has(await s.html()), { undoBefore, undoAfter });

    await s.evalPlugin(GUID, "const e = d.getElementById('summary'); e.value += ' (sửa)'; e.dispatchEvent(new w.Event('input', { bubbles: true })); return true;");
    ev.check('edit-invalidates-preview', 'Insert disabled after editing form', await s.evalPlugin(GUID, "return d.getElementById('btn-insert').disabled;"), null);
    await fillAndPreview(s);

    const status = await insert(s);
    ev.check('insert-success-status', 'success status shown', /success/.test(status.cls), status.text);
    ev.check('insert-content', 'marker text present in document', has(await s.html()), null);
    await s.screenshot(path.join(OUT, 'inserted.png'));

    await s.undo();
    await sleep(500);
    ev.check('single-undo-removes', 'one Undo removes the whole insertion', !has(await s.html()), null);
    await s.redo();
    await sleep(500);
    ev.check('redo-restores', 'Redo restores insertion', has(await s.html()), null);

    const mtime = fs.statSync(DOC).mtimeMs;
    await s.save();
    for (let i = 0; i < 40 && fs.statSync(DOC).mtimeMs === mtime; i++) await sleep(250);
    await sleep(1000);
  } finally {
    await s.stop();
  }

  const saved = JSON.parse(execFileSync('python3', [path.join(ROOT, 'scripts/runtime/inspect-ooxml.py'), DOC], { encoding: 'utf8' }));
  ev.check('saved-docx-valid', 'saved file is a valid DOCX zip', saved.zipOk === true, { parts: saved.parts });
  ev.check('saved-docx-changed', 'file differs from blank', execFileSync('sha256sum', [DOC], { encoding: 'utf8' }).split(' ')[0] !== blankHash, null);
  ev.check('saved-text', 'marker + national title saved', saved.text.includes(MARKER) && saved.text.includes('CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM'), saved.text.slice(0, 160));
  ev.check('saved-a4', 'A4 11906x16838 twips', saved.pageTwips.w === 11906 && saved.pageTwips.h === 16838, saved.pageTwips);
  ev.check('saved-margins', 'margins 20/20/30/15 mm (±1 twip)', Math.abs(saved.marginsTwips.top - 1134) <= 1 && Math.abs(saved.marginsTwips.bottom - 1134) <= 1
    && Math.abs(saved.marginsTwips.left - 1701) <= 1 && Math.abs(saved.marginsTwips.right - 850) <= 1, saved.marginsTwips);
  ev.check('saved-font', 'Times New Roman used', saved.fonts.includes('Times New Roman'), saved.fonts);
  ev.check('saved-lang', 'runs tagged vi-VN', saved.langs.includes('vi-VN'), saved.langs);

  s = await startDesktop({ home: path.join(OUT, 'home-reopen'), file: DOC });
  try {
    let reopened = false;
    let lastError = null;
    // The model may still be laying out after load; GetFileHTML can throw meanwhile.
    for (let i = 0; i < 60 && !reopened; i++) {
      try { reopened = has(await s.html()); } catch (error) { lastError = String(error.message).slice(0, 120); }
      if (!reopened) await sleep(500);
    }
    ev.check('reopen-content', 'content present after close and reopen', reopened, lastError);
    await s.screenshot(path.join(OUT, 'reopened.png'));
  } finally {
    await s.stop();
  }

  const doc = ev.write(path.join(OUT, 'evidence.json'), {
    plugin: PLUGIN, savedDocx: DOC, pluginOpen: path.join(OUT, 'plugin-open.png'),
    inserted: path.join(OUT, 'inserted.png'), reopened: path.join(OUT, 'reopened.png'),
  });
  console.log(`\n${doc.result}: ${doc.steps.filter((x) => x.status === 'PASS').length} passed, ${doc.failed} failed → ${path.relative(ROOT, OUT)}/evidence.json`);
  process.exit(doc.failed ? 1 : 0);
}

main().catch((error) => {
  console.error(error);
  process.exit(2);
});
