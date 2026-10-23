export type SbAttributionMode = 'name' | 'asin'
export const normalizeSbMode = (value: unknown): SbAttributionMode => value === 'asin' ? 'asin' : 'name'
export const sbModeLabel = (mode: SbAttributionMode) => mode === 'asin' ? 'SB 按推广 ASIN' : 'SB 按命名'

/** Month links and selectors use the same full-date contract as reports/exports. */
export function normalizeCpoDate(value: unknown, period: string): string {
  const raw = String(value || '')
  if (period !== 'monthly') return raw
  const match = /^([0-9]{4})-(0[1-9]|1[0-2])(?:-([0-9]{2}))?$/.exec(raw)
  if (!match) return raw
  const year = Number(match[1]), month = Number(match[2]), day = Number(match[3] || 1)
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const days = [31,leap ? 29 : 28,31,30,31,30,31,31,30,31,30,31][month - 1]!
  if (!year || day < 1 || day > days) return raw
  return `${match[1]}-${match[2]}-01`
}

/** One live request per view; a canonical URL update must not fetch it twice. */
export class CpoRequestGate {
  private sequence = 0
  private controller?: AbortController
  private activeKey = ''
  private completedKey = ''
  private timeout?: ReturnType<typeof setTimeout>

  start(key: string, force = false) {
    if (key === this.activeKey || (!force && key === this.completedKey)) return null
    this.cancel()
    this.completedKey = ''
    const sequence = this.sequence
    const controller = new AbortController()
    this.controller = controller
    this.activeKey = key
    this.timeout = setTimeout(() => controller.abort(), 45_000)
    return {
      signal: controller.signal,
      current: () => sequence === this.sequence,
      finish: (completedKey?: string) => {
        if (sequence !== this.sequence) return
        clearTimeout(this.timeout)
        this.activeKey = ''
        this.controller = undefined
        if (completedKey) this.completedKey = completedKey
      },
    }
  }

  cancel() {
    ++this.sequence
    this.controller?.abort()
    clearTimeout(this.timeout)
    this.controller = undefined
    this.activeKey = ''
    this.completedKey = ''
  }
}
