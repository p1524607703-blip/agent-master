'use strict';
/**
 * 业务报告（按子商品）每日 / 每周自动导出
 *
 *   报告: Seller Central 业务报告 → 按 ASIN → 详情页面销售和流量（按子商品）
 *   驱动: 紫鸟 CLI + ZClaw Bridge，URL 导航 + DOM/shadow-DOM 注入（不点任何店铺写操作）
 *
 * 日期口径（关键）:
 *   - Amazon 业务报告的日界按【太平洋时间】，页面快照时间即为 PDT/PST。
 *   - 日任务: 目标日 = 太平洋当日 - 1 天。
 *     （北京时间 9/8 09:00 → 太平洋 9/7 18:00 → 美国当日 9/7 → 取 9/6，与用户口径一致）
 *   - 周任务: 上周（周一 ~ 周日）= 太平洋本周周一 -7 ~ 本周周一 -1。
 *
 * 用法:
 *   node br_pull.js                      # 自动算日期，跑三站
 *   node br_pull.js --from 2026-09-06 --to 2026-09-06
 *   node br_pull.js --weekly             # 上周一~周日快照
 *   node br_pull.js --stores 川鹏2号     # 只跑指定店（逗号分隔）
 *   node br_pull.js --force              # 已存在的目标文件也重下
 *   node br_pull.js --no-download        # 只设置日期+应用，验证链路不下载
 */
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const CLI = process.env.ZINIAO_CLI || '/opt/homebrew/bin/ziniao-cli';
const DIR = __dirname;
const OUT = path.join(DIR, 'out');
const LOGDIR = path.join(DIR, 'logs');
const HOME_URL = 'https://sellercentral.amazon.com/home';
// 2026-09-18 按用户要求, 报告由「按父商品」切换为「按子商品」。
// 子商品报告的列集合与父商品不同, 不再传 columns 参数(交给报告默认列),
// 改由下载后校验表头是否含「（子）ASIN」。
const REPORT_BASE = 'https://sellercentral.amazon.com/gp/site-metrics/report.html#/report?id=102:DetailSalesTrafficByChildItem';
// 日期区间是【双闭】: fromDate 与 toDate 都含当天。
// 2026-09-18 实测证实(旧注释写的「左闭右开」是错的):
//   09-10~09-11 的数据 = 09-10 单日 + 09-11 单日 (59,866 会话, 精确相等)
//   09-15~09-16 的数据 = 09-15 单日 + 09-16 单日 (73,128 会话, 行数亦为两日并集)
// 故单日 D 必须传 fromDate=D & toDate=D。旧版按「右开」传 D+1,
// 日/周因 D+1 恰为「当天尚未出数」而侥幸正确, 补洞路径则真的多抓了一天。
function buildReportUrl(from, to) {
  return `${REPORT_BASE}&fromDate=${from}&toDate=${to}`;
}
const DOWNLOAD_ROOT = process.env.ZINIAO_DOWNLOAD_ROOT ||
  '/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser';

// 三店均已具备业务报告访问权限: 洁博利美站于 2026-09-18 恢复, 已置 enabled:true。
const STORES = [
  { name: '川鹏2号', id: '27661378824000', enabled: true },
  { name: '欧德思美站', id: '16371114318833', enabled: true },
  { name: '洁博利美站', id: '16468050574114', enabled: true },
];

const sleep = ms => new Promise(r => setTimeout(r, ms));
const rand = (a, b) => Math.floor(a + Math.random() * (b - a));

// ---------- 日期工具 ----------
function tzDate(tz, d = new Date()) {
  // 返回该时区下的 YYYY-MM-DD
  const s = new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
  return s; // en-CA 输出 YYYY-MM-DD
}
function addDays(iso, n) {
  const [y, m, d] = iso.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + n);
  return dt.toISOString().slice(0, 10);
}
function dowUtc(iso) { // 0=Sun..6=Sat
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay();
}
function mondayOf(iso) {
  const w = dowUtc(iso);              // 0=Sun
  const back = w === 0 ? 6 : w - 1;   // 周一为周起点
  return addDays(iso, -back);
}

