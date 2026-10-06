#!/usr/bin/env node
// 重载页面，抓取所有 MFE 资源 URL（含 versionID），并把关键 chunk 的响应体落盘
// 用法: node fetch_chunks.mjs <wsUrl> <outPrefix>
import fs from 'node:fs';
const [, , wsUrl, outPrefix = './chunk'] = process.argv;

const ws = new WebSocket(wsUrl);
let nextId = 1;
const pending = new Map();
const send = (method, params = {}) => new Promise((res, rej) => {
  const id = nextId++;
  pending.set(id, { res, rej });
  ws.send(JSON.stringify({ id, method, params }));
});

const allUrls = new Map();   // requestId -> url
const byUrl = new Map();     // url -> requestId

const WANT = [
  'GeneralSectionV2.js',
  'orderMFEWebsiteVendors.chunk.js',
  'FrequencyGroupAssociationV1.js',
  'OrderFrequencyCapV1.js',
  'CampaignCommitmentsAssociationStandard.js'
];

ws.onopen = async () => {
  try {
    await send('Network.enable', { maxTotalBufferSize: 500000000, maxResourceBufferSize: 50000000 });
    await send('Page.enable');
    console.error('[reloading to capture bodies]');
    await send('Page.reload', { ignoreCache: false });
  } catch (e) { console.error('SETUP_ERR', e.message); process.exit(1); }
};

ws.onmessage = async (ev) => {
  let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
  if (m.id && pending.has(m.id)) {
    const p = pending.get(m.id);
    if (m.error) p.rej(new Error(JSON.stringify(m.error))); else p.res(m.result);
    pending.delete(m.id);
    return;
  }
  const p = m.params || {};
  if (m.method === 'Network.requestWillBeSent') {
    const u = p.request && p.request.url;
    if (u) { allUrls.set(p.requestId, u); byUrl.set(u, p.requestId); }
  }
};

setTimeout(async () => {
  const urls = [...allUrls.values()];
  const mfe = urls.filter(u => /orderMFE|versionID=|\/d16g|\/dsp\//i.test(u));

  const report = { totalRequests: urls.length, versionHistogram: {}, wantBodies: [], saved: [] };

  // 统计 versionID 分布
  for (const u of urls) {
    const m = u.match(/versionID=(\d+)/);
    if (m) {
      const host = (u.match(/^https?:\/\/([^/]+)/) || [])[1] || '?';
      const base = u.split('?')[0].split('/').pop();
      const key = host + '|' + m[1];
      report.versionHistogram[key] = report.versionHistogram[key] || [];
      if (report.versionHistogram[key].length < 40) report.versionHistogram[key].push(base);
    }
  }

  for (const w of WANT) {
    const u = urls.find(x => x.includes(w));
    if (!u) { report.wantBodies.push({ file: w, found: false }); continue; }
    const rid = byUrl.get(u);
    let bodyInfo = { file: w, url: u, found: true };
    try {
      const r = await send('Network.getResponseBody', { requestId: rid });
      const body = r.base64Encoded ? Buffer.from(r.body, 'base64').toString('utf8') : r.body;
      const out = outPrefix + '_' + w;
      fs.writeFileSync(out, body);
      bodyInfo.savedTo = out;
      bodyInfo.bytes = body.length;
      report.saved.push(out);
    } catch (e) {
      bodyInfo.bodyError = e.message;
    }
    report.wantBodies.push(bodyInfo);
  }

  report.mfeUrlsSample = mfe.slice(0, 60);
  fs.writeFileSync(outPrefix + '_chunks.json', JSON.stringify(report, null, 1));
  console.error('[written] ' + outPrefix + '_chunks.json saved=' + report.saved.length);
  process.exit(0);
}, 30000);
