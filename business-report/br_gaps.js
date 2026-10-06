'use strict';
/**
 * 业务报告「按子商品」日级文件对账（只读，不开浏览器）
 *
 * 回答一个问题: out/ 里到底缺哪几天?
 * br_pull.js 的补洞默认只看最近 30 天, 更早/更久的断档由本脚本兜底暴露。
 *
 * 用法:
 *   node br_gaps.js                       # 默认核对最近 60 天
 *   node br_gaps.js --days 90             # 核对最近 90 天
 *   node br_gaps.js --from 2026-08-01 --to 2026-09-19
 *   node br_gaps.js --stores 川鹏2号      # 只看指定店（逗号分隔）
 *   node br_gaps.js --fill                # 有洞就自动调 export_child_daily.js 补（需紫鸟在线）
 *   node br_gaps.js --min-bytes 1024      # 小于该字节数的文件视为残缺，同样算洞（默认 1024）
 *
 * 退出码: 0 = 无洞；1 = 有洞（便于自动化判断）；10 = 配置错误
 */
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const DIR = __dirname;
const OUT = path.join(DIR, 'out');
const STORES = ['川鹏2号', '欧德思美站', '洁博利美站'];

const argv = process.argv.slice(2);
const get = (k) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : null; };
const has = (k) => argv.indexOf(k) >= 0;

function addDays(iso, n) {
  const [y, m, d] = iso.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + n);
  return dt.toISOString().slice(0, 10);
}
function tzDate(tz) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date());
}
function range(from, to) {
  const out = [];
  for (let d = from; d <= to; d = addDays(d, 1)) out.push(d);
  return out;
}

if (!fs.existsSync(OUT)) { console.error('[配置] 找不到 out/ 目录: ' + OUT); process.exit(10); }

const usToday = tzDate('America/Los_Angeles');
const usYesterday = addDays(usToday, -1);
const days = get('--days') ? parseInt(get('--days'), 10) : 60;
const from = get('--from') || addDays(usYesterday, -(days - 1));
const to = get('--to') || usYesterday;
const minBytes = get('--min-bytes') ? parseInt(get('--min-bytes'), 10) : 1024;
const only = get('--stores') ? get('--stores').split(',').map(s => s.trim()) : null;
const stores = STORES.filter(s => !only || only.includes(s));
if (!stores.length) { console.error('[配置] 没有匹配的店铺: ' + (only || []).join(',')); process.exit(10); }

const dates = range(from, to);
console.log(`对账区间: ${from} ~ ${to}（${dates.length} 天，太平洋昨日=${usYesterday}）`);
console.log(`店铺: ${stores.join(' / ')}   残缺阈值: <${minBytes} B 视为无效\n`);

const gaps = {};
let totalGap = 0;
for (const s of stores) {
  const missing = [];
  for (const d of dates) {
    const p = path.join(OUT, `BR_child_${s.name || s}_daily_${d}.csv`);
    const pp = path.join(OUT, `BR_child_${s}_daily_${d}.csv`);
    const fp = fs.existsSync(pp) ? pp : p;
    if (!fs.existsSync(fp) || fs.statSync(fp).size < minBytes) missing.push(d);
  }
  gaps[s] = missing;
  totalGap += missing.length;
  const ok = dates.length - missing.length;
  console.log(`${s}: ${ok}/${dates.length} 天齐全` + (missing.length ? `，缺 ${missing.length} 天` : '  ✅'));
  if (missing.length) {
    // 连续区间折叠显示，别刷屏
    const segs = [];
    let st = missing[0], prev = missing[0];
    for (let i = 1; i < missing.length; i++) {
      if (addDays(prev, 1) === missing[i]) { prev = missing[i]; continue; }
      segs.push(st === prev ? st : `${st}~${prev}`);
      st = prev = missing[i];
    }
    segs.push(st === prev ? st : `${st}~${prev}`);
    console.log('   ↳ ' + segs.join(', '));
  }
}

console.log(`\n合计空洞: ${totalGap} 个（店铺 × 日期）`);
if (totalGap === 0) {
  console.log('✅ 无洞，数据连续。');
  process.exit(0);
}

if (has('--fill')) {
  console.log('\n--fill 已指定，开始调用 export_child_daily.js 补洞…');
  for (const s of stores) {
    if (!gaps[s].length) continue;
    const f = gaps[s][0], t = gaps[s][gaps[s].length - 1];
    console.log(`\n>>> ${s}: ${f} ~ ${t}（${gaps[s].length} 个缺口，脚本会跳过已存在的日期）`);
    const r = spawnSync(process.execPath,
      [path.join(DIR, 'export_child_daily.js'), '--stores', s, '--from', f, '--to', t],
      { stdio: 'inherit', cwd: DIR });
    if (r.status !== 0) console.log(`[!] ${s} 补洞退出码 ${r.status}`);
  }
  console.log('\n补洞完成，建议再跑一次 node br_gaps.js 复核。');
} else {
  console.log('提示: 加 --fill 可自动补齐（需紫鸟浏览器已启动且登录态正常）。');
  console.log('      或手动: node export_child_daily.js --stores <店> --from <起> --to <止>');
}
process.exit(1);
