// Launch and drive a real ONLYOFFICE Desktop Editors instance for runtime QA.
// - runs as the unprivileged `nobody` user (the editor aborts under root);
// - uses a fresh, isolated HOME so the user's real profile is never touched;
// - installs HST plugins by extracting .plugin archives into the documented
//   per-user folder ~/.local/share/onlyoffice/desktopeditors/data/sdkjs-plugins/{GUID};
// - exposes CDP helpers; stop() terminates only the processes it started.
import { execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { connect, sleep, waitForTarget } from './cdp-client.js';

export const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../..');
export const APP_DIR = process.env.HST_ONLYOFFICE_DIR
  || path.join(ROOT, 'upstream/cache/ode/opt/onlyoffice/desktopeditors');
const PLUGIN_SUBDIR = '.local/share/onlyoffice/desktopeditors/data/sdkjs-plugins';
const EDITOR_FRAME = "document.querySelector('iframe').contentWindow";

function run(cmd, args) {
  return execFileSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
}

async function portResponds(port) {
  try {
    await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(800) });
    return true;
  } catch {
    return false;
  }
}

/** Extract one .plugin into the profile; returns its GUID (asc.{...}). */
function installPlugin(home, pluginFile) {
  const config = JSON.parse(run('python3', ['-c',
    'import sys,zipfile;print(zipfile.ZipFile(sys.argv[1]).read("config.json").decode())', pluginFile]));
  const folder = path.join(home, PLUGIN_SUBDIR, config.guid.replace(/^asc\./, ''));
  fs.mkdirSync(folder, { recursive: true });
  run('python3', ['-c', 'import sys,zipfile;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])', pluginFile, folder]);
  return config.guid;
}

export async function startDesktop({ home, file, plugins = [], port = 9333, display = ':97', lang = 'vi_VN.UTF-8' }) {
  if (!fs.existsSync(path.join(APP_DIR, 'DesktopEditors'))) throw new Error(`ONLYOFFICE not found in ${APP_DIR}`);
  if (!fs.existsSync(`/tmp/.X11-unix/X${display.slice(1)}`)) throw new Error(`X display ${display} not running (start Xvfb ${display})`);
  if (await portResponds(port)) throw new Error(`CDP port ${port} already in use — stop the stale editor first`);

  fs.rmSync(home, { recursive: true, force: true });
  fs.mkdirSync(home, { recursive: true });
  const guids = plugins.map((p) => installPlugin(home, p));
  run('chown', ['-R', 'nobody', home, path.dirname(file)]);

  const args = ['-u', 'nobody', '--', 'env', `DISPLAY=${display}`, `HOME=${home}`, `LANG=${lang}`,
    `LD_LIBRARY_PATH=${APP_DIR}`, path.join(APP_DIR, 'DesktopEditors'), `--remote-debugging-port=${port}`, file];
  const log = fs.openSync(path.join(home, 'editor.log'), 'w');
  const child = spawn('runuser', args, { stdio: ['ignore', log, log] });

  const target = await waitForTarget(port, /api\/documents\/index\.html/, 90000);
  const cdp = await connect(target);
  const session = createSession(cdp, child, port, guids);
  await session.waitForDocument();
  return session;
}

function createSession(cdp, child, port, guids) {
  const evalEditor = (body) => cdp.evaluate(`(async () => { const ed = ${EDITOR_FRAME}; const a = ed.Asc.editor; ${body} })()`);
  const pluginDoc = (guid) => `ed.document.getElementById('iframe_${guid}').contentWindow`;

  return {
    guids,
    evalEditor,
    async waitForDocument(timeoutMs = 90000) {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        try {
          // Ready when the API answers and the document model can be serialised.
          if (await evalEditor('return !!(a && a.pluginMethod_GetVersion() && typeof a.pluginMethod_GetFileHTML() === "string");')) return;
        } catch { /* editor still loading */ }
        await sleep(500);
      }
      throw new Error('document did not finish loading');
    },
    installedPluginNames: () => evalEditor(
      'return JSON.parse(ed.AscDesktopEditor.GetInstallPlugins()).flatMap((g) => (g.pluginsData || []).map((p) => p.guid));'),
    /** Open a plugin panel. The plugin list loads after the document, so retry the run request. */
    async openPlugin(guid, timeoutMs = 45000) {
      const ready = () => evalEditor(`const f = ed.document.getElementById('iframe_${guid}');
        return !!(f && f.contentWindow.document.readyState === 'complete' && f.contentWindow.Asc && f.contentWindow.Asc.plugin && f.contentWindow.Asc.plugin.info);`);
      const deadline = Date.now() + timeoutMs;
      let lastRun = 0;
      while (Date.now() < deadline) {
        if (await ready()) return;
        const exists = await evalEditor(`return !!ed.document.getElementById('iframe_${guid}');`);
        if (!exists && Date.now() - lastRun > 4000) {
          // The editor UI lazy-loads the plugin panel; early runs throw — retry.
          await evalEditor(`try { a.asc_pluginRun('${guid}', 0, ''); return true; } catch (e) { return String(e); }`);
          lastRun = Date.now();
        }
        await sleep(300);
      }
      throw new Error(`plugin ${guid} did not open`);
    },
    /** Run code inside the plugin window: `w` = plugin window, `d` = its document. */
    evalPlugin: (guid, body) => evalEditor(`const w = ${pluginDoc(guid)}; const d = w.document; ${body}`),
    /** Read-only document snapshot that does not create undo history. */
    html: () => evalEditor('return a.pluginMethod_GetFileHTML();'),
    undo: () => evalEditor('a.Undo(); return a.asc_getCanUndo();'),
    redo: () => evalEditor('a.Redo(); return a.asc_getCanRedo();'),
    save: () => evalEditor('a.asc_Save(); return true;'),
    version: () => evalEditor('return a.pluginMethod_GetVersion();'),
    async screenshot(file, display = ':97') {
      fs.mkdirSync(path.dirname(file), { recursive: true });
      run('import', ['-display', display, '-window', 'root', file]);
    },
    async stop() {
      try { cdp.close(); } catch { /* already closed */ }
      try { run('pkill', ['-TERM', '-u', 'nobody', '-f', `remote-debugging-port=${port}`]); } catch { /* none left */ }
      for (let i = 0; i < 20 && (await portResponds(port)); i++) await sleep(250);
      if (child.exitCode === null) child.kill('SIGTERM');
    },
  };
}
