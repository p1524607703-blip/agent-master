<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'

const session = useSessionStore()
const router = useRouter()

async function logout() {
  await session.logout()
  await router.replace('/login')
}
</script>

<template>
  <header class="topbar">
    <div class="top-left">
      <span class="chip">全部账户</span>
      <span class="chip">数据日按页面筛选</span>
      <span class="chip good">RDS 已连接</span>
    </div>
    <div class="top-right">
      <span class="role-label">当前身份：{{ session.roleLabel }}</span>
      <span id="current-user" class="chip">{{ session.user?.displayName || session.user?.username }}</span>
      <button id="logout-btn" class="logout-btn" type="button" @click="logout">退出</button>
    </div>
  </header>
</template>

<style scoped>
.logout-btn { border: 1px solid #d9dee8; background: #fff; color: #4b5563; border-radius: 7px; height: 30px; padding: 0 11px; cursor: pointer; }
.logout-btn:hover { border-color: #1677ff; color: #1677ff; }
</style>
