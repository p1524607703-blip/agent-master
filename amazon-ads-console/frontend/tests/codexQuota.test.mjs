import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/utils/codexQuota.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText
const {quotaDisplay} = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)
const now = Date.now()
const window = minutes => ({usedPercent:27,remainingPercent:73,windowDurationMins:minutes,resetsAt:1900000000})
const fixture = (primary=window(300),secondary=window(10080)) => ({status:'available',capturedAt:new Date(now).toISOString(),primary,secondary})

test('Plus retains both actual windows', () => {
  assert.deepEqual(quotaDisplay(fixture(),now,false).windows.map(w=>w.title),['5小时额度','每周额度'])
})
test('Pro weekly primary produces one weekly card, no fake five-hour card', () => {
  const view=quotaDisplay({...fixture(window(10080),null),planType:'prolite'},now,false)
  assert.equal(view.state,'采集正常')
  assert.equal(view.windows.length,1)
  assert.equal(view.windows[0].title,'每周额度')
  assert.equal(view.windows[0].remainingPercent,73)
})
test('window semantics follow duration even after positions change', () => {
  assert.deepEqual(quotaDisplay(fixture(null,window(10080)),now,false).windows.map(w=>w.title),['每周额度'])
  assert.equal(quotaDisplay(fixture(window(60),null),now,false).windows[0].title,'60分钟额度')
})
test('expired, failed, future or disconnected snapshots never retain percentages', () => {
  for (const [value,disconnected] of [[fixture(),true],[{...fixture(),status:'unavailable'},false],[{...fixture(),capturedAt:new Date(now-301000).toISOString()},false],[{...fixture(),capturedAt:new Date(now+31000).toISOString()},false]]) {
    const view=quotaDisplay(value,now,disconnected)
    assert.equal(view.windows.length,0)
  }
})
test('missing windows and invalid periods are never converted to unlimited or zero', () => {
  for (const value of [fixture(null,null),fixture({...window(10080),resetsAt:1e30},null)]) {
    const view=quotaDisplay(value,now,false)
    assert.equal(view.windows.length,0)
    assert.equal(view.state,'官方未返回可展示窗口')
  }
})
