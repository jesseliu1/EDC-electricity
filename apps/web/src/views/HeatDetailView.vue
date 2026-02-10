<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElButton } from 'element-plus'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const heatId = computed(() => String(route.params.id || '--'))

function handleBack() {
  router.push('/heats')
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">
        {{ t('heat.detailTitle') }}
      </h1>
      <el-button @click="handleBack">
        {{ t('common.back') }}
      </el-button>
    </div>
    <div class="rounded-xl border border-gray-200 bg-white p-6">
      <div class="text-sm text-gray-500">
        {{ t('heat.detailDeveloping') }}
      </div>
      <div class="mt-2 text-base font-semibold">
        ID: {{ heatId }}
      </div>
    </div>
  </div>
</template>
