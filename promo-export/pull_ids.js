'use strict';
// pull_ids.js — 按「促销 ID 列表」补抓详情（用于补漏 / 抓指定状态集合）
//
// 背景：promo_pull.js 从 dashboard 列表采集 ID，列表受 URL 的 status/type/日期 筛选限制。
// 当需要用「非默认筛选」的集合（如 status=CANCELED & type=BestDeal）时，
// 先用 dashboard URL 拿到 ID 列表，再用本脚本逐个进详情页提取，互不干扰。
//
// 用法：
//   node pull_ids.js --ids <id文件，每行一个UUID> --out <输出目录> [--status 已取消] [--limit N]
//
// 特性：
//   - 续跑：已写入 promotions.csv 的 ID 自动跳过
//   - 与 promo_pull.js 产出完全同构（同表头、同目录结构），可直接喂给 postprocess.py
//   - --status 用于正确标注状态列（promo_pull.js 因筛选 ENDED 而恒定写「已结束」）
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const requireConfig = require('./config');

const cfg = requireConfig();
const CLI = cfg.cliPath;
const DIR = __dirname;

const sleep = ms => new Promise(r => setTimeout(r, ms));
const rand = (a, b) => Math.floor(a + Math.random() * (b - a));

const PROMO_HEADER = ['促销ID', '促销编号', '类型', '状态', '开始日期', '结束日期', '商城', '费用', 'SKU数量', 'SKU前缀列表'];
const SKU_HEADER = ['促销ID', '促销编号', 'SKU', 'SKU前缀'];
function esc(c) { return '"' + String(c == null ? '' : c).replace(/"/g, '""') + '"'; }
function ensureHeader(p, header) {
  if (!fs.existsSync(p)) fs.writeFileSync(p, header.map(esc).join(',') + '\n', 'utf8');
}
function appendRow(p, cells) { fs.appendFileSync(p, cells.map(esc).join(',') + '\n', 'utf8'); }
function prefixOf(sku) { return String(sku).split('-').slice(0, 2).join('-'); }

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
  if (r.code !== 0) return null;
  return parseExecResult(r.out);
}
async function visitPage(url, tries = 3) {
  for (let i = 0; i < tries; i++) {
    const v = await runCli(['zclaw', 'invoke', 'visit_page', '--args', JSON.stringify({ storeId: cfg.storeId, url })], 60000);
    const tid = parseTargetId(v.out);
    if (tid) return tid;
    console.error(`    visit 重试 ${i + 1}/${tries}`);
    await sleep(3000);
  }
  return null;
}
function buildDetailUrl(uuid) {
  return `https://sellercentral.amazon.com/promotion-central/deals/view/${uuid}?region=NA&mons_sel_dir_mcid=${cfg.mcid}&mons_sel_mkid=${cfg.mkid}`;
}
// 与 promo_pull.js 完全一致：轮询等渲染 + 多页翻页累加 SKU
async function extractPromo(tid) {
  let det = null;
  for (let i = 0; i < 12; i++) {
    const d = await pageExec(tid, path.join(DIR, 'extract_detail.js'));
    if (d && d.promo) { det = d; if ((d.skus || []).length > 0) break; }
    await sleep(2000);
  }
  if (!det || !det.promo) return null;
  let allSkus = Array.from(new Set(det.skus || []));
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

function parseArgs() {
  const a = { out: null, ids: null, status: '已取消', limit: 0 };
  for (let i = 2; i < process.argv.length; i++) {
    const k = process.argv[i];
    if (k === '--ids') a.ids = process.argv[++i];
    else if (k === '--out') a.out = process.argv[++i];
    else if (k === '--status') a.status = process.argv[++i];
    else if (k === '--limit') a.limit = parseInt(process.argv[++i], 10) || 0;
  }
  return a;
}

(async () => {
  const args = parseArgs();
  if (!args.ids || !args.out) {
    console.error('用法: node pull_ids.js --ids <id文件> --out <输出目录> [--status 已取消] [--limit N]');
    process.exit(1);
  }
  const OUTDIR = path.resolve(args.out);
  fs.mkdirSync(OUTDIR, { recursive: true });
  const PROMO_CSV = path.join(OUTDIR, 'promotions.csv');
  const SKU_CSV = path.join(OUTDIR, 'promotion_skus.raw.csv');

  let ids = fs.readFileSync(args.ids, 'utf8').split('\n').map(s => s.trim())
    .filter(s => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s));
  ids = Array.from(new Set(ids));

  // 续跑：跳过已导出的
  if (fs.existsSync(PROMO_CSV)) {
    const existing = new Set(fs.readFileSync(PROMO_CSV, 'utf8').split('\n').slice(1)
      .filter(Boolean).map(l => l.split(',')[0].replace(/^"|"$/g, '')));
    const before = ids.length;
    ids = ids.filter(x => !existing.has(x));
    if (before !== ids.length) console.log(`[resume] 跳过已导出 ${before - ids.length} 条，剩余 ${ids.length}`);
  }
  if (args.limit) ids = ids.slice(0, args.limit);

  console.log(`[pull_ids] 店铺=${cfg.storeName}(${cfg.storeId}) 待抓=${ids.length} 状态标注=${args.status} out=${OUTDIR}`);
  ensureHeader(PROMO_CSV, PROMO_HEADER);
  ensureHeader(SKU_CSV, SKU_HEADER);

  const t0 = Date.now();
  let ok = 0, skip = 0;
  for (let i = 0; i < ids.length; i++) {
    const id = ids[i];
    try {
      const dtid = await visitPage(buildDetailUrl(id));
      if (!dtid) { console.error(`    [${i + 1}/${ids.length}] ${id} 导航失败，跳过`); skip++; continue; }
      const det = await extractPromo(dtid);
      if (!det || !det.promo) { console.error(`    [${i + 1}/${ids.length}] ${id} 提取失败，跳过`); skip++; continue; }
      const prefixes = Array.from(new Set((det.skus || []).map(prefixOf)));
      appendRow(PROMO_CSV, [id, det.promo, det.type || '', args.status, det.start || '', det.end || '', det.mkt || '', det.fee || '', (det.skus || []).length, prefixes.join(' | ')]);
      for (const sku of (det.skus || [])) appendRow(SKU_CSV, [id, det.promo, sku, prefixOf(sku)]);
      ok++;
      if ((i + 1) % 10 === 0) console.log(`    进度 ${i + 1}/${ids.length} (成功 ${ok})`);
    } catch (e) {
      console.error(`    [${i + 1}/${ids.length}] ${id} 异常: ${e.message}`);
      skip++;
    }
    await sleep(rand(800, 1500));
  }
  const dt = ((Date.now() - t0) / 1000 / 60).toFixed(1);
  console.log('=== DONE ===');
  console.log(JSON.stringify({ total: ids.length, ok, skip, promoCsv: PROMO_CSV, skuCsv: SKU_CSV, elapsedMin: dt }, null, 2));
})().catch(e => { console.error('FATAL', e); process.exit(1); });
