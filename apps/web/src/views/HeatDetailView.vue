<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ElDatePicker,
  ElMessage,
  ElMessageBox,
  ElTimeline,
  ElTimelineItem
} from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'
import dayjs from 'dayjs'
import { useHeatStore } from '@/stores/heat'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const heatStore = useHeatStore()

const heatId = computed(() => String(route.params.id || ''))
const current = computed(() => heatStore.current)

const editingDescription = ref(false)
const descriptionDraft = ref('')
const editingTiming = ref(false)
const timingDraft = ref<[Date, Date] | null>(null)
const activeBaselineId = ref('')
const selectBoundary = ref<'start' | 'end'>('start')
const baselineStartTs = ref<number | null>(null)
const baselineEndTs = ref<number | null>(null)

const selectedComparison = computed(() => {
  if (!current.value) return null
  if (current.value.baselineComparisons.length === 0) return null
  return (
    current.value.baselineComparisons.find((item) => item.baseline.id === activeBaselineId.value) ||
    current.value.baselineComparisons[0]
  )
})

const statusTagType = computed(() => {
  if (!current.value) return 'info'
  if (current.value.base.status === 'normal') return 'success'
  if (current.value.base.status === 'abnormal') return 'danger'
  return 'info'
})

const statusText = computed(() => {
  if (!current.value) return '--'
  if (current.value.base.status === 'normal') return t('heat.statusNormal')
  if (current.value.base.status === 'abnormal') return t('heat.statusAbnormal')
  return t('heat.statusPending')
})

const compareOption = computed<EChartsOption>(() => {
  if (!current.value) return {}

  const labels = current.value.powerCurve.map((point) => dayjs(point.timestamp).format('HH:mm'))

  return {
    grid: { left: 50, right: 20, top: 32, bottom: 30 },
    tooltip: { trigger: 'axis' },
    legend: {
      data: [t('dashboard.chart.goldenBaseline'), t('dashboard.chart.currentProduction')],
      top: 0
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels
    },
    yAxis: {
      type: 'value',
      name: `${t('dashboard.chart.power')} (kW)`
    },
    series: [
      {
        name: t('dashboard.chart.goldenBaseline'),
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, type: 'dashed', color: '#67C23A' },
        data: (
          selectedComparison.value?.baseline.power_curve || current.value.baselinePowerCurve
        ).map((point) => point.value)
      },
      {
        name: t('dashboard.chart.currentProduction'),
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#1152d4' }, // Primary blue
        markArea: {
          itemStyle: { color: 'rgba(245, 108, 108, 0.12)' }, // Lighter red area for deviation
          data: (selectedComparison.value?.deviation_ranges || current.value.deviationRanges).map(
            (range) => {
              const start = dayjs(range.start).format('HH:mm')
              const end = dayjs(range.end).format('HH:mm')
              return [{ xAxis: start }, { xAxis: end }]
            }
          )
        },
        data: current.value.powerCurve.map((point) => point.value)
      }
    ]
  }
})

function handleCreateTask() {
  ElMessage.info(t('heat.createTaskHint'))
}

function handleCreateBaselineFromHeat() {
  if (!current.value) return

  const firstPoint = current.value.powerCurve[0]
  const lastPoint = current.value.powerCurve[current.value.powerCurve.length - 1]
  const selectedStart = baselineStartTs.value
    ? dayjs(baselineStartTs.value)
    : firstPoint
      ? dayjs(firstPoint.timestamp)
      : dayjs(current.value.base.startTime)
  const selectedEnd = baselineEndTs.value
    ? dayjs(baselineEndTs.value)
    : lastPoint
      ? dayjs(lastPoint.timestamp)
      : dayjs(current.value.base.endTime)

  router.push({
    path: '/baselines',
    query: {
      sourceHeatId: current.value.base.id,
      selectedStartTime: selectedStart.toISOString(),
      selectedEndTime: selectedEnd.toISOString(),
      name: `${current.value.base.heatNo}-${t('baseline.name')}`
    }
  })
}

function handleChartPickClick(params: { dataIndex?: number }) {
  if (!current.value || params.dataIndex === undefined) return
  const point = current.value.powerCurve[params.dataIndex]
  if (!point) return

  if (selectBoundary.value === 'start') {
    baselineStartTs.value = point.timestamp
    selectBoundary.value = 'end'
  } else {
    baselineEndTs.value = point.timestamp
    selectBoundary.value = 'start'
  }

  if (baselineStartTs.value && baselineEndTs.value && baselineStartTs.value > baselineEndTs.value) {
    const tmp = baselineStartTs.value
    baselineStartTs.value = baselineEndTs.value
    baselineEndTs.value = tmp
  }
}

