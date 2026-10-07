import { createRouter, createWebHistory } from 'vue-router'
import { nextTick } from 'vue'
import DiagnosticsView from '../views/DiagnosticsView.vue'
import { canViewDiagnostics } from '../diagnostics/permissions'
import { enterPage, completePageRender } from '../diagnostics/browserTrace'
import DashboardView from '../views/DashboardView.vue'
import CpoJobsView from '../views/CpoJobsView.vue'
import IssuesView from '../views/IssuesView.vue'
import RulesView from '../views/RulesView.vue'
import ReportsView from '../views/ReportsView.vue'
import OperatorDetailView from '../views/OperatorDetailView.vue'
import ProductMappingsView from '../views/ProductMappingsView.vue'
import OperatorCpoView from '../views/OperatorCpoView.vue'
import MyCpoView from '../views/MyCpoView.vue'
import LoginView from '../views/LoginView.vue'
import { useSessionStore } from '../stores/session'

// 已下架模块（2026-09-15 用户要求暂时隐藏，视图文件保留以便随时恢复）：
//   /products   产品明细 → ProductsView.vue
//   /ad-types   广告类型 → AdTypesView.vue
const RETIRED: Record<string, string> = { '/products': '产品明细', '/ad-types': '广告类型' }

// 角色首页：运营登录后直接落到自己的页面（只含「CPO 单双数据情况」一个模块）
export const ROLE_HOME: Record<string, string> = {
  super_admin: '/operator-cpo',
  management: '/operator-cpo',
  operator: '/my-cpo',
}
export const homeFor = (role?: string | null) => ROLE_HOME[role || ''] || '/dashboard'

// 运营可访问的路由白名单：只有自己的 CPO 页面
const OPERATOR_ALLOWED = new Set(['/my-cpo'])

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/', component: OperatorCpoView, meta: { roleHome: true } },
    { path: '/dashboard', component: DashboardView },
    { path: '/cpo-jobs', component: CpoJobsView },
    { path: '/issues', component: IssuesView },
    { path: '/operator-cpo', component: OperatorCpoView, meta: { keepAlive: true } },
    // 运营页：只保留 CPO 单双数据情况，且只能看到自己的数据
    { path: '/my-cpo', component: MyCpoView, meta: { keepAlive: true } },
    { path: '/product-mappings', component: ProductMappingsView },
    { path: '/rules', component: RulesView },
    { path: '/reports', component: ReportsView },
    { path: '/diagnostics', component: DiagnosticsView, meta: { managementOnly: true } },
    { path: '/operators/:operator', component: OperatorDetailView },
    // 已下架模块直达链接 → 回看板（不暴露「模块已下线」这种信息给终端用户）
    ...Object.keys(RETIRED).map(p => ({ path: p, redirect: '/dashboard' })),
    // 其余未知路径一律兜到看板
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach(async (to) => {
  const session = useSessionStore()
  if (to.meta.public) {
    if (to.path === '/login' && session.token && await session.ensureUser()) {
      return homeFor(session.user?.roleCode)
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
  if (to.meta.managementOnly && !canViewDiagnostics(role)) return homeFor(role)
  // 运营：只能进自己的页面，其余访问一律回 /my-cpo
  if (role === 'operator' && !OPERATOR_ALLOWED.has(to.path)) {
    return '/my-cpo'
  }
  // 管理层 / 超级管理员：/my-cpo 不是他们的页面，回管理页
  if (role !== 'operator' && to.path === '/my-cpo') {
    return '/operator-cpo'
  }
  return true
})

router.afterEach(async (to, _from, failure) => {
  if (failure) return
  const pageId = enterPage(to.path)
  await nextTick()
  requestAnimationFrame(() => completePageRender(pageId, 'shell'))
})

export default router
