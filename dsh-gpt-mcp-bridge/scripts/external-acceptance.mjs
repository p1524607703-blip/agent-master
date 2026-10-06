// Deterministic protocol acceptance against REAL DSH; this is not an LLM test.
// Fixture creation and independent verification happen here. All repair actions
// are submitted as model decisions and executed ONLY by DSH's native tools.
import assert from 'node:assert/strict'
import { mkdtemp, writeFile, readFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'

const client = new Client({ name: 'dsh-external-protocol-acceptance', version: '0.5.0' })
let task
const call = async (name, args = {}) => {
  const result = await client.callTool({ name, arguments: args }, undefined, { timeout: 25000 })
  const value = JSON.parse(result.content[0].text)
  if (result.isError) throw new Error(JSON.stringify(value))
  return value
}
const fullRequest = async (taskId, item) => {
  if (item.request) return item.request
  let content = ''
  let offset = 0
  for (;;) {
    const page = await call('agent_model_request', { task_id: taskId, model_request_id: item.model_request_id,
      mode: 'full', offset, limit: 100000 })
    content += page.content
    if (!page.hasMore) return JSON.parse(content)
    offset = page.nextOffset
  }
}
try {
  await client.connect(new StreamableHTTPClientTransport(new URL(process.env.DSH_GPT_MCP_URL ?? 'http://127.0.0.1:3080/mcp')))
  const info = await call('bridge_info')
  assert.equal(info.modelDriver, 'external')
  assert.equal(info.modelApiEnabled, false)
  const directory = await mkdtemp(path.join(tmpdir(), 'dsh-native-external-'))
  const testSource = "import assert from 'node:assert/strict'; import {sum} from './sum.mjs'; assert.equal(sum([1,2,3]),6); assert.equal(sum([]),0); console.log('native-test-passed');\n"
  await writeFile(path.join(directory, 'sum.mjs'), 'export const sum = xs => xs.reduce((a,b) => a-b, 0)\n')
  await writeFile(path.join(directory, 'sum.test.mjs'), testSource)
  await writeFile(path.join(directory, 'AGENTS.md'), 'Only access this fixture directory. Do not modify the test. No network or subagents.\n')
  assert.throws(() => execFileSync(process.execPath, ['sum.test.mjs'], { cwd: directory, stdio: 'pipe' }))
  task = await call('agent_task_start', { request_id: `native-protocol-${randomUUID()}`, cwd: directory,
    prompt: 'Protocol fixture: inspect instructions/source/test, reproduce test failure, fix sum.mjs without modifying the test, run the unchanged test and report.', timeout_ms: 60000 })
  const tool = (id, name, args) => ({ id, name, arguments: JSON.stringify(args) })
  const decisions = [
    { tool_calls: [tool('instructions','read',{file_path:'AGENTS.md'}), tool('source','read',{file_path:'sum.mjs'}), tool('test','read',{file_path:'sum.test.mjs'}), tool('before','bash',{command:'node sum.test.mjs',description:'Observe baseline test failure',workdir:directory})] },
    { tool_calls: [tool('fix','edit',{file_path:'sum.mjs',old_string:'a-b',new_string:'a+b'})] },
    { tool_calls: [tool('after','bash',{command:'node sum.test.mjs',description:'Run unchanged test after repair',workdir:directory})] },
    { text: 'The isolated sum implementation is fixed and the unchanged test passes.' },
  ]
  let step = 0
  let lastResponse
  const deadline = Date.now() + 65000
  while (Date.now() < deadline) {
    const state = await call('agent_task_wait', { task_id: task.taskId, timeout_ms: 1000 })
    if (state.terminal) {
      assert.equal(state.status, 'completed', JSON.stringify(state))
      assert.equal(state.summary.steps, 4)
      assert.equal(state.summary.toolCalls, 6)
      assert.equal(state.summary.toolResults, 6)
      assert.equal(step, 4)
      assert.equal(await readFile(path.join(directory, 'sum.test.mjs'), 'utf8'), testSource)
      assert.match(execFileSync(process.execPath, ['sum.test.mjs'], { cwd: directory, encoding: 'utf8' }), /native-test-passed/)
      const replay = await call('agent_model_respond', lastResponse)
      assert.equal(replay.duplicate, true)
      const finalInfo = await call('bridge_info')
      assert.equal(finalInfo.blockedModelApiCalls, info.blockedModelApiCalls)
      console.log(JSON.stringify({ ok: true, kind: 'deterministic-native-DSH-protocol-test', cloudChatGPTVerified: false,
        directory, taskId: task.taskId, sessionId: task.sessionId, summary: state.summary,
        modelApiEnabled: finalInfo.modelApiEnabled, duplicateResponseDidNotRepeatTools: true }, null, 2))
      task = undefined
      break
    }
    for (const request of state.modelRequests ?? []) {
      const modelRequest = await fullRequest(task.taskId, request)
      assert.equal(modelRequest.provider, 'chatgpt-tunnel')
      let decision
      if (request.purpose === 'session-title') decision = { text: 'Verify native external driver' }
      else {
        assert.ok(step < decisions.length, 'unexpected extra DSH step')
        const toolResults = modelRequest.messages.filter(message => message.source?.kind === 'tool')
        if (step === 1) assert.match(JSON.stringify(toolResults), /exit code: 1/)
        if (step === 3) assert.match(JSON.stringify(toolResults.at(-1)), /native-test-passed/)
        decision = decisions[step++]
        for (const requested of decision.tool_calls ?? []) assert.ok(request.toolNames.includes(requested.name))
      }
      const response = { task_id: task.taskId, model_request_id: request.model_request_id, response_id: `decision-${randomUUID()}`, ...decision }
      await call('agent_model_respond', response)
      if (request.purpose !== 'session-title') lastResponse = response
    }
  }
  if (task) throw new Error('Native external-driver acceptance timed out')
} finally {
  if (task) {
    await call('agent_task_cancel', { task_id: task.taskId }).catch(() => {})
    await call('agent_task_wait', { task_id: task.taskId, timeout_ms: 20000 }).catch(() => {})
  }
  await client.close()
}
