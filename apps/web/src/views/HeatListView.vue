<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElDatePicker, ElPagination } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { useHeatStore } from '@/stores/heat'
import type { HeatStatus } from '@/api/heat'

const { t } = useI18n()
const router = useRouter()
const heatStore = useHeatStore()
const blockedCount = computed(
  () => heatStore.list.filter((item) => item.cutStatus === 'blocked').length
)
const majorIssueCount = computed(
  () =>
    heatStore.list.filter((item) => item.cutStatus === 'major_issue').length
)

type StatusFilter = 'all' | HeatStatus

const statusFilters: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: '全部状态' },
  { key: 'normal', label: '正常' },
  { key: 'abnormal', label: '异常' },
  { key: 'pending', label: '待处理' },
]

function statusBadgeType(status: HeatStatus) {
  if (status === 'normal') return 'success' as const
  if (status === 'abnormal') return 'danger' as const
  return 'info' as const
}

function statusText(status: HeatStatus) {
  if (status === 'normal') return t('heat.statusNormal')
  if (status === 'abnormal') return t('heat.statusAbnormal')
  return t('heat.statusPending')
}

function getDeviationClass(val: number | null): string {
  if (val === null) return 'text-slate-400'
  if (val > 10) return 'text-red-500 font-bold'
  if (val > 5) return 'text-orange-500 font-semibold'
  return 'text-slate-600'
}

function handleStatusChange(value: StatusFilter) {
  void heatStore.setStatus(value)
}

function handleDateRangeChange(value: [Date, Date] | null) {
  void heatStore.setDateRange(value)
}

function handleViewDetail(id: string) {
  router.push(`/heats/${id}`)
}

