import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from 'typescript'
const code=ts.transpileModule(readFileSync(new URL('../src/utils/codexAttribution.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText
const {confirmedShare,attributionMethod}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const value={status:'available',usedPercent:3,remainingPercent:97,confirmedPercent:3,unattributedPercent:0,members:[{userId:17,usedPercent:3,evidence:[]},{userId:18,usedPercent:0,evidence:[]}]}
test('Pan gets three percentage points of total capacity, not 100 percent of users',()=>{
  assert.equal(confirmedShare(value,17,true),3)
  assert.equal(confirmedShare(value,18,true),0)
})
test('additional official consumption is never spread by historical token counts',()=>{
  assert.equal(confirmedShare({...value,usedPercent:5,remainingPercent:95,unattributedPercent:2},17,true),3)
})
test('stale, conflicting and unknown identities do not claim a current percentage',()=>{
  assert.equal(confirmedShare(value,17,false),null)
  assert.equal(confirmedShare({...value,status:'reconciliation-required'},17,true),null)
  assert.equal(confirmedShare(value,999,true),null)
})

test('automatic inference is labelled separately from owner confirmation',()=>{
  const automatic={...value,members:[{userId:17,usedPercent:5,evidence:[{method:'observed-exclusive-period'}]}]}
  assert.equal(attributionMethod(automatic,17),'单一来源自动推定')
  automatic.members[0].evidence.push({method:'owner-confirmed'})
  assert.equal(attributionMethod(automatic,17),'本人确认＋自动推定')
  assert.equal(attributionMethod(automatic,18),'暂无已归属消耗')
})
