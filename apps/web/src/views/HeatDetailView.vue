<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ElDatePicker,
  ElDialog,
  ElMessage,
  ElMessageBox,
  ElSlider,
  ElTabs,
  ElTabPane,
  ElTimeline,
  ElTimelineItem
} from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import dayjs from 'dayjs'
import { useHeatStore } from '@/stores/heat'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent, DataZoomComponent])

interface ManualAdjustPoint {
  timestamp: number
  value: number
}

const { t } = useI18n()
const route = useRoute()
const heatStore = useHeatStore()

const heatId = computed(() => String(route.params.id || ''))
const current = computed(() => heatStore.current)

const editingDescription = ref(false)
const descriptionDraft = ref('')
const activeBaselineId = ref('')

const manualAdjustVisible = ref(false)
const manualAdjustFullscreen = ref(false)
const manualAdjustStart = ref<number | null>(null)
const manualAdjustEnd = ref<number | null>(null)
const manualAdjustRange = ref<[number, number]>([0, 0])
const manualAdjustBoundary = ref<'start' | 'end'>('start')

const selectedComparison = computed(() => {
  if (!current.value) return null
  if (current.value.baselineComparisons.length === 0) return null
  return (
    current.value.baselineComparisons.find(item => item.baseline.id === activeBaselineId.value) ||
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

  const labels = current.value.powerCurve.map(point => dayjs(point.timestamp).format('HH:mm'))

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
        data: (selectedComparison.value?.baseline.power_curve || current.value.baselinePowerCurve).map(point => point.value)
      },
      {
        name: t('dashboard.chart.currentProduction'),
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#1152d4' },
        markArea: {
          itemStyle: { color: 'rgba(245, 108, 108, 0.12)' },
          data: (selectedComparison.value?.deviation_ranges || current.value.deviationRanges).map(range => {
            const start = dayjs(range.start).format('HH:mm')
            const end = dayjs(range.end).format('HH:mm')
            return [{ xAxis: start }, { xAxis: end }]
          })
        },
        data: current.value.powerCurve.map(point => point.value)
      }
    ]
  }
})

const manualAdjustWindow = computed(() => {
  if (!current.value) {
    return { min: 0, max: 0, points: [] as ManualAdjustPoint[] }
  }

  const baseStart = dayjs(current.value.base.startTime)
  const baseEnd = dayjs(current.value.base.endTime)
  const windowStart = baseStart.subtract(5, 'hour')
  const windowEnd = baseEnd.add(5, 'hour')
  const existingCurve = current.value.powerCurve
  const firstValue = existingCurve[0]?.value || 430
  const lastValue = existingCurve[existingCurve.length - 1]?.value || firstValue
  const points: ManualAdjustPoint[] = []

  for (let cursor = windowStart.valueOf(); cursor <= windowEnd.valueOf(); cursor += 60 * 1000) {
    const existingPoint = existingCurve.find(point => point.timestamp === cursor)
    if (existingPoint) {
      points.push({ timestamp: cursor, value: existingPoint.value })
      continue
    }

    const progress = (cursor - windowStart.valueOf()) / Math.max(windowEnd.valueOf() - windowStart.valueOf(), 1)
    const edgeBlend = cursor < baseStart.valueOf() ? firstValue : lastValue
    const wave = Math.sin(progress * Math.PI * 8) * 12
    const jitter = Math.cos(progress * Math.PI * 11) * 3
    points.push({
      timestamp: cursor,
      value: Number((edgeBlend + wave + jitter).toFixed(1))
    })
  }

  return {
    min: points[0]?.timestamp || 0,
    max: points[points.length - 1]?.timestamp || 0,
    points
  }
})

const manualAdjustOption = computed<EChartsOption>(() => {
  if (!current.value || manualAdjustWindow.value.points.length === 0) return {}

  return {
    animation: false,
    grid: { left: 56, right: 24, top: 38, bottom: 86 },
    tooltip: { trigger: 'axis' },
    legend: {
      top: 0,
      data: [t('heat.manualAdjustRange')]
    },
    dataZoom: [
      { type: 'inside', moveOnMouseMove: true, zoomOnMouseWheel: true },
      { type: 'slider', height: 28, bottom: 24 }
    ],
    xAxis: {
      type: 'time',
      axisLabel: {
        formatter: (value: number) => dayjs(value).format('MM-DD HH:mm')
      }
    },
    yAxis: {
      type: 'value',
      name: `${t('dashboard.chart.power')} (kW)`
    },
    series: [
      {
        name: t('heat.manualAdjustRange'),
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#1152d4' },
        markArea:
          manualAdjustStart.value && manualAdjustEnd.value
            ? {
                itemStyle: { color: 'rgba(17, 82, 212, 0.12)' },
                data: [[{ xAxis: manualAdjustStart.value }, { xAxis: manualAdjustEnd.value }]]
              }
            : undefined,
        data: manualAdjustWindow.value.points.map(point => [point.timestamp, point.value])
      }
    ]
  }
})

