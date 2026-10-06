import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { tmpdir } from 'node:os'
import { ExternalDriver, EXTERNAL_MODEL, EXTERNAL_PROVIDER } from '../src/external-driver.js'

async function fixture(t, overrides = {}) {
  const directory = await mkdtemp(path.join(tmpdir(), 'dsh-external-test-'))
  const driver = new ExternalDriver({}, { taskStateDir: directory, maxModelRequestChars: 100000, maxInlineModelChars: 10000, ...overrides })
  driver.tasks = { records: new Map([['task', { taskId: 'task', sessionId: 'session', status: 'running', modelDriver: 'external' }]]) }
  t.after(() => driver.close())
  const controller = new AbortController()
  const options = { provider: EXTERNAL_PROVIDER, model: EXTERNAL_MODEL, sessionId: 'session', signal: controller.signal,
    system: overrides.system ?? 'Test system context', messages: [{ role: 'user', content: [{ type: 'text', text: 'Test' }] }],
    tools: overrides.tools ?? [{ name: 'read', description: 'read a file', parameters: { type: 'object' } }] }
  const chunks = []
  const done = (async () => { for await (const chunk of driver.stream(options)) chunks.push(chunk) })()
  done.catch(() => {})
  const watch = driver.watch('task')
  await watch.promise
  watch.dispose()
  return { driver, options, done, chunks, controller, pending: driver.forTask('task')[0] }
}

test('external decision resumes stream without invoking tools or reporting invented usage', async t => {
  const f = await fixture(t)
  const described = f.driver.describe(f.pending, true)
  assert.equal(described.state, 'NEED_MODEL_INPUT')
  assert.equal(described.request.system, f.options.system)
  assert.ok(!('signal' in described.request))
  const response = { model_request_id: f.pending.id, response_id: 'one', text: 'Inspect the file.', tool_calls: [{ id: 'call-1', name: 'read', arguments: '{"path":"file.txt"}' }] }
  const [a, b] = await Promise.all([f.driver.respond('task', response), f.driver.respond('task', response)])
  assert.equal(a.accepted, true)
  assert.equal(b.duplicate, true)
  await f.done
  assert.equal(f.chunks.filter(chunk => chunk.type === 'usage').length, 0)
  assert.deepEqual(f.chunks.at(-1), { type: 'finish', reason: { kind: 'tool-calls' } })
  assert.equal(f.chunks.filter(chunk => chunk.type === 'tool-call-delta').length, 1)
  assert.equal(f.driver.forTask('task').length, 0)
  const files = await readdir(f.driver.directory)
  assert.equal(files.length, 3)
  const catalog = JSON.parse(await readFile(path.join(f.driver.directory, 'capability-catalog.json'), 'utf8'))
  assert.deepEqual(catalog.toolNames, ['read'])
  assert.deepEqual(Object.keys(catalog).sort(), ['observedAt', 'toolNames'])
  const reopened = new ExternalDriver({}, { taskStateDir: path.dirname(f.driver.directory) })
  await reopened.ready
  assert.deepEqual(reopened.latestCatalog, catalog)
  reopened.close()
  const saved = JSON.parse(await readFile(path.join(f.driver.directory, `${f.pending.id}-response.json`), 'utf8'))
  assert.equal(saved.response.response_id, 'one')
  await assert.rejects(f.driver.respond('task', { ...response, text: 'different' }), /different response/)
})

