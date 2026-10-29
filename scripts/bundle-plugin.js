// Bundle one plugin entry (extensions/<id>/plugin.js) into a single IIFE
// script. Identifiers are not minified so editor-side command functions keep
// readable source when callCommand serialises them with Function#toString.
import { build } from 'esbuild';

export async function bundlePlugin(entryFile, outFile) {
  await build({
    entryPoints: [entryFile],
    outfile: outFile,
    bundle: true,
    format: 'iife',
    platform: 'browser',
    target: ['chrome100'],
    minify: false,
    sourcemap: false,
    legalComments: 'inline',
    charset: 'utf8',
    logLevel: 'warning',
  });
}
