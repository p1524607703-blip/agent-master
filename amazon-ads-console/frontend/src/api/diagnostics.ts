import { getJsonStrict } from './client'

export type DiagnosticRequest = {
  request_id: string
  timestamp?: string
  started_at?: string
  user_id?: number | null
  username?: string | null
  role?: string | null
  operator_group?: string | null
  date?: string | null
  period?: string | null
  period_start?: string | null
  period_end?: string | null
  endpoint?: string
  method?: string
  status_code?: number
  status?: string | number
  total_ms?: number
  psql_ms?: number
  psql_calls?: number
  db_wall_ms?: number
  build_ms?: number
  lock_wait_ms?: number
  cache_hit?: boolean
  cache_status?: string
  revision?: string
  l1_hit?: number
  l1_miss?: number
  l1_stale?: number
  l2_hit?: number
  l2_miss?: number
  l2_error?: number
  lock_acquired?: number
  lock_timeout?: number
  pid?: number
  exception_type?: string | null
  stack?: Array<{ file: string; line: number; function: string; exception_type?: string }>
  release_version?: string
  git_commit?: string
  timings?: { total_ms?: number; psql_ms?: number; build_ms?: number; lock_wait_ms?: number }
  cache?: { hit?: boolean; status?: string; revision?: string }
  release?: string | { release_version?: string; git_commit?: string }
  commit?: string
}

export type DiagnosticStatus = {
  release: { release_version?: string; git_commit?: string }
  cache: Record<string, unknown>
  trace: { available: boolean; retention_days?: number }
}

export type DiagnosticRequests = {
  items: DiagnosticRequest[]
  available: boolean
  retention_days?: number
  scan_truncated?: boolean
  message?: string
}

export type DiagnosticFilters = {
  request_id?: string
  user_id?: string
  username?: string
  endpoint?: string
  since?: string
  until?: string
  limit?: string
}

export const getDiagnosticsStatus = () => getJsonStrict<DiagnosticStatus>('/diagnostics/status')
export function getDiagnosticRequests(filters: DiagnosticFilters): Promise<DiagnosticRequests> {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value)
  return getJsonStrict<DiagnosticRequests>(`/diagnostics/requests?${params}`)
}