test('unknown tool, foreign ownership, duplicate call IDs and malformed arguments are refused', async t => {
  const f = await fixture(t)
  const response = { model_request_id: f.pending.id, response_id: 'one', tool_calls: [{ id: 'call', name: 'read', arguments: '{}' }] }
  await assert.rejects(f.driver.respond('foreign', response), /foreign/)
  await assert.rejects(f.driver.respond('task', { ...response, tool_calls: [{ ...response.tool_calls[0], name: 'shell_exec' }] }), /absent/)
  await assert.rejects(f.driver.respond('task', { ...response, tool_calls: [response.tool_calls[0], response.tool_calls[0]] }), /Duplicate/)
  await assert.rejects(f.driver.respond('task', { ...response, tool_calls: [{ ...response.tool_calls[0], arguments: '[]' }] }), /JSON object/)
  await assert.rejects(f.driver.respond('task', { ...response, tool_calls: [], text: '' }))
  await f.driver.respond('task', { model_request_id: f.pending.id, response_id: 'final', text: 'Done' })
  await f.done
  assert.equal(f.chunks.at(-1).reason.kind, 'stop')
})

test('cancel invalidates pending input, late response cannot execute', async t => {
  const f = await fixture(t)
  f.controller.abort()
  await assert.rejects(f.done, /cancelled/)
  await assert.rejects(f.driver.respond('task', { model_request_id: f.pending.id, response_id: 'late', text: 'Done' }), /Stale/)
  assert.equal(f.chunks.length, 0)
})

test('request paging is exact and context is not silently truncated', async t => {
  const f = await fixture(t, { maxInlineModelChars: 0 })
  assert.equal(f.driver.describe(f.pending, true).request, undefined)
  let rendered = '', offset = 0, page
  do {
    page = await f.driver.read('task', f.pending.id, offset, 40)
    rendered += page.content
    offset = page.nextOffset
  } while (page.hasMore)
  assert.equal(rendered, f.pending.serialized)
  assert.equal(JSON.parse(rendered).system, f.options.system)
  f.driver.close()
  await assert.rejects(f.done, /disposed/)
})

test('repeat request exposes a verifiable smaller delta and full fallback', async t => {
  const f = await fixture(t, { maxInlineModelChars: 0, system: 'x'.repeat(5000) })
  await f.driver.respond('task', { model_request_id: f.pending.id, response_id: 'first', text: 'Continue' })
  await f.done
  const next = { ...f.options,
    messages: [...f.options.messages, { role: 'tool', content: [{ type: 'text', text: 'Result' }] }] }
  const done = (async () => { for await (const _chunk of f.driver.stream(next)) {} })()
  done.catch(() => {})
  const watch = f.driver.watch('task')
  await watch.promise
  watch.dispose()
  const pending = f.driver.forTask('task')[0]
  const metadata = f.driver.describe(pending)
  assert.equal(metadata.deltaAvailable, true)
  assert.ok(metadata.deltaChars < metadata.totalChars)
  const deltaPage = await f.driver.read('task', pending.id, 0, 10000, 'delta')
  const delta = JSON.parse(deltaPage.content)
  assert.equal(delta.base_model_request_id, f.pending.id)
  assert.equal(delta.base_sha256, f.pending.sha256)
  assert.equal(delta.request_sha256, pending.sha256)
  assert.equal(delta.messages.retain, 1)
  assert.deepEqual(delta.messages.append, [next.messages[1]])
  const fullPage = await f.driver.read('task', pending.id, 0, 10000, 'full')
  assert.equal(JSON.parse(fullPage.content).messages.length, 2)
  await f.driver.respond('task', { model_request_id: pending.id, response_id: 'second', text: 'Done' })
  await done
})

test('unowned requests and over-capacity requests fail closed', async t => {
  const directory = await mkdtemp(path.join(tmpdir(), 'dsh-external-limit-'))
  const driver = new ExternalDriver({}, { taskStateDir: directory, maxModelRequestChars: 10 })
  t.after(() => driver.close())
  driver.tasks = { records: new Map() }
  const options = { provider: EXTERNAL_PROVIDER, model: EXTERNAL_MODEL, sessionId: 'session', messages: [] }
  await assert.rejects(async () => { for await (const _chunk of driver.stream(options)) {} }, /no active owning task/)
  driver.tasks.records.set('task', { taskId: 'task', sessionId: 'session', modelDriver: 'external', status: 'running' })
  await assert.rejects(async () => { for await (const _chunk of driver.stream(options)) {} }, /exceeds configured/)
  assert.equal(driver.pending.size, 0)
})

