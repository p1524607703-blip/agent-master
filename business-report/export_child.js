'use strict';
/**
 * 业务报告「详情页面销售和流量（按子商品）」批量区间导出（只读）
 *
 * 报告 id: 102:DetailSalesTrafficByChildItem
 * 日期口径: URL 的 fromDate / toDate 均为【含当天】, 故单日 D 传 from=to=D。
 *          （2026-09-18 实测证实: 09-10~09-11 = 09-10 单日 + 09-11 单日, 精确相等）
 *
 * 用法:
 *   node export_child.js                                  # 三店跑默认区间
 *   node export_child.js --from 2026-08-01 --to 2026-09-17
 *   node export_child.js --stores 川鹏2号,欧德思美站
 *   node export_child.js --force                          # 已存在也重下
 */
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const CLI = process.env.ZINIAO_CLI || '/opt/homebrew/bin/ziniao-cli';
const DIR = __dirname;
const OUT = path.join(DIR, 'out');
const DL_ROOT = process.env.ZINIAO_DOWNLOAD_ROOT ||
  '/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser';

const REPORT_ID = 'DetailSalesTrafficByChildItem';
const BASE = 'https://sellercentral.amazon.com/gp/site-metrics/report.html#/report?id=102:';

const STORES = [
  { name: '川鹏2号', id: '27661378824000' },
  { name: '欧德思美站', id: '16371114318833' },
  { name: '洁博利美站', id: '16468050574114' },
];

const argv = process.argv.slice(2);
const arg = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const has = k => argv.indexOf(k) >= 0;
const FROM = arg('--from', '2026-08-01');
const TO = arg('--to', '2026-09-17');
const FORCE = has('--force');
const only = arg('--stores') ? arg('--stores').split(',').map(s => s.trim()) : null;

const sleep = ms => new Promise(r => setTimeout(r, ms));
const rand = (a, b) => Math.floor(a + Math.random() * (b - a));
const log = s => console.log(s);

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
async function exec(storeId, tid, script, label, tries = 3) {
  for (let i = 0; i < tries; i++) {
    const r = await runCli(['page', 'exec', '--store-id', storeId, '--target-id', tid,
      '--script', script, '--timeout', '50000'], 70000);
    if (r.code === 0) { const res = parse(r.out); if (res) return res; log(`   [重试${i + 1}] ${label} 无法解析`); }
    else log(`   [重试${i + 1}] ${label} 失败: ${(r.err || r.out).slice(0, 140)}`);
    await sleep(rand(4000, 7000));
  }
  return null;
}

const READ_STATE = `(function(){try{
  var ps=document.querySelectorAll('kat-date-picker');var vals=[];
  for(var i=0;i<ps.length;i++){
    var p=ps[i],k=p.shadowRoot?p.shadowRoot.querySelector('kat-input'):null;
    var inp=k?(k.shadowRoot?k.shadowRoot.querySelector('input'):k):null;
    vals.push(inp&&inp.value?inp.value:p.getAttribute('value'));
  }
  var t=document.body.innerText||'';
  var m=t.match(/可能尚未完全提供自[^\\n]*/);
  return JSON.stringify({status:'OK',url:location.href,pickers:vals,
    hint:m?m[0].slice(0,70):'',empty:/没有数据|无数据|No data|未找到/.test(t),textLen:t.length});
}catch(e){return JSON.stringify({status:'ERR',msg:String(e)});}})();`;

const CLICK_DL = `(function(){try{
  var bs=document.querySelectorAll('kat-button');
  for(var i=0;i<bs.length;i++){var b=bs[i];
    if((b.getAttribute('label')||'')==='下载 (.csv)'){
      var inner=b.shadowRoot?(b.shadowRoot.querySelector('button')||b):b;
      inner.click();return JSON.stringify({status:'OK',disabled:!!inner.disabled});}}
  return JSON.stringify({status:'ERR',msg:'button not found'});
}catch(e){return JSON.stringify({status:'ERR',msg:String(e)});}})();`;

function listCsv(dir) {
  try {
    return fs.readdirSync(dir).filter(f => !/^\./.test(f))
      .map(f => ({ f, p: path.join(dir, f), st: fs.statSync(path.join(dir, f)) }));
  } catch (e) { return []; }
}
async function waitDownload(dir, startTs, timeoutMs) {
  const t0 = Date.now();
  let last = 0;
  while (Date.now() - t0 < timeoutMs) {
    const done = listCsv(dir).filter(x => /\.csv$/i.test(x.f) && x.st.mtimeMs > startTs && x.st.size > 0);
    if (done.length) {
      done.sort((a, b) => b.st.mtimeMs - a.st.mtimeMs);
      const cur = done[0];
      if (cur.st.size === last && cur.st.size > 0) return cur;
      last = cur.st.size;
    }
    await sleep(5000);
  }
  return null;
}

async function openReport(store, url) {
  await runCli(['store', 'open', '--name', store.name, '--url', url], 60000);
  await runCli(['zclaw', 'invoke', 'visit_page', '--args',
    JSON.stringify({ storeId: store.id, url: 'https://sellercentral.amazon.com/home' })], 90000);
  await sleep(rand(4000, 6000));
  for (let i = 0; i < 3; i++) {
    const v = await runCli(['zclaw', 'invoke', 'visit_page', '--args',
      JSON.stringify({ storeId: store.id, url })], 90000);
    let tid = null;
    try { const o = JSON.parse(v.out); tid = o?.data?.data?.targetId || o?.data?.targetId; } catch (e) {}
    if (tid) return tid;
    log(`   [重试${i + 1}] 打开报告页失败`);
    await sleep(rand(8000, 12000));
  }
  return null;
}

