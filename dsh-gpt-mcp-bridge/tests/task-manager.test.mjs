import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { TaskManager, summarize, classify } from '../src/task-manager.js'

export async function fixture(t, options = {}) {
  const directory = await mkdtemp(path.join(tmpdir(), 'dsh-task-test-'))
  const sessions = new Map()
  const prompts = []
  const cancelled = []
  let settle
  const gate = new Promise(resolve => { settle = resolve })
  const config = { taskStateDir: directory, workspaceRoot: directory, maxConcurrentTasks: 2, maxQueuedTasks: 4,
    maxQueueWaitMs: 60000, maxTaskDurationMs: 60000, maxWaitMs: 50, ...options.config }
  const ctx = {
    logger: { warn() {} }, permissionPresets: { set() {} },
    sessionQuery: { async readSession(id) { return { events: sessions.get(id).events } } },
    sessionController: {
      async create({ sessionId }) {
        await options.createGate
        const session = { events: [] }
        let idle = Promise.resolve()
        let finish
        const append = (type, data) => session.events.push({ seq: session.events.length, type, data })
        session.agent = {
          status: 'idle', session,
          whenIdle: () => idle,
          cancel(cause, flags) { cancelled.push({ cause, flags }); finish?.('aborted') },
          run() {
            session.agent.status = 'running'
            idle = new Promise(resolve => { finish = reason => {
              if (session.agent.status === 'idle') return
              if (!options.missingEnd) append('turn/end', { reason: { kind: reason } })
              session.agent.status = 'idle'
              resolve()
            } })
            append('turn/start', { turn: 1 })
            append('step/start', { step: 1 })
            append('tool/call', { name: 'exec', callId: 'one' })
            gate.then(() => {
              if (session.agent.status !== 'running') return
              append('tool/result', { message: { callId: 'one' } })
              append('assistant/message', { message: { content: [{ type: 'text', text: 'verified' }] } })
              finish(options.end ?? 'completed')
            })
          },
        }
        sessions.set(sessionId, session)
        return { sessionId }
      },
      async resolveAgent(id) { return sessions.has(id) ? { agent: sessions.get(id).agent } : { error: new Error('session missing') } },
      async selectModel() {},
      async prompt(request, signal) {
        signal.throwIfAborted() // Public sessionController requires the caller signal.
        prompts.push(request); sessions.get(request.sessionId).agent.run(); return { accepted: true }
      },
    },
  }
  const manager = new TaskManager(ctx, config)
  t.after(() => manager.close())
  return { manager, config, ctx, prompts, cancelled, sessions, settle, directory }
}

async function running(manager, id) {
  for (let i = 0; i < 100; i++) {
    const status = await manager.wait(id, 2)
    if (status.progress?.toolCalls > 0 || status.terminal) return status
  }
  throw new Error('task did not start')
}

test('concurrent idempotent submission, short wait, durable result, continuation', async t => {
  const f = await fixture(t)
  const args = { request_id: 'same', prompt: 'fix and test' }
  const [a, b] = await Promise.all([f.manager.start(args), f.manager.start(args)])
  assert.equal(a.taskId, b.taskId)
  const active = await running(f.manager, a.taskId)
  assert.equal(active.terminal, false)
  assert.equal(f.prompts.length, 1)
  await assert.rejects(f.manager.start({ ...args, prompt: 'different' }), /different task input/)
  await assert.rejects(f.manager.start({ request_id: 'continuing', prompt: 'next' }, a.taskId), /already has an active/)
  f.settle()
  const result = await f.manager.wait(a.taskId, 50)
  assert.equal(result.status, 'completed')
  assert.equal(result.summary.finalText, 'verified')
  assert.equal(result.summary.toolCalls, 1)
  assert.equal(result.summary.toolResults, 1)
  const persisted = JSON.parse(await readFile(path.join(f.directory, `${a.taskId}.json`), 'utf8'))
  assert.equal(persisted.status, 'completed')
  const next = await f.manager.start({ request_id: 'next', prompt: 'continue' }, a.taskId)
  assert.equal(next.sessionId, a.sessionId)
  const continued = await f.manager.wait(next.taskId, 50)
  assert.equal(continued.summary.toolCalls, 1, 'previous interval must not be counted')
  assert.equal(f.prompts.length, 2)
})

for (const [end, expected] of [['error', 'failed'], ['blocked', 'blocked'], ['max-tokens', 'failed'], ['interrupted', 'interrupted'], ['aborted', 'cancelled']]) {
  test(`durable ${end} is classified as ${expected}`, async t => {
    const f = await fixture(t, { end })
    f.settle()
    const task = await f.manager.start({ request_id: end, prompt: 'test' })
    assert.equal((await f.manager.wait(task.taskId, 50)).status, expected)
  })
}

