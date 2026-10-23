import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import ts from 'typescript'
import * as Vue from 'vue'
import * as Router from 'vue-router'

const require = createRequire(import.meta.url)
function execute(file, imports) {
  const source = readFileSync(new URL(file, import.meta.url), 'utf8')
  const code = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  const module = {exports:{}}
  new Function('require','module','exports',code)(name => {
    if (name in imports) return imports[name]
    if (name.endsWith('.vue')) return {__esModule:true,default:{render:()=>null}}
    return require(name)
  }, module, module.exports)
  return module.exports
}
const nav = execute('../src/router/navigation.ts', {vue:Vue})
const deferred = () => {let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
const flush = async () => {for(let i=0;i<5;i++) await new Promise(resolve=>setImmediate(resolve))}

test('cancelled earlier navigation cannot hide the latest pending destination', () => {
  nav.beginNavigation('/reports')
  nav.beginNavigation('/codex-devices')
  nav.finishNavigation('/reports')
  assert.equal(nav.navigationState.loading,true)
  assert.equal(nav.isNavigatingAway('/operator-cpo'),true)
  nav.finishNavigation('/codex-devices')
  assert.equal(nav.navigationState.loading,false)
})

test('old module failure refreshes the intended URL once, including its filters', () => {
  const values=new Map(),replacements=[]
  const browser={sessionStorage:{getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)},location:{replace:url=>replacements.push(url)}}
  const error=new TypeError('Failed to fetch dynamically imported module: /assets/old.js')
  assert.equal(nav.recoverNavigation(error,'/reports?date=2026-10-20',browser,100000),true)
  assert.deepEqual(replacements,['/reports?date=2026-10-20'])
  assert.equal(nav.recoverNavigation(error,'/reports',browser,100001),false)
  assert.equal(nav.recoverNavigation(error,'/codex-devices',browser,100002),false)
  assert.equal(nav.recoverNavigation(new Error('application failed'),'/reports',browser,200000),false)
  assert.equal(nav.recoverNavigation(error,'//other.example',browser,200000),false)
})

test('blocked storage cannot cause automatic reload loops', () => {
  const browser={sessionStorage:{getItem(){throw new Error('blocked')}},location:{replace(){assert.fail('must not reload')}}}
  assert.equal(nav.recoverNavigation(new Error('Unable to preload CSS for /assets/old.css'),'/reports',browser),false)
})

test('real router exposes pending lazy navigation immediately and settles after import', async () => {
  const lazy=deferred()
  const frame=globalThis.requestAnimationFrame
  globalThis.requestAnimationFrame=callback=>{callback();return 0}
  const routerModule=execute('../src/router/index.ts', {
    'vue-router':{...Router,createWebHistory:Router.createMemoryHistory},vue:Vue,
    './navigation':nav,
    '../stores/session':{useSessionStore:()=>({token:'fixture',user:{roleCode:'super_admin'},ensureUser:async()=>true})},
    '../diagnostics/permissions':{canViewDiagnostics:()=>true},
    '../diagnostics/browserTrace':{enterPage:()=>'',completePageRender(){}},
    // Preserve the asynchronous import boundary through TS's CommonJS wrapper.
    '../views/ReportsView.vue':Object.assign(lazy.promise,{__esModule:true}),
  })
  const router=routerModule.default
  try {
    await router.push('/operator-cpo')
    routerModule.prefetchRoute('/reports')
    await flush()
    assert.equal(router.currentRoute.value.path,'/operator-cpo','preloading code must not navigate')
    assert.equal(nav.navigationState.loading,false,'preloading must not block the current page')
    const pending=router.push('/reports')
    await flush()
    assert.equal(router.currentRoute.value.path,'/operator-cpo')
    assert.equal(nav.navigationState.target,'/reports')
    assert.equal(nav.navigationState.loading,true)
    lazy.resolve({__esModule:true,default:{render:()=>null}})
    await pending
    assert.equal(router.currentRoute.value.path,'/reports')
    assert.equal(nav.navigationState.loading,false)
  } finally {globalThis.requestAnimationFrame=frame}
})
