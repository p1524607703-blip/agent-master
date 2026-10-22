export type SbAttributionMode = 'name' | 'asin'
export const normalizeSbMode = (value: unknown): SbAttributionMode => value === 'asin' ? 'asin' : 'name'
export const sbModeLabel = (mode: SbAttributionMode) => mode === 'asin' ? 'SB 按推广 ASIN' : 'SB 按命名'

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
