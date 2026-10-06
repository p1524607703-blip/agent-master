'use strict';
// 通用浏览器脚本执行器: node _exec.js <browserScriptFile> [more...]
// 只读探针用, 不写任何文件、不改任何账号设置。
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { requireConfig } = require('./config');
const { ensureStore } = require('./store_guard');

const cfg = requireConfig();
const CLI = cfg.cliPath;
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
    const inner = o && o.data && o.data.data && o.data.data.result;
    if (typeof inner === 'string') { const r = JSON.parse(inner); if (r && r.status) return r; }
    if (inner && typeof inner === 'object' && inner.status) return inner;
    if (o && o.status) return o;
  } catch (e) {}
  return null;
}

async function exec(tid, file) {
  const script = fs.readFileSync(path.join(__dirname, file), 'utf8');
  const r = await runCli(['page', 'exec', '--store-id', cfg.storeId, '--target-id', tid, '--script', script, '--timeout', '60000']);
  if (r.code !== 0) return { status: 'CLI_FAIL', err: (r.err || '').slice(0, 400) };
  return parseExecResult(r.out);
}

(async () => {
  const g = await ensureStore(cfg, { remediate: true });
  console.log('[guard] ok=' + g.ok + ' ' + (g.reason || ''));
  if (!g.ok) process.exit(11);
  const tid = g.tid;
  await sleep(6000);
  for (const f of process.argv.slice(2)) {
    const r = await exec(tid, f);
    console.log('\n### ' + f);
    console.log(typeof r === 'string' ? r : JSON.stringify(r, null, 1));
    await sleep(3500);
  }
})();
