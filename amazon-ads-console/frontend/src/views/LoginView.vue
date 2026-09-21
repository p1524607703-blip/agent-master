<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import { homeFor } from '../router'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const user = await session.login(username.value.trim(), password.value)
    // 运营登录后直接进自己的页面；只接受本人有权访问的 redirect
    const raw = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    const allowed = raw.startsWith('/') && (user.roleCode !== 'operator' || raw.startsWith('/my-cpo'))
    await router.replace(allowed ? raw : homeFor(user.roleCode))
  } catch (err) {
    error.value = err instanceof Error ? err.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-card">
      <div class="brand-mark">A</div>
      <h1>AdSight</h1>
      <p class="subtitle">亚马逊广告数据系统</p>
      <form @submit.prevent="submit">
        <label for="username">账号</label>
        <input id="username" v-model="username" autocomplete="username" placeholder="请输入账号" required />
        <label for="password">密码</label>
        <input id="password" v-model="password" type="password" autocomplete="current-password" placeholder="请输入密码" required />
        <p v-if="error" id="login-error" class="error">{{ error }}</p>
        <button id="login-submit" type="submit" :disabled="loading">{{ loading ? '登录中…' : '登录' }}</button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; place-items: center; background: #f4f7fb; padding: 24px; }
.login-card { width: min(380px, 100%); background: #fff; border: 1px solid #e6eaf0; border-radius: 14px; padding: 36px; box-shadow: 0 18px 50px rgba(17, 24, 39, .08); }
.brand-mark { width: 42px; height: 42px; border-radius: 11px; display: grid; place-items: center; background: #1677ff; color: white; font-weight: 700; font-size: 20px; }
h1 { margin: 18px 0 4px; font-size: 26px; color: #111827; }
.subtitle { margin: 0 0 28px; color: #6b7280; }
form { display: grid; gap: 10px; }
label { margin-top: 8px; color: #374151; font-size: 14px; font-weight: 600; }
input { height: 42px; border: 1px solid #d9dee8; border-radius: 8px; padding: 0 12px; font-size: 14px; outline: none; }
input:focus { border-color: #1677ff; box-shadow: 0 0 0 3px rgba(22, 119, 255, .12); }
button { height: 42px; margin-top: 12px; border: 0; border-radius: 8px; background: #1677ff; color: #fff; font-size: 15px; font-weight: 600; cursor: pointer; }
button:disabled { opacity: .65; cursor: default; }
.error { margin: 4px 0 0; color: #d03050; font-size: 13px; }
</style>
