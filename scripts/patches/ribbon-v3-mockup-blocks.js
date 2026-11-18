// Runs the v3 mockup's own packItems/packRun/eff (extracted from mockup-chot-v3.html) on every group and prints
// the block structure: one line per case "app tab group state big => blocks".
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const data = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
function grab(name) {
  const i = src.indexOf('function ' + name + '('); let d = 0; const j = src.indexOf('{', i);
  for (let k = j; k < src.length; k++) { if (src[k] === '{') d++; else if (src[k] === '}') { d--; if (!d) return src.slice(i, k + 1); } }
}
let BIG = [], GI = -1, ONE = false, GS = 'L', GX = 0, IDX = new Map();
const small = (a, t, it, k) => '{' + IDX.get(it) + (k === 'S' ? 'S' : 'M') + '}';
const large = (a, t, it) => '<B' + IDX.get(it) + 'L>';
const widget = (a, t, it) => '{' + IDX.get(it) + 'W}';
const gallery = (a, t, it, st) => '<B' + IDX.get(it) + 'G>';
eval(grab('eff') + grab('packRun') + grab('packItems') + ';globalThis.eff=eff;globalThis.packItems=packItems;');
function body(g, st) {
  const items = g.items; ONE = items.length === 1;
  if (g.rows) {
    const inRows = new Set(g.rows.flat()); const pre = items.filter(i => !inRows.has(i.k));
    const byK = Object.fromEntries(items.map(i => [i.k, i]));
    const rows = g.rows.map(r => '<div class="row">' + r.map(k => k === '|' ? '{|}' : (eff(byK[k], st) === 'W' ? widget(0, 0, byK[k]) : small(0, 0, byK[k], eff(byK[k], st)))).join('') + '</div>').join('');
    return packItems('', '', pre, st) + '<div class="rows">' + rows + '</div>';
  }
  return packItems('', '', items, st);
}
function items(s) { return [...s.matchAll(/\{([^}]*)\}/g)].map(m => m[1]).join(','); }
function conv(h) {
  const out = [];
  const re = /<div class="rows">((?:<div class="row">(?:(?!<\/div>).)*<\/div>)+)<\/div>|<div class="col">((?:(?!<\/div>).)*)<\/div>|<B(\d+)([LG])>/g;
  let m;
  while ((m = re.exec(h))) {
    if (m[1] !== undefined) out.push('R[' + [...m[1].matchAll(/<div class="row">((?:(?!<\/div>).)*)<\/div>/g)].map(r => items(r[1])).join('/') + ']');
    else if (m[2] !== undefined) out.push('C[' + items(m[2]) + ']');
    else out.push(m[4] + '[' + m[3] + m[4] + ']');
  }
  return out.join(' ');
}
for (const a of data.apps) for (const t of a.tabs) for (const g of t.groups) {
  IDX = new Map(g.items.map((it, i) => [it, i]));
  for (const st of ['L', 'M', 'S']) for (const big of [0, 1]) {
    if (big && st !== 'L') continue;
    BIG = [big]; GI = 0; GS = st;
    console.log(a.id + ' ' + t.id + ' ' + g.id + ' ' + st + ' ' + big + ' => ' + conv(body(g, st)));
  }
}
