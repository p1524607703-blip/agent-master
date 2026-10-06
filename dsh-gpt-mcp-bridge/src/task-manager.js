import { createHash, randomUUID } from 'node:crypto'
import { mkdir, readFile, readdir, rename, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { EXTERNAL_PROVIDER, EXTERNAL_MODEL } from './external-driver.js'

const ACTIVE = new Set(['queued', 'running', 'cancelling'])
const digest = value => createHash('sha256').update(JSON.stringify(value)).digest('hex')

// This is an interval summary, not a second agent loop. Only DSH executes tools.
export function summarize(events, afterSeq = -1) {
  const interval = events.filter(event => event.seq > afterSeq)
  const end = interval.findLast(event => event.type === 'turn/end')
  const assistant = interval.findLast(event => event.type === 'assistant/message')
  const text = assistant?.data.message.content.filter(block => block.type === 'text').map(block => block.text).join('\n') ?? ''
  return {
    fromSeq: interval[0]?.seq ?? null,
    toSeq: interval.at(-1)?.seq ?? afterSeq,
    steps: interval.filter(event => event.type === 'step/start').length,
    toolCalls: interval.filter(event => event.type === 'tool/call').length,
    toolResults: interval.filter(event => event.type === 'tool/result').length,
    toolNames: [...new Set(interval.filter(event => event.type === 'tool/call').map(event => event.data.name))],
    endReason: end?.data.reason ?? null,
    finalText: text.slice(-24000),
    finalTextTruncated: text.length > 24000,
  }
}

export function classify(summary) {
  switch (summary.endReason?.kind) {
    case 'completed': return 'completed'
    case 'aborted': return 'cancelled'
    case 'blocked': return 'blocked'
    case 'interrupted': return 'interrupted'
    default: return 'failed' // Idle, missing turn/end, unknown reasons and max-tokens are not success.
  }
}

export class TaskManager {
  constructor(ctx, config) {
    this.ctx = ctx
    this.config = config
    this.records = new Map()
    this.workers = new Map()
    this.executionSlots = new Set()
    this.resumeQueue = new Map()
    this.queueInputs = new Map()
    this.waiters = new Map()
    this.agents = new Map()
    this.admissions = new Map()
    this.nativeHandles = new Map()
    this.deadlineTimers = new Map()
    this.writes = new Map()
    this.closed = false
    this.initialized = false
    this.ready = this.load()
    // Initialization failure is surfaced by every API; avoid an unhandled rejection.
    this.ready.catch(() => {})
  }

  async load() {
    await mkdir(this.config.taskStateDir, { recursive: true, mode: 0o700 })
    for (const file of await readdir(this.config.taskStateDir)) {
      if (!/^task-[a-f0-9]{64}\.json$/.test(file)) continue
      const record = JSON.parse(await readFile(path.join(this.config.taskStateDir, file), 'utf8'))
      if (`${record.taskId}.json` !== file || record.schema !== 1) throw new Error('Invalid task state; refusing to replay tasks')
      this.records.set(record.taskId, record)
      if (ACTIVE.has(record.status)) {
        record.status = 'interrupted'
        record.error = 'Bridge restarted. Execution was not replayed; inspect the DSH journal before explicit continuation.'
        record.finishedAt = Date.now()
        await this.save(record)
      }
    }
    this.initialized = true
  }

  save(record) {
    const serialized = JSON.stringify(record, null, 2)
    const pending = (this.writes.get(record.taskId) ?? Promise.resolve()).catch(() => {}).then(async () => {
      const target = path.join(this.config.taskStateDir, `${record.taskId}.json`)
      const temporary = `${target}.${randomUUID()}.tmp`
      await writeFile(temporary, serialized, { mode: 0o600 })
      await rename(temporary, target)
    })
    this.writes.set(record.taskId, pending)
    return pending
  }

  async require(id) {
    await this.ready
    const record = this.records.get(id) ?? [...this.records.values()]
      .filter(item => item.sessionId === id).sort((a, b) => b.createdAt - a.createdAt)[0]
    if (!record) throw new Error('Unknown managed task/session; arbitrary DSH sessions cannot be mutated through this endpoint')
    return record
  }

  watch(taskId) {
    let notify
    const promise = new Promise(resolve => { notify = resolve })
    const listeners = this.waiters.get(taskId) ?? new Set()
    listeners.add(notify)
    this.waiters.set(taskId, listeners)
    return { promise, dispose: () => {
      listeners.delete(notify)
      if (!listeners.size) this.waiters.delete(taskId)
    } }
  }

  notify(taskId) {
    for (const listener of this.waiters.get(taskId) ?? []) listener()
  }

  startWorker(record, input) {
    if (this.closed || record.status !== 'queued' || this.workers.has(record.taskId)) return
    this.queueInputs.delete(record.taskId)
    this.executionSlots.add(record.taskId)
    record.executionState = 'active'
    record.admittedAt = Date.now()
    record.queueWaitMs = record.admittedAt - record.createdAt
    record.lastProgressAt = record.admittedAt
    record.deadlineAt = Math.min(record.admittedAt + record.idleTimeoutMs, record.hardDeadlineAt)
    const worker = this.execute(record, input)
    this.workers.set(record.taskId, worker)
    this.notify(record.taskId)
    worker.finally(() => {
      this.workers.delete(record.taskId)
      this.executionSlots.delete(record.taskId)
      this.notify(record.taskId)
      this.drainQueue()
    }).catch(() => {})
  }

  drainQueue() {
    if (this.closed) return
    const sessions = new Set([...this.workers.keys()].map(id => this.records.get(id)?.sessionId))
    const waiting = [...this.resumeQueue.entries()].map(([taskId, entry]) => ({
      kind: 'resume', record: this.records.get(taskId), requestedAt: entry.requestedAt,
    }))
    const queued = [...this.records.values()]
      .filter(record => record.status === 'queued' && this.queueInputs.has(record.taskId))
      .map(record => ({ kind: 'start', record, requestedAt: record.createdAt }))
    for (const candidate of [...waiting, ...queued].sort((a, b) => a.requestedAt - b.requestedAt)) {
      if (this.executionSlots.size >= this.config.maxConcurrentTasks) break
      const { record } = candidate
      if (candidate.kind === 'resume') {
        const entry = this.resumeQueue.get(record?.taskId)
        if (!entry) continue
        if (record.status !== 'running' || record.stopReason) {
          this.resumeQueue.delete(record.taskId)
          entry.reject(new Error('Owning task ended before execution-slot admission'))
          continue
        }
        this.resumeQueue.delete(record.taskId)
        this.executionSlots.add(record.taskId)
        record.executionState = 'active'
        this.save(record).catch(error => this.ctx.logger.warn(`Execution-slot state persistence failed: ${error.message}`))
        entry.resolve()
      } else if (!sessions.has(record.sessionId)) {
        this.startWorker(record, this.queueInputs.get(record.taskId))
        sessions.add(record.sessionId)
      }
    }
  }

  async releaseExecutionSlot(taskId) {
    const record = this.records.get(taskId)
    if (!record || record.status !== 'running' || !this.executionSlots.delete(taskId)) return
    record.executionState = 'waiting_model'
    await this.save(record)
    this.notify(taskId)
    this.drainQueue()
  }

  resumeWhenSlot(taskId) {
    const record = this.records.get(taskId)
    if (this.closed || !record || record.status !== 'running' || record.stopReason) {
      return Promise.reject(new Error('Owning task is not running'))
    }
    if (this.executionSlots.has(taskId)) return Promise.resolve()
    const existing = this.resumeQueue.get(taskId)
    if (existing) return existing.promise
    let resolve, reject
    const promise = new Promise((yes, no) => { resolve = yes; reject = no })
    promise.catch(() => {})
    this.resumeQueue.set(taskId, { promise, resolve, reject, requestedAt: Date.now() })
    record.executionState = 'waiting_execution_slot'
    this.save(record).catch(error => this.ctx.logger.warn(`Execution-slot state persistence failed: ${error.message}`))
    this.notify(taskId)
    this.drainQueue()
    return promise
  }

  rejectResume(taskId) {
    const entry = this.resumeQueue.get(taskId)
    if (!entry) return
    this.resumeQueue.delete(taskId)
    entry.reject(new Error('Owning task ended before execution-slot admission'))
  }

  async start(args, previousTaskId) {
    await this.ready
    if (this.closed) throw new Error('Bridge is stopping')
    if ((args.provider === undefined) !== (args.model === undefined)) throw new Error('provider and model must be supplied together')
    const previous = previousTaskId ? await this.require(previousTaskId) : undefined
    const modelDriver = this.config.modelDriver ?? 'api'
    if (previous && (previous.modelDriver ?? 'api') !== modelDriver) throw new Error('Cannot change a session model driver through continuation; submit a new task')
    if (modelDriver === 'external' && (args.provider !== undefined || args.model !== undefined || args.reasoning_effort !== undefined)) {
      throw new Error('External-driver mode uses the current ChatGPT session; omit provider, model and reasoning_effort. No model API fallback is allowed.')
    }
    const requestId = args.request_id ?? `legacy-${randomUUID()}`
    const taskId = `task-${digest(requestId)}`
    const input = {
      prompt: args.prompt,
      cwd: previous?.cwd ?? path.resolve(this.config.workspaceRoot, args.cwd ?? '.'),
      agentPreset: args.agent_preset ?? null,
      provider: args.provider ?? null,
      model: args.model ?? null,
      reasoningEffort: args.reasoning_effort ?? null,
      durationMs: Math.min(args.timeout_ms ?? this.config.maxTaskDurationMs, this.config.maxTaskDurationMs),
      previousTaskId: previous?.taskId ?? null,
      modelDriver,
    }
    const fingerprint = digest(input)
    const existing = this.records.get(taskId)
    if (existing) {
      if (existing.fingerprint !== fingerprint) throw new Error('request_id already used with different task input')
      await this.writes.get(taskId)
      return this.view(existing)
    }
    if (this.closed) throw new Error('Bridge is stopping')
    const active = [...this.records.values()].filter(item => ACTIVE.has(item.status))
    const queued = active.filter(item => item.status === 'queued' && !this.workers.has(item.taskId))
    if (queued.length >= (this.config.maxQueuedTasks ?? 32)
      || active.length >= this.config.maxConcurrentTasks + (this.config.maxQueuedTasks ?? 32)) {
      throw new Error('Managed task queue is full')
    }
    if (previous && active.some(item => item.sessionId === previous.sessionId)) throw new Error('Session already has an active managed task')
    const now = Date.now()
    const record = {
      schema: 1, taskId, requestId, fingerprint, status: 'queued',
      modelDriver,
      sessionId: previous?.sessionId ?? `mcp-agent-${randomUUID()}`,
      cwd: input.cwd, previousTaskId: input.previousTaskId,
      createdAt: Math.max(now, (previous?.createdAt ?? 0) + 1),
      deadlineAt: now + (this.config.maxQueueWaitMs ?? this.config.maxTaskDurationMs),
      hardDeadlineAt: now + (this.config.maxTaskLifetimeMs ?? 3_600_000),
      idleTimeoutMs: input.durationMs, lastProgressAt: now, lastEventSeq: -1,
      afterSeq: -1,
    }
    // Reserve synchronously before the first write: concurrent retries share one task.
    this.records.set(taskId, record)
    this.queueInputs.set(taskId, input)
    await this.save(record)
    this.scheduleDeadline(record)
    this.drainQueue()
    return this.view(record)
  }

  view(record) {
    const { fingerprint, schema, ...view } = record
    const pending = ACTIVE.has(record.status) ? this.external?.forTask(record.taskId) ?? [] : []
    const waitingForSlot = record.status === 'queued' && !this.workers.has(record.taskId)
    const queue = waitingForSlot
      ? [...this.records.values()].filter(item => item.status === 'queued' && !this.workers.has(item.taskId)).sort((a, b) => a.createdAt - b.createdAt)
      : []
    return { ...view, terminal: !ACTIVE.has(record.status), executionOwner: 'DSH Agent Loop',
      ...(waitingForSlot ? { state: 'QUEUED', queuePosition: queue.findIndex(item => item.taskId === record.taskId) + 1 } : {}),
      ...(record.status === 'queued' && !waitingForSlot ? { state: 'STARTING' } : {}),
      ...(record.executionState === 'waiting_execution_slot' ? { state: 'WAITING_EXECUTION_SLOT' } : {}),
      ...(pending.length ? { state: 'NEED_MODEL_INPUT', modelRequests: pending.map(item => this.external.describe(item, true)) } : {}),
      nextAction: pending.length ? 'agent_model_respond' : ACTIVE.has(record.status) ? 'agent_task_wait' : null }
  }

  async resolve(sessionId) {
    const result = await this.ctx.sessionController.resolveAgent(sessionId)
    if ('error' in result) throw result.error
    return result.agent
  }

  async snapshot(record) {
    const snapshot = await this.ctx.sessionQuery.readSession(record.sessionId)
    return summarize(snapshot.events, record.afterSeq)
  }

  scheduleDeadline(record) {
    clearTimeout(this.deadlineTimers.get(record.taskId))
    if (!ACTIVE.has(record.status)) return
    const timer = setTimeout(() => {
      this.checkDeadline(record).catch(error => this.ctx.logger.warn(error.message))
    }, Math.max(1, Math.min(record.deadlineAt, record.hardDeadlineAt) - Date.now()))
    timer.unref?.()
    this.deadlineTimers.set(record.taskId, timer)
  }

  async progress(taskId, eventSeq) {
    const record = this.records.get(taskId)
    if (!record || !ACTIVE.has(record.status) || record.stopReason) return
    if (eventSeq !== undefined && eventSeq <= record.lastEventSeq) return
    if (eventSeq !== undefined) record.lastEventSeq = eventSeq
    record.lastProgressAt = Date.now()
    record.deadlineAt = Math.min(record.lastProgressAt + record.idleTimeoutMs, record.hardDeadlineAt)
    this.scheduleDeadline(record)
    await this.save(record)
  }

  async checkDeadline(record) {
    if (!ACTIVE.has(record.status) || record.stopReason) return
    if (Date.now() >= record.hardDeadlineAt) {
      await this.cancel(record.taskId, 'lifetime_exceeded')
      return
    }
    try {
      const snapshot = await this.ctx.sessionQuery.readSession(record.sessionId)
      const eventSeq = snapshot.events.at(-1)?.seq ?? -1
      if (eventSeq > record.lastEventSeq) {
        await this.progress(record.taskId, eventSeq)
        return
      }
    } catch (error) {
      this.ctx.logger.warn(`Deadline progress check failed: ${error.message}`)
    }
    if (Date.now() >= record.deadlineAt) await this.cancel(record.taskId, 'timed_out')
    else this.scheduleDeadline(record)
  }

  async execute(record, input) {
    let agent
    const admission = new AbortController()
    this.admissions.set(record.taskId, admission)
    this.scheduleDeadline(record)
    try {
      await this.save(record) // Persist intent before creating a session or submitting work.
      if (this.closed) record.stopReason = 'interrupted'
      if (record.stopReason) return
      if (!input.previousTaskId) {
        if (input.modelDriver === 'external') {
          await mkdir(input.cwd, { recursive: true })
          const preset = await this.ctx.agentPresets.resolve(input.agentPreset ?? undefined)
          const selection = { provider: EXTERNAL_PROVIDER, model: EXTERNAL_MODEL }
          const handle = await this.ctx.agents.create({
            sessionId: record.sessionId, agentOptions: selection,
            meta: { cwd: input.cwd, agentPreset: preset.id },
            setup: async agentCtx => { await this.ctx.agentPresets.mount(agentCtx, preset.id) },
          })
          this.nativeHandles.set(record.sessionId, handle)
          // The controller installs its public model-selection projection on first prompt.
          // Seed that session-local selection before admission; do not mutate global settings.
          handle.agent.session.append('model/selection', selection)
        } else {
          await this.ctx.sessionController.create({ sessionId: record.sessionId, cwd: input.cwd,
            ...(input.agentPreset ? { agentPreset: input.agentPreset } : {}) })
        }
      }
      agent = await this.resolve(record.sessionId)
      if (agent.status !== 'idle') throw new Error('Managed session is already running outside this task; no prompt was submitted')
      this.agents.set(record.taskId, agent)
      this.ctx.permissionPresets.set(agent.session, 'danger-full-access')
      if (input.provider) {
        await this.ctx.sessionController.selectModel({ sessionId: record.sessionId,
          provider: input.provider, model: input.model,
          ...(input.reasoningEffort ? { reasoningEffort: input.reasoningEffort } : {}) })
      }
      const before = await this.ctx.sessionQuery.readSession(record.sessionId)
      record.afterSeq = before.events.at(-1)?.seq ?? -1
      record.lastEventSeq = record.afterSeq
      record.startedAt = Date.now()
      record.status = 'running'
      await this.save(record)
      this.notify(record.taskId)
      if (record.stopReason || this.closed) return
      await this.ctx.sessionController.prompt({ requestId: record.requestId, sessionId: record.sessionId,
        mode: 'queue', content: [{ type: 'text', text: input.prompt }] }, admission.signal)
      if (record.stopReason || this.closed) agent.cancel({ kind: 'user' }, { keepInbox: false })
      await agent.whenIdle()
      record.summary = await this.snapshot(record)
      record.status = classify(record.summary)
      if (!record.summary.endReason) record.error = 'DSH became idle without a durable turn/end; task success is unverified'
    } catch (error) {
      if (agent && this.agents.has(record.taskId)) {
        agent.cancel({ kind: 'user' }, { keepInbox: false })
        await agent.whenIdle()
      }
      record.status = 'failed'
      record.error = error instanceof Error ? error.message : String(error)
    } finally {
      clearTimeout(this.deadlineTimers.get(record.taskId))
      this.deadlineTimers.delete(record.taskId)
      if (record.stopReason) record.status = record.stopReason
      else if (ACTIVE.has(record.status)) record.status = 'interrupted'
      record.finishedAt = Date.now()
      this.external?.stopTask(record.taskId)
      this.rejectResume(record.taskId)
      this.executionSlots.delete(record.taskId)
      this.agents.delete(record.taskId)
      this.admissions.delete(record.taskId)
      try { await this.save(record) }
      catch (error) {
        record.persistenceError = error.message
        this.ctx.logger.warn(`Task ${record.taskId} state persistence failed: ${error.message}`)
      }
      this.notify(record.taskId)
      this.drainQueue()
    }
  }

  async status(id) {
    const record = await this.require(id)
    const view = this.view(record)
    if (record.startedAt && ACTIVE.has(record.status)) {
      try {
        view.progress = await this.snapshot(record)
        if (view.progress.toSeq > record.lastEventSeq) await this.progress(record.taskId, view.progress.toSeq)
      }
      catch (error) { view.progressError = error.message }
    }
    return view
  }

  async wait(id, timeoutMs = 1000) {
    const record = await this.require(id)
    if (!ACTIVE.has(record.status)) return this.status(record.taskId)
    const worker = this.workers.get(record.taskId)
    let timer
    const pending = this.external?.watch(record.taskId)
    // A task keeps the durable `queued` status briefly while its admitted worker
    // creates/resolves the DSH session. Only wake on a queue transition when no
    // worker owns the task; otherwise wait for the worker's terminal result.
    const change = record.status === 'queued' && !worker ? this.watch(record.taskId) : undefined
    try {
      await Promise.race([...(worker ? [worker] : []), ...(change ? [change.promise] : []), ...(pending ? [pending.promise] : []), new Promise(resolve => {
        timer = setTimeout(resolve, Math.min(Math.max(0, timeoutMs), this.config.maxWaitMs))
      })])
    } finally { clearTimeout(timer); pending?.dispose(); change?.dispose() }
    return this.status(record.taskId)
  }

  async cancel(id, reason = 'cancelled') {
    const record = await this.require(id)
    if (!ACTIVE.has(record.status)) return this.view(record)
    record.stopReason ??= reason
    if (record.status === 'queued' && !this.workers.has(record.taskId)) {
      record.status = reason
      record.finishedAt = Date.now()
      this.queueInputs.delete(record.taskId)
      clearTimeout(this.deadlineTimers.get(record.taskId))
      this.deadlineTimers.delete(record.taskId)
      await this.save(record)
      this.notify(record.taskId)
      this.drainQueue()
      return this.view(record)
    }
    record.status = 'cancelling'
    this.rejectResume(record.taskId)
    // Set the stop flag before any await; setup/prompt races check the same flag.
    this.admissions.get(record.taskId)?.abort()
    this.agents.get(record.taskId)?.cancel({ kind: reason === 'interrupted' ? 'disposed' : 'user' }, { keepInbox: false })
    await this.save(record)
    this.notify(record.taskId)
    return this.view(record) // Cancellation acknowledgement is NOT completion.
  }

  async close() {
    this.closed = true
    await this.ready
    await Promise.all([...this.records.values()].filter(item => ACTIVE.has(item.status)).map(item => this.cancel(item.taskId, 'interrupted')))
    await Promise.all([...this.workers.values()])
    await Promise.all([...this.writes.values()])
    for (const handle of this.nativeHandles.values()) await handle.dispose()
    this.nativeHandles.clear()
  }
}
