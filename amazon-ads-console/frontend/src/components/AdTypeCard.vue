<script setup lang="ts">
defineProps<{
  name: string
  spend: number
  orders: number
  active?: boolean
}>()
defineEmits<{ select: [] }>()
</script>

<template>
  <button class="ad-card" :class="{ active }" @click="$emit('select')">
    <strong>{{ name }}</strong>
    <div class="ad-spend">${{ spend.toLocaleString() }}</div>
    <div class="ad-mini ad-mini-single">
      <span>广告单 {{ orders }}</span>
    </div>
  </button>
</template>
