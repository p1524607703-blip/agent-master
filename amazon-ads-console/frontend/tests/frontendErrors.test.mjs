import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import ts from 'typescript'
import * as Vue from 'vue'
const require=createRequire(import.meta.url)
function execute(file,imports={}) {const code=ts.transpileModule(readFileSync(new URL(file,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;const module={exports:{}};new Function('require','module','exports',code)(name=>imports[name]||require(name),module,module.exports);return module.exports}
const errors=execute('../src/diagnostics/frontendErrors.ts')
const nav=execute('../src/router/navigation.ts',{vue:Vue})
const flush=async()=>{for(let i=0;i<3;i++)await new Promise(resolve=>setImmediate(resolve))}
function fixture(extra={}) {const calls=[];const options={clientCommit:'a'.repeat(40),endpoint:'/api/diagnostics/frontend-errors',token:()=> 'private-token',context:()=>({page_path:'/my-cpo?secret=private',target_path:'/ad-allocation?token=private'}),fetch:async(url,init)=>{calls.push({url,...init});return {ok:true}},...extra};return {calls,reporter:errors.createFrontendReporter(options)}}
test('report stores only safe location/classification and pinned browser version',async()=>{
 const {calls,reporter}=fixture();const e=new TypeError('deactivate is not a function password=private')
 e.stack='TypeError: password=private\n at x (https://secret-host/assets/app.js?token=private:42:7)'
 assert.equal(await reporter.report('vue_error',e),true)
 const body=JSON.parse(calls[0].body);assert.equal(body.error_code,'CACHE_LIFECYCLE_ERROR');assert.equal(body.page_path,'/my-cpo');assert.equal(body.target_path,'/ad-allocation');assert.equal(body.client_commit,'a'.repeat(40));assert.deepEqual(body.stack,[{file:'/assets/app.js',line:42,column:7}]);assert.equal(calls[0].headers.Authorization,'Bearer private-token');assert.ok(!calls[0].body.includes('private'));assert.ok(!calls[0].body.includes('secret-host'))
 reporter.dispose()
})
test('duplicate storm and distinct storm are bounded; failures never reject or recurse',async()=>{
 let now=1000;const f=fixture({now:()=>now})
 for(let i=0;i<50;i++)await f.reporter.report('vue_error',new Error('same'))
 assert.equal(f.calls.length,1)
 for(let i=0;i<50;i++){const e=new Error('same');e.stack=`at https://host/assets/app.js:${i+1}:1`;await f.reporter.report('vue_error',e)}
 assert.equal(f.calls.length,30)
 now+=60001;await f.reporter.report('vue_error',new Error('same'));assert.equal(f.calls.length,31)
 const offline=fixture({fetch:async()=>{throw new Error('offline')}});assert.equal(await offline.reporter.report('javascript_error',new Error('x')),false)
 const anon=fixture({token:()=>null});assert.equal(await anon.reporter.report('javascript_error',new Error('x')),false);assert.equal(anon.calls.length,0)
 f.reporter.dispose();offline.reporter.dispose();anon.reporter.dispose()
})
test('Vue, native script and unhandled-promise handlers submit events and can be removed',async()=>{
 const browser=new EventTarget(),app={config:{}},seen=[];const reporter={report:async(kind,error,extra)=>{seen.push({kind,error,extra});return true},dispose(){}}
 const old={ErrorEvent:globalThis.ErrorEvent,HTMLScriptElement:globalThis.HTMLScriptElement,HTMLLinkElement:globalThis.HTMLLinkElement}
 globalThis.ErrorEvent=class extends Event {constructor(error){super('error');this.error=error}}
 globalThis.HTMLScriptElement=class {};globalThis.HTMLLinkElement=class {}
 const original=(...args)=>{seen.push({kind:'previous'})};app.config.errorHandler=original
 try {
  const uninstall=errors.installFrontendDiagnostics(app,reporter,browser)
  app.config.errorHandler(new TypeError('render failed'),null,'render')
  browser.dispatchEvent(new ErrorEvent(new Error('runtime')))
  const promise=new Event('unhandledrejection');promise.reason=new Error('async');browser.dispatchEvent(promise)
  assert.deepEqual(seen.map(x=>x.kind),['vue_error','previous','javascript_error','unhandled_rejection'])
  uninstall();assert.equal(app.config.errorHandler,original);browser.dispatchEvent(promise);assert.equal(seen.length,4)
 } finally {Object.assign(globalThis,old)}
})
test('navigation watchdog reports only the latest unfinished attempt and clears on completion',()=>{
 const originalSet=globalThis.setTimeout,originalClear=globalThis.clearTimeout,scheduled=[],seen=[]
 globalThis.setTimeout=(fn,delay)=>{scheduled.push({fn,delay});return {unref(){}}};globalThis.clearTimeout=()=>{}
 nav.configureNavigationDiagnostics((target,duration)=>seen.push({target,duration}))
 try {
  nav.beginNavigation('/my-cpo');nav.beginNavigation('/ad-allocation?date=private')
  scheduled[0].fn();assert.equal(seen.length,0);scheduled[1].fn();assert.equal(seen[0].target,'/ad-allocation?date=private');assert.equal(scheduled[1].delay,30000);assert.match(nav.navigationState.error,/30 秒/)
  nav.finishNavigation('/ad-allocation?date=private');assert.equal(nav.navigationState.error,'');assert.equal(nav.navigationState.loading,false)
  nav.beginNavigation('/my-cpo');nav.finishNavigation('/my-cpo');scheduled[2].fn();assert.equal(seen.length,1)
 } finally {nav.configureNavigationDiagnostics();globalThis.setTimeout=originalSet;globalThis.clearTimeout=originalClear}
})
