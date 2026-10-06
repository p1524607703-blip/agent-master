<template>
  <div class="app-wrapper">
    <Sidebar />
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import Sidebar from '@/components/Sidebar.vue'
</script>

<style>
.app-wrapper {
  display: flex;
  min-height: 100vh;
  background: linear-gradient(145deg, #c8eeff 0%, #f0fbff 55%, #daf3fb 100%);
}

.main-content {
  flex: 1;
  margin-left: 220px;
  padding: 24px;
  overflow-y: auto;
}
</style>
