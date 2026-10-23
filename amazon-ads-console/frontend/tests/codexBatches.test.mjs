import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import ts from 'typescript'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'

const require=createRequire(import.meta.url)
const transpile=source=>ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
function load(code,resolver=require){const module={exports:{}};new Function('require','module','exports',transpile(code))(resolver,module,module.exports);return module.exports}
const utils=load(readFileSync(new URL('../src/utils/codexAttribution.ts',import.meta.url),'utf8'))
const descriptor=parse(readFileSync(new URL('../src/components/CodexQuotaBatches.vue',import.meta.url),'utf8')).descriptor
const component=load(compileScript(descriptor,{id:'quota-batches-test',inlineTemplate:true}).content,
  name=>name.includes('codexAttribution')?utils:name.includes('/api/client')?{getJsonStrict:()=>{throw Error('No network in render test')}}:require(name)).default
const now=new Date().toISOString()
const batch=(status,revision=2)=>({batchId:'fixture-batch',groupId:'fixture-group',quotaCapturedAt:now,points:1,
  status,revision,updatedAt:now,confidence:'low',unattributedPercent:status==='waiting'?1:0,
  startedAt:now,throughAt:now,observeUntil:now,waitingDeviceIds:[]})
const value=rows=>({provisionalPercent:1,batchMonitoring:{status:'active',cutoverAt:now,capturedAt:now,
  pendingBatchPercent:0,recalculationCount:2,observationSeconds:1800,latestBatches:rows}})
const render=(v,fresh=true)=>renderToString(createSSRApp(component,{value:v,fresh}))

test('provisional, waiting and revised estimates stay visibly distinct',async()=>{
  const html=await render(value([batch('provisional'),batch('waiting',3),batch('observed-estimate')]))
  assert.match(html,/暂估 · 自动回算/)
  assert.match(html,/等待计量 · 待归属/)
  assert.match(html,/观察后估算 · 可修订/)
  assert.match(html,/v3/)
  assert.match(html,/暂估已包含在人员额度中，请勿再次相加/)
  assert.match(html,/30 分钟/)
})
test('empty new mechanism preserves prior Token history without inventing batches',async()=>{
  const html=await render(value([]))
  assert.match(html,/等待下一次官方额度增量/)
  assert.match(html,/此前已计量 Token 保持显示/)
})
test('stale batch figures are marked historical instead of reporting current percentages',async()=>{
  const html=await render(value([batch('provisional')]),false)
  assert.match(html,/数据暂不可确认/)
  assert.match(html,/—/)
})
test('member evidence labels preserve manual and legacy records alongside revisable estimates',()=>{
  const v={members:[{userId:1,evidence:[{method:'owner-confirmed'},{method:'observed-token-weighted-interval'},
    {method:'provisional-token-weighted-batch'}]}]}
  assert.equal(utils.attributionMethod(v,1),'本人确认＋旧版并发估算＋批次暂估（可自动回算）')
})
