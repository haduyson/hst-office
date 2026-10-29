// Unit tests for HST's own bridge logic. The editor is replaced by a minimal
// stand-in that only records calls; runtime behaviour against the real editor
// is covered by scripts/runtime/qa-*.js.
import assert from 'node:assert/strict';
import test from 'node:test';
import { classifyResult, isBusy, runCommand } from '../../extensions/shared/editor-bridge.js';

function installStandIn(behaviour) {
  const calls = [];
  globalThis.Asc = {
    scope: {},
    plugin: {
      callCommand(fn, isClose, isCalc, cb) {
        calls.push({ scope: { ...globalThis.Asc.scope }, isClose, isCalc });
        behaviour(cb);
      },
    },
  };
  return calls;
}

test('classifyResult distinguishes ok / error / unknown', () => {
  assert.deepEqual(classifyResult({ inserted: 3 }), { status: 'ok', result: { inserted: 3 } });
  assert.equal(classifyResult(undefined).status, 'unknown');
  assert.equal(classifyResult('text').status, 'unknown');
  const err = classifyResult({ error: 'boom', stage: 'insert', modified: true });
  assert.deepEqual(err, { status: 'error', error: 'insert: boom', partial: true });
  assert.equal(classifyResult({ error: 'x', stage: 'build', modified: false }).partial, false);
});

test('scope receives a JSON copy and the editor confirmation resolves ok', async () => {
  const calls = installStandIn((cb) => cb({ done: true }));
  const data = { layout: { blocks: [] }, when: new Date(0) };
  const out = await runCommand(() => {}, data);
  assert.equal(out.status, 'ok');
  assert.equal(calls.length, 1);
  assert.equal(typeof calls[0].scope.when, 'string', 'Date serialised to string, no live objects');
  assert.equal(calls[0].isClose, false);
});

test('no confirmation before timeout → unknown, never retried', async () => {
  const calls = installStandIn(() => {});
  const out = await runCommand(() => {}, {}, { timeoutMs: 20 });
  assert.equal(out.status, 'unknown');
  assert.equal(calls.length, 1);
  assert.equal(isBusy(), false);
});

test('second command while one is in flight is rejected as busy', async () => {
  let release;
  installStandIn((cb) => { release = () => cb({ ok: 1 }); });
  const first = runCommand(() => {}, {});
  assert.equal(isBusy(), true);
  assert.deepEqual(await runCommand(() => {}, {}), { status: 'busy' });
  release();
  assert.equal((await first).status, 'ok');
});

test('missing bridge → error without dispatch', async () => {
  delete globalThis.Asc;
  const out = await runCommand(() => {}, {});
  assert.equal(out.status, 'error');
});
