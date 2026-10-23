import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import ts from 'typescript'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'

const require=createRequire(import.meta.url)
const source=readFileSync(new URL('../src/components/PendingGroupExpenses.vue',import.meta.url),'utf8')
const descriptor=parse(source).descriptor
const script=compileScript(descriptor,{id:'pending-test',inlineTemplate:true}).content
const compiled=ts.transpileModule(script,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
const module={exports:{}}
new Function('require','module','exports',compiled)(require,module,module.exports)
const component=module.exports.default
const expense=(operatorName,group,campaignName,spend=10)=>({
  operatorName,group,campaignName,spend,date:'2026-01-01',account:'synthetic-store',campaignId:campaignName,
  reason:'MULTIPLE_NAMED_PRODUCTS',status:'GROUP_KNOWN_PRODUCT_PENDING',
})
const entries=[expense('子娟','ZJ1','synthetic-zj'),expense('珍凤','ZF1','synthetic-zf')]
const render=props=>renderToString(createSSRApp(component,props))

test('scoped ledger only renders authorized group and explains fee is already included',async()=>{
  const html=await render({entries,total:10,operatorName:'子娟'})
  assert.match(html,/synthetic-zj/)
  assert.doesNotMatch(html,/synthetic-zf|ZF1|珍凤/)
  assert.match(html,/已计入本组总费用/)
  assert.match(html,/尚未拆到具体款式；最终 CPO 待确认/)
  assert.match(html,/请勿重复加总/)
  assert.match(html,/命中多个款式，待确认分配规则/)
})

test('management can explicitly show all groups using authoritative pending subtotal',async()=>{
  const html=await render({entries,total:12.34,allGroups:true})
  assert.match(html,/synthetic-zj/);assert.match(html,/synthetic-zf/)
  assert.match(html,/组内待分摊费用：\$12\.34/)
  assert.doesNotMatch(html,/组内待分摊费用：\$20\.00/,'never recalculate or add the subtotal into total expenses')
  assert.match(html,/已计入各运营组总费用/)
})

test('no pending amount, unknown scope, or unsupported entry never exposes ledger',async()=>{
  for(const props of [
    {entries,total:0,operatorName:'子娟'},
    {entries,total:10},
    {entries,total:10,operatorName:'爱菊'},
    {entries:[],total:10,operatorName:'子娟'},
    {entries:[{...entries[0],status:'OTHER'}],total:10,operatorName:'子娟'},
  ]) assert.doesNotMatch(await render(props),/组内待分摊费用|synthetic-/)
})

test('alias uncertainty has its own explanation without guessing a product',async()=>{
  const html=await render({entries:[{...entries[0],reason:'CONFIRMED_ALIAS_REQUIRED'}],total:10,operatorName:'子娟'})
  assert.match(html,/组合名称待确认款式映射/)
  assert.doesNotMatch(html,/knownNameCandidates|费用承担款/)
})
