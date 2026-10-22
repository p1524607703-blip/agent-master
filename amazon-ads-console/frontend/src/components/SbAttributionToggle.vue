<script setup lang="ts">
import type { SbAttributionMode } from '../api/cpoReport'
defineProps<{ modelValue: SbAttributionMode }>()
const emit = defineEmits<{ 'update:modelValue': [mode: SbAttributionMode] }>()
</script>

<template>
  <div class="sb-mode-control">
    <span class="sb-mode-title" id="sb-mode-label">SB 费用归属</span>
    <div class="sb-mode-buttons" role="group" aria-labelledby="sb-mode-label">
      <button type="button" :class="{ active: modelValue === 'name' }" :aria-pressed="modelValue === 'name'" @click="emit('update:modelValue', 'name')">按命名</button>
      <button type="button" :class="{ active: modelValue === 'asin' }" :aria-pressed="modelValue === 'asin'" @click="emit('update:modelValue', 'asin')">按推广 ASIN</button>
    </div>
    <span class="sb-mode-help">仅切换 SB；其他广告口径保持一致</span>
  </div>
</template>

<style scoped>
.sb-mode-control{display:flex;flex-direction:column;gap:5px;flex:0 0 auto}.sb-mode-title{font-size:11px;color:#7b8492}.sb-mode-buttons{display:flex;border:1px solid #d9e0e9;border-radius:8px;overflow:hidden;background:#fff}.sb-mode-buttons button{padding:8px 14px;border:0;background:transparent;color:#556174;font:inherit;cursor:pointer;white-space:nowrap}.sb-mode-buttons button+button{border-left:1px solid #d9e0e9}.sb-mode-buttons button.active{background:#eaf2ff;color:#1766cf;font-weight:600}.sb-mode-buttons button:focus-visible{outline:2px solid #1766cf;outline-offset:-3px}.sb-mode-help{font-size:10px;color:#7b8492}
</style>
