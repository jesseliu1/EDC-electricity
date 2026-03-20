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
  ElTimelineItem,
} from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts, EChartsOption } from 'echarts'
import dayjs from 'dayjs'
import type { HeatDataSource } from '@/api/heat'
import { useHeatStore } from '@/stores/heat'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'

use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  DataZoomComponent,
])

interface ManualAdjustPoint {
  timestamp: number
  value: number
}

interface ManualAdjustMetricContext {
  metric_key: string
  metric_name: string
  unit: string
  color: string
  currentSeries: ManualAdjustPoint[]
  baselineSeries: ManualAdjustPoint[]
}

interface PointerEventPayload {
  offsetX: number
  offsetY: number
}

interface PointerState {
  startX: number
  startY: number
  dragging: boolean
}

interface DataZoomPayload {
  start?: number
  end?: number
  batch?: Array<{
    start?: number
    end?: number
  }>
}

type ExposedChart = ECharts | { value?: ECharts | undefined }

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
const manualAdjustChartRef = ref<InstanceType<typeof VChart> | null>(null)
const manualAdjustZoomWindow = ref({ start: 0, end: 100 })
let syncingManualAdjustState = false
let manualAdjustPointerState: PointerState | null = null

const pointerDragThreshold = 6

const selectedComparison = computed(() => {
  if (!current.value) return null
  if (current.value.baselineComparisons.length === 0) return null
  return (
    current.value.baselineComparisons.find((item) => item.baseline.id === activeBaselineId.value) ||
    current.value.baselineComparisons[0]
  )
})

const comparisonMetricCurves = computed(() => selectedComparison.value?.metric_curves || [])

const primaryComparisonMetric = computed<{
  metric_key: string
  metric_name: string
  unit: string
  color: string
  edc_channel_id?: string | null
  source_channel_name?: string | null
  source_channel_label?: string | null
  baseline_curve: { timestamp: number; value: number }[]
  current_curve: { timestamp: number; value: number }[]
}>(() => {
  const fallbackMetric = {
    metric_key: 'power',
    metric_name: t('dashboard.chart.power'),
    unit: 'kW',
    color: '#409EFF',
    baseline_curve: current.value?.baselinePowerCurve || [],
    current_curve: current.value?.powerCurve || [],
  }
  if (comparisonMetricCurves.value.length > 0) {
    return (
      comparisonMetricCurves.value.find((item) => item.metric_key === 'power') ||
      comparisonMetricCurves.value[0] ||
      fallbackMetric
    )
  }

  return fallbackMetric
})

const compareSeriesCount = computed(() => {
  const metricCurves =
    comparisonMetricCurves.value.length > 0
      ? comparisonMetricCurves.value
      : [primaryComparisonMetric.value]
  return metricCurves.length * 2
})

function normalizedTimestamp(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return null
  const timestamp = Number(value)
  return Number.isFinite(timestamp) ? timestamp : null
}

function inferCurveStepMs(curves: Array<{ timestamp: number }[]>) {
  const diffs = curves.flatMap((curve) =>
    curve.slice(1).reduce<number[]>((accumulator, point, index) => {
      const previousPoint = curve[index]
      if (!previousPoint) return accumulator

      const diff = point.timestamp - previousPoint.timestamp
      if (diff > 0) {
        accumulator.push(diff)
      }

      return accumulator
    }, [])
  )

  return diffs.length > 0 ? Math.min(...diffs) : 60 * 1000
}

function wrapIndex(index: number, length: number) {
  if (length <= 0) return 0
  const wrapped = index % length
  return wrapped >= 0 ? wrapped : wrapped + length
}

