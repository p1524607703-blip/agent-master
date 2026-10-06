'use strict';
/**
 * 多步诊断: 打开带日期参数的报告页 -> 读状态 -> (可选)点应用 -> 再读状态 -> 打印
 * 用法: node diag2.js <storeName> <storeId> <url> [apply 1/0] [waitMs]
 */
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const CLI = '/opt/homebrew/bin/ziniao-cli';
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
async function exec(storeId, tid, file) {
  const script = fs.readFileSync(path.join(__dirname, file), 'utf8');
  const r = await runCli(['page', 'exec', '--store-id', storeId, '--target-id', tid, '--script', script, '--timeout', '50000'], 70000);
  if (r.code !== 0) return { err: (r.err || r.out).slice(0, 200) };
  return parseExecResult(r.out);
}

(async () => {
  const [storeName, storeId, url, apply = '0', waitMs = '25000'] = process.argv.slice(2);
  console.error('[1] open', url);
  await runCli(['store', 'open', '--name', storeName, '--url', url], 60000);
  const v = await runCli(['zclaw', 'invoke', 'visit_page', '--args', JSON.stringify({ storeId, url })], 90000);
  let tid = null;
  try { const o = JSON.parse(v.out); tid = o?.data?.data?.targetId || o?.data?.targetId; } catch (e) {}
  if (!tid) { console.error('no tid', v.out.slice(0, 300)); process.exit(1); }
  console.error('[2] tid', tid, 'wait', waitMs);
  await sleep(parseInt(waitMs, 10));

  const s1 = await exec(storeId, tid, 'read_state.js');
  console.error('--- 状态1(加载后) ---');
  console.log(JSON.stringify(s1, null, 1));

  if (apply === '1') {
    const clickScript = `(function(){try{var bs=document.querySelectorAll('kat-button');for(var i=0;i<bs.length;i++){var b=bs[i];if((b.getAttribute('label')||'')==='应用'){var inner=b.shadowRoot?(b.shadowRoot.querySelector('button')||b):b;inner.click();return JSON.stringify({status:'OK',clicked:true});}}return JSON.stringify({status:'ERR',msg:'not found'});}catch(e){return JSON.stringify({status:'ERR',msg:String(e)});}})();`;
    const r = await runCli(['page', 'exec', '--store-id', storeId, '--target-id', tid, '--script', clickScript, '--timeout', '50000'], 70000);
    console.error('[3] 点击应用:', parseExecResult(r.out));
    await sleep(parseInt(waitMs, 10));
    const s2 = await exec(storeId, tid, 'read_state.js');
    console.error('--- 状态2(应用后) ---');
    console.log(JSON.stringify(s2, null, 1));
  }
})().catch(e => { console.error('FATAL', e); process.exit(9); });
