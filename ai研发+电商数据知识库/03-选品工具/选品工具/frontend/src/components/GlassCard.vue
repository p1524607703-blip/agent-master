<template>
  <div class="glass-card" :class="[`glass-card--${variant}`, { 'glass-card--hover': hoverable }]">
    <div v-if="$slots.header" class="glass-card__header">
      <slot name="header" />
    </div>
    <div class="glass-card__body">
      <slot />
    </div>
    <div v-if="$slots.footer" class="glass-card__footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'default' | 'primary' | 'dark'
  hoverable?: boolean
}>(), {
  variant: 'default',
  hoverable: false,
})
</script>

<style scoped>
.glass-card {
  background: rgba(255, 255, 255, 0.45);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: 20px;
  box-shadow: 0 8px 32px rgba(8, 145, 178, 0.10), 0 1px 0 rgba(255, 255, 255, 0.9) inset;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.glass-card--hover:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 40px rgba(8, 145, 178, 0.18), 0 1px 0 rgba(255, 255, 255, 0.9) inset;
}

.glass-card--primary {
  background: rgba(8, 145, 178, 0.12);
  border-color: rgba(8, 145, 178, 0.3);
}

.glass-card--dark {
  background: rgba(15, 23, 42, 0.6);
  border-color: rgba(255, 255, 255, 0.1);
}

.glass-card__header {
  padding: 16px 20px 0;
  font-weight: 600;
  color: var(--teal);
}

.glass-card__body {
  padding: 16px 20px;
}

.glass-card__footer {
  padding: 0 20px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.5);
}
</style>
