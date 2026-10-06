'use strict';
/**
 * 通用 runner: 打开页面 -> 等待 -> 注入脚本 -> 解析结果 -> 落盘
 * 用法: node run.js <storeName> <storeId> <url> <scriptFile> [waitMs] [outFile]
 */
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const CLI = process.env.ZINIAO_CLI || '/opt/homebrew/bin/ziniao-cli';
const sleep = ms => new Promise(r => setTimeout(r, ms));

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

(async () => {
  const [storeName, storeId, url, scriptFile, waitMs = '12000', outFile] = process.argv.slice(2);
  if (!storeName || !storeId || !url || !scriptFile) {
    console.error('usage: node run.js <storeName> <storeId> <url> <scriptFile> [waitMs] [outFile]');
    process.exit(1);
  }
  console.error('[1] store open:', storeName);
  await runCli(['store', 'open', '--name', storeName, '--url', url], 60000);
  const v = await runCli(['zclaw', 'invoke', 'visit_page', '--args', JSON.stringify({ storeId, url })], 90000);
  let tid = null;
  try { const o = JSON.parse(v.out); tid = o?.data?.data?.targetId || o?.data?.targetId; } catch (e) {}
  if (!tid) { console.error('no targetId:', v.out.slice(0, 400)); process.exit(1); }
  console.error('[2] targetId =', tid);
  await sleep(parseInt(waitMs, 10));

  const script = fs.readFileSync(scriptFile, 'utf8');
  const r = await runCli(['page', 'exec', '--store-id', storeId, '--target-id', tid, '--script', script, '--timeout', '50000'], 70000);
  if (r.code !== 0) { console.error('page exec failed:', r.err.slice(0, 400), r.out.slice(0, 400)); process.exit(2); }
  const res = parseExecResult(r.out);
  const txt = JSON.stringify(res, null, 2);
  if (outFile) { fs.writeFileSync(outFile, txt, 'utf8'); console.error('[3] 已写入', outFile); }
  process.stdout.write(txt + '\n');
})().catch(e => { console.error('FATAL', e); process.exit(9); });
