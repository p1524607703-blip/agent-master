import { nextTick, watch, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { completePageRender, currentPageId } from './browserTrace'

// Wait until the loaded data has reached the DOM, then one paint opportunity.
export function usePageRenderTrace(loading: Ref<boolean>): void {
  const route = useRoute()
  watch([loading, () => route.fullPath], async ([isLoading]) => {
    if (isLoading) return
    const pageId = currentPageId()
    await nextTick()
    requestAnimationFrame(() => completePageRender(pageId))
  }, { flush: 'post' })
}
