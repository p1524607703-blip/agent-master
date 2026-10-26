export type TokenField = 'todayTokens' | 'totalTokens' | 'currentWindowTokens'
export type TokenRecord = { todayTokens: number | string | null; totalTokens: number | string | null; currentWindowTokens?: number | string | null }

function tokenNumber(value: number | string | null | undefined): number | null {
  if (value == null || (typeof value === 'string' && !/^\d+$/.test(value))) return null
  const parsed = Number(value)
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null
}

export function sumTokens(items: TokenRecord[], field: TokenField): number | null {
  const values = items.map(item => tokenNumber(item[field])).filter((v): v is number => v !== null)
  if (!values.length) return null
  const total = values.reduce((sum, value) => sum + value, 0)
  return Number.isSafeInteger(total) ? total : null
}

export function usageShare(part: number | null, total: number | null): number | null {
  if (part === null || total === null || total <= 0 || part < 0 || part > total) return null
  return part / total * 100
}

export function percentLabel(value: number | null): string {
  if (value === null) return '—'
  if (value > 0 && value < 0.1) return '<0.1%'
  return `${value.toFixed(1)}%`
}
