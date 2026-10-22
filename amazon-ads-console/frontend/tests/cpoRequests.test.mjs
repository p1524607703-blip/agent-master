import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createRequire } from 'node:module'
import ts from 'typescript'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as Vue from 'vue'

const require = createRequire(import.meta.url)
function execute(source, imports) {
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module = { exports:{} }
  new Function('require', 'module', 'exports', compiled)(name => name in imports ? imports[name] : require(name), module, module.exports)
  return module.exports
}
const report = execute(readFileSync(new URL('../src/api/cpoReport.ts',import.meta.url),'utf8'),{})
const deferred = () => { let resolve, reject; const promise = new Promise((a,b)=>{resolve=a;reject=b}); return {promise,resolve,reject} }
const flush = async () => { for (let n=0;n<5;n++) { await Vue.nextTick(); await new Promise(resolve=>setImmediate(resolve)) } }
const renderer = Vue.createRenderer({
  createElement:()=>({}),createText:()=>({}),createComment:()=>({}),
  insert(){},remove(){},setText(){},setElementText(){},patchProp(){},
  parentNode:()=>null,nextSibling:()=>null,
})

function mountView(filename, initial, options={}) {
  const route = Vue.reactive({ path:initial.path, params:initial.params || {}, query:initial.query || {} })
  const calls=[]
  const periods=options.periods || Promise.resolve({daily:[{value:'2026-10-19'}],weekly:[],monthly:[],latestCompleteDate:'2026-10-19'})
  const navigate = async target => {
    const match=target.path.match(/^\/operators\/(.+)$/)
    if (route.path === target.path && JSON.stringify(route.query) === JSON.stringify(target.query || {})) return
    route.path=target.path;route.params=match?{operator:decodeURIComponent(match[1])}:{};route.query=target.query || {}
    await Vue.nextTick()
  }
  const imports={
    vue:Vue,'vue-router':{useRoute:()=>route,useRouter:()=>({replace:navigate,push:navigate})},
    '../stores/session':{useSessionStore:()=>({user:{roleCode:'management',displayName:'本人',operatorCode:'ZF1'}})},
    '../api/client':{
      getJson:()=>periods,
      getJsonStrict:(path,config)=>{
        const task=deferred();calls.push({path,signal:config.signal,...task})
        config.signal.addEventListener('abort',()=>task.reject(new Error('aborted')),{once:true})
        return task.promise
      },
    },
    '../api/operatorExports':{downloadOperatorReport:()=>Promise.resolve()},
    '../api/cpoReport':report,
    '../diagnostics/pageTrace':{usePageRenderTrace(){}},
    '../diagnostics/cpoQuality':{qualityLabel:()=>''},
    'naive-ui':{NButton:{},NDatePicker:{},NSelect:{}},
  }
  for(const name of ['FullFunnelRows','CampaignCostNotes','DataSkeleton','CpoDataQuality','SbAttributionToggle','PendingGroupExpenses']) imports[`../components/${name}.vue`]={default:{}}
  const source=readFileSync(resolve('src/views',filename),'utf8')
  const descriptor=parse(source).descriptor
  const script=compileScript(descriptor,{id:filename}).content
  const component=execute(script,imports).default
  const app=renderer.createApp({...component,render:()=>null})
  const instance=app.mount({})
  return {route,calls,navigate,state:instance.$.setupState,unmount:()=>app.unmount()}
}

const response = mode => ({sbAttributionMode:mode,data_date:'2026-10-19',operator:'珍凤',operators:[{name:'珍凤'}],products:[{code:'TEST'}],summary:{},detailSummary:{}})

test('canonical operator and default SB URL only fetch once; switching aborts prior mode',async()=>{
  const view=mountView('OperatorDetailView.vue',{path:'/operators/ZF',params:{operator:'ZF'},query:{period:'daily',date:'2026-10-19'}})
  try {
    await flush();assert.equal(view.calls.length,1)
    assert.match(view.calls[0].path,/sb_attribution_mode=name/)
    view.calls[0].resolve(response('name'));await flush()
    assert.equal(view.route.params.operator,'珍凤');assert.equal(view.calls.length,1)
    await view.navigate({path:view.route.path,query:{...view.route.query,sb_attribution_mode:'asin'}});await flush()
    assert.equal(view.calls.length,2)
    await view.navigate({path:view.route.path,query:{...view.route.query,sb_attribution_mode:'name'}});await flush()
    assert.equal(view.calls.length,3);assert.equal(view.calls[1].signal.aborted,true)
    view.calls[2].resolve(response('name'));await flush()
    assert.equal(view.state.detail.sbAttributionMode,'name');assert.equal(view.state.loading,false)
  } finally {view.unmount()}
})

for(const filename of ['OperatorCpoView.vue','MyCpoView.vue']) {
  test(`${filename}: explicit date loads alongside choices; failed other mode clears old amounts`,async()=>{
    const choices=deferred()
    const view=mountView(filename,{path:filename==='MyCpoView.vue'?'/my-cpo':'/operator-cpo',query:{period:'daily',date:'2026-10-19'}},{periods:choices.promise})
    try {
      await flush();assert.equal(view.calls.length,1,'report must not wait for date choices')
      view.calls[0].resolve(response('name'));await flush();assert.equal(view.calls.length,1)
      await view.navigate({path:view.route.path,query:{...view.route.query,sb_attribution_mode:'asin'}});await flush()
      view.calls[1].reject(new Error('network failed'));await flush()
      assert.equal(view.state.data.operators.length,0)
      assert.match(view.state.loadError,/network failed/)
      choices.resolve({daily:[],weekly:[],monthly:[]});await flush()
    } finally {view.unmount()}
  })
}

test('leaving while waiting for latest date never starts a report request',async()=>{
  const choices=deferred()
  const view=mountView('OperatorDetailView.vue',{path:'/operators/ZF',params:{operator:'ZF'},query:{}},{periods:choices.promise})
  view.unmount()
  choices.resolve({daily:[{value:'2026-10-19'}],weekly:[],monthly:[],latestCompleteDate:'2026-10-19'})
  await flush();assert.equal(view.calls.length,0)
})

test('request gate preserves both modes and cancels stale work',()=>{
  const gate=new report.CpoRequestGate()
  const first=gate.start('name');assert.ok(first)
  assert.equal(gate.start('name'),null)
  const second=gate.start('asin');assert.equal(first.signal.aborted,true);assert.equal(first.current(),false)
  second.finish('canonical-asin');assert.equal(gate.start('canonical-asin'),null)
  gate.cancel();assert.ok(gate.start('canonical-asin'),'returning to a kept-alive page refreshes the report')
  gate.cancel()
  assert.ok(gate.start('canonical-asin',true));gate.cancel()
})