function resetBaselineRange() {
  baselineStartTs.value = null
  baselineEndTs.value = null
}

function startEditDescription() {
  descriptionDraft.value = current.value?.base.description || ''
  editingDescription.value = true
}

async function saveDescription() {
  if (!heatId.value) return
  await heatStore.updateDescription(heatId.value, descriptionDraft.value)
  editingDescription.value = false
  ElMessage.success(t('common.success'))
}

function startEditTiming() {
  if (!current.value) return
  timingDraft.value = [
    dayjs(current.value.base.startTime).toDate(),
    dayjs(current.value.base.endTime).toDate()
  ]
  editingTiming.value = true
}

async function saveTiming() {
  if (!heatId.value || !timingDraft.value) return
  let adjustSubsequent = false
  try {
    await ElMessageBox.confirm(t('heat.adjustSubsequentConfirm'), t('common.confirm'), {
      distinguishCancelAndClose: true,
      confirmButtonText: t('heat.adjustSubsequentYes'),
      cancelButtonText: t('heat.adjustSubsequentNo'),
      type: 'warning'
    })
    adjustSubsequent = true
  } catch {
    adjustSubsequent = false
  }

  await heatStore.updateTiming(
    heatId.value,
    dayjs(timingDraft.value[0]).format('YYYY-MM-DD HH:mm:ss'),
    dayjs(timingDraft.value[1]).format('YYYY-MM-DD HH:mm:ss'),
    adjustSubsequent
  )
  editingTiming.value = false
  ElMessage.success(t('common.success'))
}

async function handleResumeCutting() {
  if (!heatId.value || !current.value) return
  let adjustSubsequent = true
  try {
    await ElMessageBox.confirm(t('heat.resumeCuttingConfirm'), t('common.warning'), {
      confirmButtonText: t('heat.resumeCuttingWithSubsequent'),
      cancelButtonText: t('heat.resumeCuttingOnlyCurrent'),
      distinguishCancelAndClose: true,
      type: 'warning'
    })
    adjustSubsequent = true
  } catch {
    adjustSubsequent = false
  }

  await heatStore.resumeCutting(heatId.value, adjustSubsequent)
  await heatStore.fetchDetail(heatId.value)
  ElMessage.success(t('heat.resumeCuttingSuccess'))
}

