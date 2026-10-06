'use strict';
// 一次性补抓脚本 (2026-09-15): 在"已完整加载"的 fba-return 页面上翻完整个 7 天窗口,
// 去重后补进 master.csv。不重新导航(页面已是 LAST_7_DAYS + pageSize=1000 状态)。
// 不改动 daily_pull.js。
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { requireConfig } = require('./config');
const cfg = requireConfig();
const CLI = cfg.cliPath, STORE_ID = cfg.storeId, DIR = __dirname;
const HEADER = ['Marketplace','Order ID','Image','Title','ASIN','Seller SKU','Return Reason','Authorization Date','Refund Date','Unit Received Date','Disposition','Status','Action'];
const MASTER = path.join(DIR,'master.csv');
const GOOD = path.join(DIR,'master.csv.good.bak');
const TID = process.argv[2];
if(!TID){ console.error('usage: node _recover.js <targetId>'); process.exit(1); }

const sleep = ms => new Promise(r=>setTimeout(r,ms));
function runCli(args, timeout=60000){ return new Promise(res=>{ const cp=spawn(CLI,args,{timeout}); let out='',err=''; cp.stdout.on('data',d=>out+=d); cp.stderr.on('data',d=>err+=d); cp.on('close',c=>res({code:c,out,err})); cp.on('error',e=>res({code:-1,out,err:String(e)})); }); }
function parseExec(s){ try{ const o=JSON.parse(s); const inner=o&&o.data&&o.data.data&&o.data.data.result; if(typeof inner==='string'){const r=JSON.parse(inner); if(r&&r.status) return r;} if(inner&&typeof inner==='object'&&inner.status) return inner; if(o&&o.status) return o; }catch(e){} return null; }
async function exec(file){ const script=fs.readFileSync(path.join(DIR,file),'utf8'); const r=await runCli(['page','exec','--store-id',STORE_ID,'--target-id',TID,'--script',script,'--timeout','50000']); if(r.code!==0){ console.error('   exec fail', r.err.slice(0,200)); return null;} return parseExec(r.out); }
function parseCSVLine(line){ const row=[]; let i=0,field='',inQ=false; while(i<line.length){const c=line[i]; if(inQ){ if(c==='"'){ if(line[i+1]==='"'){field+='"';i+=2;continue;} inQ=false;i++;continue;} field+=c;i++;continue;} else { if(c==='"'){inQ=true;i++;continue;} if(c===','){row.push(field);field='';i++;continue;} field+=c;i++; } } row.push(field); return row; }
function rowKey(cells){ const o=cells[1]||''; let a=cells[4]||''; if(!a){const m=(cells[3]||'').match(/B0[A-Z0-9]{8}/); a=m?m[0]:'';} return o+'|'+a; }
const esc=c=>'"'+String(c==null?'':c).replace(/"/g,'""')+'"';

(async()=>{
  const t0=Date.now();
  const txt=fs.readFileSync(MASTER,'utf8');
  const lines=txt.split('\n').filter(l=>l.length);
  const existing=new Set();
  for(let i=1;i<lines.length;i++) existing.add(rowKey(parseCSVLine(lines[i])));
  console.log('master rows before =', lines.length-1);

  const collected=[]; const seen=new Set();
  let prevFirst=null, pages=0, stuck=false;
  while(pages<25){
    let full=null;
    for(let i=0;i<6;i++){ full=await exec('extract_full.js'); if(full&&full.status==='OK'&&full.rowCount>0) break; await sleep(3000); }
    if(!full||full.status!=='OK'||!full.rowCount){ console.log('   提取为空/失败, 停止'); break; }
    const rows=full.rows||[];
    const firstKey=rows[0].join('\u0001');
    if(firstKey===prevFirst){ console.log('   首行未变化 -> 停止'); stuck=true; break; }
    prevFirst=firstKey;
    let add=0; for(const r of rows){ if(!Array.isArray(r)||r.length!==HEADER.length) continue; const k=rowKey(r); if(!seen.has(k)){ seen.add(k); collected.push(r); add++; } }
    pages++;
    console.log(`   第 ${pages} 页: ${rows.length} 行 (页内唯一 +${add}, 累计唯一 ${collected.length}) | 首行=${rows[0][1]}`);
    const nx=await exec('_next2.js');
    if(!nx||nx.status!=='OK'){ console.log('   无下一页 (next=', JSON.stringify(nx),'), 停止'); break; }
    let changed=false;
    for(let w=0;w<12;w++){ await sleep(4000); const f2=await exec('extract_full.js'); if(f2&&f2.status==='OK'&&f2.rows&&f2.rows.length){ const k2=f2.rows[0].join('\u0001'); if(k2!==prevFirst){ changed=true; break; } } }
    if(!changed){ console.log('   翻页后首行仍不变 -> 停止'); stuck=true; break; }
  }
  console.log('legacy: pages=',pages,' unique collected=',collected.length,' stuck=',stuck);

  const newLines=[], newCells=[];
  for(const r of collected){ const k=rowKey(r); if(!existing.has(k)){ existing.add(k); newLines.push(r.map(esc).join(',')); newCells.push(r); } }
  console.log('NEW rows =', newLines.length, '(vs master)');
  if(newLines.length){
    const content=lines.concat(newLines).join('\n');
    const tmp=MASTER+'.tmp'; fs.writeFileSync(tmp,content,'utf8'); fs.renameSync(tmp,MASTER);
    fs.copyFileSync(MASTER,GOOD);
    console.log('master rows after =', lines.length-1+newLines.length, '; good.bak updated');
    // refund-date distribution
    const cnt=new Map();
    for(const r of newCells){ let d=String(r[8]||'').trim(); const m=d.match(/^(\d{2})\/(\d{2})\/(\d{4})$/); d=m?(m[1]+'-'+m[2]):(d==='--'||!d?'未标注':d); cnt.set(d,(cnt.get(d)||0)+1); }
    const entries=[...cnt.entries()].sort((a,b)=>{ if(a[0]==='未标注')return 1; if(b[0]==='未标注')return -1; return a[0]<b[0]?-1:1; });
    const bj=new Date(Date.now()+8*3600*1000);
    const name=`${bj.getUTCMonth()+1}月${bj.getUTCDate()}日导出增量数据_补抓 `+entries.map(([d,n])=>`${d} (${n} 条)`).join(' + ')+'.csv';
    const rep=path.join(DIR,name);
    fs.writeFileSync(rep, [HEADER.map(esc).join(',')].concat(newLines).join('\n'), 'utf8');
    console.log(JSON.stringify({newRows:newLines.length, masterTotal:lines.length-1+newLines.length, dist:entries, report:rep}, null, 2));
  } else {
    console.log('无新增, 未生成报告');
  }
  console.log('elapsedSec=', ((Date.now()-t0)/1000).toFixed(1));
})().catch(e=>{ console.error('FATAL', e); process.exit(1); });
