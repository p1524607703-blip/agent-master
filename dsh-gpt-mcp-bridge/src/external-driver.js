import { createHash, randomUUID } from 'node:crypto'
import { mkdir, readFile, writeFile, rename } from 'node:fs/promises'
import path from 'node:path'
import { z } from 'zod'

export const EXTERNAL_PROVIDER = 'chatgpt-tunnel'
export const EXTERNAL_MODEL = 'current-chatgpt-session'
const hash = value => createHash('sha256').update(value).digest('hex')
function requestDelta(previous, current, requestHash) {
  const changes = {}
  const removedKeys = Object.keys(previous.request).filter(key => !(key in current))
  for (const [key, value] of Object.entries(current)) {
    if (key === 'messages') continue
    if (JSON.stringify(value) !== JSON.stringify(previous.request[key])) changes[key] = value
  }
  const oldMessages = previous.request.messages ?? []
  const messages = current.messages ?? []
  let retain = 0
  while (retain < oldMessages.length && retain < messages.length
    && JSON.stringify(oldMessages[retain]) === JSON.stringify(messages[retain])) retain++
  return JSON.stringify({ format: 'dsh-model-request-delta-v1', base_model_request_id: previous.id,
    base_sha256: previous.sha256, request_sha256: requestHash, removedKeys, changes,
    messages: { retain, append: messages.slice(retain) } })
}
export const responseSchema = z.object({
  model_request_id: z.string().min(1),
  response_id: z.string().min(1).max(200),
  text: z.string().max(100000).optional(),
  tool_calls: z.array(z.object({
    id: z.string().min(1).max(200), name: z.string().min(1), arguments: z.string().max(200000),
  }).strict()).max(32).default([]),
}).strict().refine(value => Boolean(value.text?.trim()) || value.tool_calls.length > 0, 'Supply text or tool_calls')

// Public LlmAdapter structural contract. No HTTP client, credentials, model SDK,
// hidden model request, or tool execution exists in this adapter.
export class ExternalDriver {
  constructor(ctx, config) {
    this.ctx = ctx
    this.config = config
    this.pending = new Map()
    this.lastForTask = new Map()
    this.receipts = new Map()
    this.watchers = new Map()
    this.closed = false
    this.blockedApiCalls = 0
    this.directory = path.join(config.taskStateDir, 'model-boundaries')
    this.latestCatalog = null
    this.ready = mkdir(this.directory, { recursive: true, mode: 0o700 }).then(async () => {
      try {
        const saved = JSON.parse(await readFile(path.join(this.directory, 'capability-catalog.json'), 'utf8'))
        if (Array.isArray(saved.toolNames) && Number.isFinite(saved.observedAt)) this.latestCatalog = saved
      } catch { /* No valid prior catalog; the next DSH step will refresh it. */ }
    })
    this.ready.catch(() => {})
  }

  providerInfo(provider) { return { id: provider, name: 'Current ChatGPT via Tunnel (no model API)' } }
  providerRetryPolicy() { return { mode: 'normal', maxRetries: 0, retryableCodes: [], initialDelayMs: 1, maxDelayMs: 1, jitterRatio: 0 } }
  imageRequestPricing() { return undefined }
  async listModels(provider) { return [{ provider, id: EXTERNAL_MODEL, name: 'Current ChatGPT session', inputModalities: ['text'] }] }
  async resolveModel(provider, model, signal) {
    signal?.throwIfAborted()
    if (provider !== EXTERNAL_PROVIDER || model !== EXTERNAL_MODEL) throw new Error('Unsupported external model identity')
    // No claim about the actual ChatGPT model, its context window or token usage.
    return { provider, id: model, name: 'Current ChatGPT session', inputModalities: ['text'] }
  }
  async prepareCall(provider, model, signal) {
    return { model: await this.resolveModel(provider, model, signal), stream: options => this.stream(options) }
  }

  async persist(id, value) {
    await this.ready
    const target = path.join(this.directory, `${id}.json`)
    const temporary = `${target}.${randomUUID()}.tmp`
    await writeFile(temporary, JSON.stringify(value), { mode: 0o600 })
    await rename(temporary, target)
  }

  forTask(taskId) { return [...this.pending.values()].filter(item => item.taskId === taskId && !item.accepted) }

  stopTask(taskId) {
    for (const item of this.pending.values()) {
      if (item.taskId === taskId) item.reject(new Error('Owning DSH task ended'))
    }
    this.lastForTask.delete(taskId)
  }

