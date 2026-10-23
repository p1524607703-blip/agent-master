import { reactive } from 'vue'

export const navigationState = reactive({ target: '', loading: false, error: '' })

export function beginNavigation(target: string): void {
  navigationState.target = target
  navigationState.loading = true
  navigationState.error = ''
}

export function finishNavigation(target: string, error = ''): void {
  if (navigationState.target !== target) return
  navigationState.loading = false
  navigationState.error = error
}

export function isNavigatingAway(path: string): boolean {
  return navigationState.loading && navigationState.target.split(/[?#]/)[0] !== path
}

export function isChunkLoadError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return /failed to fetch dynamically imported module|error loading dynamically imported module|importing a module script failed|unable to preload css|loading chunk .* failed/i.test(message)
}

// Keep the intended destination, and permit only one automatic refresh per
// minute. A persistent network failure must never create a reload loop.
export function recoverNavigation(error: unknown, target: string,
  browser: Pick<Window, 'sessionStorage' | 'location'> = window, now = Date.now()): boolean {
  if (!isChunkLoadError(error) || !target.startsWith('/') || target.startsWith('//')) return false
  try {
    const key = 'adsight.navigation-recovery'
    const previous = Number(browser.sessionStorage.getItem(key))
    if (previous && now - previous < 60_000) return false
    browser.sessionStorage.setItem(key, String(now))
    browser.location.replace(target)
    return true
  } catch {
    return false
  }
}
