import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/pages/Dashboard/index.vue'),
    meta: { title: '数据仪表盘' }
  },
  {
    path: '/trends',
    name: 'TrendDiscovery',
    component: () => import('@/pages/TrendDiscovery/index.vue'),
    meta: { title: '趋势发现' }
  },
  {
    path: '/analysis',
    name: 'AIAnalysis',
    component: () => import('@/pages/AIAnalysis/index.vue'),
    meta: { title: 'AI分析' }
  },
  {
    path: '/products',
    name: 'ProductBoard',
    component: () => import('@/pages/ProductBoard/index.vue'),
    meta: { title: '商品看板' }
  },
  {
    path: '/agents',
    name: 'AgentMonitor',
    component: () => import('@/pages/AgentMonitor/index.vue'),
    meta: { title: 'Agent监控' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  document.title = `${to.meta.title ?? 'RADAR AI'} — 选品雷达`
})

export default router
