<script setup lang="ts">
import AppSidebar from './components/AppSidebar.vue'
import AppTopbar from './components/AppTopbar.vue'
import { NConfigProvider, type GlobalThemeOverrides } from 'naive-ui'
import { useRoute } from 'vue-router'

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
        <router-view v-slot="{ Component, route: viewRoute }">
          <KeepAlive :max="4">
            <component :is="Component" v-if="viewRoute.meta.keepAlive" />
          </KeepAlive>
          <component :is="Component" v-if="!viewRoute.meta.keepAlive" />
        </router-view>
      </div>
    </div>
  </NConfigProvider>
</template>
