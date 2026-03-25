<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import dayjs from 'dayjs'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElDatePicker, ElMessage, ElPagination } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import SystemReadinessBanner from '@/components/common/SystemReadinessBanner.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { useHeatStore } from '@/stores/heat'
import type { HeatStatus } from '@/api/heat'
import type { HeatItem } from '@/stores/heat'
import { isShowtimeMode } from '@/utils/showtime'

const { t } = useI18n()
const router = useRouter()
const heatStore = useHeatStore()
const expandedHeatId = ref('')
const showtimeMode = isShowtimeMode()
const demoRecordSources = new Set<HeatItem['recordSource']>([
  'demo_seed',
  'mock_stream',
  'demo_curve',
  'mock_curve'
])

const blockedCount = computed(
  () => heatStore.list.filter((item) => item.cutStatus === 'blocked').length
)
const majorIssueCount = computed(
  () => heatStore.list.filter((item) => item.cutStatus === 'major_issue').length
)
const hasDemoHeatRecords = computed(
  () => showtimeMode && heatStore.list.some((item) => demoRecordSources.has(item.recordSource))
)

type StatusFilter = 'all' | HeatStatus

const statusFilters: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: '全部状态' },
  { key: 'normal', label: '正常' },
  { key: 'abnormal', label: '异常' },
  { key: 'pending', label: '待处理' }
]

const hasActiveListFilters = computed(
  () => heatStore.filters.status !== 'all' || heatStore.filters.dateRange !== null
)
const activeStatusFilterLabel = computed(
  () => statusFilters.find((item) => item.key === heatStore.filters.status)?.label || '全部状态'
)
const emptyStateTitle = computed(() =>
  hasActiveListFilters.value ? t('heat.emptyStateFilteredTitle') : t('heat.emptyStateNoData')
)
const emptyStateDescription = computed(() => {
  if (!hasActiveListFilters.value) {
    return t('common.noData')
  }
  return t('heat.emptyStateFilteredBody', {
    filter: activeStatusFilterLabel.value
  })
})

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

function dataSourceText(source: HeatItem['recordSource']) {
  if (source === 'live_edc') return t('heat.dataSource.liveEdc')
  if (source === 'live_inferred') return t('heat.dataSource.liveInferred')
  if (source === 'mock_curve') return t('heat.dataSource.demoCurve')
  if (source === 'mock_stream') return t('heat.dataSource.demoSeed')
  if (source === 'demo_curve') return t('heat.dataSource.demoCurve')
  if (source === 'none') return t('heat.dataSource.none')
  return t('heat.dataSource.none')
}

function getDeviationClass(val: number | null): string {
  if (val === null) return 'text-slate-400'
  if (val > 10) return 'text-red-500 font-bold'
  if (val > 5) return 'text-orange-500 font-semibold'
  return 'text-slate-600'
}

function getDeviationBarClass(value: number | null) {
  if (value === null) return 'w-0'
  if (value > 10) return 'bg-red-400 w-full'
  if (value > 7) return 'bg-orange-400 w-4/5'
  if (value > 5) return 'bg-orange-300 w-3/5'
  if (value > 2) return 'bg-primary w-2/5'
  return 'bg-primary w-1/4'
}

function buildSeries(seed: string, base: number, amplitude: number) {
  const signature = seed.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return Array.from({ length: 24 }).map((_, index) => {
    const phase = signature / 29
    const wave = Math.sin(index / 3.2 + phase)
    const jitter = Math.cos(index / 5.1 + phase / 2)
    return Number((base + wave * amplitude + jitter * amplitude * 0.25).toFixed(1))
  })
}

function buildSparklinePath(values: number[]) {
  if (values.length === 0) return ''
  const min = Math.min(...values)
  const max = Math.max(...values)
  const width = 240
  const height = 72
  const stepX = width / Math.max(values.length - 1, 1)
  const range = max - min || 1

  return values
    .map((value, index) => {
      const x = Number((index * stepX).toFixed(2))
      const y = Number((height - ((value - min) / range) * (height - 10) - 5).toFixed(2))
      return `${index === 0 ? 'M' : 'L'}${x},${y}`
    })
    .join(' ')
}

