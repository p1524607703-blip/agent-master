'use strict';
/**
 * 业务报告「按子商品」逐日导出（只读）
 *
 * 与 export_child.js 的区别:
 *   export_child.js        一次抓一整段区间 → 跨天聚合, CSV 无日期列, 不能做日级分析
 *   本脚本                  按天循环, 每天一份 CSV, 文件名带日期 → 真正的日级数据
 *
 * 日期口径: URL 的 fromDate/toDate 均含当天, 故单日 D 传 from=to=D（已实测证实）。
 * 产出: out/BR_child_<店铺>_daily_<YYYY-MM-DD>.csv   已存在则跳过（幂等, 可续跑）
 *
 * 用法:
 *   node export_child_daily.js --from 2026-08-01 --to 2026-09-17
 *   node export_child_daily.js --stores 川鹏2号 --from 2026-08-01 --to 2026-09-17
 *   node export_child_daily.js --force            # 已存在也重下
 */
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const CLI = process.env.ZINIAO_CLI || '/opt/homebrew/bin/ziniao-cli';
const DIR = __dirname;
const OUT = path.join(DIR, 'out');
const LOGDIR = path.join(DIR, 'logs');
const DL_ROOT = process.env.ZINIAO_DOWNLOAD_ROOT ||
  '/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser';

const REPORT_ID = 'DetailSalesTrafficByChildItem';
const BASE = 'https://sellercentral.amazon.com/gp/site-metrics/report.html#/report?id=102:';
const HOME_URL = 'https://sellercentral.amazon.com/home';

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

let LOG = [], LOGNAME = 'child_daily.log';
function log(s) { const line = `[${new Date().toISOString()}] ${s}`; LOG.push(line); console.log(s); }
function flush() {
  if (!fs.existsSync(LOGDIR)) fs.mkdirSync(LOGDIR, { recursive: true });
  fs.writeFileSync(path.join(LOGDIR, LOGNAME), LOG.join('\n') + '\n', 'utf8');
}

function addDays(iso, n) {
  const [y, m, d] = iso.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + n);
  return dt.toISOString().slice(0, 10);
}
function dayList(from, to) {
  const out = [];
  for (let d = from; d <= to; d = addDays(d, 1)) out.push(d);
  return out;
}

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
    if (r.code === 0) { const res = parse(r.out); if (res) return res; }
    await sleep(rand(3000, 6000));
  }
  return null;
}
async function visit(storeId, url) {
  const v = await runCli(['zclaw', 'invoke', 'visit_page', '--args',
    JSON.stringify({ storeId, url })], 90000);
  try { const o = JSON.parse(v.out); return o?.data?.data?.targetId || o?.data?.targetId || null; }
  catch (e) { return null; }
}