function buildManualAdjustSeries(
  source: ManualAdjustPoint[],
  contextStart: number,
  contextEnd: number,
  stepMs: number
) {
  const sorted = [...source].sort((left, right) => left.timestamp - right.timestamp)
  if (sorted.length === 0) return [] as ManualAdjustPoint[]
  const firstPoint = sorted[0]
  if (!firstPoint) return [] as ManualAdjustPoint[]

  const exactValueMap = new Map(sorted.map((point) => [point.timestamp, point.value]))
  const anchorTimestamp = firstPoint.timestamp
  const totalPoints = Math.floor((contextEnd - contextStart) / stepMs) + 1

  return Array.from({ length: totalPoints }, (_, index) => {
    const timestamp = contextStart + index * stepMs
    const exactValue = exactValueMap.get(timestamp)
    if (exactValue !== undefined) {
      return { timestamp, value: exactValue }
    }

    const relativeIndex = Math.round((timestamp - anchorTimestamp) / stepMs)
    const sourcePoint = sorted[wrapIndex(relativeIndex, sorted.length)] ?? firstPoint
    return { timestamp, value: sourcePoint.value }
  })
}

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

function dataSourceText(source: HeatDataSource) {
  if (source === 'live_edc') return t('heat.dataSource.liveEdc')
  if (source === 'live_inferred') return t('heat.dataSource.liveInferred')
  if (source === 'mock_curve') return t('heat.dataSource.demoCurve')
  if (source === 'mock_stream') return t('heat.dataSource.demoSeed')
  if (source === 'demo_curve') return t('heat.dataSource.demoCurve')
  if (source === 'none') return t('heat.dataSource.none')
  return t('heat.dataSource.none')
}

const shouldShowSourceBanner = computed(() => {
  if (!current.value) return false
  return (
    current.value.base.recordSource !== 'live_edc' ||
    current.value.base.currentCurveSource !== 'live_edc' ||
    current.value.base.baselineCurveSource !== 'live_edc'
  )
})

const compareOption = computed<EChartsOption>(() => {
  if (!current.value) return {}
  const metricCurves =
    comparisonMetricCurves.value.length > 0
      ? comparisonMetricCurves.value
      : [primaryComparisonMetric.value]
  const units = Array.from(new Set(metricCurves.map((item) => item.unit)))
  const firstCurrentCurve = metricCurves[0]?.current_curve || current.value.powerCurve
  const deviationRanges =
    selectedComparison.value?.deviation_ranges || current.value.deviationRanges

  return {
    animation: false,
    grid: { left: 56, right: 72, top: 40, bottom: 32 },
    tooltip: { trigger: 'axis' },
    legend: {
      data: metricCurves.flatMap((item) => [
        `${item.metric_name}-${t('dashboard.chart.goldenBaseline')}`,
        `${item.metric_name}-${t('dashboard.chart.currentProduction')}`,
      ]),
      top: 0,
    },
    xAxis: {
      type: 'time',
      axisLabel: {
        formatter: (value: number) => dayjs(value).format('HH:mm'),
      },
    },
    yAxis: units.map((unit, index) => ({
      type: 'value',
      name: unit,
      position: index % 2 === 0 ? 'left' : 'right',
      offset: index > 1 ? Math.floor((index - 1) / 2) * 56 : 0,
      splitLine: index === 0 ? { lineStyle: { color: '#e2e8f0' } } : { show: false },
    })),
    series: metricCurves.flatMap((metric, index) => [
      {
        name: `${metric.metric_name}-${t('dashboard.chart.goldenBaseline')}`,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: units.indexOf(metric.unit),
        lineStyle: { width: 2, type: 'dashed', color: metric.color },
        data: metric.baseline_curve.map((point) => [point.timestamp, point.value]),
      },
      {
        name: `${metric.metric_name}-${t('dashboard.chart.currentProduction')}`,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: units.indexOf(metric.unit),
        lineStyle: { width: index === 0 ? 2.5 : 2, color: metric.color },
        areaStyle: index === 0 ? { color: metric.color, opacity: 0.05 } : undefined,
        markArea:
          index === 0
            ? {
                itemStyle: { color: 'rgba(245, 108, 108, 0.12)' },
                data: deviationRanges.map((range) => [
                  { xAxis: range.start },
                  { xAxis: range.end },
                ]),
              }
            : undefined,
        data: metric.current_curve.map((point) => [point.timestamp, point.value]),
      },
    ]),
    dataZoom: firstCurrentCurve.length > 120 ? [{ type: 'inside' }] : undefined,
  }
})

