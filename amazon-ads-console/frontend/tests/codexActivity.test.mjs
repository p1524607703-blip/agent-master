import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from 'typescript'
const code = ts.transpileModule(readFileSync(new URL('../src/utils/codexActivity.ts', import.meta.url), 'utf8'), {compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText
const {activityState, activityLabels} = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const now = Date.parse('2026-10-22T10:00:00Z')
const device = {revoked:false, activityStatus:'recent', activeRequests:0, lastActivityAt:new Date(now-60000).toISOString()}

test('a server request is active without client heartbeat or process reports', () => {
  assert.equal(activityState({...device, activityStatus:'active', activeRequests:2, lastActivityAt:null}, now, true), 'active')
  assert.equal(activityLabels.active, '正在使用')
})
test('recent requests expire locally at five minutes without another response', () => {
  assert.equal(activityState(device, now, true), 'recent')
  assert.equal(activityState(device, now+240000, true), 'recent')
  assert.equal(activityState(device, now+241000, true), 'idle')
  assert.equal(activityLabels.idle, '暂无近期请求')
})
test('refresh failures, missing server fields and invalid timestamps never show green', () => {
  assert.equal(activityState({...device, activityStatus:'active', activeRequests:1}, now, false), 'unknown')
  assert.equal(activityState({...device, activityStatus:undefined}, now, true), 'unknown')
  assert.equal(activityState({...device, lastActivityAt:'bad'}, now, true), 'unknown')
  assert.equal(activityState({...device, lastActivityAt:new Date(now+31000).toISOString()}, now, true), 'unknown')
})
test('heartbeat alone does not indicate usage and revoked credentials stay disabled', () => {
  assert.equal(activityState({...device, activityStatus:'idle', lastActivityAt:null, agentOnline:true, codexRunning:true}, now, true), 'idle')
  assert.equal(activityState({...device, revoked:true, activityStatus:'active', activeRequests:3}, now, true), 'revoked')
})