function normalizeManualAdjustRange() {
  if (!manualAdjustStart.value || !manualAdjustEnd.value) return
  if (manualAdjustStart.value > manualAdjustEnd.value) {
    const start = manualAdjustStart.value
    manualAdjustStart.value = manualAdjustEnd.value
    manualAdjustEnd.value = start
  }
  manualAdjustRange.value = [manualAdjustStart.value, manualAdjustEnd.value]
}

watch(manualAdjustRange, value => {
  if (!value || value.length !== 2) return
  if (manualAdjustStart.value !== value[0]) {
    manualAdjustStart.value = value[0]
  }
  if (manualAdjustEnd.value !== value[1]) {
    manualAdjustEnd.value = value[1]
  }
  normalizeManualAdjustRange()
})

watch([manualAdjustStart, manualAdjustEnd], () => {
  normalizeManualAdjustRange()
})

function handleCreateTask() {
  ElMessage.info(t('heat.createTaskHint'))
}

function openManualAdjust() {
  if (!current.value) return
  manualAdjustStart.value = dayjs(current.value.base.startTime).valueOf()
  manualAdjustEnd.value = dayjs(current.value.base.endTime).valueOf()
  normalizeManualAdjustRange()
  manualAdjustBoundary.value = 'start'
  manualAdjustVisible.value = true
}

function handleManualAdjustChartClick(params: { dataIndex?: number }) {
  if (params.dataIndex === undefined) return
  const point = manualAdjustWindow.value.points[params.dataIndex]
  if (!point) return

  if (manualAdjustBoundary.value === 'start') {
    manualAdjustStart.value = point.timestamp
    manualAdjustBoundary.value = 'end'
  } else {
    manualAdjustEnd.value = point.timestamp
    manualAdjustBoundary.value = 'start'
  }

  normalizeManualAdjustRange()
}