test('an external agent decision is accepted but cannot execute before slot readmission', async t => {
  const directory = await mkdtemp(path.join(tmpdir(), 'dsh-external-slot-'))
  const driver = new ExternalDriver({}, { taskStateDir: directory, maxModelRequestChars: 100000 })
  t.after(() => driver.close())
  let admit
  const slot = new Promise(resolve => { admit = resolve })
  const order = []
  driver.tasks = {
    records: new Map([['task', { taskId: 'task', sessionId: 'session', status: 'running', modelDriver: 'external' }]]),
    async releaseExecutionSlot() {
      assert.equal(driver.pending.size, 0, 'model request is not published before slot release')
      order.push('released')
    },
    resumeWhenSlot() { order.push('waiting'); return slot },
  }
  const chunks = []
  const done = (async () => {
    for await (const chunk of driver.stream({ provider: EXTERNAL_PROVIDER, model: EXTERNAL_MODEL,
      sessionId: 'session', purpose: 'agent-step', messages: [], tools: [] })) chunks.push(chunk)
  })()
  done.catch(() => {})
  const watch = driver.watch('task')
  await watch.promise
  watch.dispose()
  const pending = driver.forTask('task')[0]
  assert.deepEqual(order, ['released'])
  const accepted = await driver.respond('task', { model_request_id: pending.id, response_id: 'slot-test', text: 'Done' })
  assert.equal(accepted.accepted, true)
  assert.deepEqual(order, ['released', 'waiting'])
  assert.equal(chunks.length, 0, 'DSH receives no model output while waiting for its execution slot')
  admit()
  await done
  assert.equal(chunks.at(-1).type, 'finish')
})

test('live DSH child model requests inherit only their managed root task ownership', async t => {
  const directory = await mkdtemp(path.join(tmpdir(), 'dsh-external-child-'))
  const children = new Map([['child', { session: { header: { origin: 'subagent', parentSession: 'root' } } }],
    ['foreign', { session: { header: { origin: 'user', parentSession: 'root' } } }]])
  const driver = new ExternalDriver({ agents: { get: id => children.get(id) } },
    { taskStateDir: directory, maxModelRequestChars: 100000 })
  driver.tasks = { records: new Map([['task', { taskId: 'task', sessionId: 'root', status: 'running', modelDriver: 'external' }]]) }
  t.after(() => driver.close())
  assert.equal(driver.owningTask('child')?.taskId, 'task')
  assert.equal(driver.owningTask('foreign'), undefined)
  assert.equal(driver.owningTask('unknown'), undefined)
  const done = (async () => {
    for await (const _chunk of driver.stream({ provider: EXTERNAL_PROVIDER, model: EXTERNAL_MODEL,
      sessionId: 'child', purpose: 'agent-step', messages: [], tools: [] })) {}
  })()
  done.catch(() => {})
  const watch = driver.watch('task')
  await watch.promise
  watch.dispose()
  const pending = driver.forTask('task')[0]
  assert.equal(pending.sessionId, 'child')
  await driver.respond('task', { model_request_id: pending.id, response_id: 'child-answer', text: 'Child done' })
  await done
})

test('background subagent decisions are refused until their lifetime is bridge-managed', async t => {
  const f = await fixture(t, { tools: [{ name: 'subagent', parameters: { type: 'object' } }] })
  const response = { model_request_id: f.pending.id, response_id: 'child',
    tool_calls: [{ id: 'delegate', name: 'subagent', arguments: '{"description":"test","prompt":"test"}' }] }
  await assert.rejects(f.driver.respond('task', response), /run_in_background:false/)
  await f.driver.respond('task', { ...response,
    tool_calls: [{ ...response.tool_calls[0], arguments: '{"description":"test","prompt":"test","run_in_background":false}' }] })
  await f.done
})