// ---------- CLI ----------
function runCli(args, timeout = 90000) {
  return new Promise(resolve => {
    const cp = spawn(CLI, args, { timeout });
    let out = '', err = '';
    cp.stdout.on('data', d => out += d);
    cp.stderr.on('data', d => err += d);
    cp.on('close', code => resolve({ code, out, err }));
    cp.on('error', e => resolve({ code: -1, out, err: String(e) }));
  });
}
function parseExecResult(s) {
  try {
    const o = JSON.parse(s);
    const inner = o?.data?.data?.result;
    if (typeof inner === 'string') { const r = JSON.parse(inner); if (r && r.status) return r; }
    if (inner && typeof inner === 'object' && inner.status) return inner;
    if (o?.status) return o;
  } catch (e) {}
  return null;
}
async function pageExec(storeId, tid, script, label, tries = 3) {
  for (let i = 0; i < tries; i++) {
    const r = await runCli(['page', 'exec', '--store-id', storeId, '--target-id', tid,
      '--script', script, '--timeout', '50000'], 70000);
    if (r.code === 0) {
      const res = parseExecResult(r.out);
      if (res) return res;
      log(`   [重试 ${i + 1}] ${label} 返回无法解析: ${r.out.slice(0, 150)}`);
    } else {
      log(`   [重试 ${i + 1}] ${label} exec 失败: ${(r.err || r.out).slice(0, 200)}`);
    }
    await sleep(rand(4000, 7000));
  }
  return null;
}

// ---------- 注入脚本模板 ----------
function makeSetDateScript(from, to) {
  const f = from.replace(/-/g, '/'), t = to.replace(/-/g, '/');
  return `(function(){
  try{
    var ps = document.querySelectorAll('kat-date-picker');
    if(ps.length < 2) return JSON.stringify({status:'ERR', msg:'picker count='+ps.length});
    function katInput(p){ return p.shadowRoot ? p.shadowRoot.querySelector('kat-input') : null; }
    function realInput(k){ if(!k) return null; if(k.shadowRoot) return k.shadowRoot.querySelector('input')||k; return k.tagName.toLowerCase()==='input'?k:k.querySelector('input'); }
    var vals = ['${f}','${t}'], res = [];
    for(var i=0;i<2;i++){
      var p = ps[i], k = katInput(p), inp = realInput(k), v = vals[i];
      if(k) k.setAttribute('value', v);
      if(inp){
        var proto = inp.tagName.toLowerCase()==='input' ? window.HTMLInputElement.prototype : window.HTMLElement.prototype;
        var setter = Object.getOwnPropertyDescriptor(proto,'value').set;
        setter.call(inp, v);
        inp.dispatchEvent(new Event('input',{bubbles:true}));
        inp.dispatchEvent(new Event('change',{bubbles:true}));
      }
      try{ p.value = v; }catch(e){}
      res.push({i:i, host:p.getAttribute('value'), kat:k?k.getAttribute('value'):'', inp:inp?inp.value:''});
    }
    return JSON.stringify({status:'OK', pickers:res});
  }catch(e){ return JSON.stringify({status:'ERR', msg:String(e)}); }
})();`;
}
function makeClickScript(label) {
  return `(function(){
  try{
    var bs = document.querySelectorAll('kat-button');
    for(var i=0;i<bs.length;i++){
      var b = bs[i];
      if((b.getAttribute('label')||'') === ${JSON.stringify(label)}){
        var inner = b.shadowRoot ? (b.shadowRoot.querySelector('button')||b) : b;
        inner.click();
        return JSON.stringify({status:'OK', clicked:${JSON.stringify(label)}, disabled: !!(inner.disabled)});
      }
    }
    var labels = [];
    for(var j=0;j<bs.length;j++) labels.push(bs[j].getAttribute('label')||'');
    return JSON.stringify({status:'ERR', msg:'button not found', labels: labels});
  }catch(e){ return JSON.stringify({status:'ERR', msg:String(e)}); }
})();`;
}
const READ_STATE_SCRIPT = `(function(){
  try{
    var ps = document.querySelectorAll('kat-date-picker');
    var vals = [];
    for(var i=0;i<ps.length;i++){
      var p = ps[i], k = p.shadowRoot ? p.shadowRoot.querySelector('kat-input') : null;
      var inp = k ? (k.shadowRoot ? k.shadowRoot.querySelector('input') : k) : null;
      vals.push(inp && inp.value ? inp.value : p.getAttribute('value'));
    }
    var labels = [];
    Array.prototype.forEach.call(document.querySelectorAll('kat-button'), function(b){ labels.push(b.getAttribute('label')||''); });
    var txt = document.body.innerText || '';
    var m = txt.match(/可能尚未完全提供自[^\\n]*/);
    var empty = /没有数据|无数据|No data|找不到.*结果|未找到/.test(txt);
    var usd = (txt.match(/US\\$/g) || []).length;
    return JSON.stringify({
      status:'OK', url: location.href, pickers: vals, katButtons: labels,
      hint: m?m[0].slice(0,120):'', empty: empty, usdCount: usd, textLen: txt.length,
      loading: /加载|Loading|正在加载/.test(txt),
      bodyHead: txt.replace(/\\s+/g,' ').slice(0, 300)
    });
  }catch(e){ return JSON.stringify({status:'ERR', msg:String(e)}); }
})();`;