const manualAdjustContext = computed(() => {
  if (!current.value) {
    return {
      min: 0,
      max: 0,
      stepMs: 60 * 1000,
      metrics: [] as ManualAdjustMetricContext[],
      baselineFilled: false,
    }
  }

  const metricCurves =
    comparisonMetricCurves.value.length > 0
      ? comparisonMetricCurves.value
      : [primaryComparisonMetric.value]
  const contextStart = dayjs(current.value.base.startTime).startOf('day').valueOf()
  const rawContextEnd = dayjs(current.value.base.startTime).endOf('day').valueOf()
  const stepMs = inferCurveStepMs(
    metricCurves.flatMap((metric) => [metric.current_curve, metric.baseline_curve])
  )
  const alignedContextEnd =
    contextStart + Math.floor((rawContextEnd - contextStart) / stepMs) * stepMs
  const metrics = metricCurves.map((metric) => ({
    metric_key: metric.metric_key,
    metric_name: metric.metric_name,
    unit: metric.unit,
    color: metric.color,
    currentSeries: buildManualAdjustSeries(
      metric.current_curve,
      contextStart,
      alignedContextEnd,
      stepMs
    ),
    baselineSeries: buildManualAdjustSeries(
      metric.baseline_curve,
      contextStart,
      alignedContextEnd,
      stepMs
    ),
  }))

  return {
    min: metrics[0]?.currentSeries[0]?.timestamp || contextStart,
    max:
      metrics[0]?.currentSeries[metrics[0].currentSeries.length - 1]?.timestamp ||
      alignedContextEnd,
    stepMs,
    metrics,
    baselineFilled:
      metrics.length > 0 &&
      metrics.every(
        (metric) =>
          metric.currentSeries.length > 0 &&
          metric.currentSeries.length === metric.baselineSeries.length
      ),
  }
})

const manualAdjustSelectionProbe = computed(() => ({
  start: normalizedTimestamp(manualAdjustStart.value),
  end: normalizedTimestamp(manualAdjustEnd.value),
  zoomStart: manualAdjustZoomWindow.value.start,
  zoomEnd: manualAdjustZoomWindow.value.end,
  contextStart: manualAdjustContext.value.min,
  contextEnd: manualAdjustContext.value.max,
  contextDurationMinutes:
    manualAdjustContext.value.max > manualAdjustContext.value.min
      ? Math.floor((manualAdjustContext.value.max - manualAdjustContext.value.min) / (60 * 1000))
      : 0,
  baselineFilled: manualAdjustContext.value.baselineFilled ? 'true' : 'false',
  seriesCount: manualAdjustContext.value.metrics.length * 2,
}))

function calculateZoomWindowByRange(start: number, end: number) {
  const contextStart = manualAdjustContext.value.min
  const contextEnd = manualAdjustContext.value.max
  const contextDuration = Math.max(contextEnd - contextStart, 1)
  const selectedDuration = Math.max(end - start, manualAdjustContext.value.stepMs)
  const padding = Math.max(selectedDuration * 0.25, 15 * 60 * 1000)
  const viewportStart = Math.max(start - padding, contextStart)
  const viewportEnd = Math.min(end + padding, contextEnd)

  return {
    start: Number((((viewportStart - contextStart) / contextDuration) * 100).toFixed(2)),
    end: Number((((viewportEnd - contextStart) / contextDuration) * 100).toFixed(2)),
  }
}

function syncManualAdjustZoomToCurrentRange() {
  if (!manualAdjustStart.value || !manualAdjustEnd.value) return
  manualAdjustZoomWindow.value = calculateZoomWindowByRange(
    manualAdjustStart.value,
    manualAdjustEnd.value
  )
}

