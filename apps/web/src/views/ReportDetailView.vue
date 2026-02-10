<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElButton, ElCard, ElEmpty } from 'element-plus'
import { useReportStore } from '@/stores/report'
import { reportApi } from '@/api/report'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const reportStore = useReportStore()

const reportDate = computed(() => String(route.params.date || ''))
const detail = computed(() => reportStore.current)

function handleBack() {
  router.push('/reports')
}

function handleExport() {
  if (!reportDate.value) return
  window.open(reportApi.exportPdfUrl(reportDate.value), '_blank')
}

onMounted(() => {
  if (!reportDate.value) return
  void reportStore.fetchDetail(reportDate.value)
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between gap-4 flex-wrap">
      <h1 class="text-2xl font-bold text-gray-900">
        {{ t('report.dailyReport') }} - {{ reportDate }}
      </h1>
      <div class="flex items-center gap-2">
        <el-button @click="handleBack">
          {{ t('common.back') }}
        </el-button>
        <el-button
          type="primary"
          @click="handleExport"
        >
          {{ t('report.exportPdf') }}
        </el-button>
      </div>
    </div>

    <el-card v-if="detail">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-lg bg-gray-50 p-3">
          <div class="text-sm text-gray-500">
            {{ t('report.totalHeats') }}
          </div>
          <div class="mt-1 text-xl font-semibold">
            {{ detail.totalHeats }}
          </div>
        </div>
        <div class="rounded-lg bg-gray-50 p-3">
          <div class="text-sm text-gray-500">
            {{ t('report.normalRate') }}
          </div>
          <div class="mt-1 text-xl font-semibold">
            {{ detail.normalRate }}%
          </div>
        </div>
        <div class="rounded-lg bg-gray-50 p-3">
          <div class="text-sm text-gray-500">
            {{ t('dashboard.avgDeviation') }}
          </div>
          <div class="mt-1 text-xl font-semibold">
            {{ detail.avgDeviation }}%
          </div>
        </div>
        <div class="rounded-lg bg-gray-50 p-3">
          <div class="text-sm text-gray-500">
            {{ t('task.statusCompleted') }}
          </div>
          <div class="mt-1 text-xl font-semibold">
            {{ detail.completedTasks }}
          </div>
        </div>
      </div>
    </el-card>

    <el-card v-if="detail">
      <template #header>
        <span>{{ t('report.topDeviationHeats') }}</span>
      </template>
      <div class="space-y-2">
        <div
          v-for="item in detail.topDeviations"
          :key="item.heatNo"
          class="rounded-md border border-gray-200 px-3 py-2 flex items-center justify-between"
        >
          <span>{{ item.heatNo }}</span>
          <span class="text-red-600 font-medium">{{ item.deviation }}%</span>
        </div>
      </div>
    </el-card>

    <el-empty
      v-else
      :description="t('common.loading')"
    />
  </div>
</template>
