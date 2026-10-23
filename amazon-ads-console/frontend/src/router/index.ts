import { createRouter, createWebHistory } from 'vue-router'
import { nextTick } from 'vue'
import { homeFor, canAccessRoute } from './access'
export { ROLE_HOME, homeFor } from './access'
import { enterPage, completePageRender } from '../diagnostics/browserTrace'
import { useSessionStore } from '../stores/session'
import { beginNavigation, finishNavigation, navigationState, recoverNavigation } from './navigation'

const DiagnosticsView = () => import('../views/DiagnosticsView.vue')
const CodexDevicesView = () => import('../views/CodexDevicesView.vue')
const OperatorDetailView = () => import('../views/OperatorDetailView.vue')
const ProductMappingsView = () => import('../views/ProductMappingsView.vue')
const OperatorCpoView = () => import('../views/OperatorCpoView.vue')
const MyCpoView = () => import('../views/MyCpoView.vue')
const LoginView = () => import('../views/LoginView.vue')
const AllocationView = () => import('../views/AllocationView.vue')
const DataChangesView = () => import('../views/DataChangesView.vue')
const DataMaintenanceView = () => import('../views/DataMaintenanceView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/', component: OperatorCpoView, meta: { roleHome: true } },
    { path: '/operator-cpo', component: OperatorCpoView, meta: { keepAlive: true } },
    // Personal detail remains scoped to the authenticated operator group.
    { path: '/my-cpo', component: MyCpoView, meta: { keepAlive: true } },
    { path: '/ad-allocation', component: AllocationView },
    { path: '/data-changes', component: DataChangesView },
    { path: '/product-mappings', component: ProductMappingsView },
    { path: '/data-maintenance', component: DataMaintenanceView },
    { path: '/reports', redirect: '/data-maintenance' },
    { path: '/cpo-jobs', redirect: '/data-maintenance?tab=imports' },
    { path: '/diagnostics', component: DiagnosticsView },
    { path: '/codex-devices', component: CodexDevicesView },
    { path: '/operators/:operator', component: OperatorDetailView },
    // Old bookmarks and unknown URLs return to the authenticated role's home.
    { path: '/:pathMatch(.*)*', component: OperatorCpoView, meta: { roleHome: true } },
  ],
})

const prefetched = new Set<string>()
// Fetch only the code for a visible menu item on hover/focus; component setup
// and its data requests still run only after an authorized navigation.
export function prefetchRoute(path: string): void {
  if (!canAccessRoute(useSessionStore().user?.roleCode, path) || prefetched.has(path)) return
  const records = router.resolve(path).matched
  const component = records[records.length - 1]?.components?.default
  if (typeof component !== 'function') return
  prefetched.add(path)
  void Promise.resolve().then(() => (component as () => Promise<unknown>)())
    .catch(() => { prefetched.delete(path) })
}

router.beforeEach(async (to) => {
  beginNavigation(to.fullPath)
  const session = useSessionStore()
  if (to.meta.public) {
    if (to.path === '/login' && session.token && await session.ensureUser()) {
      const home = homeFor(session.user?.roleCode)
      return home === '/login' ? true : home
    }
    return true
  }

  if (!session.token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (!await session.ensureUser()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  const role = session.user?.roleCode
  if (to.meta.roleHome) return homeFor(role)
  if (!canAccessRoute(role, to.path)) return homeFor(role)
  return true
})

router.afterEach(async (to, _from, failure) => {
  finishNavigation(to.fullPath)
  if (failure) return
  const pageId = enterPage(to.path)
  await nextTick()
  requestAnimationFrame(() => completePageRender(pageId, 'shell'))
})

router.onError((error, to) => {
  if (navigationState.target !== to.fullPath) return
  if (recoverNavigation(error, to.fullPath)) return
  finishNavigation(to.fullPath, '页面加载失败，请重新加载后重试。')
})

export default router
