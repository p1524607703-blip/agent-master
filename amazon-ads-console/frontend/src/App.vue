<script setup lang="ts">
import AppSidebar from './components/AppSidebar.vue'
import AppTopbar from './components/AppTopbar.vue'
import { NConfigProvider, type GlobalThemeOverrides } from 'naive-ui'
import { useRoute } from 'vue-router'
import { navigationState } from './router/navigation'

const retryNavigation = () => window.location.assign(navigationState.target)

const route = useRoute()
const naiveTheme: GlobalThemeOverrides = {
  common: {
    primaryColor: '#1677ff',
    primaryColorHover: '#4096ff',
    primaryColorPressed: '#0958d9',
    borderRadius: '7px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif',
  },
}
</script>

<template>
  <NConfigProvider :theme-overrides="naiveTheme">
    <router-view v-if="route.meta.public" />
    <div v-else class="app-shell">
      <AppSidebar />
      <div class="app-main">
        <AppTopbar />
        <div v-if="navigationState.loading" class="navigation-progress" role="status" aria-live="polite">正在打开页面…</div>
        <div v-if="navigationState.error" class="navigation-error" role="alert">
          {{ navigationState.error }} <button class="btn compact" type="button" @click="retryNavigation">重新加载</button>
        </div>
        <router-view v-slot="{ Component }">
          <!-- One route vnode must keep the same parent across cached and uncached pages. -->
          <KeepAlive :include="['MyCpoView', 'OperatorCpoView']" :max="4">
            <component :is="Component" />
          </KeepAlive>
        </router-view>
      </div>
    </div>
  </NConfigProvider>
</template>

<style scoped>
.navigation-progress{position:sticky;top:52px;z-index:4;padding:7px 20px;border-bottom:2px solid #1677ff;background:#edf5ff;color:#1769c2;font-size:12px}
.navigation-error{margin:12px 20px;padding:10px 12px;border:1px solid #f4c987;border-radius:8px;background:#fff7e9;color:#8a5900;font-size:12px;display:flex;align-items:center;justify-content:space-between;gap:12px}
</style>
