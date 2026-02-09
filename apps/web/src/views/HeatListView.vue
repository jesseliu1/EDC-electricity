<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="min-h-screen bg-gray-100 flex items-center justify-center">
    <div class="text-center">
      <h1 class="text-3xl font-bold text-gray-800 mb-4">
        {{ t('heat.title') }}
      </h1>
      <p class="text-gray-600">炉次列表页面开发中...</p>
    </div>
  </div>
</template>