function getPreviewPower(item: HeatItem) {
  const cached = heatStore.previews[item.id]?.powerCurve
  if (cached && cached.length > 0) {
    return cached.map(point => point.value)
  }
  return buildSeries(item.id, 430 + (item.deviationPercent || 0), 22)
}

function getPreviewTemperature(item: HeatItem) {
  const cached = heatStore.previews[item.id]?.temperatureCurve
  if (cached && cached.length > 0) {
    return cached.map(point => point.value)
  }
  return buildSeries(`${item.id}-temp`, item.temperature || 1450, 12)
}

function getPeakPower(item: HeatItem) {
  return Number(Math.max(...getPreviewPower(item)).toFixed(1))
}

function getDurationMinutes(item: HeatItem) {
  const start = dayjs(item.startTime)
  const end = dayjs(item.endTime)
  return Math.max(end.diff(start, 'minute'), 0)
}

function handleStatusChange(value: StatusFilter) {
  expandedHeatId.value = ''
  void heatStore.setStatus(value)
}

function handleDateRangeChange(value: [Date, Date] | null) {
  expandedHeatId.value = ''
  void heatStore.setDateRange(value)
}

function handleResetFilters() {
  expandedHeatId.value = ''
  void heatStore.resetFilters()
}

function handleViewDetail(id: string) {
  router.push(`/heats/${id}`)
}

function handleExport() {
  ElMessage.info(t('heat.exportHint'))
}

function toggleExpand(id: string) {
  const nextExpanded = expandedHeatId.value === id ? '' : id
  expandedHeatId.value = nextExpanded
  if (nextExpanded) {
    void heatStore.fetchPreview(id)
  }
}

