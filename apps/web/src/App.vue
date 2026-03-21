<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { AppLayout } from '@/components/layout'
import { useRuntimeStatusStore } from '@/stores/runtimeStatus'

const route = useRoute()
const runtimeStatusStore = useRuntimeStatusStore()
let refreshTimer: ReturnType<typeof setInterval> | undefined

async function refreshRuntimeStatus() {
  await runtimeStatusStore.fetchRuntimeStatus()
}

onMounted(() => {
  void refreshRuntimeStatus()
  refreshTimer = setInterval(() => {
    void refreshRuntimeStatus()
  }, 30000)
})

watch(
  () => route.fullPath,
  () => {
    void refreshRuntimeStatus()
  }
)

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<template>
  <AppLayout>
    <RouterView />
  </AppLayout>
</template>

<style scoped>
/* App 级别样式 */
</style>