const READ_STATE = `(function(){try{
  var ps=document.querySelectorAll('kat-date-picker');var vals=[];
  for(var i=0;i<ps.length;i++){
    var p=ps[i],k=p.shadowRoot?p.shadowRoot.querySelector('kat-input'):null;
    var inp=k?(k.shadowRoot?k.shadowRoot.querySelector('input'):k):null;
    vals.push(inp&&inp.value?inp.value:p.getAttribute('value'));
  }
  var t=document.body.innerText||'';
  return JSON.stringify({status:'OK',pickers:vals,
    empty:/没有数据|无数据|No data|未找到/.test(t)});
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
async function waitDownload(dir, startTs, timeoutMs = 180000) {
  const t0 = Date.now();
  let last = -1, stable = 0, best = null;
  while (Date.now() - t0 < timeoutMs) {
    const done = listCsv(dir).filter(x => /\.csv$/i.test(x.f) && x.st.mtimeMs > startTs && x.st.size > 0);
    if (done.length) {
      done.sort((a, b) => b.st.mtimeMs - a.st.mtimeMs);
      const cur = done[0];
      if (cur.st.size === last) { stable++; if (stable >= 1) return cur; }
      else { stable = 0; last = cur.st.size; best = cur; }
    }
    await sleep(3500);
  }
  return best;
}

function urlFor(from, to) { return `${BASE}${REPORT_ID}&fromDate=${from}&toDate=${to}`; }

// 报告页是 SPA, 日期只体现在 URL 的 hash 上; 直接 visit_page 到只差 hash 的 URL
// 不会触发重新加载(实测 pickers 停在旧区间)。故这里改写 href 后强制 reload。
function navScript(url) {
  return `(function(){try{
    location.href=${JSON.stringify(url)};
    setTimeout(function(){try{location.reload();}catch(e){}},150);
    return JSON.stringify({status:'OK'});
  }catch(e){return JSON.stringify({status:'ERR',msg:String(e)});}})();`;
}

async function setDay(storeId, tid, d) {
  const want = d.replace(/-/g, '/');
  for (let attempt = 0; attempt < 3; attempt++) {
    await exec(storeId, tid, navScript(urlFor(d, d)), 'nav');
    for (let k = 0; k < 10; k++) {
      const st = await exec(storeId, tid, READ_STATE, 'state', 2);
      if (st && st.status === 'OK') {
        if (st.pickers[0] === want && st.pickers[1] === want) return { ok: true, st };
      }
      await sleep(rand(3000, 5000));
    }
  }
  return { ok: false, st: null };
}

async function runStore(store, days) {
  log(`\n########## ${store.name} — ${days.length} 天 ##########`);
  const dlDir = path.join(DL_ROOT, store.name);
  if (!fs.existsSync(dlDir)) { log(`   [失败] 无下载目录`); return { store: store.name, error: 'no dl dir' }; }

  const todo = days.filter(d => FORCE || !(() => {
    const p = path.join(OUT, `BR_child_${store.name}_daily_${d}.csv`);
    return fs.existsSync(p) && fs.statSync(p).size > 0;
  })());
  if (!todo.length) { log(`   全部已存在, 跳过`); return { store: store.name, skipped: days.length, ok: 0, fail: 0 }; }
  log(`   待抓 ${todo.length} 天（跳过已存在 ${days.length - todo.length} 天）`);

  let tid = await visit(store.id, urlFor(todo[0], todo[0]));
  if (!tid) {
    await runCli(['store', 'open', '--name', store.name, '--url', urlFor(todo[0], todo[0])], 60000);
    await visit(store.id, HOME_URL);
    await sleep(rand(4000, 6000));
    tid = await visit(store.id, urlFor(todo[0], todo[0]));
  }
  if (!tid) { log('   [失败] 打不开报告页'); return { store: store.name, error: 'open failed' }; }

  let ok = 0, fail = 0, empty = 0;
  for (let i = 0; i < todo.length; i++) {
    const d = todo[i];
    const outName = `BR_child_${store.name}_daily_${d}.csv`;
    const outPath = path.join(OUT, outName);
    const want = d.replace(/-/g, '/');
    try {
      if (i > 0) {
        const t2 = await visit(store.id, urlFor(d, d));
        if (t2) tid = t2;
      }
      const day = await setDay(store.id, tid, d);
      if (!day.ok) {
        log(`   [${i + 1}/${todo.length}] ${d}  ✗ 日期未生效 (pickers=${(day.st && day.st.pickers || []).join('~')})`);
        fail++; await sleep(rand(4000, 7000)); continue;
      }
      const startTs = Date.now() - 2000;
      const dl = await exec(store.id, tid, CLICK_DL, 'dl');
      if (!dl || dl.status !== 'OK') {
        log(`   [${i + 1}/${todo.length}] ${d}  ✗ 下载按钮失败`); fail++; continue;
      }
      const got = await waitDownload(dlDir, startTs);
      if (!got) { log(`   [${i + 1}/${todo.length}] ${d}  ✗ 等不到文件`); fail++; continue; }
      fs.renameSync(got.p, outPath);
      const raw = fs.readFileSync(outPath, 'utf8').replace(/^\uFEFF/, '');
      const lines = raw.split('\n').filter(l => l.trim());
      if (lines.length < 2 || !lines[0].includes('（子）ASIN')) {
        log(`   [${i + 1}/${todo.length}] ${d}  ⚠ 行数/表头异常 (${lines.length} 行)`); empty++;
      } else {
        log(`   [${i + 1}/${todo.length}] ${d}  ✓ ${lines.length - 1} 行 / ${(got.st.size / 1024).toFixed(0)} KB`);
      }
      ok++;
    } catch (e) {
      log(`   [${i + 1}/${todo.length}] ${d}  ✗ ${e.message}`); fail++;
    }
    flush();
    await sleep(rand(3000, 6000));
  }
  log(`  ${store.name} 完成: 成功 ${ok} / 失败 ${fail} / 异常 ${empty}`);
  return { store: store.name, ok, fail, empty };
}

(async () => {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  const days = dayList(FROM, TO);
  LOGNAME = `child_daily_${FROM}_${TO}.log`;
  const targets = STORES.filter(s => !only || only.includes(s.name));
  log(`报告=按子商品  店铺: ${targets.map(s => s.name).join(', ')}  区间 ${FROM}~${TO}  共 ${days.length} 天`);
  const res = [];
  for (const s of targets) {
    try { res.push(await runStore(s, days)); }
    catch (e) { log(`  [异常] ${s.name}: ${e.message}`); res.push({ store: s.name, error: String(e.message) }); }
    flush();
  }
  log('\n===== 汇总 =====');
  for (const r of res) log(`  ${r.store}: ${r.error ? 'FAIL ' + r.error : `成功 ${r.ok} / 失败 ${r.fail || 0}${r.skipped ? ` / 跳过 ${r.skipped}` : ''}`}`);
  flush();
  process.exit(0);
})().catch(e => { log('FATAL ' + e.stack); flush(); process.exit(9); });