onMounted(() => {
  if (!heatId.value) return
  void heatStore.fetchDetail(heatId.value).then(() => {
    activeBaselineId.value = heatStore.current?.baselineComparisons[0]?.baseline.id || ''
  })
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <!-- 页面头部 -->
    <PageHeader
      :title="current?.base.heatNo || '--'"
      :subtitle="`ID: ${heatId}`"
      :description="current?.base.description || 'Furnace-A01'"
    >
      <template #actions>
        <StatusBadge :type="statusTagType" class="mr-2">
          {{ statusText }}
        </StatusBadge>
        <button
          v-if="current?.base.cutStatus === 'major_issue' || current?.base.cutStatus === 'blocked'"
          class="flex items-center gap-2 bg-orange-50 border border-orange-200 text-orange-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-orange-100 transition-colors"
          @click="handleResumeCutting"
        >
          <span class="material-symbols-outlined text-[18px]">play_arrow</span>
          {{ t('heat.resumeCutting') }}
        </button>
        <button
          class="flex items-center gap-2 bg-white border border-green-500 text-green-600 px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-50 transition-colors"
          @click="handleCreateBaselineFromHeat"
        >
          <span class="material-symbols-outlined text-[18px]">bookmark_add</span>
          {{ t('heat.createBaselineFromHeat') }}
        </button>
        <button
          class="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
          @click="handleCreateTask"
        >
          <span class="material-symbols-outlined text-[18px]">assignment</span>
          {{ t('heat.createTask') }}
        </button>
      </template>
    </PageHeader>

    <div
      v-if="current"
      class="grid grid-cols-1 gap-6 xl:grid-cols-3"
    >
      <!-- 左侧：图表区 -->
      <div class="xl:col-span-2 space-y-6">
        <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
          <div class="flex flex-col lg:flex-row justify-between lg:items-center mb-4 gap-4">
            <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2">
              <span class="material-symbols-outlined text-primary text-[20px]">ssid_chart</span>
              {{ t('heat.compareWithBaseline') }}
            </h3>
            <div class="flex items-center gap-3">
              <!-- 嵌入 ElTabs -->
              <el-tabs v-model="activeBaselineId" class="-mb-[15px] mr-2">
                <el-tab-pane
                  v-for="item in current.baselineComparisons"
                  :key="item.baseline.id"
                  :name="item.baseline.id"
                  :label="item.baseline.name"
                />
              </el-tabs>
            </div>
          </div>
          <v-chart
            :option="compareOption"
            autoresize
            class="h-80"
            @click="handleChartPickClick"
          />
          <div class="flex flex-wrap items-center gap-3 mt-4 pt-4 border-t border-border-light text-sm">
            <button
              class="px-3 py-1.5 rounded bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors font-medium border border-slate-200"
              :class="{ 'bg-primary border-primary text-white hover:bg-primary-dark': selectBoundary === 'start' }"
              @click="selectBoundary = 'start'"
            >
              {{ t('heat.pickBaselineStart') }}
            </button>
            <button
              class="px-3 py-1.5 rounded bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors font-medium border border-slate-200"
              :class="{ 'bg-primary border-primary text-white hover:bg-primary-dark': selectBoundary === 'end' }"
              @click="selectBoundary = 'end'"
            >
              {{ t('heat.pickBaselineEnd') }}
            </button>
            <button class="px-3 py-1.5 rounded text-slate-500 hover:text-slate-700 underline" @click="resetBaselineRange">
               清除选择
            </button>
            <div class="ml-auto font-mono text-slate-500 bg-slate-50 px-3 py-1.5 rounded border border-border-light">
              <span class="text-xs text-slate-400 mr-2 uppercase">Selected Range:</span>
              {{ baselineStartTs ? dayjs(baselineStartTs).format('HH:mm:ss') : '--' }}
              ~
              {{ baselineEndTs ? dayjs(baselineEndTs).format('HH:mm:ss') : '--' }}
            </div>
          </div>
        </div>

        <!-- 异常区间 -->
        <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
           <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2 mb-4 pb-4 border-b border-border-light">
              <span class="material-symbols-outlined text-red-500 text-[20px]">warning</span>
              {{ t('heat.abnormalRanges') }}
            </h3>
          <div
            v-if="(selectedComparison?.deviation_ranges || current.deviationRanges).length > 0"
            class="space-y-3"
          >
            <div
              v-for="(range, idx) in selectedComparison?.deviation_ranges || current.deviationRanges"
              :key="`${range.start}-${range.end}`"
              class="rounded-lg border border-red-200 bg-red-50 p-4 flex items-center justify-between"
            >
              <div class="flex items-center gap-3">
                <span class="w-6 h-6 rounded-full bg-red-100 text-red-700 flex items-center justify-center text-xs font-bold">{{ idx + 1 }}</span>
                <span class="font-mono text-sm text-red-900">
                  {{ dayjs(range.start).format('HH:mm:ss') }} <span class="text-red-300 mx-2">to</span> {{ dayjs(range.end).format('HH:mm:ss') }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-xs text-red-500 uppercase tracking-widest font-semibold">Deviation</span>
                <span class="text-lg font-bold text-red-600">{{ range.deviation }}%</span>
              </div>
            </div>
          </div>
          <div v-else class="py-8 flex flex-col items-center justify-center">
            <span class="material-symbols-outlined text-slate-300 text-4xl">check_circle</span>
            <p class="text-sm text-slate-500 mt-2 font-medium">无明显偏差区间</p>
          </div>
        </div>
      </div>

      <!-- 右侧：详情 + 轴线 -->
      <div class="space-y-6">
        <!-- 详情卡片 -->
        <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
          <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2 mb-4 pb-4 border-b border-border-light">
              <span class="material-symbols-outlined text-primary text-[20px]">feed</span>
              {{ t('heat.detailSummary') }}
          </h3>
          <div class="space-y-4 text-sm text-slate-700">
            <div class="flex flex-col gap-1 border-b border-slate-50 pb-3">
              <div class="flex justify-between items-center">
                <span class="text-slate-500">{{ t('heat.description') }}</span>
                <button v-if="!editingDescription" @click="startEditDescription" class="text-primary hover:underline flex items-center gap-1 text-xs">
                  <span class="material-symbols-outlined text-[14px]">edit</span> {{ t('common.edit') }}
                </button>
              </div>
              <template v-if="!editingDescription">
                <span class="font-semibold text-slate-800">{{ current.base.description || t('common.noDescription') }}</span>
              </template>
              <template v-else>
                 <div class="flex gap-2 w-full mt-1">
                  <input
                    v-model="descriptionDraft"
                    class="flex-1 bg-slate-50 border border-border-light rounded px-2 py-1 text-sm outline-none focus:border-primary"
                    @keyup.enter="saveDescription"
                  />
                  <button class="bg-primary text-white px-3 rounded text-xs font-bold" @click="saveDescription">Save</button>
                  <button class="text-slate-400 text-xs hover:text-slate-600" @click="editingDescription = false">Cancel</button>
                 </div>
              </template>
            </div>

            <div class="flex flex-col gap-1 border-b border-slate-50 pb-3">
               <div class="flex justify-between items-center">
                <span class="text-slate-500">时序与切割分析</span>
                <button v-if="!editingTiming" @click="startEditTiming" class="text-primary hover:underline flex items-center gap-1 text-xs">
                  <span class="material-symbols-outlined text-[14px]">edit</span> {{ t('heat.editTiming') }}
                </button>
              </div>
              <template v-if="!editingTiming">
                <div class="flex flex-col gap-1 mt-1 text-xs font-mono bg-slate-50 p-2 rounded">
                  <div class="flex justify-between">
                    <span class="text-slate-400 font-sans">Start</span>
                    <span>{{ current.base.startTime }}</span>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-slate-400 font-sans">End</span>
                    <span>{{ current.base.endTime }}</span>
                  </div>
                </div>
              </template>
              <template v-else>
                 <div class="mt-2 flex flex-col gap-2">
                    <el-date-picker
                      v-model="timingDraft"
                      type="datetimerange"
                      :range-separator="t('heat.to')"
                      :start-placeholder="t('heat.startTime')"
                      :end-placeholder="t('heat.endTime')"
                      class="!w-full"
                    />
                    <div class="flex justify-end gap-2">
                      <button class="text-slate-400 text-xs hover:text-slate-600" @click="editingTiming = false">Cancel</button>
                      <button class="bg-primary text-white px-3 py-1 rounded text-xs font-bold" @click="saveTiming">Save Settings</button>
                    </div>
                 </div>
              </template>
            </div>

            <div class="flex justify-between items-center py-1">
              <span class="text-slate-500">{{ t('heat.cutStatus') }}</span>
              <span class="font-semibold">{{ t(`heat.cutStatus${current.base.cutStatus}`) }}</span>
            </div>
            <div class="flex justify-between items-center py-1">
              <span class="text-slate-500">{{ t('heat.cutReasonLabel') }}</span>
              <span class="font-semibold">{{ t(`heat.cutReason.${current.base.cutReason || 'unknown'}`) }}</span>
            </div>
            <div class="flex justify-between items-center py-1">
              <span class="text-slate-500">{{ t('heat.mismatchDurationMinutes') }}</span>
              <span class="font-semibold text-orange-600">{{ current.base.mismatchDurationMinutes === null ? '--' : `${current.base.mismatchDurationMinutes}m` }}</span>
            </div>
            <div class="flex justify-between items-center py-1">
              <span class="text-slate-500">{{ t('heat.temperature') }}</span>
              <span class="font-semibold">{{ current.base.temperature ?? '--' }}</span>
            </div>
            <div class="flex justify-between items-center py-1">
              <span class="text-slate-500">{{ t('heat.baselineName') }}</span>
              <span class="font-semibold break-all text-right max-w-[60%]">{{ selectedComparison?.baseline.name || '--' }}</span>
            </div>
          </div>
        </div>

        <!-- 生产流程轴线 -->
        <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
           <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2 mb-4 pb-4 border-b border-border-light">
              <span class="material-symbols-outlined text-primary text-[20px]">timeline</span>
              {{ t('heat.cuttingTimeline') }}
          </h3>
          <el-timeline class="pl-1 pt-2">
            <el-timeline-item
              v-for="(item, index) in current.cuttingTimeline"
              :key="`${item.event_type}-${item.timestamp}`"
              :timestamp="dayjs(item.timestamp).format('HH:mm:ss')"
              placement="top"
              :color="index === current.cuttingTimeline.length - 1 ? '#1152d4' : '#e2e8f0'"
            >
              <div class="font-semibold text-sm text-slate-800 tracking-tight">{{ item.title }}</div>
              <div class="text-xs text-slate-500 mt-1">{{ item.detail }}</div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="py-16 flex flex-col items-center justify-center bg-white rounded-xl border border-border-light shadow-card">
      <span class="material-symbols-outlined text-slate-300 text-5xl">pending</span>
      <p class="text-sm text-slate-400 mt-3">{{ t('common.loading') }}</p>
    </div>
  </div>
</template>
