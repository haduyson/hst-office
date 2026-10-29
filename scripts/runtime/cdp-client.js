// Minimal Chrome DevTools Protocol client for driving ONLYOFFICE Desktop
// Editors (CEF) started with --remote-debugging-port. Uses Node 22's global
// WebSocket so runtime QA needs no extra dependencies.

export async function listTargets(port) {
  const res = await fetch(`http://127.0.0.1:${port}/json/list`);
  return res.json();
}

/** Poll until a target whose URL matches `pattern` appears. */
export async function waitForTarget(port, pattern, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const found = (await listTargets(port)).find((t) => pattern.test(t.url));
      if (found) return found;
    } catch { /* debugger port not up yet */ }
    await sleep(500);
  }
  throw new Error(`CDP target ${pattern} not found within ${timeoutMs} ms`);
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Open a CDP session on one target; returns { send, evaluate, close }. */
export async function connect(target) {
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });
  let nextId = 1;
  const pending = new Map();
  ws.addEventListener('message', (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message));
      else resolve(msg.result);
    }
  });

  function send(method, params = {}) {
    const id = nextId++;
    ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
  }

  /** Evaluate an expression (awaiting promises) inside an optional execution context. */
  async function evaluate(expression, contextId) {
    const params = { expression, awaitPromise: true, returnByValue: true };
    if (contextId) params.contextId = contextId;
    const out = await send('Runtime.evaluate', params);
    if (out.exceptionDetails) {
      const detail = out.exceptionDetails.exception?.description || out.exceptionDetails.text;
      throw new Error(`Evaluation failed: ${detail}`);
    }
    return out.result.value;
  }

  return { send, evaluate, close: () => ws.close() };
}
