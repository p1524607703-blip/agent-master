import type { App } from 'vue'

export type FrontendErrorKind = 'vue_error' | 'javascript_error' | 'unhandled_rejection' | 'resource_error' | 'router_error' | 'navigation_timeout'
type Frame = { file: string; line: number; column: number }
type ErrorContext = { page_path: string; target_path?: string }
type Options = {
  clientCommit: string; endpoint: string; token: () => string | null; context: () => ErrorContext
  fetch?: typeof fetch; now?: () => number
}
const PAGES = new Set(['/','/login','/my-cpo','/operator-cpo','/ad-allocation','/data-changes','/product-mappings','/data-maintenance','/reports','/cpo-jobs','/diagnostics','/codex-devices'])
export function safePage(input: string): string {
  try {const path = new URL(input, 'http://localhost').pathname;return PAGES.has(path) ? path : path.startsWith('/operators/') ? '/operators/:operator' : '/unknown'}
  catch {return '/unknown'}
}
export function errorCode(kind: FrontendErrorKind, error: unknown): string {
  const message = error instanceof Error ? error.message : typeof error === 'string' ? error : ''
  if (kind === 'navigation_timeout') return 'NAVIGATION_TIMEOUT'
  if (kind === 'resource_error') return 'RESOURCE_LOAD_FAILED'
  if (/deactivate is not a function|activate is not a function/.test(message)) return 'CACHE_LIFECYCLE_ERROR'
  if (/null.*(?:parentNode|reading)|Cannot read properties of null/.test(message)) return 'NULL_DOM_NODE'
  if (/failed to fetch dynamically imported module|loading chunk|importing a module script failed|unable to preload css/i.test(message)) return 'CHUNK_LOAD_FAILED'
  return kind === 'router_error' ? 'ROUTER_ERROR' : kind === 'unhandled_rejection' ? 'UNHANDLED_REJECTION' : 'JAVASCRIPT_ERROR'
}
export function safeFrames(stack: string): Frame[] {
  const frames: Frame[] = []
  for (const line of stack.split('\n')) {
    const match = line.match(/(?:https?:\/\/[^\s/]+)?(\/(?:assets|src)\/[A-Za-z0-9_./-]+\.(?:js|ts|vue|css))(?:\?[^\s:)]*)?:(\d+):(\d+)/)
    if (match && !match[1]!.includes('..')) frames.push({file:match[1]!,line:Number(match[2]),column:Number(match[3])})
    if (frames.length === 12) break
  }
  return frames
}
const EXCEPTIONS = new Set(['Error','TypeError','ReferenceError','SyntaxError','RangeError','URIError','EvalError'])

export function createFrontendReporter(options: Options) {
  const send = options.fetch || fetch
  const now = options.now || Date.now
  const recent = new Map<string, number>()
  let sent: number[] = []
  let disposed = false
  return {
    async report(kind: FrontendErrorKind, error: unknown, extra: { duration_ms?: number; target_path?: string; resource?: string } = {}): Promise<boolean> {
      // Use native fetch, not tracedFetch: failed telemetry must never report itself.
      if (disposed) return false
      try {
        const token = options.token()
        if (!token) return false
        const context = options.context()
        const code = errorCode(kind, error)
        const stack = error instanceof Error ? safeFrames(error.stack || '') : []
        if (extra.resource) stack.push(...safeFrames(`${extra.resource}:0:0`))
        const page = safePage(context.page_path), target = context.target_path || extra.target_path || ''
        const safeTarget = target ? safePage(target) : ''
        const fingerprint = JSON.stringify([token,kind,code,page,safeTarget,stack[0]])
        const at = now()
        for (const [key,time] of recent) if (at-time >= 5000) recent.delete(key)
        sent = sent.filter(time => at-time < 60000)
        if (recent.has(fingerprint) || sent.length >= 30) return false
        recent.set(fingerprint, at);sent.push(at)
        const payload = {
          event_id: globalThis.crypto?.randomUUID?.() || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{const n=Math.random()*16|0;return(c==='x'?n:(n&3)|8).toString(16)}),
          kind, error_code:code, exception_type: kind === 'navigation_timeout' ? 'NavigationTimeout' : kind === 'resource_error' ? 'ResourceError' : error instanceof Error && EXCEPTIONS.has(error.name) ? error.name : 'Error',
          page_path:page,target_path:safeTarget, client_commit:options.clientCommit,
          duration_ms:Math.max(0,Math.min(86400000,Math.round(extra.duration_ms || 0))),occurrences:1,stack:stack.slice(0,12),
        }
        const controller = new AbortController()
        const timeout = setTimeout(() => controller.abort(),5000)
        try {
          const response = await send(options.endpoint,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify(payload),keepalive:true,signal:controller.signal})
          return response.ok
        } finally {clearTimeout(timeout)}
      } catch {return false}
    },
    dispose() {disposed=true;recent.clear();sent=[]},
  }
}
export type FrontendReporter = ReturnType<typeof createFrontendReporter>
export function installFrontendDiagnostics(app: App, reporter: FrontendReporter, browser: Window = window): () => void {
  const previous = app.config.errorHandler
  app.config.errorHandler = (error,instance,info) => {
    void reporter.report('vue_error',error)
    if (previous) previous(error,instance,info)
    else console.error(error)
  }
  const onError = (event: Event) => {
    if (event instanceof ErrorEvent) void reporter.report('javascript_error',event.error || event.message)
    else {
      const target = event.target
      const resource = target instanceof HTMLScriptElement ? target.src : target instanceof HTMLLinkElement ? target.href : ''
      if (resource) void reporter.report('resource_error',null,{resource})
    }
  }
  const onRejected = (event: PromiseRejectionEvent) => {void reporter.report('unhandled_rejection',event.reason)}
  browser.addEventListener('error',onError,true)
  browser.addEventListener('unhandledrejection',onRejected)
  return () => {app.config.errorHandler=previous;browser.removeEventListener('error',onError,true);browser.removeEventListener('unhandledrejection',onRejected);reporter.dispose()}
}
