<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { useReportStore } from '@/stores/report'

const { t } = useI18n()
const router = useRouter()
const reportStore = useReportStore()

function handleView(date: string) {
  router.push(`/reports/${date}`)
}

onMounted(() => {
  void reportStore.fetchList()
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <!-- 页面头部 -->
    <PageHeader
      :title="t('report.title')"
      subtitle="Reports & Audit"
      description="昨日偏差统计与数据审计管理"
    >
      <template #actions>
        <button
          class="flex items-center gap-2 bg-white border border-border-light text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
        >
          <span class="material-symbols-outlined text-[18px]">calendar_month</span>
          历史查询
        </button>
        <button
          class="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
        >
          <span class="material-symbols-outlined text-[18px]">picture_as_pdf</span>
          导出昨日报告 PDF
        </button>
      </template>
    </PageHeader>

    <!-- 报告列表 -->
    <div class="bg-white rounded-xl border border-border-light shadow-card overflow-hidden">
      <div v-if="reportStore.list.length > 0">
        <div
          v-for="item in reportStore.list"
          :key="item.date"
          class="border-b border-border-light last:border-0 p-5 hover:bg-slate-50 transition-colors cursor-pointer group flex items-center justify-between gap-4"
          @click="handleView(item.date)"
        >
          <div class="flex items-center gap-4">
            <div class="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <span class="material-symbols-outlined text-[22px]">description</span>
            </div>
            <div>
              <p class="text-sm font-bold text-slate-800">{{ item.date }}</p>
              <p class="text-xs text-slate-500 mt-0.5">
                {{ t('report.totalHeats') }}: {{ item.totalHeats }}
                · {{ t('report.normalRate') }}:
                {{ ((item.normalHeats / item.totalHeats) * 100).toFixed(1) }}%
              </p>
            </div>
          </div>

          <div class="flex items-center gap-4 shrink-0">
            <StatusBadge type="info">
              {{ t('dashboard.avgDeviation') }}: {{ item.avgDeviation }}%
            </StatusBadge>
            <span class="material-symbols-outlined text-slate-400 group-hover:text-primary transition-colors text-[20px]">chevron_right</span>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="py-16 flex flex-col items-center justify-center">
        <span class="material-symbols-outlined text-slate-300 text-5xl">picture_as_pdf</span>
        <p class="text-sm text-slate-400 mt-3">{{ t('common.noData') }}</p>
      </div>
    </div>
  </div>
</template>
