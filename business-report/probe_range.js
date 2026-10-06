'use strict';
/**
 * 只读探针：验证 Amazon 业务报告 URL 的 fromDate/toDate 到底是「左闭右开」还是「双闭」。
 * 用法:
 *   node probe_range.js --report parent --from 2026-09-17 --to 2026-09-17 --tag p_1day
 *   node probe_range.js --report child  --from 2026-09-17 --to 2026-09-18 --tag c_2day
 * 下载到的 CSV 会立刻搬到 /tmp/brprobe/ 下重命名, 避免污染 out/ 与店铺下载目录。
 */
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const CLI = process.env.ZINIAO_CLI || '/opt/homebrew/bin/ziniao-cli';
const DL_ROOT = '/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser';
const STORE = { name: '欧德思美站', id: '16371114318833' };
const DEST = '/tmp/brprobe';

const argv = process.argv.slice(2);
const arg = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const report = arg('--report', 'parent');
const from = arg('--from', '2026-09-17');
const to = arg('--to', '2026-09-17');
const tag = arg('--tag', 'probe');
const withCols = argv.includes('--cols');

const REP_ID = report === 'child' ? 'DetailSalesTrafficByChildItem' : 'DetailSalesTrafficByParentItem';
const COLS = '0%2F2%2F7%2F8%2F9%2F10%2F11%2F12%2F29%2F30%2F31%2F32%2F33%2F34%2F35%2F36';
const URL_ = `https://sellercentral.amazon.com/gp/site-metrics/report.html#/report?id=102:${REP_ID}`
  + `&fromDate=${from}&toDate=${to}` + (withCols ? `&columns=${COLS}` : '');

const sleep = ms => new Promise(r => setTimeout(r, ms));
const rand = (a, b) => Math.floor(a + Math.random() * (b - a));

function runCli(a, t = 90000) {
  return new Promise(res => {
    const cp = spawn(CLI, a, { timeout: t });
    let o = '', e = '';
    cp.stdout.on('data', d => o += d);
    cp.stderr.on('data', d => e += d);
    cp.on('close', c => res({ code: c, out: o, err: e }));
    cp.on('error', x => res({ code: -1, out: '', err: String(x) }));
  });
}
function parse(s) {
  try {
    const o = JSON.parse(s);
    const i = o?.data?.data?.result;
    if (typeof i === 'string') { const r = JSON.parse(i); if (r && r.status) return r; }
    if (i && i.status) return i;
    if (o?.status) return o;
  } catch (e) {}
  return null;
}
async function exec(tid, script, label, tries = 3) {
  for (let i = 0; i < tries; i++) {
    const r = await runCli(['page', 'exec', '--store-id', STORE.id, '--target-id', tid,
      '--script', script, '--timeout', '50000'], 70000);
    if (r.code === 0) {
      const res = parse(r.out);
      if (res) return res;
      console.log(`  [retry ${i + 1}] ${label} unparsable: ${r.out.slice(0, 120)}`);
    } else {
      console.log(`  [retry ${i + 1}] ${label} exec fail: ${(r.err || r.out).slice(0, 160)}`);
    }
    await sleep(rand(4000, 7000));
  }
  return null;
}

const STATE = `(function(){try{
  var ps=document.querySelectorAll('kat-date-picker');var vals=[];
  for(var i=0;i<ps.length;i++){
    var p=ps[i],k=p.shadowRoot?p.shadowRoot.querySelector('kat-input'):null;
    var inp=k?(k.shadowRoot?k.shadowRoot.querySelector('input'):k):null;
    vals.push(inp&&inp.value?inp.value:p.getAttribute('value'));
  }
  var ths=[];
  Array.prototype.forEach.call(document.querySelectorAll('th'),function(t){
    var s=(t.innerText||'').replace(/\\s+/g,' ').trim(); if(s) ths.push(s);
  });
  var t=document.body.innerText||'';
  var m=t.match(/可能尚未完全提供自[^\\n]*/);
  return JSON.stringify({status:'OK',url:location.href,pickers:vals,ths:ths,
    trCount:document.querySelectorAll('tbody tr').length,
    hint:m?m[0].slice(0,70):'',empty:/没有数据|无数据|No data|未找到/.test(t),textLen:t.length});
}catch(e){return JSON.stringify({status:'ERR',msg:String(e)});}})();`;

