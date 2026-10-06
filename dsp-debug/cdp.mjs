#!/usr/bin/env node
// 极简 CDP 客户端：cdp.mjs <wsUrl> <method> [paramsJson] [--wait ms]
// 打印一行 JSON 结果；对 Page.captureScreenshot 会额外把 base64 写到 stdout 第二行
const argc = process.argv.slice(2);
const wsUrl = argc[0];
const method = argc[1];
let params = {};
let waitMs = 20000;
for (let i = 2; i < argc; i++) {
  if (argc[i] === '--wait') { waitMs = parseInt(argc[i + 1], 10); i++; }
  else if (!params.__set) { try { params = JSON.parse(argc[i]); params.__set = undefined; delete params.__set; } catch (e) { params = {}; } }
}
if (!wsUrl || !method) { console.error('usage: cdp.mjs <wsUrl> <method> [paramsJson] [--wait ms]'); process.exit(2); }

const ws = new WebSocket(wsUrl);
let done = false;
const finish = (code) => { if (!done) { done = true; try { ws.close(); } catch (e) {} process.exit(code); } };
const timer = setTimeout(() => { console.error('TIMEOUT'); finish(3); }, waitMs);

ws.onopen = () => { ws.send(JSON.stringify({ id: 1, method, params })); };
ws.onmessage = (ev) => {
  let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
  if (m.id !== 1) return;
  clearTimeout(timer);
  if (m.error) { console.log(JSON.stringify({ ok: false, error: m.error })); finish(1); }
  else {
    const r = m.result || {};
    if (r.data && typeof r.data === 'string') {
      const meta = { ...r }; delete meta.data;
      console.log(JSON.stringify({ ok: true, result: meta }));
      console.log(r.data);
    } else {
      console.log(JSON.stringify({ ok: true, result: r }));
    }
    finish(0);
  }
};
ws.onerror = (e) => { clearTimeout(timer); console.error('WSERR', (e && e.message) || String(e)); finish(1); };
