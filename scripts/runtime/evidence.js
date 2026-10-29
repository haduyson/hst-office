// Records runtime QA steps (expected vs actual) and writes evidence.json with
// artifact hashes. A step is PASS only when its check returned true.
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export function sha256File(file) {
  return createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

export function createEvidence(meta) {
  const steps = [];
  return {
    steps,
    /** Record a check; `actual` is stored verbatim (keep it small and free of personal data). */
    check(id, expected, passed, actual) {
      const status = passed ? 'PASS' : 'FAIL';
      steps.push({ id, expected, actual, status });
      console.log(`${status}  ${id}${passed ? '' : `  → ${JSON.stringify(actual)}`}`);
      return passed;
    },
    note(id, actual) {
      steps.push({ id, actual, status: 'INFO' });
    },
    write(file, artifacts = {}) {
      const hashed = Object.fromEntries(Object.entries(artifacts)
        .filter(([, p]) => p && fs.existsSync(p))
        .map(([k, p]) => [k, { path: path.relative(path.dirname(file), p), sha256: sha256File(p) }]));
      const failed = steps.filter((s) => s.status === 'FAIL').length;
      const doc = { ...meta, finishedAt: new Date().toISOString(), result: failed ? 'FAIL' : 'PASS', failed, steps, artifacts: hashed };
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, `${JSON.stringify(doc, null, 2)}\n`);
      return doc;
    },
  };
}