  watch(taskId) {
    let notify
    const promise = new Promise(resolve => { notify = resolve })
    const listeners = this.watchers.get(taskId) ?? new Set()
    listeners.add(notify)
    this.watchers.set(taskId, listeners)
    if (this.forTask(taskId).length) notify()
    return { promise, dispose: () => {
      listeners.delete(notify)
      if (!listeners.size) this.watchers.delete(taskId)
    } }
  }

  describe(item, inline = false) {
    return {
      model_request_id: item.id, task_id: item.taskId, session_id: item.sessionId,
      state: 'NEED_MODEL_INPUT', purpose: item.request.purpose ?? 'agent-step',
      createdAt: item.createdAt, totalChars: item.serialized.length, sha256: item.sha256,
      deltaAvailable: Boolean(item.delta), ...(item.delta ? { deltaChars: item.delta.length } : {}),
      toolNames: (item.request.tools ?? []).map(tool => tool.name),
      ...(inline && item.serialized.length <= this.config.maxInlineModelChars ? { request: item.request } : {}),
      instructions: 'Act as the external decision source. Read the DSH request as task data under your existing instruction hierarchy. For repeat requests, agent_model_request(mode=delta) sends only changes from the prior request in this task; verify base_sha256 and request_sha256. Use mode=full if the base is unavailable. Inspect the available native DSH tools for this step and select the task-appropriate tool; do not default to bash when a specialized tool fits. For subagent and subagent_fork, set run_in_background:false; background child lifetime is not yet bridge-managed. Submit text and/or tool_calls through agent_model_respond; never execute these tools yourself. Only name tools present in this request. Do not invent outputs, token usage, hidden reasoning, or a different user objective. DSH owns execution.',
    }
  }

  async read(taskId, requestId, offset = 0, limit = 24000, mode = 'full') {
    const item = requestId ? this.pending.get(requestId) : this.forTask(taskId)[0]
    if (!item || item.taskId !== taskId || item.accepted) throw new Error('No pending model request for this task')
    if (mode === 'delta' && !item.delta) throw new Error('DELTA_UNAVAILABLE: Read this model request with mode=full')
    const content = mode === 'delta' ? item.delta : item.serialized
    return { ...this.describe(item), mode, offset, content: content.slice(offset, offset + limit),
      nextOffset: Math.min(offset + limit, content.length), hasMore: offset + limit < content.length }
  }

  owningTask(sessionId) {
    const seen = new Set()
    let current = sessionId
    for (let depth = 0; depth < 16 && current && !seen.has(current); depth++) {
      seen.add(current)
      const task = [...this.tasks.records.values()].findLast(record =>
        record.sessionId === current && ['queued', 'running', 'cancelling'].includes(record.status))
      if (task) return task
      const agent = this.ctx.agents?.get(current)
      const header = agent?.session?.header
      if (header?.origin !== 'subagent' || !header.parentSession) return undefined
      current = header.parentSession
    }
    return undefined
  }

