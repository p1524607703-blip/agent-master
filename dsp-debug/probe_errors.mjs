#!/usr/bin/env node
// 在指定 target 上安装持久错误钩子，重载页面，抓异常堆栈 + 失败资源 + 4xx/5xx 响应
// 用法: node probe_errors.mjs <wsUrl> <waitSeconds> <outJson>
import fs from 'node:fs';
const [, , wsUrl, waitSec = '30', outJson = 'errors.json'] = process.argv;
const ws = new WebSocket(wsUrl);
let nextId = 1;
const pending = new Map();
const errors = [];       // Runtime.exceptionThrown
const consoleErrs = [];  // console.error
const logEntries = [];   // Log.entryAdded
const failedReqs = [];   // Network.loadingFailed
const badResponses = []; // status >= 400
const requests = {};     // requestId -> url

const send = (method, params = {}) => new Promise((res, rej) => {
  const id = nextId++;
  pending.set(id, { res, rej, method });
  ws.send(JSON.stringify({ id, method, params }));
});

const HOOK = `(function(){
  window.__ERRS = [];
  function rec(o){ try { o.t = Date.now(); window.__ERRS.push(o); } catch(e){} }
  window.addEventListener('error', function(ev){
    try {
      if (ev && ev.target && ev.target !== window && ev.target.tagName) {
        rec({kind:'resource', tag: ev.target.tagName, url: ev.target.src || ev.target.href || ''});
      } else {
        rec({kind:'error', msg: ev && ev.message, src: ev && ev.filename, line: ev && ev.lineno, col: ev && ev.colno,
             stack: (ev && ev.error && ev.error.stack) || null});
      }
    } catch(e){}
  }, true);
  window.addEventListener('unhandledrejection', function(ev){
    var r = ev && ev.reason;
    rec({kind:'rejection', msg: r && r.message ? r.message : String(r), stack: r && r.stack ? r.stack : null});
  });
  var ce = console.error;
  console.error = function(){
    try {
      rec({kind:'console.error', args: Array.prototype.slice.call(arguments).map(function(a){
        if (a && a.stack) return String(a.stack);
        if (typeof a === 'object') { try { return JSON.stringify(a).slice(0,600); } catch(e){ return '[obj]'; } }
        return String(a).slice(0,600);
      })});
    } catch(e){}
    return ce.apply(console, arguments);
  };
  var cw = console.warn;
  console.warn = function(){
    try { rec({kind:'console.warn', args: Array.prototype.slice.call(arguments).map(function(a){
      if (a && a.stack) return String(a.stack);
      return String(a).slice(0,400); })}); } catch(e){}
    return cw.apply(console, arguments);
  };
})();`;

ws.onopen = async () => {
  try {
    await send('Page.enable');
    await send('Runtime.enable');
    await send('Log.enable');
    await send('Network.enable', { maxTotalBufferSize: 100000000, maxResourceBufferSize: 5000000 });
    const add = await send('Page.addScriptToEvaluateOnNewDocument', { source: HOOK, runImmediately: true });
    console.error('[hook id]', JSON.stringify(add.result));
    await send('Page.reload', { ignoreCache: true });
    console.error('[reloaded, waiting ' + waitSec + 's]');
  } catch (e) { console.error('SETUP_ERR', e.message); ws.close(); process.exit(1); }
};

ws.onmessage = (ev) => {
  let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
  if (m.id && pending.has(m.id)) {
    const p = pending.get(m.id);
    if (m.error) p.rej(new Error(JSON.stringify(m.error))); else p.res(m.result);
    pending.delete(m.id);
    return;
  }
  const p = m.params || {};
  switch (m.method) {
    case 'Runtime.exceptionThrown': {
      const d = p.exceptionDetails || {};
      const ex = d.exception || {};
      errors.push({
        text: d.text, url: d.url, line: d.lineNumber, col: d.columnNumber,
        desc: (ex.description || ex.value || '').toString().slice(0, 1500),
        stack: (ex.preview && ex.preview.properties) ? ex.preview.properties : null
      });
      break;
    }
    case 'Runtime.consoleAPICalled':
      if (p.type === 'error' || p.type === 'warning') {
        consoleErrs.push({ type: p.type, args: (p.args || []).map(a => (a.description || a.value || '').toString().slice(0, 1200)) });
      }
      break;
    case 'Log.entryAdded': {
      const e = p.entry || {};
      if (e.level === 'error' || e.source === 'network' || e.source === 'javascript') {
        logEntries.push({ level: e.level, source: e.source, text: (e.text || '').slice(0, 600), url: e.url });
      }
      break;
    }
    case 'Network.requestWillBeSent':
      requests[p.requestId] = p.request && p.request.url;
      break;
    case 'Network.loadingFailed':
      failedReqs.push({ url: requests[p.requestId] || '?', errorText: p.errorText, type: p.type, canceled: p.canceled });
      break;
    case 'Network.responseReceived': {
      const r = p.response || {};
      if (r.status >= 400) badResponses.push({ status: r.status, url: r.url, mime: r.mimeType });
      break;
    }
  }
};

setTimeout(async () => {
  let pageErrs = null;
  try {
    const r = await send('Runtime.evaluate', { expression: 'JSON.stringify(window.__ERRS || [])', returnByValue: true });
    pageErrs = r.result && r.result.value ? JSON.parse(r.result.value) : null;
  } catch (e) { pageErrs = { evalError: e.message }; }

  const dedupe = arr => { const seen = new Set(); return arr.filter(x => { const k = JSON.stringify(x).slice(0, 300); if (seen.has(k)) return false; seen.add(k); return true; }); };

  const out = {
    wsUrl,
    exceptionThrown: dedupe(errors).slice(0, 30),
    consoleErrors: dedupe(consoleErrs).slice(0, 40),
    logEntries: dedupe(logEntries).slice(0, 40),
    failedRequests: dedupe(failedReqs).slice(0, 40),
    badResponses: dedupe(badResponses).slice(0, 40),
    pageHookErrors: pageErrs
  };
  const fs2 = fs;
  fs2.writeFileSync(outJson, JSON.stringify(out, null, 1));
  console.error('[written] ' + outJson + '  exceptions=' + out.exceptionThrown.length + ' badResp=' + out.badResponses.length + ' failed=' + out.failedRequests.length + ' hookErrs=' + (Array.isArray(pageErrs) ? pageErrs.length : 'n/a'));
  process.exit(0);
}, parseInt(waitSec, 10) * 1000);

ws.onerror = e => { console.error('WSERR', (e && e.message) || String(e)); process.exit(1); };