const CLICK = `(function(){try{
  var bs=document.querySelectorAll('kat-button');
  for(var i=0;i<bs.length;i++){var b=bs[i];
    if((b.getAttribute('label')||'')==='下载 (.csv)'){
      var inner=b.shadowRoot?(b.shadowRoot.querySelector('button')||b):b;
      inner.click();return JSON.stringify({status:'OK',disabled:!!inner.disabled});}}
  var l=[];for(var j=0;j<bs.length;j++)l.push(bs[j].getAttribute('label')||'');
  return JSON.stringify({status:'ERR',msg:'no dl button',labels:l});
}catch(e){return JSON.stringify({status:'ERR',msg:String(e)});}})();`;

function listCsv(dir) {
  try {
    return fs.readdirSync(dir).filter(f => !/^\./.test(f))
      .map(f => ({ f, p: path.join(dir, f), st: fs.statSync(path.join(dir, f)) }));
  } catch (e) { return []; }
}
async function waitDownload(dir, startTs, timeoutMs = 150000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const done = listCsv(dir).filter(x => /\.csv$/i.test(x.f) && x.st.mtimeMs > startTs && x.st.size > 0);
    if (done.length) { done.sort((a, b) => b.st.mtimeMs - a.st.mtimeMs); return done[0]; }
    await sleep(4000);
  }
  return null;
}

(async () => {
  if (!fs.existsSync(DEST)) fs.mkdirSync(DEST, { recursive: true });
  console.log(`报告=${report} (${REP_ID})  区间 ${from} ~ ${to}  cols=${withCols}`);
  console.log(`URL: ${URL_}\n`);

  await runCli(['store', 'open', '--name', STORE.name, '--url', URL_], 60000);
  await runCli(['zclaw', 'invoke', 'visit_page',
    '--args', JSON.stringify({ storeId: STORE.id, url: 'https://sellercentral.amazon.com/home' })], 90000);
  await sleep(rand(4000, 6000));

  let tid = null;
  for (let i = 0; i < 3 && !tid; i++) {
    const v = await runCli(['zclaw', 'invoke', 'visit_page',
      '--args', JSON.stringify({ storeId: STORE.id, url: URL_ })], 90000);
    try { const o = JSON.parse(v.out); tid = o?.data?.data?.targetId || o?.data?.targetId; } catch (e) {}
    if (!tid) { console.log(`  [retry ${i + 1}] open failed`); await sleep(rand(8000, 12000)); }
  }
  if (!tid) { console.log('[FAIL] 打不开报告页'); process.exit(1); }
  console.log(`targetId=${tid}`);
  await sleep(rand(20000, 24000));

  let st = null;
  for (let i = 0; i < 6; i++) {
    st = await exec(tid, STATE, 'state');
    if (st && st.status === 'OK') {
      console.log(`  [${i + 1}] pickers=${(st.pickers || []).join(' ~ ')}  tbodyRows=${st.trCount}  empty=${st.empty}  textLen=${st.textLen}`);
      if (st.ths && st.ths.length) console.log(`      表头(${st.ths.length}): ${st.ths.join(' | ')}`);
      if (st.hint) console.log(`      hint: ${st.hint}`);
      if (i >= 1) break;
    }
    await sleep(rand(7000, 10000));
  }

  const dlDir = path.join(DL_ROOT, STORE.name);
  if (!fs.existsSync(dlDir)) { console.log('[FAIL] 无下载目录 ' + dlDir); process.exit(1); }
  const startTs = Date.now() - 2000;
  const dl = await exec(tid, CLICK, 'download');
  console.log('  下载按钮:', JSON.stringify(dl));
  if (!dl || dl.status !== 'OK') { console.log('[FAIL] 点不到下载'); process.exit(1); }

  const got = await waitDownload(dlDir, startTs);
  if (!got) { console.log('[FAIL] 等不到 CSV'); process.exit(1); }
  await sleep(1500);
  const dst = path.join(DEST, `${tag}.csv`);
  fs.renameSync(got.p, dst);
  const raw = fs.readFileSync(dst, 'utf8').replace(/^\uFEFF/, '');
  const lines = raw.split('\n').filter(l => l.trim());
  console.log(`\n归档: ${dst}  (${lines.length} 行含表头, ${fs.statSync(dst).size} B)`);
  console.log('CSV 表头: ' + (lines[0] || '').slice(0, 400));
  fs.writeFileSync(path.join(DEST, `${tag}.state.json`), JSON.stringify(st, null, 2));
})().catch(e => { console.log('FATAL', e.stack); process.exit(9); });