async function saveManualAdjust() {
  if (!heatId.value || !manualAdjustStart.value || !manualAdjustEnd.value) return

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
    dayjs(manualAdjustStart.value).format('YYYY-MM-DD HH:mm:ss'),
    dayjs(manualAdjustEnd.value).format('YYYY-MM-DD HH:mm:ss'),
    adjustSubsequent
  )
  await heatStore.fetchDetail(heatId.value)
  manualAdjustVisible.value = false
  ElMessage.success(t('common.success'))
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
    <PageHeader
      :title="current?.base.heatNo || '--'"
      :subtitle="`ID: ${heatId}`"
      :description="current?.base.description || 'Furnace-A01'"
    >
      <template #actions>
        <StatusBadge
          :type="statusTagType"
          class="mr-2"
        >
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
          @click="openManualAdjust"
        >
          <span class="material-symbols-outlined text-[18px]">tune</span>
          {{ t('heat.manualAdjust') }}
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
      <div class="xl:col-span-2 space-y-6">
        <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
          <div class="flex flex-col lg:flex-row justify-between lg:items-center mb-4 gap-4">
            <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2">
              <span class="material-symbols-outlined text-primary text-[20px]">ssid_chart</span>
              {{ t('heat.compareWithBaseline') }}
            </h3>
            <div class="flex items-center gap-3">
              <el-tabs
                v-model="activeBaselineId"
                class="-mb-[15px] mr-2"
              >
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
          />
        </div>

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
          <div
            v-else
            class="py-8 flex flex-col items-center justify-center"
          >
            <span class="material-symbols-outlined text-slate-300 text-4xl">check_circle</span>
            <p class="text-sm text-slate-500 mt-2 font-medium">
              无明显偏差区间
            </p>
          </div>
        </div>
      </div>

      <div class="space-y-6">
        <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
          <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2 mb-4 pb-4 border-b border-border-light">
            <span class="material-symbols-outlined text-primary text-[20px]">feed</span>
            {{ t('heat.detailSummary') }}
          </h3>
          <div class="space-y-4 text-sm text-slate-700">
            <div class="flex flex-col gap-1 border-b border-slate-50 pb-3">
              <div class="flex justify-between items-center">
                <span class="text-slate-500">{{ t('heat.description') }}</span>
                <button
                  v-if="!editingDescription"
                  class="text-primary hover:underline flex items-center gap-1 text-xs"
                  @click="startEditDescription"
                >
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
                  >
                  <button
                    class="bg-primary text-white px-3 rounded text-xs font-bold"
                    @click="saveDescription"
                  >
                    Save
                  </button>
                  <button
                    class="text-slate-400 text-xs hover:text-slate-600"
                    @click="editingDescription = false"
                  >
                    Cancel
                  </button>
                </div>
              </template>
            </div>

            <div class="rounded-lg bg-slate-50 border border-border-light p-3">
              <div class="text-xs uppercase tracking-wider text-slate-400">
                时序与切割分析
              </div>
              <div class="mt-3 space-y-2 font-mono text-xs">
                <div class="flex justify-between">
                  <span class="font-sans text-slate-400">{{ t('heat.startTime') }}</span>
                  <span>{{ current.base.startTime }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="font-sans text-slate-400">{{ t('heat.endTime') }}</span>
                  <span>{{ current.base.endTime }}</span>
                </div>
              </div>
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
              <div class="font-semibold text-sm text-slate-800 tracking-tight">
                {{ item.title }}
              </div>
              <div class="text-xs text-slate-500 mt-1">
                {{ item.detail }}
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </div>
    </div>

    <div
      v-else
      class="py-16 flex flex-col items-center justify-center bg-white rounded-xl border border-border-light shadow-card"
    >
      <span class="material-symbols-outlined text-slate-300 text-5xl">pending</span>
      <p class="text-sm text-slate-400 mt-3">
        {{ t('common.loading') }}
      </p>
    </div>

    <el-dialog
      v-model="manualAdjustVisible"
      :title="t('heat.manualAdjust')"
      :fullscreen="manualAdjustFullscreen"
      width="1100px"
      append-to-body
    >
      <div class="space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="text-sm text-slate-500">
            {{ t('heat.manualAdjustHint') }}
          </div>
          <div class="flex items-center gap-2">
            <button
              class="rounded-lg border border-border-light px-3 py-1.5 text-sm text-slate-600 transition-colors hover:border-primary/30 hover:text-primary"
              @click="manualAdjustBoundary = 'start'"
            >
              {{ t('heat.pickBaselineStart') }}
            </button>
            <button
              class="rounded-lg border border-border-light px-3 py-1.5 text-sm text-slate-600 transition-colors hover:border-primary/30 hover:text-primary"
              @click="manualAdjustBoundary = 'end'"
            >
              {{ t('heat.pickBaselineEnd') }}
            </button>
            <button
              class="rounded-lg border border-border-light px-3 py-1.5 text-sm text-slate-600 transition-colors hover:border-primary/30 hover:text-primary"
              @click="manualAdjustFullscreen = !manualAdjustFullscreen"
            >
              {{ manualAdjustFullscreen ? t('heat.exitFullscreen') : t('baseline.wizard.fullscreen') }}
            </button>
          </div>
        </div>

        <v-chart
          :option="manualAdjustOption"
          autoresize
          class="h-[460px]"
          @click="handleManualAdjustChartClick"
        />

        <div class="rounded-xl border border-border-light bg-slate-50 px-5 py-4">
          <el-slider
            v-model="manualAdjustRange"
            range
            :min="manualAdjustWindow.min"
            :max="manualAdjustWindow.max"
            :step="60 * 1000"
            :format-tooltip="(value: number) => dayjs(value).format('MM-DD HH:mm:ss')"
          />
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <el-date-picker
            v-model="manualAdjustStart"
            type="datetime"
            value-format="x"
            format="YYYY-MM-DD HH:mm:ss"
            class="!w-full"
          />
          <el-date-picker
            v-model="manualAdjustEnd"
            type="datetime"
            value-format="x"
            format="YYYY-MM-DD HH:mm:ss"
            class="!w-full"
          />
        </div>
      </div>
      <template #footer>
        <div class="flex justify-between">
          <el-button @click="manualAdjustVisible = false">
            {{ t('common.cancel') }}
          </el-button>
          <div class="flex items-center gap-2">
            <el-button @click="manualAdjustVisible = false">
              {{ t('common.back') }}
            </el-button>
            <el-button
              type="primary"
              @click="saveManualAdjust"
            >
              {{ t('common.save') }}
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