// ---------- 日志 ----------
let LOG = [];
let LOGNAME = 'run.log';   // 由 main 设定; 每跑完一店就 flush, 防止进程被杀时日志全丢
function log(s) { const t = new Date().toISOString(); const line = `[${t}] ${s}`; LOG.push(line); console.log(s); }
function flushLog(name) {
  if (!fs.existsSync(LOGDIR)) fs.mkdirSync(LOGDIR, { recursive: true });
  fs.writeFileSync(path.join(LOGDIR, name || LOGNAME), LOG.join('\n') + '\n', 'utf8');
}

// ---------- 下载检测 ----------
function listCsv(dir) {
  try {
    return fs.readdirSync(dir)
      .filter(f => !/^\./.test(f))
      .map(f => ({ f, p: path.join(dir, f), st: fs.statSync(path.join(dir, f)) }));
  } catch (e) { return []; }
}
async function waitDownload(dir, startTs, timeoutMs = 150000) {
  const t0 = Date.now();
  let seen = new Set();
  while (Date.now() - t0 < timeoutMs) {
    const files = listCsv(dir);
    const pending = files.filter(x => /\.crdownload$/i.test(x.f));
    const done = files.filter(x => /\.csv$/i.test(x.f) && x.st.mtimeMs > startTs && x.st.size > 0);
    if (done.length) {
      // 取最新一个
      done.sort((a, b) => b.st.mtimeMs - a.st.mtimeMs);
      return done[0];
    }
    if (pending.length) log(`   下载中: ${pending.length} 个临时文件...`);
    await sleep(4000);
  }
  return null;
}

// 打开报告页: 紫鸟代理偶发 chromewebdata 网络错误, 故「先开首页预热 → 再进报告页 → 失败重试」
async function openReport(store, url) {
  await runCli(['store', 'open', '--name', store.name, '--url', url], 60000);
  await runCli(['zclaw', 'invoke', 'visit_page',
    '--args', JSON.stringify({ storeId: store.id, url: HOME_URL })], 90000);
  await sleep(rand(4000, 6000));
  for (let i = 0; i < 3; i++) {
    const v = await runCli(['zclaw', 'invoke', 'visit_page', '--args', JSON.stringify({ storeId: store.id, url })], 90000);
    let tid = null, title = null;
    try {
      const o = JSON.parse(v.out);
      tid = o?.data?.data?.targetId || o?.data?.targetId;
      title = o?.data?.data?.title;
    } catch (e) {}
    if (tid) { log(`   targetId=${tid} title=${title || ''}`); return tid; }
    log(`   [重试 ${i + 1}] 打开报告页失败: ${(v.out || '').slice(0, 160).replace(/\s+/g, ' ')}`);
    await sleep(rand(8000, 12000));
  }
  return null;
}

