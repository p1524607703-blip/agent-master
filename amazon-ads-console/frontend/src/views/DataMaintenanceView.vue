<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
const imports = computed(() => route.query.tab === 'imports')
const ReportsView = defineAsyncComponent(() => import('./ReportsView.vue'))
const ImportsView = defineAsyncComponent(() => import('./CpoJobsView.vue'))
</script>

<template>
  <section class="maintenance-page">
    <div class="type-tabs maintenance-tabs" aria-label="数据维护功能">
      <router-link class="tab" :class="{active: !imports}" to="/data-maintenance">报告覆盖</router-link>
      <router-link class="tab" :class="{active: imports}" to="/data-maintenance?tab=imports">手动补传</router-link>
    </div>
    <ImportsView v-if="imports" />
    <ReportsView v-else />
  </section>
</template>

<style scoped>
.maintenance-tabs{padding:20px 24px 0;margin-bottom:0}
.maintenance-tabs a{text-decoration:none}
</style>