test('idle without a durable end is not success', async t => {
  const f = await fixture(t, { missingEnd: true })
  f.settle()
  const task = await f.manager.start({ request_id: 'missing-end', prompt: 'test' })
  const result = await f.manager.wait(task.taskId, 50)
  assert.equal(result.status, 'failed')
  assert.match(result.error, /without a durable/)
})

test('cancel discards inbox and waits for native quiescence; arbitrary session is refused', async t => {
  const f = await fixture(t)
  const task = await f.manager.start({ request_id: 'cancel', prompt: 'test' })
  await running(f.manager, task.taskId)
  await assert.rejects(f.manager.cancel('unrelated-session'), /Unknown managed/)
  await f.manager.cancel(task.sessionId)
  assert.equal((await f.manager.wait(task.taskId, 50)).status, 'cancelled')
  assert.deepEqual(f.cancelled[0].flags, { keepInbox: false })
})

test('cancel during session setup never submits a prompt', async t => {
  let release
  const createGate = new Promise(resolve => { release = resolve })
  const f = await fixture(t, { createGate })
  const task = await f.manager.start({ request_id: 'setup', prompt: 'test' })
  await f.manager.cancel(task.taskId)
  release()
  assert.equal((await f.manager.wait(task.taskId, 50)).status, 'cancelled')
  assert.equal(f.prompts.length, 0)
})

test('task runtime budget cancels the loop independently of HTTP waits', async t => {
  const f = await fixture(t, { config: { maxTaskDurationMs: 30, maxWaitMs: 200 } })
  const task = await f.manager.start({ request_id: 'deadline', prompt: 'test' })
  assert.equal((await f.manager.wait(task.taskId, 200)).status, 'timed_out')
})

test('real progress renews inactivity lease but polling does not', async t => {
  const f = await fixture(t, { config: { maxTaskDurationMs: 200, maxTaskLifetimeMs: 1000 } })
  const task = await f.manager.start({ request_id: 'lease', prompt: 'test' })
  await running(f.manager, task.taskId)
  const first = await f.manager.status(task.taskId)
  await new Promise(resolve => setTimeout(resolve, 20))
  const polled = await f.manager.status(task.taskId)
  assert.equal(polled.deadlineAt, first.deadlineAt)
  await f.manager.progress(task.taskId)
  const renewed = await f.manager.status(task.taskId)
  assert.ok(renewed.deadlineAt > first.deadlineAt)
  assert.ok(renewed.deadlineAt <= renewed.hardDeadlineAt)
  f.settle()
  assert.equal((await f.manager.wait(task.taskId, 50)).status, 'completed')
})

test('maximum task lifetime stops work despite renewed progress', async t => {
  const f = await fixture(t, { config: { maxTaskDurationMs: 200, maxTaskLifetimeMs: 40, maxWaitMs: 100 } })
  const task = await f.manager.start({ request_id: 'hard-cap', prompt: 'test' })
  await f.manager.progress(task.taskId)
  assert.equal((await f.manager.wait(task.taskId, 100)).status, 'lifetime_exceeded')
})

test('bounded concurrency queues distinct sessions and drains FIFO', async t => {
  const f = await fixture(t, { config: { maxConcurrentTasks: 1 } })
  const first = await f.manager.start({ request_id: 'first', prompt: 'test' })
  await running(f.manager, first.taskId)
  const second = await f.manager.start({ request_id: 'second', prompt: 'test' })
  assert.equal(second.status, 'queued')
  assert.equal(second.state, 'QUEUED')
  assert.equal(second.queuePosition, 1)
  assert.equal(f.prompts.length, 1)
  f.settle()
  assert.equal((await f.manager.wait(first.taskId, 50)).status, 'completed')
  assert.equal((await f.manager.wait(second.taskId, 50)).status, 'completed')
  assert.equal(f.prompts.length, 2)
})