const manualAdjustOption = computed<EChartsOption>(() => {
  if (!current.value || manualAdjustContext.value.metrics.length === 0) return {}
  const metricContexts = manualAdjustContext.value.metrics
  const units = Array.from(new Set(metricContexts.map((metric) => metric.unit)))

  return {
    animation: false,
    grid: { left: 56, right: 72, top: 40, bottom: 86 },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) =>
        typeof value === 'number' ? value.toFixed(2).replace(/\.00$/, '') : `${value || ''}`,
    },
    legend: {
      top: 0,
      data: metricContexts.flatMap((metric) => [
        `${metric.metric_name}-${t('dashboard.chart.goldenBaseline')}`,
        `${metric.metric_name}-${t('dashboard.chart.currentProduction')}`,
      ]),
    },
    dataZoom: [
      {
        type: 'inside',
        moveOnMouseMove: true,
        zoomOnMouseWheel: true,
        start: manualAdjustZoomWindow.value.start,
        end: manualAdjustZoomWindow.value.end,
      },
      {
        type: 'slider',
        height: 28,
        bottom: 24,
        start: manualAdjustZoomWindow.value.start,
        end: manualAdjustZoomWindow.value.end,
      },
    ],
    xAxis: {
      type: 'time',
      axisLabel: {
        formatter: (value: number) => dayjs(value).format('HH:mm:ss'),
      },
    },
    yAxis: units.map((unit, index) => ({
      type: 'value',
      name: unit,
      position: index % 2 === 0 ? 'left' : 'right',
      offset: index > 1 ? Math.floor((index - 1) / 2) * 56 : 0,
      splitLine: index === 0 ? { lineStyle: { color: '#e2e8f0' } } : { show: false },
    })),
    series: metricContexts.flatMap((metric, index) => [
      {
        name: `${metric.metric_name}-${t('dashboard.chart.goldenBaseline')}`,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: units.indexOf(metric.unit),
        lineStyle: { width: 2, type: 'dashed', color: metric.color },
        data: metric.baselineSeries.map((point) => [point.timestamp, point.value]),
      },
      {
        name: `${metric.metric_name}-${t('dashboard.chart.currentProduction')}`,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: units.indexOf(metric.unit),
        lineStyle: { width: index === 0 ? 2.5 : 2, color: metric.color },
        areaStyle: index === 0 ? { color: metric.color, opacity: 0.05 } : undefined,
        markArea:
          index === 0 && manualAdjustStart.value && manualAdjustEnd.value
            ? {
                itemStyle: { color: 'rgba(17, 82, 212, 0.12)' },
                data: [[{ xAxis: manualAdjustStart.value }, { xAxis: manualAdjustEnd.value }]],
              }
            : undefined,
        data: metric.currentSeries.map((point) => [point.timestamp, point.value]),
      },
    ]),
  }
})

function normalizeManualAdjustBounds(start: number, end: number): [number, number] {
  const min = manualAdjustContext.value.min
  const max = manualAdjustContext.value.max
  const clampedStart = Math.min(Math.max(start, min), max)
  const clampedEnd = Math.min(Math.max(end, min), max)

  return clampedStart <= clampedEnd ? [clampedStart, clampedEnd] : [clampedEnd, clampedStart]
}

function resolveManualAdjustChartInstance() {
  const chartRef = manualAdjustChartRef.value?.chart as ExposedChart | undefined
  if (!chartRef) return null
  if ('containPixel' in chartRef && 'convertFromPixel' in chartRef) {
    return chartRef
  }
  if ('value' in chartRef) {
    return chartRef.value ?? null
  }
  return null
}

function clearManualAdjustPointerState() {
  manualAdjustPointerState = null
}

function selectNearestManualAdjustPoint(targetTimestamp: number) {
  const primarySeries = manualAdjustContext.value.metrics[0]?.currentSeries || []
  const point = primarySeries.reduce<ManualAdjustPoint | null>((closestPoint, currentPoint) => {
    if (!closestPoint) return currentPoint
    return Math.abs(currentPoint.timestamp - targetTimestamp) <
      Math.abs(closestPoint.timestamp - targetTimestamp)
      ? currentPoint
      : closestPoint
  }, null)

  if (!point) return

  if (!manualAdjustStart.value) {
    manualAdjustStart.value = point.timestamp
  } else if (!manualAdjustEnd.value) {
    manualAdjustEnd.value = point.timestamp
  } else if (
    Math.abs(point.timestamp - manualAdjustStart.value) <=
    Math.abs(point.timestamp - manualAdjustEnd.value)
  ) {
    manualAdjustStart.value = point.timestamp
  } else {
    manualAdjustEnd.value = point.timestamp
  }

  syncRangeFromBounds()
}

function handleManualAdjustPointerDown(event: PointerEventPayload) {
  manualAdjustPointerState = {
    startX: event.offsetX,
    startY: event.offsetY,
    dragging: false,
  }
}

