export type BrowserTraceEvent = {
  event: 'api_start' | 'api_end' | 'page_enter' | 'render_complete'
  timestamp: string
  page_id: string
  page_path: string
  request_id?: string
  method?: string
  endpoint?: string
  duration_ms?: number
  status_code?: number
  outcome?: 'ok' | 'http_error' | 'network_error'
  stage?: 'shell' | 'data'
}

// This bounded buffer only lives in this tab. Never retain headers, bodies, tokens or query strings.
const CAPACITY = 300
const events: BrowserTraceEvent[] = []
let page = { id: '', path: '', entered: 0 }

function id(): string {
  return globalThis.crypto?.randomUUID?.() || `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

function safePath(input: string): string {
  try { return new URL(input, globalThis.location?.origin || 'http://localhost').pathname }
  catch { return input.split(/[?#]/)[0] || '/' }
}

function append(event: Omit<BrowserTraceEvent, 'timestamp'>): BrowserTraceEvent {
  const recorded = { ...event, timestamp: new Date().toISOString() }
  events.push(recorded)
  if (events.length > CAPACITY) events.splice(0, events.length - CAPACITY)
  return recorded
}

export function enterPage(path: string): string {
  page = { id: id(), path: safePath(path), entered: performance.now() }
  append({ event: 'page_enter', page_id: page.id, page_path: page.path })
  return page.id
}

export function currentPageId(): string { return page.id }

export function completePageRender(pageId: string, stage: 'shell' | 'data' = 'data'): void {
  if (!pageId || pageId !== page.id) return
  append({ event: 'render_complete', page_id: page.id, page_path: page.path,
    duration_ms: Math.round((performance.now() - page.entered) * 100) / 100, stage })
}

export function browserTraceSnapshot(): { captured_at: string; capacity: number; events: BrowserTraceEvent[] } {
  return { captured_at: new Date().toISOString(), capacity: CAPACITY, events: events.map(e => ({ ...e })) }
}

export function clearBrowserTrace(): void { events.splice(0) }

export async function tracedFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const requestId = id()
  const headers = new Headers(init.headers)
  headers.set('X-Request-ID', requestId)
  const base = { page_id: page.id, page_path: page.path, request_id: requestId,
    method: (init.method || 'GET').toUpperCase(), endpoint: safePath(url) }
  const started = performance.now()
  const startEvent = append({ ...base, event: 'api_start' })
  try {
    const response = await fetch(url, { ...init, headers })
    const serverRequestId = response.headers.get('X-Request-ID') || requestId
    // Nginx owns the authoritative ID. Update this exact start event, so
    // overlapping calls to the same endpoint remain paired in exported traces.
    startEvent.request_id = serverRequestId
    append({ ...base, event: 'api_end', request_id: serverRequestId,
      duration_ms: Math.round((performance.now() - started) * 100) / 100,
      status_code: response.status, outcome: response.ok ? 'ok' : 'http_error' })
    return response
  } catch (error) {
    append({ ...base, event: 'api_end', duration_ms: Math.round((performance.now() - started) * 100) / 100,
      outcome: 'network_error' })
    throw error
  }
}

export function downloadEvidence(value: unknown, filename: string): void {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export async function copyEvidence(value: string | unknown): Promise<void> {
  const content = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(content)
    return
  }
  const field = document.createElement('textarea')
  field.value = content
  field.style.position = 'fixed'
  field.style.opacity = '0'
  document.body.appendChild(field)
  field.select()
  const copied = document.execCommand('copy')
  field.remove()
  if (!copied) throw new Error('复制失败，请下载记录')
}
