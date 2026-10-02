<template>
  <div class="fullscreen-layout">
    <router-view />
  </div>
</template>

<script setup>
</script>

<style scoped>
.fullscreen-layout {
  width: 100vw;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-page);
  color: var(--text-main);
  overflow-x: hidden;
}
</style>