onMounted(() => {
  void heatStore.fetchList()
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <!-- 页面头部 -->
    <PageHeader
      :title="t('heat.title')"
      subtitle="Heat Browser"
      description="按黄金基线对比炉次曲线，定位偏差区间并生成纠偏建议（支持历史追溯）。"
    >
      <template #actions>
        <button
          class="flex items-center gap-2 bg-white border border-border-light text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
        >
          <span class="material-symbols-outlined text-[18px]">download</span>
          导出 Excel
        </button>
        <button
          class="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
          @click="heatStore.ingestMockHeat"
        >
          <span class="material-symbols-outlined text-[18px]">add</span>
          {{ t('heat.ingestMockHeat') }}
        </button>
      </template>
    </PageHeader>

    <!-- 筛选区 -->
    <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-4 items-end">
        <!-- 时间范围 -->
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[16px]">calendar_month</span>
            {{ t('heat.filterDateRange') }}
          </label>
          <el-date-picker
            :model-value="heatStore.filters.dateRange"
            type="daterange"
            unlink-panels
            :range-separator="t('heat.to')"
            :start-placeholder="t('heat.startDate')"
            :end-placeholder="t('heat.endDate')"
            class="!w-full"
            @update:model-value="handleDateRangeChange"
          />
        </div>
        <!-- 设备 ID -->
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[16px]">precision_manufacturing</span>
            设备 ID (局部)
          </label>
          <div class="flex items-center bg-slate-100 rounded-lg px-3 py-2 border border-transparent focus-within:border-primary/30 transition-all">
            <input type="text" class="bg-transparent border-none focus:ring-0 focus:outline-none text-sm text-slate-700 w-full placeholder:text-slate-400 p-0" placeholder="筛选特定炉台..." />
          </div>
        </div>
        <!-- 合金号 -->
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[16px]">grid_view</span>
            合金号
          </label>
          <div class="flex items-center bg-slate-100 rounded-lg px-3 py-2 border border-transparent focus-within:border-primary/30 transition-all">
            <input type="text" class="bg-transparent border-none focus:ring-0 focus:outline-none text-sm text-slate-700 w-full placeholder:text-slate-400 p-0" placeholder="例如: Al-Si10Mg" />
          </div>
        </div>
        <!-- 状态筛选 -->
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[16px]">search</span>
            偏差范围
          </label>
          <div class="flex bg-slate-100 p-1 rounded-lg">
            <button
              v-for="f in statusFilters"
              :key="f.key"
              :class="[
                'flex-1 px-2 py-1.5 text-xs font-medium rounded-md transition-all duration-200 text-center',
                heatStore.filters.status === f.key
                  ? 'bg-white text-primary shadow-sm font-bold'
                  : 'text-slate-500 hover:text-slate-700',
              ]"
              @click="handleStatusChange(f.key)"
            >
              {{ f.label }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 告警条 -->
    <div
      v-if="majorIssueCount > 0 || blockedCount > 0"
      class="flex items-center gap-3 bg-orange-50 border border-orange-200 rounded-xl p-4 text-sm text-orange-700"
    >
      <span class="material-symbols-outlined text-orange-500">warning</span>
      {{ t('heat.cuttingAlert', { major: majorIssueCount, blocked: blockedCount }) }}
    </div>

    <!-- 炉次表格 -->
    <div class="bg-white rounded-xl border border-border-light shadow-card overflow-hidden">
      <div v-if="heatStore.list.length > 0">
        <table class="w-full">
          <thead class="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm">
            <tr class="border-b border-border-light">
              <th class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-6 py-3">序号</th>
              <th class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">{{ t('heat.heatNo') }}</th>
              <th class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">时间 / 设备</th>
              <th class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">黄金基线偏离度</th>
              <th class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">{{ t('heat.status') }}</th>
              <th class="text-right text-xs font-semibold text-slate-400 uppercase tracking-wider px-6 py-3">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(item, idx) in heatStore.list"
              :key="item.id"
              class="border-b border-border-light last:border-0 hover:bg-slate-50 transition-colors cursor-pointer group"
              @click="handleViewDetail(item.id)"
            >
              <td class="px-6 py-4">
                <span class="text-sm font-bold text-slate-500">{{ String(idx + 1).padStart(2, '0') }}</span>
              </td>
              <td class="px-4 py-4">
                <span class="text-sm font-semibold text-primary">{{ item.heatNo }}</span>
              </td>
              <td class="px-4 py-4">
                <div class="text-sm text-slate-700">{{ item.startTime }}</div>
                <div class="text-xs text-slate-400">{{ item.description || 'Furnace-A01' }}</div>
              </td>
              <td class="px-4 py-4">
                <div class="flex items-center gap-2">
                  <span class="text-xs text-slate-400">偏离度</span>
                  <span :class="['text-sm', getDeviationClass(item.deviationPercent)]">
                    {{ item.deviationPercent !== null ? `${item.deviationPercent}%` : '--' }}
                  </span>
                </div>
                <!-- 偏差进度条 -->
                <div class="w-20 h-1 bg-slate-200 rounded-full mt-1">
                  <div
                    class="h-1 rounded-full transition-all"
                    :class="item.deviationPercent !== null && item.deviationPercent > 10 ? 'bg-red-400' : item.deviationPercent !== null && item.deviationPercent > 5 ? 'bg-orange-400' : 'bg-primary'"
                    :style="{ width: `${Math.min((item.deviationPercent || 0) * 10, 100)}%` }"
                  />
                </div>
              </td>
              <td class="px-4 py-4">
                <StatusBadge :type="statusBadgeType(item.status)">
                  {{ statusText(item.status) }}
                </StatusBadge>
              </td>
              <td class="px-6 py-4 text-right">
                <span class="material-symbols-outlined text-slate-400 group-hover:text-primary transition-colors text-[20px]">chevron_right</span>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 分页 -->
        <div class="px-6 py-4 border-t border-border-light flex justify-end">
          <el-pagination
            background
            layout="total, sizes, prev, pager, next"
            :current-page="heatStore.page"
            :page-size="heatStore.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="heatStore.total"
            @update:current-page="heatStore.setPage"
            @update:page-size="heatStore.setPageSize"
          />
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="py-16 flex flex-col items-center justify-center">
        <span class="material-symbols-outlined text-slate-300 text-5xl">dataset</span>
        <p class="text-sm text-slate-400 mt-3">{{ t('common.noData') }}</p>
      </div>
    </div>
  </div>
</template>
