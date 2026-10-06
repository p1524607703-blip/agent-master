import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'
import { apply } from '../src/index.js'

test('HTTP tool discovery exposes orchestration only; tasks survive client disconnect', async t => {
  const routes = new Map()
  const cleanups = []
  const events = []
  let finish
  let idle = Promise.resolve()
  let promptCount = 0
  const agent = {
    status: 'idle', session: {}, whenIdle: () => idle,
    cancel() { finish?.('aborted') },
  }
  const ctx = {
    webServer: { host: '127.0.0.1', register(route) { routes.set(route.path, route.handler); return () => routes.delete(route.path) } },
    logger: { info() {}, warn() {} }, permissionPresets: { set() {} },
    effect(fn) { cleanups.push(fn()) },
    sessionQuery: { async readSession() { return { events } } },
    sessionController: {
      async create({ sessionId }) { return { sessionId } },
      async resolveAgent() { return { agent } },
      async prompt(_request, signal) {
        signal.throwIfAborted()
        promptCount++
        agent.status = 'running'
        idle = new Promise(resolve => { finish = kind => {
          events.push({ seq: events.length, type: 'turn/end', data: { reason: { kind } } })
          agent.status = 'idle'
          resolve()
        } })
        return { accepted: true }
      },
    },
  }
  const directory = await mkdtemp(path.join(tmpdir(), 'dsh-http-test-'))
  apply(ctx, { taskStateDir: directory, workspaceRoot: directory, modelDriver: 'api' })
  const http = createServer((req, res) => routes.get(req.url)?.(req, res))
  await new Promise(resolve => http.listen(0, '127.0.0.1', resolve))
  t.after(async () => {
    for (const cleanup of cleanups) await cleanup()
    http.closeAllConnections()
    await new Promise(resolve => http.close(resolve))
  })
  const endpoint = new URL(`http://127.0.0.1:${http.address().port}/mcp`)
  const connect = async () => {
    const client = new Client({ name: 'test', version: '1.0.0' })
    await client.connect(new StreamableHTTPClientTransport(endpoint))
    return client
  }
  const parse = response => {
    assert.ok(!response.isError, JSON.stringify(response))
    return JSON.parse(response.content[0].text)
  }
  const client = await connect()
  const names = (await client.listTools()).tools.map(tool => tool.name)
  assert.ok(names.includes('agent_task_start'))
  assert.ok(names.includes('bridge_self_test'))
  assert.ok(names.includes('harness_run'))
  assert.ok(names.includes('harness_read_session'))
  for (const bypass of ['fs_read', 'fs_write', 'shell_exec', 'process_start', 'git_commit', 'harness_prompt', 'harness_create_session']) assert.ok(!names.includes(bypass), bypass)
  const rejected = await client.callTool({ name: 'shell_exec', arguments: { command: 'exit 1' } })
  assert.equal(rejected.isError, true)
  const info = parse(await client.callTool({ name: 'bridge_info', arguments: {} }))
  assert.equal(info.executionOwner, 'DSH Agent Loop')
  assert.deepEqual(info.registeredTools, [...names].sort())
  assert.match(info.registryVersion, /^[a-f0-9]{16}$/)
  assert.equal(info.directToolsAvailable, false)
  const selfTest = parse(await client.callTool({ name: 'bridge_self_test', arguments: {} }))
  assert.equal(selfTest.ok, true)
  assert.equal(selfTest.executionVerified, false)
  assert.equal(selfTest.registryVersion, info.registryVersion)
  const task = parse(await client.callTool({ name: 'agent_task_start', arguments: { request_id: 'http-retry', prompt: 'test' } }))
  await client.close()
  const next = await connect()
  t.after(() => next.close())
  const retry = parse(await next.callTool({ name: 'agent_task_start', arguments: { request_id: 'http-retry', prompt: 'test' } }))
  assert.equal(retry.taskId, task.taskId)
  const pending = parse(await next.callTool({ name: 'harness_wait', arguments: { session_id: task.sessionId, timeout_ms: 10 } }))
  assert.equal(pending.terminal, false)
  assert.equal(promptCount, 1)
  finish('completed')
  const complete = parse(await next.callTool({ name: 'agent_task_wait', arguments: { task_id: task.taskId, timeout_ms: 100 } }))
  assert.equal(complete.status, 'completed')
  assert.equal(complete.summary.endReason.kind, 'completed')
})
