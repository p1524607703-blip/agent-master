'use strict';
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const requireConfig = require('./config');

const cfg = requireConfig();
const CLI = cfg.cliPath;
const DIR = __dirname;
const OUT = path.join(DIR, 'out');
let PROMO_CSV = path.join(OUT, 'promotions.csv');
// raw 多行 SKU（每促销所有 SKU）写到 .raw.csv，避免覆盖后处理产出的 4 列交付物 promotion_skus.csv
let SKU_CSV = path.join(OUT, 'promotion_skus.raw.csv');

const sleep = ms => new Promise(r => setTimeout(r, ms));
const rand = (a, b) => Math.floor(a + Math.random() * (b - a));

// ---- CSV 工具 ----
const PROMO_HEADER = ['促销ID', '促销编号', '类型', '状态', '开始日期', '结束日期', '商城', '费用', 'SKU数量', 'SKU前缀列表'];
const SKU_HEADER = ['促销ID', '促销编号', 'SKU', 'SKU前缀'];
function esc(c) { return '"' + String(c == null ? '' : c).replace(/"/g, '""') + '"'; }
function ensureHeader(p, header) {
  if (!fs.existsSync(p)) fs.writeFileSync(p, header.map(esc).join(',') + '\n', 'utf8');
}
function appendRow(p, cells) { fs.appendFileSync(p, cells.map(esc).join(',') + '\n', 'utf8'); }
function prefixOf(sku) {
  const parts = String(sku).split('-');
  return parts.slice(0, 2).join('-');
}

// ---- CLI 调用 ----
function runCli(args, timeout = 60000) {
  return new Promise(resolve => {
    const cp = spawn(CLI, args, { timeout });
    let out = '', err = '';
    cp.stdout.on('data', d => out += d);
    cp.stderr.on('data', d => err += d);
    cp.on('close', code => resolve({ code, out, err }));
    cp.on('error', e => resolve({ code: -1, out, err: String(e) }));
  });
}
function parseTargetId(out) {
  try { const o = JSON.parse(out); return o?.data?.data?.targetId || o?.data?.targetId || null; } catch (e) { return null; }
}
function parseExecResult(s) {
  try {
    const o = JSON.parse(s);
    const inner = o?.data?.data?.result;
    if (typeof inner === 'string') { const r = JSON.parse(inner); if (r && typeof r === 'object') return r; }
    if (o?.data?.data && typeof o.data.data === 'object') return o.data.data;
    if (o?.status) return o;
  } catch (e) {}
  return null;
}
async function pageExec(tid, scriptFile, timeout = 30000) {
  const script = fs.readFileSync(scriptFile, 'utf8');
  const r = await runCli(['page', 'exec', '--store-id', cfg.storeId, '--target-id', tid, '--script', script, '--timeout', String(timeout)], timeout + 5000);
  if (r.code !== 0) { console.error('  page exec failed:', r.err.slice(0, 200)); return null; }
  return parseExecResult(r.out);
}
async function visitPage(url, tries = 3) {
  for (let i = 0; i < tries; i++) {
    const v = await runCli(['zclaw', 'invoke', 'visit_page', '--args', JSON.stringify({ storeId: cfg.storeId, url })], 60000);
    const tid = parseTargetId(v.out);
    if (tid) return tid;
    console.error(`  visit_page 重试 ${i + 1}/${tries} ...`);
    await sleep(3000);
  }
  throw new Error('visit_page 失败，放弃');
}

// 提取单个促销详情：轮询等商品表渲染 + 多页累加 SKU
// 详情页商品表是 ag-Grid 且异步渲染，单次快照会残缺；故由 Node 侧轮询并翻页。
async function extractPromo(tid) {
  let det = null;
  for (let i = 0; i < 12; i++) {
    const d = await pageExec(tid, path.join(DIR, 'extract_detail.js'));
    if (d && d.promo) {
      det = d;
      if ((d.skus || []).length > 0) break; // 商品表已渲染
    }
    await sleep(2000);
  }
  if (!det || !det.promo) return null;
  let allSkus = Array.from(new Set(det.skus || []));
  // 商品表多页：翻页累加
  if (det.pager && det.pager.pages > 1) {
    let guard = 0;
    while (guard++ < det.pager.pages) {
      const nx = await pageExec(tid, path.join(DIR, 'click_detail_next.js'));
      if (!nx || !nx.clicked) break;
      await sleep(2000);
      const d2 = await pageExec(tid, path.join(DIR, 'extract_detail.js'));
      if (d2 && d2.skus) for (const s of d2.skus) if (allSkus.indexOf(s) < 0) allSkus.push(s);
      if (nx.page && nx.pages && nx.page >= nx.pages) break;
    }
  }
  det.skus = allSkus;
  return det;
}

// ---- URL 构造（筛选条件编码在 URL，精确复现用户手动设置） ----
function buildDashUrl(from, to) {
  // status=ENDED, type=BestDeal+LightningDeal (Z划算+秒杀), 日期区间
  return `https://sellercentral.amazon.com/promotion-central/dashboard?status=ENDED&type=BestDeal%2CLightningDeal&store=${cfg.mkid}&startDate=gt%3A${from}&endDate=lt%3A${to}`;
}
function buildDetailUrl(uuid) {
  return `https://sellercentral.amazon.com/promotion-central/deals/view/${uuid}?region=NA&mons_sel_dir_mcid=${cfg.mcid}&mons_sel_mkid=${cfg.mkid}`;
}

// ---- 参数 ----
function prevMonthRange() {
  // 按北京时间(UTC+8)计算上个月首日/末日；to 用下月 1 号作为排他上界，确保整月包含
  const bj = new Date(Date.now() + 8 * 3600 * 1000);
  let y = bj.getUTCFullYear(), m = bj.getUTCMonth() - 1; // 上个月
  if (m < 0) { m = 11; y--; }
  const from = `${y}-${String(m + 1).padStart(2, '0')}-01`;
  const lastDay = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
  const to = `${y}-${String(m + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
  return { from, to };
}
function parseArgs() {
  const a = { limit: 0, out: OUT };
  for (let i = 2; i < process.argv.length; i++) {
    const arg = process.argv[i];
    if (arg === '--from') a.from = process.argv[++i];
    else if (arg === '--to') a.to = process.argv[++i];
    else if (arg === '--limit') a.limit = parseInt(process.argv[++i], 10) || 0;
    else if (arg === '--out') a.out = process.argv[++i];
  }
  if (!a.from || !a.to) { const pm = prevMonthRange(); a.from = pm.from; a.to = pm.to; a.autoRange = true; }
  return a;
}

// ---- 主流程 ----
(async () => {
  // 并发锁：防止同一目录被多实例同时写 CSV（手动重跑与月任务撞车等）
  const LOCK = path.join(OUT, '.lock');
  let ownsLock = false;
  if (fs.existsSync(LOCK)) {
    let old = '';
    try { old = fs.readFileSync(LOCK, 'utf8').trim(); } catch (e) {}
    console.error(`[lock] 检测到已有实例在运行 (out/.lock, pid=${old})，退出以避免并发写文件。强制重跑请先删除 out/.lock`);
    process.exit(3);
  }
  fs.writeFileSync(LOCK, String(process.pid));
  ownsLock = true;
  process.on('exit', () => { if (ownsLock) { try { fs.unlinkSync(LOCK); } catch (e) {} } });

  const t0 = Date.now();
  const args = parseArgs();
  // --out 覆盖输出目录（默认 out/），确保 CSV 路径与续跑/去重口径一致
  const OUTDIR = args.out || OUT;
  PROMO_CSV = path.join(OUTDIR, 'promotions.csv');
  SKU_CSV = path.join(OUTDIR, 'promotion_skus.raw.csv');
  console.log(`[promo_pull] 店铺=${cfg.storeName}(${cfg.storeId}) 范围=${args.from} ~ ${args.to}${args.autoRange ? ' (自动=上月)' : ''}${args.limit ? ' limit=' + args.limit : ''} out=${OUTDIR}`);

  // 1) 打开 dashboard（精确复现筛选，不动用户原标签页）
  console.log('[1] 打开 dashboard 并复现筛选(已结束 / Z划算+秒杀 / 日期区间) ...');
  let tid = await visitPage(buildDashUrl(args.from, args.to));
  await sleep(rand(5000, 7000));

  // 2) 翻页收集所有促销 UUID
  console.log('[2] 收集促销 UUID（翻页）...');
  let allIds = [];
  let pages = 0;
  while (pages < 20) {
    let ids = [];
    for (let i = 0; i < 20; i++) { ids = (await pageExec(tid, path.join(DIR, 'extract_dashboard_ids.js')))?.ids || []; if (ids.length) break; await sleep(2000); }
    const before = allIds.length;
    for (const id of ids) if (!allIds.includes(id)) allIds.push(id);
    const added = allIds.length - before;
    console.log(`    第 ${pages + 1} 页: +${added} (累计 ${allIds.length})`);
    if (args.limit && allIds.length >= args.limit) { allIds.length = args.limit; break; }
    pages++;
    // 兜底：翻页后连续无新增（分页尺寸误判/重复页）即停，避免漏采或死循环
    if (added === 0 && pages > 1) { console.log('    连续无新增，停止翻页'); break; }
    const nx = await pageExec(tid, path.join(DIR, 'click_next.js'));
    if (!nx || nx.status !== 'CLICKED') { console.log('    下一页不可用，停止翻页'); break; }
    if (nx.disabledBefore) { console.log('    已是最后一页，停止翻页'); break; }
    await sleep(rand(4000, 6000));
  }
  console.log(`[2] 共收集 ${allIds.length} 个促销 UUID`);

  // 续跑支持：跳过已导出的促销（中断后重跑不重复、不漏）
  if (fs.existsSync(PROMO_CSV)) {
    const existing = new Set(fs.readFileSync(PROMO_CSV, 'utf8').split('\n').slice(1).filter(Boolean).map(l => l.split(',')[0].replace(/^"|"$/g, '')));
    const before = allIds.length;
    allIds = allIds.filter(id => !existing.has(id));
    if (before !== allIds.length) console.log(`[resume] 跳过已导出 ${before - allIds.length} 条，剩余 ${allIds.length}`);
  }

  // 3) 逐个进详情页提取
  console.log('[3] 逐个进详情页提取字段 + SKU ...');
  ensureHeader(PROMO_CSV, PROMO_HEADER);
  ensureHeader(SKU_CSV, SKU_HEADER);
  let ok = 0, skip = 0;
  for (let i = 0; i < allIds.length; i++) {
    const id = allIds[i];
    try {
      // 详情页导航（复用同一工作 tab）
      const dtid = await visitPage(buildDetailUrl(id)).catch(() => null);
      if (!dtid) { console.error(`    [${i + 1}/${allIds.length}] ${id} 导航失败，跳过`); skip++; continue; }
      // 轮询等商品表渲染 + 多页累加 SKU
      const det = await extractPromo(dtid);
      if (!det || !det.promo) { console.error(`    [${i + 1}/${allIds.length}] ${id} 提取失败，跳过`); skip++; continue; }
      det.status = det.status || '已结束'; // 按筛选条件 ENDED 兜底
      const prefixes = Array.from(new Set((det.skus || []).map(prefixOf)));
      appendRow(PROMO_CSV, [id, det.promo, det.type || '', det.status, det.start || '', det.end || '', det.mkt || '', det.fee || '', (det.skus || []).length, prefixes.join(' | ')]);
      for (const sku of (det.skus || [])) appendRow(SKU_CSV, [id, det.promo, sku, prefixOf(sku)]);
      ok++;
      if ((i + 1) % 10 === 0) console.log(`    进度 ${i + 1}/${allIds.length} (成功 ${ok})`);
    } catch (e) {
      console.error(`    [${i + 1}/${allIds.length}] ${id} 异常，跳过: ${e.message}`);
      skip++;
    }
    await sleep(rand(800, 1500)); // 轻量节流，避免触发限流
  }

  const dt = ((Date.now() - t0) / 1000 / 60).toFixed(1);
  console.log('=== DONE ===');
  console.log(JSON.stringify({ total: allIds.length, ok, skip, promoCsv: PROMO_CSV, skuCsv: SKU_CSV, elapsedMin: dt }, null, 2));
})().catch(e => { console.error('FATAL', e); process.exit(1); });