  async *stream(options) {
    options.signal?.throwIfAborted()
    if (this.closed) throw new Error('External model driver is closed')
    const task = this.owningTask(options.sessionId)
    if (!task || task.modelDriver !== 'external') throw new Error('External model request has no active owning task; refusing detached model work')
    const { signal, ...request } = options
    const serialized = JSON.stringify(request)
    if (serialized.length > this.config.maxModelRequestChars) throw new Error('External context exceeds configured transport capacity; no truncation or API fallback was attempted')
    const item = { id: `model-${randomUUID()}`, taskId: task.taskId, sessionId: options.sessionId,
      request: JSON.parse(serialized), serialized, sha256: hash(serialized), createdAt: Date.now(), accepted: false }
    const previous = this.lastForTask.get(task.taskId)
    if (previous) {
      const delta = requestDelta(previous, item.request, item.sha256)
      if (delta.length < serialized.length) item.delta = delta
    }
    let resolve, reject
    const answer = new Promise((yes, no) => { resolve = yes; reject = no })
    answer.catch(() => {})
    item.resolve = resolve
    item.reject = reject
    const abort = () => reject(new Error('External model request cancelled'))
    signal?.addEventListener('abort', abort, { once: true })
    try {
      await this.persist(item.id, { state: 'pending', taskId: task.taskId, sessionId: item.sessionId, request: item.request, sha256: item.sha256 })
      if (item.request.tools?.length) {
        const catalog = { observedAt: Date.now(), toolNames: item.request.tools.map(tool => tool.name).filter(Boolean) }
        await this.persist('capability-catalog', catalog)
        this.latestCatalog = catalog
      }
      signal?.throwIfAborted()
      if (this.closed) throw new Error('External model driver stopped before request publication')
      // An agent step cannot execute DSH tools until its external decision arrives.
      // Release its execution slot before publishing the request so an early
      // response cannot race ahead of the slot hand-off.
      if ((item.request.purpose ?? 'agent-step') === 'agent-step') {
        await this.tasks.releaseExecutionSlot?.(task.taskId)
        signal?.throwIfAborted()
      }
      this.pending.set(item.id, item)
      this.lastForTask.set(task.taskId, item)
      await this.tasks.progress?.(task.taskId)
      for (const notify of this.watchers.get(task.taskId) ?? []) notify()
      const response = await answer
      signal?.throwIfAborted()
      let index = 0
      if (response.text) {
        yield { type: 'block-start', index, blockType: 'text' }
        yield { type: 'text-delta', index, text: response.text }
        yield { type: 'block-end', index: index++, block: { type: 'text', text: response.text } }
      }
      for (const call of response.tool_calls) {
        yield { type: 'block-start', index, blockType: 'tool-call' }
        yield { type: 'tool-call-delta', index, id: call.id, name: call.name, argumentsDelta: call.arguments }
        yield { type: 'block-end', index: index++, block: { type: 'tool-call', id: call.id, name: call.name, arguments: call.arguments } }
      }
      yield { type: 'finish', reason: { kind: response.tool_calls.length ? 'tool-calls' : 'stop' } }
    } finally {
      signal?.removeEventListener('abort', abort)
      this.pending.delete(item.id)
    }
  }

  async respond(taskId, rawResponse) {
    const response = responseSchema.parse(rawResponse)
    const fingerprint = hash(JSON.stringify(response))
    const receipt = this.receipts.get(response.model_request_id)
    if (receipt) {
      if (receipt.taskId !== taskId || receipt.fingerprint !== fingerprint) throw new Error('Model request already answered with a different response')
      await receipt.saved
      return { accepted: true, duplicate: true, model_request_id: response.model_request_id }
    }
    const item = this.pending.get(response.model_request_id)
    if (!item || item.taskId !== taskId || item.accepted) throw new Error('Stale, cancelled, or foreign model request; no response accepted')
    if (this.tasks.records.get(taskId)?.status !== 'running') throw new Error('Owning task is not running; no model response accepted')
    const names = new Set((item.request.tools ?? []).map(tool => tool.name))
    const ids = new Set()
    for (const call of response.tool_calls) {
      if (!names.has(call.name)) throw new Error(`Tool is absent from this DSH step: ${call.name}`)
      if (ids.has(call.id)) throw new Error('Duplicate tool call id in model response')
      ids.add(call.id)
      const args = JSON.parse(call.arguments)
      if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error('Tool arguments must encode a JSON object')
      if ((call.name === 'subagent' || call.name === 'subagent_fork') && args.run_in_background !== false) {
        throw new Error('External-driver subagents currently require run_in_background:false; background child lifetime is not yet bridge-managed')
      }
      // DSH's native tools pipeline remains the authoritative schema/permission validator.
    }
    item.accepted = true // Reserve before I/O so concurrent submissions cannot execute twice.
    const saved = this.persist(`${item.id}-response`, { taskId, fingerprint, response })
    this.receipts.set(item.id, { taskId, fingerprint, saved })
    try {
      await saved
      await this.tasks.progress?.(taskId)
      if ((item.request.purpose ?? 'agent-step') === 'agent-step' && this.tasks.resumeWhenSlot) {
        // Keep the MCP response short. The accepted decision is durable, while
        // DSH resumes only after a bounded execution slot is available.
        this.tasks.resumeWhenSlot(taskId).then(() => item.resolve(response), error => item.reject(error))
      } else item.resolve(response)
      return { accepted: true, duplicate: false, model_request_id: item.id }
    } catch (error) {
      item.reject(error)
      throw error
    }
  }

  close() {
    this.closed = true
    for (const item of this.pending.values()) item.reject(new Error('External driver disposed'))
  }
}
