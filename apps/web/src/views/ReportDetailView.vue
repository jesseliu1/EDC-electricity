<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useReportStore } from '@/stores/report'
import { reportApi } from '@/api/report'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()
const route = useRoute()
const reportStore = useReportStore()

const reportDate = computed(() => String(route.params.date || ''))
const detail = computed(() => reportStore.current)

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
  <div
    class="flex flex-col gap-6"
    data-testid="report-detail-page"
  >
    <PageHeader
      :title="`${t('report.dailyReport')} - ${reportDate}`"
      subtitle="Data compiled from 00:00 to 23:59"
    >
      <template #actions>
        <button
          class="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
          @click="handleExport"
        >
          <span class="material-symbols-outlined text-[18px]">download</span>
          {{ t('report.exportPdf') }}
        </button>
      </template>
    </PageHeader>

    <template v-if="detail">
      <div class="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        <!-- 统计卡片区块 -->
        <div class="bg-white rounded-xl border border-border-light shadow-card p-5 relative overflow-hidden group hover:border-border-dark transition-colors">
          <div class="flex justify-between items-start">
            <span class="text-sm font-medium text-slate-500">{{ t('report.totalHeats') }}</span>
            <span class="material-symbols-outlined text-slate-200 text-3xl group-hover:text-primary transition-colors">local_fire_department</span>
          </div>
          <div class="mt-2 text-3xl font-bold text-slate-800">
            {{ detail.totalHeats }}
          </div>
        </div>

        <div class="bg-white rounded-xl border border-border-light shadow-card p-5 relative overflow-hidden group hover:border-border-dark transition-colors">
          <div class="flex justify-between items-start">
            <span class="text-sm font-medium text-slate-500">{{ t('report.normalRate') }}</span>
            <span class="material-symbols-outlined text-slate-200 text-3xl group-hover:text-green-500 transition-colors">check_circle</span>
          </div>
          <div class="mt-2 text-3xl font-bold text-green-600">
            {{ detail.normalRate }}%
          </div>
        </div>

        <div class="bg-white rounded-xl border border-border-light shadow-card p-5 relative overflow-hidden group hover:border-border-dark transition-colors">
          <div class="flex justify-between items-start">
            <span class="text-sm font-medium text-slate-500">{{ t('dashboard.avgDeviation') }}</span>
            <span class="material-symbols-outlined text-slate-200 text-3xl group-hover:text-orange-500 transition-colors">trending_up</span>
          </div>
          <div class="mt-2 text-3xl font-bold text-slate-800">
            {{ detail.avgDeviation }}%
          </div>
        </div>

        <div class="bg-white rounded-xl border border-border-light shadow-card p-5 relative overflow-hidden group hover:border-border-dark transition-colors">
          <div class="flex justify-between items-start">
            <span class="text-sm font-medium text-slate-500">{{ t('task.statusCompleted') }}</span>
            <span class="material-symbols-outlined text-slate-200 text-3xl group-hover:text-primary transition-colors">task_alt</span>
          </div>
          <div class="mt-2 text-3xl font-bold text-slate-800">
            {{ detail.completedTasks }}
          </div>
        </div>
      </div>

      <!-- Top Deviations 表格区 -->
      <div class="bg-white rounded-xl border border-border-light shadow-card overflow-hidden">
        <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2 p-5 pb-4 border-b border-border-light bg-slate-50/50">
          <span class="material-symbols-outlined text-primary text-[20px]">sort</span>
          {{ t('report.topDeviationHeats') }}
        </h3>
        
        <div
          v-if="detail.topDeviations.length > 0"
          class="divide-y divide-border-light"
        >
          <div
            v-for="(item, index) in detail.topDeviations"
            :key="item.heatNo"
            class="px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
          >
            <div class="flex items-center gap-4">
              <span class="font-mono font-bold text-sm text-slate-300 w-6">#{{ index + 1 }}</span>
              <span class="font-semibold text-slate-800">{{ item.heatNo }}</span>
            </div>
            <div class="flex flex-col items-end gap-1">
              <span class="font-bold text-red-600 font-mono tracking-tight">{{ item.deviation }}%</span>
              <div class="w-32 h-1.5 bg-slate-100 rounded-full overflow-hidden flex justify-end">
                <div
                  class="h-full bg-red-500 rounded-full"
                  :style="{ width: `${Math.min(item.deviation, 100)}%` }"
                />
              </div>
            </div>
          </div>
        </div>
        <div
          v-else
          class="py-12 flex flex-col items-center justify-center"
        >
          <span class="material-symbols-outlined text-slate-300 text-4xl">check_circle</span>
          <p class="text-sm text-slate-500 mt-2 font-medium">
            No deviations recorded
          </p>
        </div>
      </div>
    </template>

    <div
      v-else
      class="py-16 flex flex-col items-center justify-center bg-white rounded-xl border border-border-light shadow-card"
    >
      <span class="material-symbols-outlined text-slate-300 text-5xl">pending</span>
      <p class="text-sm text-slate-400 mt-3">
        {{ t('common.loading') }}
      </p>
    </div>
  </div>
</template>