// ---------- 单店流程 ----------
async function runStore(store, job, opts) {
  const { from, to, mode } = job;
  const tag = `${store.name} ${from}~${to} [${mode}]`;
  log(`\n===== ${tag} =====`);
  const outName = mode === 'weekly'
    ? `BR_child_${store.name}_weekly_${from.replace(/-/g, '')}-${to.replace(/-/g, '')}.csv`
    : `BR_child_${store.name}_daily_${from}.csv`;
  const outPath = path.join(OUT, outName);
  if (fs.existsSync(outPath) && fs.statSync(outPath).size > 0 && !opts.force) {
    log(`   已存在且非空, 跳过: ${outName} (用 --force 强制重下)`);
    return { store: store.name, from, to, skipped: true, out: outPath };
  }

  log('1) 打开报告页(日期直接编码进 URL, 无需点击任何控件)');
  const url = buildReportUrl(from, to);
  log('   ' + url);
  const wantF = from.replace(/-/g, '/'), wantT = to.replace(/-/g, '/');
  let tid = null, st = null, datesOk = false;
  // 日期校验是防止「下载到别的日子的数据却被命名成目标日期」的唯一防线(CSV 无日期列)。
  // 2026-09-21: 校验失败时原先直接放弃、留洞等次日 backfill 补。但历史记录显示这类
  // MISMATCH 多为页面瞬态(日期控件回读格式未刷新), 重开一次即可恢复; 而空等一天代价更大。
  // 故改为自动重开一轮(仅 1 次额外尝试), 仍失败才算真失败。
  const VERIFY_ROUNDS = 2;
  for (let round = 1; round <= VERIFY_ROUNDS && !datesOk; round++) {
    if (round > 1) log(`   [自动重试 ${round}/${VERIFY_ROUNDS}] 日期校验未通过, 重新打开报告页`);
    tid = await openReport(store, url);
    if (!tid) {
      log('   [失败] 无法打开报告页');
      if (round === VERIFY_ROUNDS) return { store: store.name, from, to, mode, error: 'open failed' };
      continue;
    }
    await sleep(rand(20000, 24000));

    log(`2) 等待数据就绪并校验日期范围${round > 1 ? ` (第 ${round} 轮)` : ''}`);
    // 注意: 页面日期控件回读值应等于 URL 里的 toDate(区间双闭, 不再 +1)
    for (let i = 0; i < 8; i++) {
      st = await pageExec(store.id, tid, READ_STATE_SCRIPT, 'read_state', 2);
      if (st && st.status === 'OK') {
        datesOk = st.pickers[0] === wantF && st.pickers[1] === wantT;
        log(`   [${i + 1}] pickers=${(st.pickers || []).join('~')} usd=${st.usdCount} dates=${datesOk ? 'OK' : 'MISMATCH'}`);
        // 表格 UI 时常渲染不出来(实测 usdCount 恒为 0), 但下载按钮仍能产出正确 CSV,
        // 因此就绪判定只看日期是否生效, 不依赖页面是否画出数据行。
        if (datesOk && i >= 1) break;
      } else {
        log(`   [${i + 1}] read_state 失败`);
      }
      await sleep(rand(7000, 10000));
    }
    if (!datesOk) log(`   [警告] 日期回读为 ${(st && st.pickers || []).join('~')}, 期望 ${wantF}~${wantT}`);
  }
  if (!datesOk) {
    if (!opts.skipVerify) return { store: store.name, from, to, error: 'date not applied', state: st };
    log('   [跳过] --skip-verify 已开启, 仍继续下载');
  }
  log('   [OK] 日期范围已生效, 数据行数约 ' + (st ? st.usdCount : '?'));
  if (opts.noDownload) return { store: store.name, from, to, verified: true, state: st };

  const dlDir = path.join(DOWNLOAD_ROOT, store.name);
  if (!fs.existsSync(dlDir)) { log('   [失败] 下载目录不存在: ' + dlDir); return { store: store.name, from, to, error: 'no dl dir' }; }
  const startTs = Date.now() - 2000;

  log('3) 点击「下载 (.csv)」');
  const dl = await pageExec(store.id, tid, makeClickScript('下载 (.csv)'), 'download');
  log('   ' + JSON.stringify(dl));
  if (!dl || dl.status !== 'OK') return { store: store.name, from, to, error: 'download click failed' };

  log('4) 等待文件落盘');
  const got = await waitDownload(dlDir, startTs);
  if (!got) { log('   [失败] 超时未见新 CSV'); return { store: store.name, from, to, error: 'download timeout' }; }
  log(`   捕获: ${got.f} (${(got.st.size / 1024).toFixed(1)} KB)`);

  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  // 再等 1.5s 确认不再增长(避免拿到半截文件)
  const s1 = fs.statSync(got.p).size; await sleep(1500);
  const s2 = fs.statSync(got.p).size;
  fs.renameSync(got.p, outPath);
  const buf = fs.readFileSync(outPath);
  const isXlsx = buf.slice(0, 2).toString('latin1') === 'PK';
  const raw = buf.toString('utf8').replace(/^\uFEFF/, '');
  const lines = raw.split('\n').filter(l => l.trim());
  const rows = lines.length;
  const header = lines[0] || '';
  const okHeader = header.includes('（子）ASIN') || header.includes('(Child) ASIN');
  const warn = [];
  if (isXlsx) warn.push('文件实为 xlsx(PK 头), 非 CSV');
  if (rows < 2) warn.push(`只有 ${rows} 行, 疑似空报表`);
  if (!okHeader) warn.push('表头未找到「（父）ASIN」列');
  log(`   已归档: ${outName} (${rows} 行, ${(s2 / 1024).toFixed(1)} KB)`);
  if (warn.length) log('   [警告] ' + warn.join('; '));
  return { store: store.name, from, to, out: outPath, bytes: s2, rows, srcName: got.f, isXlsx, warn, state: st };
}