function handleManualAdjustPointerMove(event: PointerEventPayload) {
  if (!manualAdjustPointerState) return

  if (
    Math.abs(event.offsetX - manualAdjustPointerState.startX) > pointerDragThreshold ||
    Math.abs(event.offsetY - manualAdjustPointerState.startY) > pointerDragThreshold
  ) {
    manualAdjustPointerState.dragging = true
  }
}

function handleManualAdjustPointerClick(event: PointerEventPayload) {
  const pointerState = manualAdjustPointerState
  clearManualAdjustPointerState()
  if (!pointerState || pointerState.dragging) return

  const instance = resolveManualAdjustChartInstance()
  if (!instance) return

  const pixel: [number, number] = [event.offsetX, event.offsetY]
  if (!instance.containPixel({ gridIndex: 0 }, pixel)) return

  const converted = instance.convertFromPixel({ gridIndex: 0 }, pixel)
  const timestamp = Number(Array.isArray(converted) ? converted[0] : converted)
  if (!Number.isFinite(timestamp)) return

  selectNearestManualAdjustPoint(timestamp)
}

function handleManualAdjustDataZoom(payload: DataZoomPayload) {
  const latest = payload.batch?.[0] || payload
  manualAdjustZoomWindow.value = {
    start: latest.start ?? manualAdjustZoomWindow.value.start,
    end: latest.end ?? manualAdjustZoomWindow.value.end,
  }
}

function syncRangeFromBounds() {
  if (!manualAdjustStart.value || !manualAdjustEnd.value) return

  const [nextStart, nextEnd] = normalizeManualAdjustBounds(
    manualAdjustStart.value,
    manualAdjustEnd.value
  )

  syncingManualAdjustState = true
  if (manualAdjustStart.value !== nextStart) {
    manualAdjustStart.value = nextStart
  }
  if (manualAdjustEnd.value !== nextEnd) {
    manualAdjustEnd.value = nextEnd
  }
  if (manualAdjustRange.value[0] !== nextStart || manualAdjustRange.value[1] !== nextEnd) {
    manualAdjustRange.value = [nextStart, nextEnd]
  }
  syncingManualAdjustState = false
}

watch(manualAdjustRange, (value) => {
  if (syncingManualAdjustState || !value || value.length !== 2) return

  const [nextStart, nextEnd] = normalizeManualAdjustBounds(value[0], value[1])
  syncingManualAdjustState = true
  if (manualAdjustStart.value !== nextStart) {
    manualAdjustStart.value = nextStart
  }
  if (manualAdjustEnd.value !== nextEnd) {
    manualAdjustEnd.value = nextEnd
  }
  if (manualAdjustRange.value[0] !== nextStart || manualAdjustRange.value[1] !== nextEnd) {
    manualAdjustRange.value = [nextStart, nextEnd]
  }
  syncingManualAdjustState = false
})

watch([manualAdjustStart, manualAdjustEnd], () => {
  if (syncingManualAdjustState || !manualAdjustStart.value || !manualAdjustEnd.value) return
  syncRangeFromBounds()
})

watch(
  () => current.value?.baselineComparisons,
  (comparisons) => {
    const items = comparisons || []
    if (items.length === 0) {
      activeBaselineId.value = ''
      return
    }
    if (!items.some((item) => item.baseline.id === activeBaselineId.value)) {
      activeBaselineId.value = items[0]?.baseline.id || ''
    }
  },
  { immediate: true, deep: true }
)

function handleCreateTask() {
  ElMessage.info(t('heat.createTaskHint'))
}

function openManualAdjust() {
  if (!current.value) return
  manualAdjustStart.value = dayjs(current.value.base.startTime).valueOf()
  manualAdjustEnd.value = dayjs(current.value.base.endTime).valueOf()
  syncRangeFromBounds()
  syncManualAdjustZoomToCurrentRange()
  manualAdjustVisible.value = true
}

