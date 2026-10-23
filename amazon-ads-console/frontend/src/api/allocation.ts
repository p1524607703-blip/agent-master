import { API_BASE, AUTH_TOKEN_KEY } from './client'

export type JsonObject = Record<string, unknown>
export type AllocationCapabilities = { enabled: boolean; environment?: string; authoritative_source_connected?: boolean; can_create_run?: boolean; confirmed_reference_available?: boolean; export_formats?: string[]; production_ready?: boolean; comparison_available?: boolean; controlled_bridge_available?: boolean; message?: string }
export type AllocationProvenance = { source_label?: string | null; report_exported_date?: string | null; fact_snapshot_date?: string | null; rule_version?: string | null; scope_label?: string | null; mapping_version?: string | null; source_sha256?: string | null }
export type AllocationRun = { run_id: string; status?: string; calculation_status?: string; review_status?: string; purpose?: string; provenance?: AllocationProvenance; revision?: string | number; period?: string; created_at?: string; summary?: JsonObject; capabilities?: JsonObject; [key: string]: unknown }
export type ChangeBatch = { id: string; status: string; version: number; etag: string; content_hash: string; row_count: number; error_count: number; file_name: string; created_by: string | number; operator_code?: string; created_at?: string; review_reason?: string; capabilities: { can_submit?: boolean; can_review?: boolean; can_apply?: boolean } }
export type ChangeRow = { line: number; old_values?: JsonObject; new_values?: JsonObject; changed_fields?: string[]; errors?: unknown[]; record_key?: string }
export type CursorPage<T> = { items: T[]; next_cursor: string | null; total?: number }

export class ModuleApiError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) { super(message); this.status = status; this.code = code }
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra }
}

async function checked(path: string, init: RequestInit = {}): Promise<Response> {
  let response: Response
  try { response = await fetch(`${API_BASE}${path}`, { ...init, headers: headers(init.headers as Record<string, string> | undefined) }) }
  catch { throw new ModuleApiError(0, 'NETWORK_ERROR', '连接失败，请检查网络后重试。') }
  if (response.ok) return response
  const body = await response.json().catch(() => ({})) as JsonObject
  const detail = (body.error || body.detail || body) as JsonObject | string
  const code = typeof detail === 'object' && detail ? String(detail.code || '') : ''
  const message = response.status === 401 ? '登录已失效，请重新登录。' : response.status === 403 ? '当前账号没有此操作权限。' : code === 'MODULE_DISABLED' ? '模块尚未启用，当前只能查看开发验收入口。' : typeof detail === 'string' ? detail : String(detail?.message || `请求失败（${response.status}），请重试。`)
  throw new ModuleApiError(response.status, code, message)
}

export async function moduleGet<T>(path: string): Promise<T> {
  const response = await checked(path)
  const body = await response.json()
  return (body && typeof body === 'object' && 'data' in body ? body.data : body) as T
}

export function requestKey(): string {
  // getRandomValues is also available on the console's HTTP IP origin.
  const bytes = new Uint8Array(16)
  globalThis.crypto.getRandomValues(bytes)
  bytes[6] = (bytes[6]! & 0x0f) | 0x40
  bytes[8] = (bytes[8]! & 0x3f) | 0x80
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export async function modulePost<T>(path: string, body: unknown, etag?: string): Promise<T> {
  const response = await checked(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestKey(), ...(etag ? { 'If-Match': etag } : {}) }, body: JSON.stringify(body) })
  const result = await response.json()
  return (result && typeof result === 'object' && 'data' in result ? result.data : result) as T
}

export function listItems<T>(body: { items?: T[] } | T[]): T[] { return Array.isArray(body) ? body : body.items || [] }

function pageQuery(cursor?: string | null): string {
  const query = new URLSearchParams({ limit: '50' })
  if (cursor != null) query.set('cursor', cursor)
  return `?${query}`
}

export async function authenticatedDownload(path: string, fallbackName: string): Promise<void> {
  const response = await checked(path)
  const blob = await response.blob()
  const contentDisposition = response.headers.get('Content-Disposition') || ''
  const match = contentDisposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i)
  let name = match?.[1] || match?.[2] || fallbackName
  try { name = decodeURIComponent(name) } catch { /* Keep a literal server filename if decoding fails. */ }
  name = name.replace(/[\\/\u0000-\u001f]/g, '_')
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = name; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const allocationApi = {
  capabilities: () => moduleGet<AllocationCapabilities>('/ad-allocation/v1/capabilities'),
  runs: (cursor?: string | null) => moduleGet<CursorPage<AllocationRun>>('/ad-allocation/v1/runs' + pageQuery(cursor)),
  run: (id: string) => moduleGet<AllocationRun>(`/ad-allocation/v1/runs/${encodeURIComponent(id)}`),
  rows: (id: string, report: string, cursor?: string | null) => moduleGet<CursorPage<JsonObject>>(`/ad-allocation/v1/runs/${encodeURIComponent(id)}/${report}` + pageQuery(cursor)),
  workbook: (id: string) => authenticatedDownload(`/ad-allocation/v1/runs/${encodeURIComponent(id)}/workbook.xlsx`, `款式费用_${id}.xlsx`),
  create: (period: string, timezone: string, snapshot: unknown) => modulePost<AllocationRun>('/ad-allocation/v1/runs', { period, report_timezone: timezone, snapshot }),
  export: async (id: string, report: string) => {
    const result = await modulePost<{ export_id: string }>(`/ad-allocation/v1/runs/${encodeURIComponent(id)}/exports`, { format: 'csv', report })
    if (!result.export_id) throw new Error('导出接口没有返回文件编号。')
    await authenticatedDownload(`/ad-allocation/v1/exports/${encodeURIComponent(result.export_id)}/download`, `试算_${report}_${id}.csv`)
  },
}

export const changesApi = {
  list: (cursor?: string | null) => moduleGet<CursorPage<ChangeBatch>>('/data-changes' + pageQuery(cursor)),
  batch: (id: string) => moduleGet<ChangeBatch>(`/data-changes/${encodeURIComponent(id)}`),
  rows: (id: string, cursor?: string | null) => moduleGet<CursorPage<ChangeRow>>(`/data-changes/${encodeURIComponent(id)}/rows` + pageQuery(cursor)),
  template: (kind: 'mapping' | 'mapping-add' = 'mapping') => authenticatedDownload('/data-changes/templates?template=' + kind, kind === 'mapping-add' ? '新增ASIN模板.csv' : '运营映射变更模板.csv'),
  upload: (fileName: string, csvText: string, context: JsonObject) => modulePost<ChangeBatch>('/data-changes/uploads', { file_name: fileName, csv_text: csvText, context }),
  submit: (batch: ChangeBatch) => modulePost<ChangeBatch>(`/data-changes/${encodeURIComponent(batch.id)}/submit`, {}, batch.etag),
  withdraw: (batch: ChangeBatch) => modulePost<ChangeBatch>(`/data-changes/${encodeURIComponent(batch.id)}/withdraw`, {}, batch.etag),
  decision: (batch: ChangeBatch, decision: 'APPROVE' | 'REJECT', reason: string) => modulePost<ChangeBatch>(`/data-changes/${encodeURIComponent(batch.id)}/decision`, { decision, reason, content_hash: batch.content_hash }, batch.etag),
}