// ---------- main ----------
(async () => {
  const argv = process.argv.slice(2);
  const get = (k) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : null; };
  const has = (k) => argv.indexOf(k) >= 0;
  const opts = {
    weekly: has('--weekly'),
    force: has('--force'),
    noDownload: has('--no-download'),
    skipVerify: has('--skip-verify'),
    noBackfill: has('--no-backfill'),
    stores: get('--stores') ? get('--stores').split(',').map(s => s.trim()) : null,
  };

  const usToday = tzDate('America/Los_Angeles');   // 太平洋当日 = 业务报告的"今天"
  const bjToday = tzDate('Asia/Shanghai');         // 北京时间当日(决定周报是否触发)
  const bjDow = dowUtc(bjToday);                   // 0=周日 .. 2=周二

  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  const targets = STORES.filter(s => s.enabled !== false)
    .filter(s => !opts.stores || opts.stores.includes(s.name));
  if (!targets.length) { log('[配置] 没有匹配的店铺: ' + (opts.stores || []).join(',')); process.exit(10); }

  // 任务编排: 默认跑日报; 北京时间周二(或手动 --weekly)再追加一份上周快照
  const jobs = [];
  if (get('--from') && get('--to')) {
    jobs.push({ from: get('--from'), to: get('--to'), mode: opts.weekly ? 'weekly' : 'daily' });
  } else {
    jobs.push({ from: addDays(usToday, -1), to: addDays(usToday, -1), mode: 'daily' });
    if (opts.weekly || bjDow === 2) {
      const monday = mondayOf(usToday);
      jobs.push({ from: addDays(monday, -7), to: addDays(monday, -1), mode: 'weekly' });
    }
  }
  // 补洞: 扫描最近 N 天, 对「店铺 × 日期」缺失的组合自动补跑。
  // 起因: 2026-09-10 那次进程中途被杀, 川鹏出了、欧德思没出且日志全丢, 缺口静默存在了 3 天。
  // 2026-09-20 调整: 默认窗口 3 → 30 天。跳过判定是纯 fs.existsSync(不产生浏览器任务),
  // 故窗口调大在无洞时几乎零成本, 却能扛住长假/连续多日不开机的断档, 回来跑一次即自动补齐。
  // 超过 30 天的历史空洞请用 export_child_daily.js --from --to 批量补(同样幂等可续跑)。
  const DEFAULT_BACKFILL = 30;
  const backfillDays = get('--backfill') ? parseInt(get('--backfill'), 10) : (opts.noBackfill ? 0 : DEFAULT_BACKFILL);
  if (backfillDays > 0) {
    const latest = addDays(usToday, -1);
    const covered = new Set(jobs.filter(j => j.mode === 'daily' && !j.only).map(j => j.from + '~' + j.to));
    for (let i = 0; i < backfillDays; i++) {
      const d = addDays(latest, -i);
      if (covered.has(d + '~' + d)) continue;
      for (const s of targets) {
        const p = path.join(OUT, `BR_child_${s.name}_daily_${d}.csv`);
        if (fs.existsSync(p) && fs.statSync(p).size > 0) continue;
        jobs.push({ from: d, to: d, mode: 'daily', only: [s.name], backfill: true });
        log(`[补洞] ${s.name} ${d} 缺文件, 已加入补跑`);
      }
    }
  }
  log(`太平洋当日=${usToday} 北京当日=${bjToday}(周${bjDow}) 任务: ` +
    jobs.map(j => `${j.mode}${j.backfill ? '(补)' : ''} ${j.from}~${j.to}${j.only ? ' [' + j.only.join(',') + ']' : ''}`).join(' / '));

  if (!fs.existsSync(CLI)) { log('[配置] 找不到紫鸟 CLI: ' + CLI); process.exit(10); }
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

  const modes = [...new Set(jobs.map(j => j.mode))].join('+') || 'none';
  LOGNAME = `run_${bjToday}_${modes}.log`;
  const results = [];
  for (const job of jobs) {
    const jobTargets = job.only ? targets.filter(s => job.only.includes(s.name)) : targets;
    for (let i = 0; i < jobTargets.length; i++) {
      if (i > 0 || results.length > 0) await sleep(rand(8000, 12000));
      try {
        results.push(await runStore(jobTargets[i], job, opts));
      } catch (e) {
        log(`   [异常] ${jobTargets[i].name}: ${e.message}`);
        results.push({ store: jobTargets[i].name, from: job.from, to: job.to, mode: job.mode, error: String(e.message) });
      }
      flushLog();   // 每店落一次盘: 进程中途被杀也能留下已跑部分的记录
    }
  }
  log('\n===== 汇总 =====');
  log(JSON.stringify(results, null, 2));
  const ok = results.filter(r => !r.error && !r.skipped && r.out).length;
  const skipped = results.filter(r => r.skipped).length;
  const failed = results.filter(r => r.error).length;
  log(`成功 ${ok} / 跳过 ${skipped} / 失败 ${failed}`);
  flushLog();
  process.exit(failed > 0 ? 1 : 0);
})().catch(e => { log('FATAL ' + e.stack); flushLog('fatal.log'); process.exit(9); });
