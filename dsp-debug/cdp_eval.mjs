#!/usr/bin/env node
// 直连 CDP 执行页面脚本（支持 awaitPromise）：
//   node cdp_eval.mjs <wsUrl> <scriptFile> [timeoutMs]
// 输出：第 1 行 JSON 元信息，第 2 行结果值
import fs from 'node:fs';

const [, , wsUrl, scriptFile, timeoutArg] = process.argv;
if (!wsUrl || !scriptFile) { console.error('usage: cdp_eval.mjs <wsUrl> <scriptFile> [timeoutMs]'); process.exit(2); }
const timeoutMs = parseInt(timeoutArg || '60000', 10);
const src = fs.readFileSync(scriptFile, 'utf8');

const ws = new WebSocket(wsUrl);
let done = false;
const finish = (c) => { if (!done) { done = true; try { ws.close(); } catch (e) {} process.exit(c); } };
const timer = setTimeout(() => { console.log(JSON.stringify({ ok: false, error: 'CLIENT_TIMEOUT' })); finish(3); }, timeoutMs + 5000);

ws.onopen = () => {
  ws.send(JSON.stringify({
    id: 1, method: 'Runtime.evaluate',
    params: { expression: src, awaitPromise: true, returnByValue: true, userGesture: false, timeout: timeoutMs }
  }));
};
ws.onmessage = (ev) => {
  let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
  if (m.id !== 1) return;
  clearTimeout(timer);
  if (m.error) { console.log(JSON.stringify({ ok: false, error: m.error })); finish(1); return; }
  const r = m.result || {};
  if (r.exceptionDetails) {
    console.log(JSON.stringify({ ok: false, exception: (r.exceptionDetails.exception && r.exceptionDetails.exception.description) || r.exceptionDetails.text }));
    finish(1); return;
  }
  const val = r.result ? r.result.value : null;
  console.log(JSON.stringify({ ok: true, type: r.result ? r.result.type : null }));
  console.log(typeof val === 'string' ? val : JSON.stringify(val));
  finish(0);
};
ws.onerror = (e) => { clearTimeout(timer); console.log(JSON.stringify({ ok: false, error: 'WSERR ' + ((e && e.message) || String(e)) })); finish(1); };
