<script setup lang="ts">
import { NSkeleton } from 'naive-ui'

withDefaults(defineProps<{
  variant?: 'dashboard' | 'table' | 'detail' | 'cards'
  rows?: number
}>(), {
  variant: 'table',
  rows: 7,
})
</script>

<template>
  <div class="data-skeleton" :class="`variant-${variant}`" aria-busy="true" aria-label="数据加载中">
    <template v-if="variant === 'dashboard'">
      <div class="skeleton-kpis">
        <NSkeleton v-for="i in 6" :key="`kpi-${i}`" height="96px" :sharp="false" />
      </div>
      <div class="skeleton-panels">
        <NSkeleton v-for="i in 2" :key="`panel-${i}`" height="320px" :sharp="false" />
      </div>
      <NSkeleton height="260px" :sharp="false" />
    </template>

    <template v-else-if="variant === 'cards'">
      <div class="skeleton-kpis skeleton-kpis-4">
        <NSkeleton v-for="i in 4" :key="`card-${i}`" height="112px" :sharp="false" />
      </div>
      <div class="skeleton-table">
        <NSkeleton v-for="i in rows" :key="`row-${i}`" height="44px" :sharp="false" />
      </div>
    </template>

    <template v-else-if="variant === 'detail'">
      <div class="skeleton-kpis skeleton-kpis-4">
        <NSkeleton v-for="i in 4" :key="`detail-kpi-${i}`" height="82px" :sharp="false" />
      </div>
      <div class="skeleton-table wide">
        <NSkeleton height="54px" :sharp="false" />
        <NSkeleton v-for="i in rows" :key="`detail-row-${i}`" height="46px" :sharp="false" />
      </div>
    </template>

    <template v-else>
      <div class="skeleton-table">
        <NSkeleton height="52px" :sharp="false" />
        <NSkeleton v-for="i in rows" :key="`table-row-${i}`" height="46px" :sharp="false" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.data-skeleton{display:flex;flex-direction:column;gap:14px;margin-top:14px;min-width:0}
.skeleton-kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}
.skeleton-kpis-4{grid-template-columns:repeat(4,minmax(0,1fr))}
.skeleton-panels{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.skeleton-table{display:flex;flex-direction:column;gap:8px;padding:14px;border:1px solid #edf0f4;border-radius:12px;background:#fff}
.skeleton-table.wide{overflow:hidden}
@media(max-width:1100px){.skeleton-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.skeleton-kpis-4{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.skeleton-kpis,.skeleton-kpis-4,.skeleton-panels{grid-template-columns:1fr}}
</style>