async function saveManualAdjust() {
  if (!heatId.value || !manualAdjustStart.value || !manualAdjustEnd.value) return

  let adjustSubsequent = false
  try {
    await ElMessageBox.confirm(t('heat.adjustSubsequentConfirm'), t('common.confirm'), {
      distinguishCancelAndClose: true,
      confirmButtonText: t('heat.adjustSubsequentYes'),
      cancelButtonText: t('heat.adjustSubsequentNo'),
      type: 'warning',
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
      type: 'warning',
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
  <div
    class="flex flex-col gap-6"
    data-testid="heat-detail-page"
  >
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
          data-testid="heat-manual-adjust-button"
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
        <div
          v-if="shouldShowSourceBanner"
          class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
          data-testid="heat-detail-source-banner"
        >
          <div class="font-semibold">
            {{ t('heat.detailSourceTitle') }}
          </div>
          <div class="mt-2 flex flex-wrap gap-3 text-amber-700">
            <span>{{ t('heat.recordSourceLabel') }}: {{ dataSourceText(current.base.recordSource) }}</span>
            <span>{{ t('heat.currentCurveSourceLabel') }}: {{ dataSourceText(current.base.currentCurveSource) }}</span>
            <span>{{ t('heat.baselineCurveSourceLabel') }}: {{ dataSourceText(current.base.baselineCurveSource) }}</span>
          </div>
        </div>

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
            data-testid="heat-compare-chart"
            :data-series-count="compareSeriesCount"
          />
        </div>

        <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
          <h3
            class="text-sm font-bold text-slate-800 flex items-center gap-2 mb-4 pb-4 border-b border-border-light"
          >
            <span class="material-symbols-outlined text-red-500 text-[20px]">warning</span>
            {{ t('heat.abnormalRanges') }}
          </h3>
          <div
            v-if="(selectedComparison?.deviation_ranges || current.deviationRanges).length > 0"
            class="space-y-3"
            data-testid="heat-abnormal-range-list"
          >
            <div
              v-for="(range, idx) in selectedComparison?.deviation_ranges ||
                current.deviationRanges"
              :key="`${range.start}-${range.end}`"
              class="rounded-lg border border-red-200 bg-red-50 p-4 flex items-center justify-between"
              data-testid="heat-abnormal-range-item"
            >
              <div class="flex items-center gap-3">
                <span
                  class="w-6 h-6 rounded-full bg-red-100 text-red-700 flex items-center justify-center text-xs font-bold"
                >
                  {{ idx + 1 }}
                </span>
                <span class="font-mono text-sm text-red-900">
                  {{ dayjs(range.start).format('HH:mm:ss') }}
                  <span class="text-red-300 mx-2">to</span>
                  {{ dayjs(range.end).format('HH:mm:ss') }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-xs text-red-500 uppercase tracking-widest font-semibold">
                  Deviation
                </span>
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
          <h3
            class="text-sm font-bold text-slate-800 flex items-center gap-2 mb-4 pb-4 border-b border-border-light"
          >
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
                  <span class="material-symbols-outlined text-[14px]">edit</span>
                  {{ t('common.edit') }}
                </button>
              </div>
              <template v-if="!editingDescription">
                <span class="font-semibold text-slate-800">{{
                  current.base.description || t('common.noDescription')
                }}</span>
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
              <span class="font-semibold">{{
                t(`heat.cutReason.${current.base.cutReason || 'unknown'}`)
              }}</span>
            </div>
            <div class="flex justify-between items-center py-1">
              <span class="text-slate-500">{{ t('heat.mismatchDurationMinutes') }}</span>
              <span class="font-semibold text-orange-600">{{
                current.base.mismatchDurationMinutes === null
                  ? '--'
                  : `${current.base.mismatchDurationMinutes}m`
              }}</span>
            </div>
            <div class="flex justify-between items-center py-1">
              <span class="text-slate-500">{{ t('heat.temperature') }}</span>
              <span class="font-semibold">{{ current.base.temperature ?? '--' }}</span>
            </div>
            <div class="flex justify-between items-center py-1">
              <span class="text-slate-500">{{ t('heat.baselineName') }}</span>
              <span class="font-semibold break-all text-right max-w-[60%]">{{
                selectedComparison?.baseline.name || '--'
              }}</span>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-xl border border-border-light shadow-card p-5">
          <h3
            class="text-sm font-bold text-slate-800 flex items-center gap-2 mb-4 pb-4 border-b border-border-light"
          >
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
      data-testid="manual-adjust-dialog"
    >
      <div
        class="sr-only"
        data-testid="manual-adjust-selection-state"
        :data-start="manualAdjustSelectionProbe.start ?? ''"
        :data-end="manualAdjustSelectionProbe.end ?? ''"
        :data-zoom-start="manualAdjustSelectionProbe.zoomStart"
        :data-zoom-end="manualAdjustSelectionProbe.zoomEnd"
        :data-context-start="manualAdjustSelectionProbe.contextStart"
        :data-context-end="manualAdjustSelectionProbe.contextEnd"
        :data-context-duration-minutes="manualAdjustSelectionProbe.contextDurationMinutes"
        :data-baseline-filled="manualAdjustSelectionProbe.baselineFilled"
      />
      <div class="space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="space-y-1">
            <div class="text-sm text-slate-500">
              {{ t('heat.manualAdjustHint') }}
            </div>
            <div class="text-xs text-slate-400">
              点击图表会自动更新离点击位置最近的起点或终点，图表、滑块和时间输入框会同步联动。
            </div>
          </div>
          <div class="flex items-center gap-2">
            <el-tabs
              v-if="current?.baselineComparisons.length"
              v-model="activeBaselineId"
              class="-mb-[15px] mr-2"
              data-testid="manual-adjust-baseline-tabs"
            >
              <el-tab-pane
                v-for="item in current.baselineComparisons"
                :key="`manual-adjust-${item.baseline.id}`"
                :name="item.baseline.id"
                :label="item.baseline.name"
              />
            </el-tabs>
            <button
              data-testid="manual-adjust-fullscreen-toggle"
              class="rounded-lg border border-border-light px-3 py-1.5 text-sm text-slate-600 transition-colors hover:border-primary/30 hover:text-primary"
              @click="manualAdjustFullscreen = !manualAdjustFullscreen"
            >
              {{
                manualAdjustFullscreen ? t('heat.exitFullscreen') : t('baseline.wizard.fullscreen')
              }}
            </button>
          </div>
        </div>

        <div
          data-testid="manual-adjust-chart"
          :data-series-count="manualAdjustSelectionProbe.seriesCount"
          :data-range-start="manualAdjustSelectionProbe.start ?? ''"
          :data-range-end="manualAdjustSelectionProbe.end ?? ''"
          :data-baseline-filled="manualAdjustSelectionProbe.baselineFilled"
        >
          <v-chart
            ref="manualAdjustChartRef"
            :option="manualAdjustOption"
            autoresize
            class="h-[460px]"
            @datazoom="handleManualAdjustDataZoom"
            @zr:mousedown="handleManualAdjustPointerDown($event)"
            @zr:mousemove="handleManualAdjustPointerMove($event)"
            @zr:click="handleManualAdjustPointerClick($event)"
            @zr:globalout="clearManualAdjustPointerState"
          />
        </div>

        <div class="rounded-xl border border-border-light bg-slate-50 px-5 py-4">
          <el-slider
            v-model="manualAdjustRange"
            range
            :min="manualAdjustContext.min"
            :max="manualAdjustContext.max"
            :step="manualAdjustContext.stepMs"
            :format-tooltip="(value: number) => dayjs(value).format('MM-DD HH:mm:ss')"
          />
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div
            class="space-y-2"
            data-testid="manual-adjust-start-field"
          >
            <div class="text-sm font-medium text-slate-600">
              {{ t('heat.startTime') }}
            </div>
            <el-date-picker
              v-model="manualAdjustStart"
              type="datetime"
              value-format="x"
              format="YYYY-MM-DD HH:mm:ss"
              class="!w-full"
            />
          </div>
          <div
            class="space-y-2"
            data-testid="manual-adjust-end-field"
          >
            <div class="text-sm font-medium text-slate-600">
              {{ t('heat.endTime') }}
            </div>
            <el-date-picker
              v-model="manualAdjustEnd"
              type="datetime"
              value-format="x"
              format="YYYY-MM-DD HH:mm:ss"
              class="!w-full"
            />
          </div>
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
              data-testid="manual-adjust-save"
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
