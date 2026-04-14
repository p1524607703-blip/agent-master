<template>
  <div class="stat-card">
    <div class="stat-card__icon" :style="{ background: `linear-gradient(135deg, ${color}22, ${color}44)` }">
      <el-icon :style="{ color }"><component :is="icon" /></el-icon>
    </div>
    <div class="stat-card__content">
      <div class="stat-card__value">{{ formattedValue }}</div>
      <div class="stat-card__label">{{ label }}</div>
    </div>
    <div v-if="delta !== undefined" class="stat-card__delta" :class="delta >= 0 ? 'delta--up' : 'delta--down'">
      <span>{{ delta >= 0 ? '↑' : '↓' }} {{ Math.abs(delta) }}%</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  label: string
  value: number | string
  icon?: string
  color?: string
  delta?: number
  prefix?: string
  suffix?: string
}>(), {
  color: '#0891b2',
  icon: 'DataLine',
})

const formattedValue = computed(() => {
  const v = props.value
  if (typeof v === 'number') {
    return `${props.prefix ?? ''}${v.toLocaleString()}${props.suffix ?? ''}`
  }
  return v
})
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(255, 255, 255, 0.45);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 4px 16px rgba(8, 145, 178, 0.08);
  transition: transform 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-1px);
}

.stat-card__icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.stat-card__value {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.stat-card__label {
  font-size: 13px;
  color: #64748b;
  margin-top: 2px;
}

.stat-card__delta {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 20px;
}

.delta--up {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}

.delta--down {
  background: rgba(239, 68, 68, 0.15);
  color: #dc2626;
}
</style>
