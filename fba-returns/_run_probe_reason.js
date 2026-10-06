'use strict';
// 临时探针：打开 FBA 退货页 → 设 LAST_7_DAYS → 注入 1000/页 → 探测 Return Reason 列的图标结构
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { requireConfig } = require('./config');
const cfg = requireConfig();
const CLI = cfg.cliPath;
const DIR = __dirname;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const rand = (a, b) => Math.floor(a + Math.random() * (b - a));

function runCli(args, timeout = 60000) {
  return new Promise(resolve => {
    const cp = spawn(CLI, args, { timeout });
    let out = '', err = '';
    cp.stdout.on('data', d => out += d); cp.stderr.on('data', d => err += d);
    cp.on('close', code => resolve({ code, out, err })); cp.on('error', e => resolve({ code: -1, out, err: String(e) }));
  });
}
function parse(s){ try{ const o=JSON.parse(s); const inner=o?.data?.data?.result; if(typeof inner==='string'){const r=JSON.parse(inner); if(r&&r.status)return r;} if(inner&&inner.status)return inner; if(o?.status)return o; }catch(e){} return null; }
async function exec(tid, file){ const sc=fs.readFileSync(file,'utf8'); const r=await runCli(['page','exec','--store-id',cfg.storeId,'--target-id',tid,'--script',sc,'--timeout','50000'],55000); if(r.code!==0){console.error('exec fail',r.err.slice(0,200));return null;} return parse(r.out); }

(async () => {
  await runCli(['store','open','--name',cfg.storeName,'--url',cfg.marketplaceUrl],90000);
  const v = await runCli(['zclaw','invoke','visit_page','--args',JSON.stringify({storeId:cfg.storeId,url:cfg.marketplaceUrl})],60000);
  let tid=null; try{ const o=JSON.parse(v.out); tid=o?.data?.data?.targetId||o?.data?.targetId; }catch(e){}
  if(!tid){ console.error('no targetId'); process.exit(1); }
  console.log('targetId=', tid);
  await sleep(7000);
  let f=null; for(let i=0;i<4;i++){ f=await exec(tid, path.join(DIR,'set_filter.js')); if(f&&f.status==='OK')break; await sleep(4000); }
  console.log('filter:', JSON.stringify(f));
  await sleep(9000);
  const inj=path.join(DIR,'_inject_probe_tmp.js');
  fs.writeFileSync(inj, `(function(){try{function find(){return Array.from(document.querySelectorAll('select')).find(function(s){var o=Array.from(s.options).map(function(x){return x.value;}).join(',');return /25|50|100/.test(o);});}var sel=null,t=0;while(t<25&&!(sel=find())){t++;}if(!sel)return JSON.stringify({status:'NO_SELECT'});var opt=document.createElement('option');opt.value='1000';opt.text='1000';sel.appendChild(opt);sel.value='1000';sel.dispatchEvent(new Event('change',{bubbles:true}));return JSON.stringify({status:'OK',setTo:sel.value});}catch(e){return JSON.stringify({status:'ERR',msg:String(e)});}})();`);
  let i2=null; for(let i=0;i<5;i++){ i2=await exec(tid, inj); if(i2&&i2.status==='OK')break; await sleep(5000); }
  console.log('inject:', JSON.stringify(i2));
  await sleep(11000);
  const res = await exec(tid, path.join(DIR,'_probe_reason_icon.js'));
  console.log('=== PROBE RESULT ===');
  console.log(JSON.stringify(res, null, 2));
  try{ fs.unlinkSync(inj); }catch(e){}
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