async function runStore(store, from, to) {
  const tag = `${store.name} ${from}~${to}`;
  log(`\n===== ${tag} [child] =====`);
  const stamp = `${from.replace(/-/g, '')}-${to.replace(/-/g, '')}`;
  const outName = `BR_child_${store.name}_${stamp}.csv`;
  const outPath = path.join(OUT, outName);
  if (fs.existsSync(outPath) && fs.statSync(outPath).size > 0 && !FORCE) {
    log(`   已存在, 跳过: ${outName}`);
    return { store: store.name, skipped: true, out: outPath };
  }

  const url = `${BASE}${REPORT_ID}&fromDate=${from}&toDate=${to}`;
  log(`1) 打开报告页\n   ${url}`);
  const tid = await openReport(store, url);
  if (!tid) return { store: store.name, error: 'open failed' };
  await sleep(rand(22000, 26000));

  log('2) 校验日期回读');
  const wantF = from.replace(/-/g, '/'), wantT = to.replace(/-/g, '/');
  let st = null, ok = false;
  for (let i = 0; i < 8; i++) {
    st = await exec(store.id, tid, READ_STATE, 'read_state', 2);
    if (st && st.status === 'OK') {
      ok = st.pickers[0] === wantF && st.pickers[1] === wantT;
      log(`   [${i + 1}] pickers=${(st.pickers || []).join('~')} dates=${ok ? 'OK' : 'MISMATCH'}`);
      if (st.hint) log(`        hint: ${st.hint}`);
      if (ok && i >= 1) break;
    } else log(`   [${i + 1}] read_state 失败`);
    await sleep(rand(7000, 10000));
  }
  if (!ok) {
    log(`   [警告] 日期回读 ${(st && st.pickers || []).join('~')}, 期望 ${wantF}~${wantT}`);
    return { store: store.name, error: 'date not applied', state: st };
  }

  const dlDir = path.join(DL_ROOT, store.name);
  if (!fs.existsSync(dlDir)) return { store: store.name, error: 'no download dir' };
  const startTs = Date.now() - 2000;

  log('3) 点击「下载 (.csv)」');
  const dl = await exec(store.id, tid, CLICK_DL, 'download');
  log('   ' + JSON.stringify(dl));
  if (!dl || dl.status !== 'OK') return { store: store.name, error: 'download click failed' };

  log('4) 等待落盘（大区间可能较慢）');
  const got = await waitDownload(dlDir, startTs, 420000);
  if (!got) return { store: store.name, error: 'download timeout' };
  log(`   捕获: ${got.f} (${(got.st.size / 1048576).toFixed(2)} MB)`);

  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  fs.renameSync(got.p, outPath);
  const buf = fs.readFileSync(outPath);
  const isXlsx = buf.slice(0, 2).toString('latin1') === 'PK';
  const raw = buf.toString('utf8').replace(/^\uFEFF/, '');
  const lines = raw.split('\n').filter(l => l.trim());
  const header = lines[0] || '';
  const warn = [];
  if (isXlsx) warn.push('实为 xlsx');
  if (lines.length < 2) warn.push('疑似空报表');
  if (!header.includes('（子）ASIN')) warn.push('表头缺少「（子）ASIN」列');
  log(`   已归档: ${outName} (${lines.length} 行含表头, ${(got.st.size / 1048576).toFixed(2)} MB)`);
  if (warn.length) log('   [警告] ' + warn.join('; '));
  return { store: store.name, out: outPath, rows: lines.length, bytes: got.st.size, isXlsx, warn, header };
}

(async () => {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  const targets = STORES.filter(s => !only || only.includes(s.name));
  if (!targets.length) { log('[配置] 无匹配店铺'); process.exit(10); }
  log(`报告=按子商品(${REPORT_ID})  区间 ${FROM} ~ ${TO}(含当天)  店铺: ${targets.map(s => s.name).join(', ')}`);

  const results = [];
  for (let i = 0; i < targets.length; i++) {
    if (i > 0) await sleep(rand(8000, 12000));
    try { results.push(await runStore(targets[i], FROM, TO)); }
    catch (e) { log(`   [异常] ${targets[i].name}: ${e.message}`); results.push({ store: targets[i].name, error: String(e.message) }); }
  }
  log('\n===== 汇总 =====');
  for (const r of results) {
    log(`  ${r.store}: ${r.error ? 'FAIL ' + r.error : (r.skipped ? 'SKIP' : `OK ${r.rows} 行 / ${(r.bytes / 1048576).toFixed(2)} MB`)}`);
  }
  const bad = results.filter(r => r.error).length;
  log(`成功 ${results.filter(r => !r.error && !r.skipped).length} / 跳过 ${results.filter(r => r.skipped).length} / 失败 ${bad}`);
  process.exit(bad ? 1 : 0);
})().catch(e => { log('FATAL ' + e.stack); process.exit(9); });
