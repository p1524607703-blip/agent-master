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
const access = execute('../src/router/access.ts', {})
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
    './access':access,
    '../diagnostics/browserTrace':{enterPage:()=>'',completePageRender(){}},
    // Preserve the asynchronous import boundary through TS's CommonJS wrapper.
    '../views/DataMaintenanceView.vue':Object.assign(lazy.promise,{__esModule:true}),
  })
  const router=routerModule.default
  try {
    await router.push('/operator-cpo')
    routerModule.prefetchRoute('/data-maintenance')
    await flush()
    assert.equal(router.currentRoute.value.path,'/operator-cpo','preloading code must not navigate')
    assert.equal(nav.navigationState.loading,false,'preloading must not block the current page')
    const pending=router.push('/data-maintenance')
    await flush()
    assert.equal(router.currentRoute.value.path,'/operator-cpo')
    assert.equal(nav.navigationState.target,'/data-maintenance')
    assert.equal(nav.navigationState.loading,true)
    lazy.resolve({__esModule:true,default:{render:()=>null}})
    await pending
    assert.equal(router.currentRoute.value.path,'/data-maintenance')
    assert.equal(nav.navigationState.loading,false)
  } finally {globalThis.requestAnimationFrame=frame}
})


test('role menus have three business entries and reserve system entries for super admins', () => {
  const paths = role => access.navigationFor(role).flatMap(group => group.items.map(([path]) => path))
  assert.deepEqual(paths('management'), ['/operator-cpo', '/ad-allocation', '/product-mappings'])
  assert.equal(paths('super_admin').length, 6)
  assert.deepEqual(paths('operator'), ['/my-cpo', '/operator-cpo', '/ad-allocation', '/data-changes'])
  for (const role of ['management','operator','viewer',null]) {
    for (const path of ['/codex-devices','/diagnostics','/data-maintenance']) assert.equal(access.canAccessRoute(role,path), false)
  }
  assert.equal(access.canAccessRoute('management','/data-changes'), true)
  assert.equal(access.canAccessRoute('operator','/data-changes'), true)
  assert.equal(access.canAccessRoute('management','/operators/ZF'), true)
  assert.deepEqual(paths('viewer'), [])
})

test('real router rejects direct system links and retires old bookmarks for each role', async () => {
  const frame=globalThis.requestAnimationFrame
  globalThis.requestAnimationFrame=callback=>{callback();return 0}
  try {
    for (const role of ['management','operator','super_admin']) {
      const routerModule=execute('../src/router/index.ts', {
        'vue-router':{...Router,createWebHistory:Router.createMemoryHistory},vue:Vue,
        './navigation':nav,'./access':access,
        '../stores/session':{useSessionStore:()=>({token:'fixture',user:{roleCode:role},ensureUser:async()=>true})},
        '../diagnostics/browserTrace':{enterPage:()=>'',completePageRender(){}},
      })
      const router=routerModule.default
      for (const path of ['/dashboard','/issues','/rules','/products','/ad-types','/unknown']) {
        await router.push(path)
        assert.equal(router.currentRoute.value.path,access.homeFor(role))
      }
      for (const path of ['/codex-devices','/diagnostics','/data-maintenance']) {
        await router.push(path)
        assert.equal(router.currentRoute.value.path,role==='super_admin'?path:access.homeFor(role))
      }
      await router.push('/reports')
      assert.equal(router.currentRoute.value.path,role==='super_admin'?'/data-maintenance':access.homeFor(role))
      await router.push('/cpo-jobs')
      if(role==='super_admin') assert.equal(router.currentRoute.value.query.tab,'imports')
      else assert.equal(router.currentRoute.value.path,access.homeFor(role))
      await router.push('/data-changes')
      assert.equal(router.currentRoute.value.path,'/data-changes')
    }
  } finally {globalThis.requestAnimationFrame=frame}
})
