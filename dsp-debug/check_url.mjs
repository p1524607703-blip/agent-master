#!/usr/bin/env node
// 用一个一次性标签页逐个导航到目标 URL，读取 HTTP 状态码（不执行、不污染业务页）
// 用法: node check_url.mjs <cdpPort> <url1> <url2> ...
import fs from 'node:fs';
const [, , port, ...urls] = process.argv;
const base = 'http://127.0.0.1:' + port;

async function newTab() {
  const r = await fetch(base + '/json/new', { method: 'PUT' });
  return await r.json();
}
async function closeTab(id) {
  try { await fetch(base + '/json/close/' + id); } catch (e) {}
}

const results = [];

for (const url of urls) {
  const t = await newTab();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  let id = 1; const pend = new Map();
  const send = (m, p = {}) => new Promise((res) => { const i = id++; pend.set(i, res); ws.send(JSON.stringify({ id: i, method: m, params: p })); });
  const done = new Promise((resolve) => {
    ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); return; }
      const p = m.params || {};
      if (m.method === 'Network.responseReceived' && p.response && p.response.url === url) {
        resolve({ url, status: p.response.status, mime: p.response.mimeType, fromCache: p.response.fromDiskCache === true, encLen: (p.response.headers['content-length'] || p.response.headers['Content-Length'] || '') });
      }
      if (m.method === 'Network.loadingFailed' && p.type === 'Document') {
        resolve({ url, status: 'FAILED', error: p.errorText });
      }
    };
  });
  await new Promise((res) => { ws.onopen = () => res(); });
  await send('Network.enable');
  await send('Page.navigate', { url });
  const r = await Promise.race([done, new Promise(res => setTimeout(() => res({ url, status: 'TIMEOUT' }), 25000))]);
  results.push(r);
  ws.close();
  await closeTab(t.id);
}

console.log(JSON.stringify(results, null, 1));
fs.writeFileSync('./url_status.json', JSON.stringify(results, null, 1));
process.exit(0);