onMounted(() => {
  void heatStore.fetchList()
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <PageHeader
      :title="t('heat.title')"
      subtitle="Heat Browser"
      description="按黄金基线对比炉次曲线，定位偏差区间并生成纠偏建议（支持历史追溯）。"
    >
      <template #actions>
        <button
          data-testid="heat-export-button"
          class="flex items-center gap-2 bg-white border border-border-light text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
          @click="handleExport"
        >
          <span class="material-symbols-outlined text-[18px]">download</span>
          {{ t('heat.exportAction') }}
        </button>
      </template>
    </PageHeader>

    <SystemReadinessBanner
      section="heats"
      test-id="heat-runtime-banner"
    />

    <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-4 items-end">
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
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[16px]">precision_manufacturing</span>
            设备 ID (局部)
          </label>
          <div class="flex items-center bg-slate-100 rounded-lg px-3 py-2 border border-transparent focus-within:border-primary/30 transition-all">
            <input
              type="text"
              class="bg-transparent border-none focus:ring-0 focus:outline-none text-sm text-slate-700 w-full placeholder:text-slate-400 p-0"
              placeholder="筛选特定炉台..."
            >
          </div>
        </div>
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[16px]">grid_view</span>
            合金号
          </label>
          <div class="flex items-center bg-slate-100 rounded-lg px-3 py-2 border border-transparent focus-within:border-primary/30 transition-all">
            <input
              type="text"
              class="bg-transparent border-none focus:ring-0 focus:outline-none text-sm text-slate-700 w-full placeholder:text-slate-400 p-0"
              placeholder="例如: Al-Si10Mg"
            >
          </div>
        </div>
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
                  : 'text-slate-500 hover:text-slate-700'
              ]"
              @click="handleStatusChange(f.key)"
            >
              {{ f.label }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="majorIssueCount > 0 || blockedCount > 0"
      class="flex items-center gap-3 bg-orange-50 border border-orange-200 rounded-xl p-4 text-sm text-orange-700"
    >
      <span class="material-symbols-outlined text-orange-500">warning</span>
      {{ t('heat.cuttingAlert', { major: majorIssueCount, blocked: blockedCount }) }}
    </div>

    <div
      v-if="hasDemoHeatRecords"
      class="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
      data-testid="heat-list-source-banner"
    >
      <span class="material-symbols-outlined text-amber-600">info</span>
      <div>
        <div class="font-semibold">
          {{ t('heat.demoSeedBannerTitle') }}
        </div>
        <div class="mt-1 text-amber-700">
          {{ t('heat.demoSeedBannerBody') }}
        </div>
      </div>
    </div>

    <div class="bg-white rounded-xl border border-border-light shadow-card overflow-hidden">
      <div v-if="heatStore.list.length > 0">
        <table class="w-full">
          <thead class="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm">
            <tr class="border-b border-border-light">
              <th class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-6 py-3">
                序号
              </th>
              <th class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">
                {{ t('heat.heatNo') }}
              </th>
              <th class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">
                时间 / 设备
              </th>
              <th class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">
                黄金基线偏离度
              </th>
              <th class="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">
                {{ t('heat.status') }}
              </th>
              <th class="text-right text-xs font-semibold text-slate-400 uppercase tracking-wider px-6 py-3">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            <template
              v-for="(item, idx) in heatStore.list"
              :key="item.id"
            >
              <tr
                :data-testid="`heat-row-${item.id}`"
                class="border-b border-border-light hover:bg-slate-50 transition-colors cursor-pointer group"
                @click="handleViewDetail(item.id)"
              >
                <td class="px-6 py-4">
                  <span class="text-sm font-bold text-slate-500">{{ String(idx + 1).padStart(2, '0') }}</span>
                </td>
                <td class="px-4 py-4">
                  <span class="text-sm font-semibold text-primary">{{ item.heatNo }}</span>
                </td>
                <td class="px-4 py-4">
                  <div class="text-sm text-slate-700">
                    {{ item.startTime }}
                  </div>
                  <div class="text-xs text-slate-400">
                    {{ item.description || 'Furnace-A01' }}
                  </div>
                  <div class="mt-2">
                    <span class="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                      {{ dataSourceText(item.recordSource) }}
                    </span>
                  </div>
                </td>
                <td class="px-4 py-4">
                  <div class="flex items-center gap-2">
                    <span class="text-xs text-slate-400">偏离度</span>
                    <span :class="['text-sm', getDeviationClass(item.deviationPercent)]">
                      {{ item.deviationPercent !== null ? `${item.deviationPercent}%` : '--' }}
                    </span>
                  </div>
                  <div class="w-20 h-1 bg-slate-200 rounded-full mt-1 overflow-hidden">
                    <div
                      class="h-1 rounded-full transition-all"
                      :class="getDeviationBarClass(item.deviationPercent)"
                    />
                  </div>
                </td>
                <td class="px-4 py-4">
                  <StatusBadge :type="statusBadgeType(item.status)">
                    {{ statusText(item.status) }}
                  </StatusBadge>
                </td>
                <td class="px-6 py-4">
                  <div class="flex items-center justify-end gap-2">
                    <button
                      data-testid="heat-row-expand"
                      class="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border-light text-slate-500 transition-colors hover:border-primary/30 hover:text-primary"
                      @click.stop="toggleExpand(item.id)"
                    >
                      <span
                        class="material-symbols-outlined text-[20px] transition-transform"
                        :class="expandedHeatId === item.id ? 'rotate-180' : ''"
                      >
                        expand_more
                      </span>
                    </button>
                    <span class="material-symbols-outlined text-slate-400 group-hover:text-primary transition-colors text-[20px]">chevron_right</span>
                  </div>
                </td>
              </tr>

              <tr
                v-if="expandedHeatId === item.id"
                class="bg-slate-50/70"
              >
                <td
                  class="px-6 py-5"
                  colspan="6"
                >
                  <div
                    class="rounded-xl border border-border-light bg-white p-5 shadow-subtle"
                    data-testid="heat-expanded-panel"
                  >
                    <div class="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_320px]">
                      <div class="rounded-xl border border-border-light bg-slate-50 p-4">
                        <div class="flex items-center justify-between">
                          <div class="text-sm font-semibold text-slate-800">
                            功率微缩曲线
                          </div>
                          <div class="text-xs text-slate-500">
                            Peak {{ getPeakPower(item) }} kW
                          </div>
                        </div>
                        <svg
                          viewBox="0 0 240 72"
                          class="mt-3 h-[72px] w-full"
                        >
                          <path
                            :d="buildSparklinePath(getPreviewPower(item))"
                            fill="none"
                            stroke="#1152d4"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            stroke-width="2.5"
                          />
                        </svg>
                      </div>

                      <div class="rounded-xl border border-border-light bg-slate-50 p-4">
                        <div class="flex items-center justify-between">
                          <div class="text-sm font-semibold text-slate-800">
                            温度微缩曲线
                          </div>
                          <div class="text-xs text-slate-500">
                            {{ item.temperature || '--' }} °C
                          </div>
                        </div>
                        <svg
                          viewBox="0 0 240 72"
                          class="mt-3 h-[72px] w-full"
                        >
                          <path
                            :d="buildSparklinePath(getPreviewTemperature(item))"
                            fill="none"
                            stroke="#f97316"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            stroke-width="2.5"
                          />
                        </svg>
                      </div>

                      <div class="rounded-xl border border-border-light bg-slate-50 p-5">
                        <div class="text-sm font-semibold text-slate-800">
                          关键摘要
                        </div>
                        <div class="mt-4 space-y-4">
                          <div class="rounded-lg bg-white px-4 py-3">
                            <div class="text-xs uppercase tracking-wider text-slate-400">
                              峰值功率
                            </div>
                            <div class="mt-2 text-2xl font-bold text-slate-900">
                              {{ getPeakPower(item) }}
                            </div>
                            <div class="mt-1 text-xs text-slate-500">
                              kW
                            </div>
                          </div>
                          <div class="rounded-lg bg-white px-4 py-3">
                            <div class="text-xs uppercase tracking-wider text-slate-400">
                              熔炼时长
                            </div>
                            <div class="mt-2 text-2xl font-bold text-slate-900">
                              {{ getDurationMinutes(item) }}
                            </div>
                            <div class="mt-1 text-xs text-slate-500">
                              分钟
                            </div>
                          </div>
                          <div class="rounded-lg bg-white px-4 py-3">
                            <div class="text-xs uppercase tracking-wider text-slate-400">
                              平均偏差
                            </div>
                            <div class="mt-2 text-2xl font-bold text-slate-900">
                              {{ item.avgDeviationPercent !== null ? `${item.avgDeviationPercent}%` : '--' }}
                            </div>
                            <div class="mt-1 text-xs text-slate-500">
                              与默认黄金基线对比
                            </div>
                          </div>
                          <div class="rounded-lg bg-white px-4 py-3">
                            <div class="text-xs uppercase tracking-wider text-slate-400">
                              切割状态
                            </div>
                            <div class="mt-3">
                              <StatusBadge :type="statusBadgeType(item.status)">
                                {{ statusText(item.status) }}
                              </StatusBadge>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div class="mt-5 flex justify-end">
                      <button
                        data-testid="heat-view-report-button"
                        class="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-dark"
                        @click.stop="handleViewDetail(item.id)"
                      >
                        <span class="material-symbols-outlined text-[18px]">description</span>
                        {{ t('heat.viewDetailAction') }}
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

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

      <div
        v-else
        class="py-16 flex flex-col items-center justify-center"
      >
        <span class="material-symbols-outlined text-slate-300 text-5xl">dataset</span>
        <p class="mt-3 text-sm font-medium text-slate-500">
          {{ emptyStateTitle }}
        </p>
        <p class="mt-2 text-sm text-slate-400">
          {{ emptyStateDescription }}
        </p>
        <button
          v-if="hasActiveListFilters"
          class="mt-4 inline-flex items-center rounded-lg border border-border-light bg-white px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-primary/30 hover:text-primary"
          @click="handleResetFilters"
        >
          {{ t('heat.resetFilters') }}
        </button>
      </div>
    </div>
  </div>
</template>
