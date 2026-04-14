<template>
  <aside class="sidebar">
    <!-- Logo -->
    <div class="sidebar__logo">
      <div class="logo-icon">R</div>
      <div class="logo-text">
        <span class="logo-title">RADAR AI</span>
        <span class="logo-sub">选品雷达</span>
      </div>
    </div>

    <!-- Nav -->
    <nav class="sidebar__nav">
      <RouterLink
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ 'nav-item--active': $route.path === item.path }"
      >
        <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>

    <!-- Bottom status -->
    <div class="sidebar__footer">
      <div class="system-status">
        <span class="status-dot" :class="systemOk ? 'status-dot--ok' : 'status-dot--warn'" />
        <span class="status-text">{{ systemOk ? '系统正常' : '检查中...' }}</span>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'

const $route = useRoute()
const systemOk = ref(true)

const navItems = [
  { path: '/',         icon: 'DataBoard',   label: '仪表盘' },
  { path: '/trends',   icon: 'TrendCharts', label: '趋势发现' },
  { path: '/analysis', icon: 'MagicStick',  label: 'AI分析' },
  { path: '/products', icon: 'Grid',        label: '选品看板' },
  { path: '/agents',   icon: 'Monitor',     label: 'Agent监控' },
]
</script>

<style scoped>
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: 220px;
  height: 100vh;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(24px) saturate(200%);
  -webkit-backdrop-filter: blur(24px) saturate(200%);
  border-right: 1px solid rgba(255, 255, 255, 0.75);
  box-shadow: 4px 0 24px rgba(8, 145, 178, 0.08);
  display: flex;
  flex-direction: column;
  z-index: 100;
}

.sidebar__logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 24px 20px 20px;
  border-bottom: 1px solid rgba(8, 145, 178, 0.1);
}

.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #0891b2, #22d3ee);
  color: white;
  font-weight: 800;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-title {
  font-weight: 700;
  font-size: 15px;
  color: #0891b2;
  display: block;
  line-height: 1.2;
}

.logo-sub {
  font-size: 11px;
  color: #94a3b8;
}

.sidebar__nav {
  flex: 1;
  padding: 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #475569;
  text-decoration: none;
  transition: all 0.15s ease;
}

.nav-item:hover {
  background: rgba(8, 145, 178, 0.08);
  color: #0891b2;
}

.nav-item--active {
  background: linear-gradient(135deg, rgba(8, 145, 178, 0.15), rgba(34, 211, 238, 0.1));
  color: #0891b2;
  font-weight: 600;
  border: 1px solid rgba(8, 145, 178, 0.2);
}

.nav-icon {
  font-size: 18px;
}

.sidebar__footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(8, 145, 178, 0.08);
}

.system-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot--ok {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}

.status-dot--warn {
  background: #f59e0b;
}

.status-text {
  font-size: 12px;
  color: #64748b;
}
</style>
