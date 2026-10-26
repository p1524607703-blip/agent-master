<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '../stores/session'
import { navigationFor } from '../router/access'
import { prefetchRoute } from '../router'

const session = useSessionStore()
const groups = computed(() => navigationFor(session.user?.roleCode))
</script>

<template>
  <aside class="sidebar compact-sidebar">
    <div class="brand" aria-label="AdSight运营控制台"><span class="logo" aria-hidden="true">A</span><span class="brand-name">AdSight<span class="brand-subtitle">运营控制台</span></span></div>
    <nav aria-label="主导航">
      <section v-for="group in groups" :key="group.title" class="nav-group">
        <div class="nav-title">{{ group.title }}</div>
        <router-link v-for="[path, label] in group.items" :key="path" :to="path" class="nav-item"
          @pointerenter="prefetchRoute(path)" @focus="prefetchRoute(path)">{{ label }}</router-link>
      </section>
    </nav>
  </aside>
</template>

<style scoped>
.brand .logo{flex-shrink:0}
.brand-name{min-width:0;line-height:1.2}
.brand-subtitle{display:block;font-size:12px;font-weight:500;margin-top:4px}
.compact-sidebar{display:flex;flex-direction:column;overflow-y:auto;overflow-x:hidden}
.nav-group + .nav-group{margin-top:16px;padding-top:8px;border-top:1px solid var(--border,#e7eaf0)}
@media(max-width:760px){.nav-group + .nav-group{margin-top:0;padding-top:0;border-top:0}}
</style>
