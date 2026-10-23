import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles.css'

import { API_BASE, AUTH_TOKEN_KEY } from './api/client'
import { createFrontendReporter, installFrontendDiagnostics } from './diagnostics/frontendErrors'
import { configureNavigationDiagnostics, navigationState } from './router/navigation'

const app = createApp(App)
const reporter = createFrontendReporter({
  clientCommit: import.meta.env.VITE_APP_COMMIT || 'development',
  endpoint: `${API_BASE}/diagnostics/frontend-errors`,
  token: () => localStorage.getItem(AUTH_TOKEN_KEY),
  context: () => ({page_path:router.currentRoute.value.path || location.pathname,
    target_path:navigationState.loading ? navigationState.target : ''}),
})
installFrontendDiagnostics(app, reporter)
configureNavigationDiagnostics((target,duration) => {void reporter.report('navigation_timeout',null,{target_path:target,duration_ms:duration})})
router.onError((error) => {void reporter.report('router_error',error)})
app.use(createPinia()).use(router).mount('#app')