test('external model wait yields its slot and accepted decisions resume under the same cap', async t => {
  const f = await fixture(t, { config: { maxConcurrentTasks: 1, maxQueuedTasks: 2 } })
  const first = await f.manager.start({ request_id: 'yield-first', prompt: 'test' })
  await running(f.manager, first.taskId)
  await f.manager.releaseExecutionSlot(first.taskId)
  assert.equal((await f.manager.status(first.taskId)).executionState, 'waiting_model')
  const second = await f.manager.start({ request_id: 'yield-second', prompt: 'test' })
  await running(f.manager, second.taskId)
  assert.equal(f.prompts.length, 2, 'a second session starts while the first awaits ChatGPT')
  const resume = f.manager.resumeWhenSlot(first.taskId)
  assert.equal((await f.manager.status(first.taskId)).state, 'WAITING_EXECUTION_SLOT')
  const third = await f.manager.start({ request_id: 'yield-third', prompt: 'test' })
  assert.equal(third.state, 'QUEUED')
  await f.manager.releaseExecutionSlot(second.taskId)
  await resume
  assert.deepEqual([...f.manager.executionSlots], [first.taskId])
  await f.manager.releaseExecutionSlot(first.taskId)
  await running(f.manager, third.taskId)
  assert.equal(f.manager.executionSlots.size, 1)
  f.settle()
  for (const task of [first, second, third]) {
    assert.equal((await f.manager.wait(task.taskId, 50)).status, 'completed')
  }
})

test('waiting-model tasks count toward total capacity and cancelled resumes never run', async t => {
  const f = await fixture(t, { config: { maxConcurrentTasks: 1, maxQueuedTasks: 1 } })
  const first = await f.manager.start({ request_id: 'capacity-first', prompt: 'test' })
  await running(f.manager, first.taskId)
  await f.manager.releaseExecutionSlot(first.taskId)
  const second = await f.manager.start({ request_id: 'capacity-second', prompt: 'test' })
  await running(f.manager, second.taskId)
  await assert.rejects(f.manager.start({ request_id: 'capacity-third', prompt: 'test' }), /queue is full/)
  const resume = f.manager.resumeWhenSlot(first.taskId)
  await f.manager.cancel(first.taskId)
  await assert.rejects(resume, /ended before execution-slot admission/)
  assert.equal((await f.manager.wait(first.taskId, 50)).status, 'cancelled')
  f.settle()
  assert.equal((await f.manager.wait(second.taskId, 50)).status, 'completed')
})

test('queued cancellation never starts work and queue capacity fails clearly', async t => {
  const f = await fixture(t, { config: { maxConcurrentTasks: 1, maxQueuedTasks: 1 } })
  const first = await f.manager.start({ request_id: 'first-capacity', prompt: 'test' })
  await running(f.manager, first.taskId)
  const queued = await f.manager.start({ request_id: 'queued-cancel', prompt: 'test' })
  await assert.rejects(f.manager.start({ request_id: 'queue-full', prompt: 'test' }), /queue is full/)
  const cancelled = await f.manager.cancel(queued.taskId)
  assert.equal(cancelled.status, 'cancelled')
  f.settle()
  assert.equal((await f.manager.wait(first.taskId, 50)).status, 'completed')
  assert.equal(f.prompts.length, 1)
})

test('graceful teardown interrupts running and queued tasks', async t => {
  const f = await fixture(t, { config: { maxConcurrentTasks: 1 } })
  const task = await f.manager.start({ request_id: 'first', prompt: 'test' })
  await running(f.manager, task.taskId)
  const queued = await f.manager.start({ request_id: 'queued', prompt: 'test' })
  await f.manager.close()
  assert.equal((await f.manager.status(task.taskId)).status, 'interrupted')
  assert.equal((await f.manager.status(queued.taskId)).status, 'interrupted')
  await assert.rejects(f.manager.start({ request_id: 'third', prompt: 'test' }), /stopping/)
})

test('restart retains identity, marks abandoned work interrupted, never replays', async t => {
  const f = await fixture(t)
  f.settle()
  const args = { request_id: 'restart', prompt: 'test' }
  const task = await f.manager.start(args)
  await f.manager.wait(task.taskId, 50)
  await f.manager.close()
  const filename = path.join(f.directory, `${task.taskId}.json`)
  const record = JSON.parse(await readFile(filename, 'utf8'))
  record.status = 'running' // Simulate persisted intent left by a process crash.
  await writeFile(filename, JSON.stringify(record))
  const restarted = new TaskManager(f.ctx, f.config)
  t.after(() => restarted.close())
  assert.equal((await restarted.start(args)).status, 'interrupted')
  assert.equal(f.prompts.length, 1)
})

test('summary bounds output and does not equate unknown extension reasons to success', () => {
  const result = summarize([{ seq: 1, type: 'assistant/message', data: { message: { content: [{ type: 'text', text: 'x'.repeat(30000) }] } } }])
  assert.equal(result.finalText.length, 24000)
  assert.equal(result.finalTextTruncated, true)
  assert.equal(classify({ endReason: { kind: 'custom' } }), 'failed')
})
