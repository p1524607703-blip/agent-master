'use strict';
// 一次性补抓 (2026-09-15): 修正版全窗扫描。相对 daily_pull.js 的关键差异 =
//   (1) 注入 pageSize 后"等表格真正渲染满"(轮询 rowCount 稳定) 再提取, 而非固定 sleep;
//   (2) 翻页后"等首行变化"再提取, 而非盲等固定时长;
//   (3) Next 按钮精确匹配(避免误点 stray '>')。
// 不覆写 daily_pull.js。
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { requireConfig } = require('./config');
const cfg = requireConfig();
const CLI = cfg.cliPath, STORE_ID = cfg.storeId, STORE_NAME = cfg.storeName, URL_ = cfg.marketplaceUrl, DIR = __dirname;
const HEADER = ['Marketplace','Order ID','Image','Title','ASIN','Seller SKU','Return Reason','Authorization Date','Refund Date','Unit Received Date','Disposition','Status','Action'];
const MASTER = path.join(DIR,'master.csv');
const GOOD = path.join(DIR,'master.csv.good.bak');
const PAGE_SIZE = 1000, MAX_PAGES = 20;

const sleep = ms => new Promise(r=>setTimeout(r,ms));
const rand=(a,b)=>Math.floor(a+Math.random()*(b-a));
const esc=c=>'"'+String(c==null?'':c).replace(/"/g,'""')+'"';
function runCli(args, timeout=60000){ return new Promise(res=>{ const cp=spawn(CLI,args,{timeout}); let out='',err=''; cp.stdout.on('data',d=>out+=d); cp.stderr.on('data',d=>err+=d); cp.on('close',c=>res({code:c,out,err})); cp.on('error',e=>res({code:-1,out,err:String(e)})); }); }
function parseExec(s){ try{ const o=JSON.parse(s); const inner=o&&o.data&&o.data.data&&o.data.data.result; if(typeof inner==='string'){const r=JSON.parse(inner); if(r&&r.status) return r;} if(inner&&typeof inner==='object'&&inner.status) return inner; if(o&&o.status) return o; }catch(e){} return null; }
function parseCSVLine(line){ const row=[]; let i=0,field='',inQ=false; while(i<line.length){const c=line[i]; if(inQ){ if(c==='"'){ if(line[i+1]==='"'){field+='"';i+=2;continue;} inQ=false;i++;continue;} field+=c;i++;continue;} else { if(c==='"'){inQ=true;i++;continue;} if(c===','){row.push(field);field='';i++;continue;} field+=c;i++; } } row.push(field); return row; }
function rowKey(cells){ const o=cells[1]||''; let a=cells[4]||''; if(!a){const m=(cells[3]||'').match(/B0[A-Z0-9]{8}/); a=m?m[0]:'';} return o+'|'+a; }
function makeInject(val){ return `(function(){try{function find(){return Array.from(document.querySelectorAll('select')).find(function(s){var o=Array.from(s.options).map(function(x){return x.value;}).join(',');return /25|50|100/.test(o);});}var sel=null,t=0;while(t<25&&!(sel=find())){t++;}if(!sel)return JSON.stringify({status:'NO_SELECT'});var opt=document.createElement('option');opt.value=String(${val});opt.text=String(${val});sel.appendChild(opt);sel.value=String(${val});sel.dispatchEvent(new Event('change',{bubbles:true}));return JSON.stringify({status:'OK',setTo:sel.value});}catch(e){return JSON.stringify({status:'ERR',msg:String(e)});}})();`; }
function execStr(str, timeout=55000){ return runCli(['page','exec','--store-id',STORE_ID,'--target-id',TID,'--script',str,'--timeout','50000'], timeout).then(r=> r.code!==0 ? (console.error('   exec fail', r.err.slice(0,200)), null) : parseExec(r.out)); }
function execFile(f, timeout){ return execStr(fs.readFileSync(path.join(DIR,f),'utf8'), timeout); }
const stat = f => { try { return fs.statSync(f).mtimeMs; } catch(e){ return -1; } };

let TID = null;

(async()=>{
  const t0=Date.now();
  await runCli(['store','open','--name',STORE_NAME,'--url',URL_],60000);
  const v=await runCli(['zclaw','invoke','visit_page','--args',JSON.stringify({storeId:STORE_ID,url:URL_})],60000);
  try{ const o=JSON.parse(v.out); TID=o&&o.data&&o.data.data&&o.data.data.targetId||o&&o.data&&o.data.targetId; }catch(e){}
  if(!TID){ console.error('no targetId:', v.out.slice(0,200)); process.exit(1); }
  console.log('targetId =', TID);
  await sleep(6000);

  // 0b) 等页面就绪: 轮询 radio 控件出现(筛选 UI 渲染完成)
  console.log('0b) 等待筛选控件就绪 ...');
  const radioProbe = `(function(){try{var n=document.querySelectorAll('input[type=radio]').length;var t=document.querySelector('table')?document.querySelector('table').querySelectorAll('tbody tr').length:-1;return JSON.stringify({status:'OK',radios:n,rows:t,url:location.href});}catch(e){return JSON.stringify({status:'ERR',msg:String(e)});}})();`;
  let rr=null;
  for(let i=0;i<30;i++){ rr=await execStr(radioProbe); if(rr&&rr.status==='OK'&&rr.radios>0) break; await sleep(3000); }
  console.log('   ', JSON.stringify(rr));
  if(!rr||rr.status!=='OK'||!rr.radios){ console.error('页面未就绪(无筛选控件), 中止'); process.exit(1); }

  console.log('1) 筛选 LAST_7_DAYS');
  let f=null; for(let i=0;i<6;i++){ f=await execFile('set_filter.js'); if(f&&f.status==='OK') break; await sleep(rand(4000,6000)); }
  console.log('   ', JSON.stringify(f)); if(!f||f.status!=='OK'){ console.error('筛选失败'); process.exit(1); }
  await sleep(rand(8000,11000));

  console.log('2) 注入 recordsPerPage =', PAGE_SIZE);
  const inj=makeInject(PAGE_SIZE); let ir=null;
  for(let i=0;i<6;i++){ ir=await execStr(inj); if(ir&&ir.status==='OK') break; await sleep(rand(5000,7000)); }
  console.log('   ', JSON.stringify(ir)); if(!ir||ir.status!=='OK'){ console.error('注入失败'); process.exit(1); }

  // 2b) ★等表格真正渲染满: 轮询 rowCount 连续 2 次相同且 >0
  console.log('2b) 等待表格渲染满 ...');
  let lastN=-1, stable=0, ready=0;
  for(let i=0;i<40;i++){
    const r=await execFile('extract_full.js');
    const n=(r&&r.status==='OK')?r.rowCount:0;
    if(n>0 && n===lastN){ stable++; if(stable>=2){ ready=n; break; } } else { stable=0; }
    lastN=n;
    if(i%3===0) console.log(`     ... rowCount=${n}`);
    await sleep(3000);
  }
  console.log('   表格就绪 rowCount =', ready, ready>=PAGE_SIZE?'(满页)':'(未满, 可能是窗口内真就这么少)');
  if(ready<=0){ console.error('表格始终为空, 中止'); process.exit(1); }

  const txt=fs.readFileSync(MASTER,'utf8'); const lines=txt.split('\n').filter(l=>l.length);
  const existing=new Set(); for(let i=1;i<lines.length;i++) existing.add(rowKey(parseCSVLine(lines[i])));
  console.log('   master rows before =', lines.length-1);

  const collected=[], seen=new Set(); let prevFirst=null, pages=0, stop='';
  while(pages<MAX_PAGES){
    let full=null; for(let i=0;i<5;i++){ full=await execFile('extract_full.js'); if(full&&full.status==='OK'&&full.rowCount>0) break; await sleep(3000); }
    if(!full||full.status!=='OK'||!full.rowCount){ stop='提取为空'; break; }
    const rows=full.rows||[]; const fk=rows[0].join('\u0001');
    if(fk===prevFirst){ stop='首行未变化'; break; }
    prevFirst=fk;
    let add=0; for(const r of rows){ if(!Array.isArray(r)||r.length!==HEADER.length) continue; const k=rowKey(r); if(!seen.has(k)){ seen.add(k); collected.push(r); add++; } }
    pages++;
    console.log(`   第 ${pages} 页: ${rows.length} 行 (页内唯一+${add}, 累计唯一 ${collected.length}) 首行=${rows[0][1]}`);
    const nx=await execFile('_next2.js');
    if(!nx||nx.status!=='OK'){ stop='无下一页('+JSON.stringify(nx)+')'; break; }
    let changed=false;
    for(let w=0;w<12;w++){ await sleep(4000); const f2=await execFile('extract_full.js'); if(f2&&f2.status==='OK'&&f2.rows&&f2.rows.length){ if(f2.rows[0].join('\u0001')!==prevFirst){ changed=true; break; } } }
    if(!changed){ stop='翻页后首行不变(可能触达UI上限或翻页失败)'; break; }
  }
  console.log('pages=',pages,' collected=',collected.length,' stop=',stop);

  const newLines=[], newCells=[];
  for(const r of collected){ const k=rowKey(r); if(!existing.has(k)){ existing.add(k); newLines.push(r.map(esc).join(',')); newCells.push(r); } }
  console.log('NEW =', newLines.length);
  let report=null;
  if(newLines.length){
    fs.writeFileSync(MASTER+'.tmp', lines.concat(newLines).join('\n'),'utf8'); fs.renameSync(MASTER+'.tmp', MASTER);
    fs.copyFileSync(MASTER,GOOD);
    console.log('master rows after =', lines.length-1+newLines.length);
    const cnt=new Map(); for(const r of newCells){ let d=String(r[8]||'').trim(); const m=d.match(/^(\d{2})\/(\d{2})\/(\d{4})$/); d=m?(m[1]+'-'+m[2]):((d==='--'||!d)?'未标注':d); cnt.set(d,(cnt.get(d)||0)+1); }
    const ent=[...cnt.entries()].sort((a,b)=>{ if(a[0]==='未标注')return 1; if(b[0]==='未标注')return -1; return a[0]<b[0]?-1:1; });
    const bj=new Date(Date.now()+8*3600*1000);
    report=path.join(DIR,`${bj.getUTCMonth()+1}月${bj.getUTCDate()}日导出增量数据_补抓 `+ent.map(([d,n])=>`${d} (${n} 条)`).join(' + ')+'.csv');
    fs.writeFileSync(report,[HEADER.map(esc).join(',')].concat(newLines).join('\n'),'utf8');
    console.log(JSON.stringify({newRows:newLines.length, masterTotal:lines.length-1+newLines.length, dist:ent, report},null,2));
  } else {
    console.log('无新增');
  }
  console.log(JSON.stringify({pagesPulled:pages, rowsCollected:collected.length, newRows:newLines.length, masterTotal:lines.length-1+newLines.length, stopReason:stop, dailyReport:report||'(无新增, 未生成)', elapsedSec:((Date.now()-t0)/1000).toFixed(1)},null,2));
})().catch(e=>{ console.error('FATAL',e); process.exit(1); });
