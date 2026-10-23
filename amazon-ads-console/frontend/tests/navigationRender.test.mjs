import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import ts from 'typescript'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as Vue from 'vue'
import * as Router from 'vue-router'

const require = createRequire(import.meta.url)
function execute(source, imports) {
  const code = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  const module = {exports:{}}
  new Function('require','module','exports',code)(name => name in imports ? imports[name] : require(name),module,module.exports)
  return module.exports
}
function makeRenderer() {
  const node = (kind,text='') => ({kind,text,children:[],parent:null})
  const remove = child => { if(child.parent) {const siblings=child.parent.children;siblings.splice(siblings.indexOf(child),1);child.parent=null} }
  return Vue.createRenderer({
    createElement:kind=>node(kind),createText:text=>node('text',text),createComment:text=>node('comment',text),
    insert(child,parent,anchor=null) {remove(child);const i=anchor?parent.children.indexOf(anchor):-1;parent.children.splice(i<0?parent.children.length:i,0,child);child.parent=parent},
    remove,setText:(node,text)=>{node.text=text},setElementText:(node,text)=>{node.text=text;node.children=[]},patchProp(){},
    parentNode:node=>node.parent,nextSibling:node=>node.parent?.children[node.parent.children.indexOf(node)+1] || null,
  })
}
const visibleText = node => node.kind==='comment' ? '' : node.text + node.children.map(visibleText).join('')

test('real App keeps content mounted when switching repeatedly between cached CPO and uncached pages',async()=>{
  const navigation=execute(readFileSync(new URL('../src/router/navigation.ts',import.meta.url),'utf8'),{vue:Vue})
  const mounts={},unmounts={},errors=[]
  const page = name => ({name,setup(){mounts[name]=(mounts[name]||0)+1;Vue.onBeforeUnmount(()=>unmounts[name]=(unmounts[name]||0)+1);return()=>Vue.h('main',name)}})
  const router=Router.createRouter({history:Router.createMemoryHistory(),routes:[
    {path:'/my-cpo',component:page('MyCpoView'),meta:{keepAlive:true}},
    {path:'/operator-cpo',component:page('OperatorCpoView'),meta:{keepAlive:true}},
    {path:'/ad-allocation',component:page('AllocationView')},
    {path:'/data-changes',component:page('DataChangesView')},
  ]})
  router.beforeEach(to=>{navigation.beginNavigation(to.fullPath)})
  router.afterEach(to=>{navigation.finishNavigation(to.fullPath)})
  const descriptor=parse(readFileSync(new URL('../src/App.vue',import.meta.url),'utf8')).descriptor
  const source=compileScript(descriptor,{id:'app-navigation-regression',inlineTemplate:true}).content
  const empty={render:()=>null}
  const App=execute(source,{vue:Vue,'vue-router':Router,'./router/navigation':navigation,
    './components/AppSidebar.vue':empty,'./components/AppTopbar.vue':empty,
    'naive-ui':{NConfigProvider:{props:['themeOverrides'],setup:(_,context)=>()=>context.slots.default?.()}},
  }).default
  await router.push('/ad-allocation')
  const root={kind:'root',text:'',children:[],parent:null}
  const app=makeRenderer().createApp(App)
  app.use(router);app.config.errorHandler=error=>errors.push(error)
  app.mount(root)
  try {
    for(let cycle=0;cycle<12;cycle++) {
      for(const [path,name] of [['/my-cpo','MyCpoView'],['/operator-cpo','OperatorCpoView'],['/ad-allocation','AllocationView'],['/data-changes','DataChangesView']]) {
        await router.push(path);await Vue.nextTick()
        assert.deepEqual(errors.map(error=>error.message),[],`${path}: page rendering must not throw`)
        assert.equal(visibleText(root),name,`${path}: destination content must be visible`)
        assert.equal(navigation.navigationState.loading,false)
      }
    }
    assert.equal(mounts.MyCpoView,1,'personal CPO retains its cached component')
    assert.equal(mounts.OperatorCpoView,1,'team CPO retains its cached component')
    assert.ok(unmounts.AllocationView>=12,'allocation pages leave the cache and release resources')
    await router.push('/my-cpo?period=monthly&date=2026-09-01');await Vue.nextTick()
    assert.equal(visibleText(root),'MyCpoView')
    assert.equal(mounts.MyCpoView,1,'query changes do not discard cached CPO state')
  } finally {app.unmount()}
})
