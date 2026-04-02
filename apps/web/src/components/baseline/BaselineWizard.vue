<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ElButton,
  ElCard,
  ElDatePicker,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElRadio,
  ElSelect,
  ElStep,
  ElSteps,
} from 'element-plus'
import { FullScreen } from '@element-plus/icons-vue'
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
import { useBaselineDefinitionStore } from '@/stores/baselineDefinition'
import { baselineDefinitionApi } from '@/api/baselineDefinition'
import type { BaselinePreviewJobResponse, BaselinePreviewJobStatus } from '@/api/baselineDefinition'
import { heatApi } from '@/api/heat'
import type { HeatRuntimeSnapshotStatus } from '@/api/heat'

use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  DataZoomComponent,
])

interface PreviewMetricCurve {
  metricId: string
  metricName: string
  unit: string
  color: string
  points: Array<{ timestamp: number; value: number }>
}

interface HeatCandidate {
  id: string
  heatNo: string
  date: string
  startTime: number
  endTime: number
}

interface WizardSubmitPayload {
  name: string
  description: string
  definitionId: string
  sourceHeatId: string
  selectedStartTime?: string
  selectedEndTime?: string
  tolerancePercent: number
  mode: 'draft' | 'publish'
}

interface Props {
  initialSourceHeatId?: string
  initialSelectedStartTime?: string
  initialSelectedEndTime?: string
  initialName?: string
  submitting?: boolean
}

interface Emits {
  (e: 'cancel'): void
  (e: 'submit', payload: WizardSubmitPayload): void
}

type ChartSurface = 'inline' | 'fullscreen'

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
type ChartRuntimeSeriesSummary = {
  name: string
  type: string
  pointCount: number
}

const props = withDefaults(defineProps<Props>(), {
  initialSourceHeatId: '',
  initialSelectedStartTime: '',
  initialSelectedEndTime: '',
  initialName: '',
  submitting: false,
})

const emit = defineEmits<Emits>()
const { t } = useI18n()
const baselineDefinitionStore = useBaselineDefinitionStore()

const activeStep = ref(0)
const selectedHeatId = ref('')
const selectingBoundary = ref<'start' | 'end'>('start')
const fullscreenVisible = ref(false)
const previewCurves = ref<PreviewMetricCurve[]>([])
const heatCandidates = ref<HeatCandidate[]>([])
const inlineChartRef = ref<InstanceType<typeof VChart> | null>(null)
const fullscreenChartRef = ref<InstanceType<typeof VChart> | null>(null)
const zoomWindow = ref({ start: 0, end: 100 })
const heatCandidatesError = ref('')
const heatCandidatesEmpty = ref(false)
const heatCandidatesSnapshotStatus = ref<HeatRuntimeSnapshotStatus>('warming')
const previewError = ref('')
const previewLoading = ref(false)
const previewJobStatus = ref<BaselinePreviewJobStatus>('idle')
const previewJobUpdatedAt = ref('')
const heatCandidatesLoading = ref(false)
const stepTwoActivated = ref(false)
const stepTwoBootstrapping = ref(false)
const previewWindowLabel = ref('')
const heatCandidatesDate = ref<Date | null>(dayjs().toDate())
const currentPreviewRequestKey = ref('')
let previewRequestToken = 0
let heatCandidatesRetryTimer: number | null = null
let previewPollTimer: number | null = null

const formData = ref({
  name: '',
  description: '',
  definitionId: '',
  tolerancePercent: 15,
})

const selectedStart = ref<number | null>(null)
const selectedEnd = ref<number | null>(null)
const pointerStates: Partial<Record<ChartSurface, PointerState>> = {}
const pointerDragThreshold = 6

const selectedDefinition = computed(
  () => baselineDefinitionStore.list.find((item) => item.id === formData.value.definitionId) || null
)

const metricBindingSummary = computed(() => {
  const metrics = selectedDefinition.value?.metrics || []
  const bound = metrics.filter((metric) => Boolean(metric.edcChannelId))
  const unbound = metrics.filter((metric) => !metric.edcChannelId)

  return {
    total: metrics.length,
    boundCount: bound.length,
    unboundCount: unbound.length,
    unboundMetrics: unbound,
  }
})

function resolveMetricBindingLabel(edcChannelId: string | null) {
  if (!edcChannelId) return t('baseline.wizard.metricUnbound')
  return t('baseline.wizard.metricBoundTo', { channelId: edcChannelId })
}

const selectedHeat = computed(
  () => heatCandidates.value.find((item) => item.id === selectedHeatId.value) || null
)

const selectionProbe = computed(() => ({
  boundary: selectingBoundary.value,
  start: normalizedTimestamp(selectedStart.value),
  end: normalizedTimestamp(selectedEnd.value),
  zoomStart: zoomWindow.value.start,
  zoomEnd: zoomWindow.value.end,
  fullscreen: fullscreenVisible.value ? 'true' : 'false',
}))

function mapPreviewCurves(
  curves: Array<{
    metric_id: string
    metric_name: string
    unit: string
    color: string
    points: Array<{ timestamp: number; value: number }>
  }>
) {
  return curves.map((curve) => ({
    metricId: curve.metric_id,
    metricName: curve.metric_name,
    unit: curve.unit,
    color: curve.color,
    points: [...curve.points].sort((left, right) => left.timestamp - right.timestamp),
  }))
}

async function loadHeatCandidates() {
  clearHeatCandidatesRetry()
  heatCandidatesError.value = ''
  heatCandidatesEmpty.value = false
  heatCandidatesLoading.value = true
  const previousCandidates = [...heatCandidates.value]
  try {
    const dateValue = heatCandidatesDate.value ? dayjs(heatCandidatesDate.value) : null
    const data = await heatApi.list({
      page: 1,
      page_size: 50,
      start_date: dateValue ? dateValue.startOf('day').toISOString() : undefined,
      end_date: dateValue ? dateValue.endOf('day').toISOString() : undefined,
    })
    heatCandidatesSnapshotStatus.value = data.snapshot_status
    const nextCandidates = data.items.map((item) => ({
      id: item.id,
      heatNo: item.heat_no,
      date: dayjs(item.start_time).format('YYYY-MM-DD HH:mm:ss'),
      startTime: dayjs(item.start_time).valueOf(),
      endTime: dayjs(item.end_time).valueOf(),
    }))
    const shouldKeepPreviousCandidates =
      nextCandidates.length === 0 &&
      data.snapshot_status !== 'ready' &&
      previousCandidates.length > 0
    heatCandidates.value = shouldKeepPreviousCandidates ? previousCandidates : nextCandidates
    if (heatCandidates.value.length === 0 && data.snapshot_status === 'ready') {
      heatCandidatesEmpty.value = true
    }
    if (heatCandidates.value.length === 0 && data.snapshot_status !== 'ready') {
      if (data.snapshot_status === 'warming') {
        await heatApi.refreshRuntime()
      }
      scheduleHeatCandidatesRetry()
    }
  } catch (error) {
    console.error('BaselineWizard heat list request failed.', error)
    if (previousCandidates.length === 0) {
      heatCandidates.value = []
      selectedHeatId.value = ''
      selectedStart.value = null
      selectedEnd.value = null
    }
    heatCandidatesEmpty.value = false
    heatCandidatesSnapshotStatus.value = 'warming'
    heatCandidatesError.value = t('baseline.wizard.heatCandidatesUnavailable')
  } finally {
    heatCandidatesLoading.value = false
  }

  if (props.initialSourceHeatId) {
    const exists = heatCandidates.value.some((item) => item.id === props.initialSourceHeatId)
    if (!exists) {
      const start = props.initialSelectedStartTime
        ? dayjs(props.initialSelectedStartTime)
        : dayjs().subtract(4, 'hour')
      const end = props.initialSelectedEndTime
        ? dayjs(props.initialSelectedEndTime)
        : start.add(35, 'minute')

      heatCandidates.value.unshift({
        id: props.initialSourceHeatId,
        heatNo: props.initialName || `H-PREFILL-${props.initialSourceHeatId}`,
        date: start.format('YYYY-MM-DD HH:mm:ss'),
        startTime: start.valueOf(),
        endTime: end.valueOf(),
      })
    }
  }

  if (
    selectedHeatId.value &&
    !heatCandidates.value.some((item) => item.id === selectedHeatId.value)
  ) {
    const fallbackHeat = heatCandidates.value[0]
    selectedHeatId.value = fallbackHeat?.id || ''
  }
}

async function loadPreviewCurves() {
  if (!stepTwoActivated.value) return
  if (!formData.value.definitionId) return

  const targetHeatId = selectedHeatId.value || heatCandidates.value[0]?.id
  if (!targetHeatId) return

  const selectedHeatItem = heatCandidates.value.find((item) => item.id === targetHeatId)
  const nextPreviewRequestKey = selectedHeatItem
    ? `${formData.value.definitionId}:${dayjs(selectedHeatItem.startTime).format('YYYY-MM-DD')}`
    : `${formData.value.definitionId}:${targetHeatId}`
  const isSamePreviewRequest = currentPreviewRequestKey.value === nextPreviewRequestKey
  currentPreviewRequestKey.value = nextPreviewRequestKey

  if (!isSamePreviewRequest) {
    clearPreviewPoll()
    previewCurves.value = []
    previewError.value = ''
    previewWindowLabel.value = ''
    previewJobUpdatedAt.value = ''
    previewJobStatus.value = 'idle'
  }

  const requestToken = ++previewRequestToken
  try {
    previewLoading.value = true
    const preview = await baselineDefinitionApi.startPreviewJob(
      formData.value.definitionId,
      targetHeatId
    )
    if (requestToken !== previewRequestToken) return
    applyPreviewJobState(preview)
    if (preview.status === 'running') {
      schedulePreviewPoll(targetHeatId)
    } else {
      clearPreviewPoll()
    }
  } catch (error) {
    if (requestToken !== previewRequestToken) return
    console.error('BaselineWizard preview request failed.', error)
    previewJobStatus.value = 'failed'
    previewError.value = t('baseline.wizard.previewUnavailable')
  } finally {
    if (requestToken === previewRequestToken && previewJobStatus.value !== 'running') {
      previewLoading.value = false
    }
  }
}

function clearPreviewPoll() {
  if (previewPollTimer !== null) {
    window.clearTimeout(previewPollTimer)
    previewPollTimer = null
  }
}

function applyPreviewJobState(previewJob: BaselinePreviewJobResponse) {
  previewJobStatus.value = previewJob.status
  previewWindowLabel.value = `${dayjs(previewJob.range_start).format('MM-DD HH:mm:ss')} ~ ${dayjs(
    previewJob.range_end
  ).format('MM-DD HH:mm:ss')}`
  previewJobUpdatedAt.value = previewJob.completed_at
    ? dayjs(previewJob.completed_at).format('YYYY-MM-DD HH:mm:ss')
    : ''

  const mappedCurves = mapPreviewCurves(previewJob.curves_data)
  if (mappedCurves.some((curve) => curve.points.length > 0)) {
    previewCurves.value = mappedCurves
    zoomWindow.value = { start: 0, end: 100 }
  }

  if (previewJob.status === 'failed') {
    previewError.value = previewJob.last_error || t('baseline.wizard.previewUnavailable')
    previewLoading.value = false
    return
  }

  if (previewJob.status === 'succeeded') {
    previewError.value = ''
    previewLoading.value = false
  }
}

function schedulePreviewPoll(heatId: string) {
  clearPreviewPoll()
  previewPollTimer = window.setTimeout(async () => {
    const requestToken = ++previewRequestToken
    try {
      const preview = await baselineDefinitionApi.getPreviewJob(formData.value.definitionId, heatId)
      if (requestToken !== previewRequestToken) return
      applyPreviewJobState(preview)
      if (preview.status === 'running') {
        schedulePreviewPoll(heatId)
      } else {
        clearPreviewPoll()
      }
    } catch (error) {
      if (requestToken !== previewRequestToken) return
      console.error('BaselineWizard preview polling failed.', error)
      previewJobStatus.value = 'failed'
      previewError.value = t('baseline.wizard.previewUnavailable')
      previewLoading.value = false
    }
  }, 3000)
}

async function ensureStepTwoData() {
  stepTwoBootstrapping.value = true
  try {
    if (heatCandidates.value.length === 0 && !heatCandidatesLoading.value) {
      await loadHeatCandidates()
    }

    if (props.initialSourceHeatId) {
      selectedHeatId.value = props.initialSourceHeatId
    } else if (!selectedHeatId.value && heatCandidates.value[0]) {
      selectedHeatId.value = heatCandidates.value[0].id
    }

    if (props.initialSelectedStartTime && props.initialSelectedEndTime) {
      selectedStart.value = dayjs(props.initialSelectedStartTime).valueOf()
      selectedEnd.value = dayjs(props.initialSelectedEndTime).valueOf()
      normalizeRange()
    } else if (!selectedStart.value || !selectedEnd.value) {
      resetRangeByHeat()
    }
  } finally {
    stepTwoBootstrapping.value = false
  }

  await loadPreviewCurves()
}

function clearHeatCandidatesRetry() {
  if (heatCandidatesRetryTimer !== null) {
    window.clearTimeout(heatCandidatesRetryTimer)
    heatCandidatesRetryTimer = null
  }
}

function scheduleHeatCandidatesRetry() {
  clearHeatCandidatesRetry()
  heatCandidatesRetryTimer = window.setTimeout(() => {
    void loadHeatCandidates()
  }, 2500)
}

async function handleRefreshHeatCandidates() {
  await loadHeatCandidates()
  if (!stepTwoActivated.value || stepTwoBootstrapping.value) {
    return
  }
  if (!selectedHeatId.value && heatCandidates.value[0]) {
    selectedHeatId.value = heatCandidates.value[0].id
    return
  }
  if (selectedHeatId.value) {
    await loadPreviewCurves()
  }
}

function handleCandidateDateChange(value: Date | null) {
  heatCandidatesDate.value = value
  selectedHeatId.value = ''
  selectedStart.value = null
  selectedEnd.value = null
  clearPreviewPoll()
  previewCurves.value = []
  previewError.value = ''
  previewJobStatus.value = 'idle'
  previewJobUpdatedAt.value = ''
  previewWindowLabel.value = ''
  currentPreviewRequestKey.value = ''
  heatCandidatesEmpty.value = false
  heatCandidatesSnapshotStatus.value = 'warming'
  void loadHeatCandidates()
}

const heatCandidatesPreparing = computed(
  () =>
    heatCandidatesSnapshotStatus.value === 'warming' ||
    heatCandidatesSnapshotStatus.value === 'refreshing_history'
)
const previewHasCachedData = computed(() =>
  previewCurves.value.some((curve) => curve.points.length > 0)
)
const previewRunning = computed(() => previewJobStatus.value === 'running')
const canProceedPreviewStep = computed(() => hasPreviewData.value && !previewRunning.value)
const nextStepDisabled = computed(
  () => props.submitting || (activeStep.value === 1 && !canProceedPreviewStep.value)
)
const previewStatusHint = computed(() => {
  if (previewRunning.value && previewHasCachedData.value && previewJobUpdatedAt.value) {
    return t('baseline.wizard.previewRefreshingCached', { time: previewJobUpdatedAt.value })
  }
  if (previewRunning.value) {
    return t('baseline.wizard.previewLoadingLong')
  }
  if (previewJobUpdatedAt.value) {
    return t('baseline.wizard.previewLoadedAt', { time: previewJobUpdatedAt.value })
  }
  return ''
})

function normalizedTimestamp(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return null
  const timestamp = Number(value)
  return Number.isFinite(timestamp) ? timestamp : null
}

function normalizeRange() {
  const start = normalizedTimestamp(selectedStart.value)
  const end = normalizedTimestamp(selectedEnd.value)
  if (start === null || end === null) return

  if (start > end) {
    selectedStart.value = end
    selectedEnd.value = start
    return
  }

  selectedStart.value = start
  selectedEnd.value = end
}

function resetRangeByHeat() {
  if (!selectedHeat.value) {
    selectedStart.value = null
    selectedEnd.value = null
    return
  }

  selectedStart.value = selectedHeat.value.startTime
  selectedEnd.value = selectedHeat.value.endTime
}

function handleSelectHeat(id: string) {
  selectedHeatId.value = id
  selectingBoundary.value = 'start'
  resetRangeByHeat()
}

const primaryPreviewCurve = computed(() => {
  const definition = selectedDefinition.value
  const primaryMetric = definition?.metrics[0]
  if (!primaryMetric) return null
  return previewCurves.value.find((curve) => curve.metricId === primaryMetric.id) || null
})

const hasPreviewData = computed(() => previewCurves.value.some((curve) => curve.points.length > 0))

function selectNearestPoint(targetTimestamp: number) {
  const points = primaryPreviewCurve.value?.points || []
  const point = points.reduce<{ timestamp: number; value: number } | null>(
    (closestPoint, currentPoint) => {
      if (!closestPoint) return currentPoint
      return Math.abs(currentPoint.timestamp - targetTimestamp) <
        Math.abs(closestPoint.timestamp - targetTimestamp)
        ? currentPoint
        : closestPoint
    },
    null
  )

  if (!point) return

  if (selectingBoundary.value === 'start') {
    selectedStart.value = point.timestamp
    selectingBoundary.value = 'end'
  } else {
    selectedEnd.value = point.timestamp
    selectingBoundary.value = 'start'
  }

  normalizeRange()
}

function clearPointerState(surface: ChartSurface) {
  delete pointerStates[surface]
}

function resolveChartInstance(surface: ChartSurface) {
  const chartRef = (
    surface === 'inline' ? inlineChartRef.value?.chart : fullscreenChartRef.value?.chart
  ) as ExposedChart | undefined
  if (!chartRef) return null
  if ('containPixel' in chartRef && 'convertFromPixel' in chartRef) {
    return chartRef
  }
  if ('value' in chartRef) {
    return chartRef.value ?? null
  }
  return null
}

function handleChartPointerSelect(surface: ChartSurface, event: PointerEventPayload) {
  const instance = resolveChartInstance(surface)
  if (!instance) return

  const pixel: [number, number] = [event.offsetX, event.offsetY]
  if (!instance.containPixel({ gridIndex: 0 }, pixel)) return

  const converted = instance.convertFromPixel({ gridIndex: 0 }, pixel)
  const timestamp = Number(Array.isArray(converted) ? converted[0] : converted)
  if (!Number.isFinite(timestamp)) return

  selectNearestPoint(timestamp)
}

function handleChartPointerDown(surface: ChartSurface, event: PointerEventPayload) {
  pointerStates[surface] = {
    startX: event.offsetX,
    startY: event.offsetY,
    dragging: false,
  }
}

function handleChartPointerMove(surface: ChartSurface, event: PointerEventPayload) {
  const state = pointerStates[surface]
  if (!state) return

  if (
    Math.abs(event.offsetX - state.startX) > pointerDragThreshold ||
    Math.abs(event.offsetY - state.startY) > pointerDragThreshold
  ) {
    state.dragging = true
  }
}

function handleChartPointerClick(surface: ChartSurface, event: PointerEventPayload) {
  const state = pointerStates[surface]
  clearPointerState(surface)
  if (!state || state.dragging) return
  handleChartPointerSelect(surface, event)
}

function adjustBoundary(boundary: 'start' | 'end', deltaSecond: number) {
  const start = normalizedTimestamp(selectedStart.value)
  const end = normalizedTimestamp(selectedEnd.value)

  if (boundary === 'start' && start !== null) {
    selectedStart.value = start + deltaSecond * 1000
  }
  if (boundary === 'end' && end !== null) {
    selectedEnd.value = end + deltaSecond * 1000
  }
  normalizeRange()
}

function formatDuration(durationSecond: number) {
  const total = Math.max(durationSecond, 0)
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  return `${days}天 ${hours}小时 ${minutes}分钟 ${seconds}秒`
}

function handleChartDataZoom(payload: DataZoomPayload) {
  const latest = payload.batch?.[0] || payload
  zoomWindow.value = {
    start: latest.start ?? zoomWindow.value.start,
    end: latest.end ?? zoomWindow.value.end,
  }
}

function summarizeChartSeries(option: EChartsOption): ChartRuntimeSeriesSummary[] {
  const rawSeries = option.series
  const seriesList = Array.isArray(rawSeries) ? rawSeries : rawSeries ? [rawSeries] : []

  return seriesList.map((series) => {
    const candidate = series as { name?: string; type?: string; data?: unknown[] }
    return {
      name: String(candidate.name || ''),
      type: String(candidate.type || ''),
      pointCount: Array.isArray(candidate.data) ? candidate.data.length : 0,
    }
  })
}

const chartOption = computed<EChartsOption>(() => {
  const definition = selectedDefinition.value
  if (!definition || !hasPreviewData.value) return {}

  const rangeStart = normalizedTimestamp(selectedStart.value)
  const rangeEnd = normalizedTimestamp(selectedEnd.value)

  const metrics = [...definition.metrics].sort((left, right) => left.sortOrder - right.sortOrder)
  const units = Array.from(new Set(metrics.map((metric) => metric.unit)))
  const yAxis = units.map((unit, index) => ({
    type: 'value' as const,
    name: unit,
    position: index % 2 === 0 ? ('left' as const) : ('right' as const),
    offset: index > 1 ? Math.floor((index - 1) / 2) * 56 : 0,
    axisLabel: { color: '#64748b' },
    nameTextStyle: { color: '#64748b' },
    splitLine: index === 0 ? { lineStyle: { color: '#e2e8f0' } } : { show: false },
  }))

  return {
    animation: false,
    grid: { left: 56, right: 72, top: 48, bottom: 86 },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) =>
        typeof value === 'number' ? value.toFixed(2).replace(/\.00$/, '') : `${value || ''}`,
    },
    legend: {
      top: 0,
      data: metrics.map((metric) => metric.name),
    },
    dataZoom: [
      {
        type: 'inside',
        moveOnMouseMove: true,
        zoomOnMouseWheel: true,
        start: zoomWindow.value.start,
        end: zoomWindow.value.end,
      },
      {
        type: 'slider',
        height: 28,
        bottom: 24,
        start: zoomWindow.value.start,
        end: zoomWindow.value.end,
      },
    ],
    xAxis: {
      type: 'time',
      minInterval: 60 * 1000,
      axisLabel: {
        color: '#64748b',
        formatter: (value: number) => dayjs(value).format('MM-DD HH:mm'),
      },
    },
    yAxis,
    series: metrics.map((metric, index) => ({
      name: metric.name,
      type: 'line' as const,
      smooth: true,
      showSymbol: false,
      yAxisIndex: units.indexOf(metric.unit),
      lineStyle: { width: index === 0 ? 2.5 : 2, color: metric.color },
      itemStyle: { color: metric.color },
      markArea:
        index === 0 && rangeStart !== null && rangeEnd !== null
          ? {
              itemStyle: { color: 'rgba(17, 82, 212, 0.12)' },
              data: [[{ xAxis: rangeStart }, { xAxis: rangeEnd }]],
            }
          : undefined,
      data:
        previewCurves.value
          .find((curve) => curve.metricId === metric.id)
          ?.points.map((point) => [point.timestamp, point.value]) || [],
    })),
  }
})

const chartRuntimeSeriesSummary = computed(() =>
  JSON.stringify(summarizeChartSeries(chartOption.value))
)

const summaryStats = computed(() => {
  const definition = selectedDefinition.value
  const primaryMetric = definition?.metrics[0]
  const rangeStart = normalizedTimestamp(selectedStart.value)
  const rangeEnd = normalizedTimestamp(selectedEnd.value)

  if (!primaryMetric || rangeStart === null || rangeEnd === null) {
    return {
      label: '--',
      avg: 0,
      peak: 0,
      durationSecond: 0,
      unit: '',
    }
  }

  const selectedPoints =
    primaryPreviewCurve.value?.points
      .filter((point) => point.timestamp >= rangeStart && point.timestamp <= rangeEnd)
      .map((point) => point.value) || []

  if (selectedPoints.length === 0) {
    return {
      label: `${primaryMetric.name} (${primaryMetric.unit})`,
      avg: 0,
      peak: 0,
      durationSecond: 0,
      unit: primaryMetric.unit,
    }
  }

  const avg = selectedPoints.reduce((sum, value) => sum + value, 0) / selectedPoints.length

  return {
    label: `${primaryMetric.name} (${primaryMetric.unit})`,
    avg: Number(avg.toFixed(primaryMetric.unit === 'MPa' ? 2 : 1)),
    peak: Number(Math.max(...selectedPoints).toFixed(primaryMetric.unit === 'MPa' ? 2 : 1)),
    durationSecond: Math.floor((rangeEnd - rangeStart) / 1000),
    unit: primaryMetric.unit,
  }
})

const previewHeatSummary = computed(() => {
  if (!selectedHeat.value) return '--'
  return `${selectedHeat.value.heatNo} · ${dayjs(selectedHeat.value.startTime).format(
    'MM-DD HH:mm:ss'
  )} ~ ${dayjs(selectedHeat.value.endTime).format('MM-DD HH:mm:ss')}`
})

async function nextStep() {
  if (props.submitting) {
    return
  }
  if (activeStep.value === 0 && !formData.value.name.trim()) {
    ElMessage.warning(t('baseline.wizard.nameRequired'))
    return
  }
  if (activeStep.value === 0 && !formData.value.definitionId) {
    ElMessage.warning(t('baseline.wizard.definitionRequired'))
    return
  }
  if (activeStep.value === 1 && !selectedHeatId.value) {
    ElMessage.warning(t('baseline.wizard.selectHeatRequired'))
    return
  }
  if (activeStep.value === 1 && previewRunning.value) {
    ElMessage.warning(t('baseline.wizard.previewLoadingLong'))
    return
  }
  if (activeStep.value === 1 && !hasPreviewData.value) {
    ElMessage.warning(previewError.value || t('baseline.wizard.previewUnavailable'))
    return
  }
  if (activeStep.value === 1 && (!selectedStart.value || !selectedEnd.value)) {
    ElMessage.warning(t('baseline.wizard.pointRangeRequired'))
    return
  }

  if (activeStep.value === 0) {
    stepTwoActivated.value = true
    activeStep.value = 1
    await ensureStepTwoData()
    return
  }

  if (activeStep.value < 2) {
    activeStep.value += 1
  }
}

function prevStep() {
  if (props.submitting) {
    return
  }
  if (activeStep.value > 0) {
    activeStep.value -= 1
  }
}

function submit(mode: 'draft' | 'publish') {
  if (props.submitting) {
    return
  }
  if (!selectedHeatId.value || !formData.value.name.trim() || !formData.value.definitionId) {
    ElMessage.warning(t('baseline.wizard.incompleteForm'))
    return
  }

  const rangeStart = normalizedTimestamp(selectedStart.value)
  const rangeEnd = normalizedTimestamp(selectedEnd.value)

  emit('submit', {
    name: formData.value.name.trim(),
    description: formData.value.description.trim(),
    definitionId: formData.value.definitionId,
    sourceHeatId: selectedHeatId.value,
    selectedStartTime: rangeStart !== null ? dayjs(rangeStart).toISOString() : undefined,
    selectedEndTime: rangeEnd !== null ? dayjs(rangeEnd).toISOString() : undefined,
    tolerancePercent: formData.value.tolerancePercent,
    mode,
  })
}

watch(
  () => formData.value.definitionId,
  async () => {
    if (!stepTwoActivated.value || stepTwoBootstrapping.value) {
      return
    }
    if (!selectedHeatId.value && heatCandidates.value[0]) {
      selectedHeatId.value = heatCandidates.value[0].id
    }
    if (props.initialSelectedStartTime && props.initialSelectedEndTime) {
      selectedStart.value = dayjs(props.initialSelectedStartTime).valueOf()
      selectedEnd.value = dayjs(props.initialSelectedEndTime).valueOf()
      normalizeRange()
    } else if (!selectedStart.value || !selectedEnd.value) {
      resetRangeByHeat()
    }
    await loadPreviewCurves()
  }
)

watch(selectedHeatId, async () => {
  if (!stepTwoActivated.value || stepTwoBootstrapping.value) {
    return
  }
  if (activeStep.value === 1 || !selectedStart.value || !selectedEnd.value) {
    resetRangeByHeat()
  }
  await loadPreviewCurves()
})

onMounted(async () => {
  await baselineDefinitionStore.fetchList('active')

  const firstDefinition = baselineDefinitionStore.list[0]
  if (!formData.value.definitionId && firstDefinition) {
    formData.value.definitionId = firstDefinition.id
  }

  formData.value.name = props.initialName || ''

  if (props.initialSourceHeatId) {
    selectedHeatId.value = props.initialSourceHeatId
  }
})

onBeforeUnmount(() => {
  clearHeatCandidatesRetry()
  clearPreviewPoll()
})
</script>

<template>
  <div class="space-y-6" data-testid="baseline-wizard">
    <div
      class="sr-only"
      data-testid="baseline-wizard-selection-state"
      :data-boundary="selectionProbe.boundary"
      :data-start="selectionProbe.start ?? ''"
      :data-end="selectionProbe.end ?? ''"
      :data-zoom-start="selectionProbe.zoomStart"
      :data-zoom-end="selectionProbe.zoomEnd"
      :data-fullscreen="selectionProbe.fullscreen"
    />

    <el-steps :active="activeStep + 1" finish-status="success">
      <el-step :title="t('baseline.wizard.step1')" />
      <el-step :title="t('baseline.wizard.step2')" />
      <el-step :title="t('baseline.wizard.step3')" />
    </el-steps>

    <div v-if="activeStep === 0" class="space-y-4">
      <el-card>
        <el-form label-position="top">
          <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <el-form-item :label="t('baseline.name')">
              <el-input
                v-model="formData.name"
                :placeholder="t('baseline.wizard.namePlaceholder')"
                data-testid="baseline-wizard-name-input"
              />
            </el-form-item>
            <el-form-item :label="t('baseline.wizard.definition')">
              <el-select
                v-model="formData.definitionId"
                class="w-full"
                :placeholder="t('baseline.wizard.definitionPlaceholder')"
                data-testid="baseline-wizard-definition-select"
              >
                <el-option
                  v-for="item in baselineDefinitionStore.list"
                  :key="item.id"
                  :label="item.definitionName"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </div>

          <div class="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_220px]">
            <el-form-item :label="t('baseline.wizard.description')">
              <el-input
                v-model="formData.description"
                type="textarea"
                :rows="4"
                :placeholder="t('baseline.wizard.descriptionPlaceholder')"
              />
            </el-form-item>
            <el-form-item :label="t('baseline.tolerance')">
              <el-input-number
                v-model="formData.tolerancePercent"
                class="w-full"
                :min="0"
                :max="100"
                :step="0.5"
              />
            </el-form-item>
          </div>
        </el-form>
      </el-card>

      <el-card v-if="selectedDefinition">
        <template #header>
          <div class="flex items-center justify-between">
            <span>{{ selectedDefinition.definitionName }}</span>
            <span class="text-xs text-slate-500">
              {{ selectedDefinition.metrics.length }} 条曲线 ·
              {{ selectedDefinition.expectedDurationMinutes }} 分钟
            </span>
          </div>
        </template>

        <div
          v-if="metricBindingSummary.unboundCount > 0"
          data-testid="baseline-wizard-binding-warning"
          class="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700"
        >
          {{ t('baseline.wizard.bindingWarning', { count: metricBindingSummary.unboundCount }) }}
          <span class="ml-1 text-amber-800">
            {{ metricBindingSummary.unboundMetrics.map((metric) => metric.name).join(' / ') }}
          </span>
        </div>

        <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div
            v-for="metric in selectedDefinition.metrics"
            :key="metric.id"
            class="rounded-lg border border-border-light bg-slate-50 p-3"
          >
            <div class="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <span class="h-2.5 w-2.5 rounded-full" :style="{ backgroundColor: metric.color }" />
              {{ metric.name }}
            </div>
            <div class="mt-1 text-xs text-slate-500">
              {{ metric.unit }}
            </div>
            <div class="mt-2 text-xs">
              <span
                class="inline-flex rounded-full px-2 py-0.5 font-medium"
                :class="
                  metric.edcChannelId
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-amber-100 text-amber-700'
                "
              >
                {{
                  metric.edcChannelId
                    ? t('baseline.wizard.metricBound')
                    : t('baseline.wizard.metricUnboundShort')
                }}
              </span>
              <div class="mt-2 text-xs text-slate-500">
                {{ resolveMetricBindingLabel(metric.edcChannelId) }}
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <div v-if="activeStep === 1" class="space-y-4">
      <el-card>
        <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div class="space-y-1">
            <div class="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              {{ t('baseline.wizard.heatCandidatesDate') }}
            </div>
            <el-date-picker
              v-model="heatCandidatesDate"
              type="date"
              format="YYYY-MM-DD"
              class="!w-[220px]"
              @update:model-value="handleCandidateDateChange"
            />
          </div>
          <el-button
            :loading="heatCandidatesLoading"
            :disabled="previewRunning"
            data-testid="baseline-wizard-refresh-candidates"
            @click="handleRefreshHeatCandidates"
          >
            {{ t('baseline.wizard.refreshHeatCandidates') }}
          </el-button>
        </div>
        <div
          class="max-h-[520px] overflow-y-auto pr-2 md:max-h-[360px]"
          data-testid="baseline-wizard-heat-candidate-list"
        >
          <div
            v-if="heatCandidatesPreparing && !heatCandidatesLoading && heatCandidates.length === 0"
            class="mb-3 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-700"
          >
            {{ t('baseline.wizard.heatCandidatesPreparing') }}
          </div>
          <div
            v-if="heatCandidatesLoading"
            class="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600"
          >
            {{ t('baseline.wizard.previewLoading') }}
          </div>
          <div
            v-if="heatCandidatesError"
            class="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {{ heatCandidatesError }}
          </div>
          <el-empty
            v-if="!heatCandidatesLoading && heatCandidates.length === 0 && heatCandidatesEmpty"
            :description="t('baseline.wizard.heatCandidatesEmpty')"
          />
          <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label
              v-for="item in heatCandidates"
              :key="item.id"
              class="cursor-pointer rounded-lg border p-4 transition hover:border-primary"
              :class="selectedHeatId === item.id ? 'border-primary bg-blue-50' : 'border-gray-200'"
            >
              <el-radio
                :model-value="selectedHeatId"
                :value="item.id"
                @change="handleSelectHeat(item.id)"
              >
                {{ item.heatNo }}
              </el-radio>
              <div class="mt-2 text-xs text-gray-500">{{ item.date }}</div>
              <div class="mt-1 text-xs text-slate-400">
                {{ dayjs(item.startTime).format('MM-DD HH:mm:ss') }} ~
                {{ dayjs(item.endTime).format('MM-DD HH:mm:ss') }}
              </div>
            </label>
          </div>
        </div>
      </el-card>

      <el-card>
        <template #header>
          <div class="flex items-center justify-between">
            <div>
              <div>{{ t('baseline.wizard.chartPickTitle') }}</div>
              <div class="mt-1 text-xs text-slate-500">
                {{ selectedDefinition?.definitionName || '--' }} ·
                {{ t('baseline.wizard.pickHint') }}
              </div>
              <div class="mt-1 text-xs text-slate-400">
                {{ t('baseline.wizard.previewHeatWindow', { heat: previewHeatSummary }) }}
              </div>
              <div v-if="previewWindowLabel" class="mt-1 text-xs text-slate-400">
                {{ t('baseline.wizard.previewDayWindow', { range: previewWindowLabel }) }}
              </div>
              <div
                v-if="previewStatusHint"
                class="mt-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-700"
              >
                {{ previewStatusHint }}
              </div>
            </div>
            <el-button
              :icon="FullScreen"
              data-testid="baseline-wizard-fullscreen-button"
              @click="fullscreenVisible = true"
            >
              {{ t('baseline.wizard.fullscreen') }}
            </el-button>
          </div>
        </template>

        <div v-if="selectedDefinition && hasPreviewData" class="space-y-4">
          <div
            class="relative"
            data-testid="baseline-wizard-chart"
            :data-runtime-series-summary="chartRuntimeSeriesSummary"
            :data-definition-id="formData.definitionId"
            :data-heat-id="selectedHeatId"
          >
            <v-chart
              ref="inlineChartRef"
              :option="chartOption"
              autoresize
              class="h-[420px]"
              @datazoom="handleChartDataZoom"
              @zr:mousedown="handleChartPointerDown('inline', $event)"
              @zr:mousemove="handleChartPointerMove('inline', $event)"
              @zr:click="handleChartPointerClick('inline', $event)"
              @zr:globalout="clearPointerState('inline')"
            />
            <div
              v-if="previewLoading"
              class="absolute inset-0 flex items-center justify-center rounded-lg bg-white/70 text-sm font-medium text-slate-600 backdrop-blur-[1px]"
            >
              {{ t('baseline.wizard.previewLoading') }}
            </div>
          </div>

          <div class="grid grid-cols-1 gap-4 xl:grid-cols-[220px_1fr]">
            <div class="space-y-2" data-testid="baseline-wizard-point-range-panel">
              <div class="text-sm text-gray-500">
                {{ t('baseline.wizard.pointRange') }}
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <el-button
                  :type="selectingBoundary === 'start' ? 'primary' : 'default'"
                  data-testid="baseline-wizard-pick-start"
                  @click="selectingBoundary = 'start'"
                >
                  {{ t('baseline.wizard.pickStart') }}
                </el-button>
                <el-button
                  :type="selectingBoundary === 'end' ? 'primary' : 'default'"
                  data-testid="baseline-wizard-pick-end"
                  @click="selectingBoundary = 'end'"
                >
                  {{ t('baseline.wizard.pickEnd') }}
                </el-button>
              </div>
            </div>

            <div class="grid grid-cols-1 gap-4">
              <el-form-item
                :label="t('baseline.wizard.rangeStart')"
                data-testid="baseline-wizard-start-form-item"
              >
                <div class="grid w-full grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto]">
                  <el-date-picker
                    v-model="selectedStart"
                    type="datetime"
                    value-format="x"
                    format="YYYY-MM-DD HH:mm:ss"
                    class="w-full"
                    data-testid="baseline-wizard-range-start"
                  />
                  <el-button @click="adjustBoundary('start', -1)"> -1s </el-button>
                  <el-button @click="adjustBoundary('start', 1)"> +1s </el-button>
                </div>
              </el-form-item>
              <el-form-item
                :label="t('baseline.wizard.rangeEnd')"
                data-testid="baseline-wizard-end-form-item"
              >
                <div class="grid w-full grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto]">
                  <el-date-picker
                    v-model="selectedEnd"
                    type="datetime"
                    value-format="x"
                    format="YYYY-MM-DD HH:mm:ss"
                    class="w-full"
                    data-testid="baseline-wizard-range-end"
                  />
                  <el-button @click="adjustBoundary('end', -1)"> -1s </el-button>
                  <el-button @click="adjustBoundary('end', 1)"> +1s </el-button>
                </div>
              </el-form-item>
            </div>
          </div>
        </div>
        <div
          v-else-if="previewLoading"
          class="flex h-[420px] items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500"
          data-testid="baseline-wizard-preview-loading"
        >
          {{ t('baseline.wizard.previewLoading') }}
        </div>
        <el-empty
          v-else
          data-testid="baseline-wizard-preview-empty"
          :description="previewError || t('common.noData')"
        />
      </el-card>

      <el-card>
        <div class="grid grid-cols-1 gap-4 text-sm md:grid-cols-3">
          <div class="rounded-lg bg-gray-50 p-3">
            <div class="text-gray-500">
              {{ summaryStats.label }}
            </div>
            <div class="mt-1 text-lg font-semibold">
              {{ summaryStats.avg }}
            </div>
          </div>
          <div class="rounded-lg bg-gray-50 p-3">
            <div class="text-gray-500">
              {{ t('baseline.wizard.peakPower') }}
            </div>
            <div class="mt-1 text-lg font-semibold">
              {{ summaryStats.peak }}{{ summaryStats.unit ? ` ${summaryStats.unit}` : '' }}
            </div>
          </div>
          <div class="rounded-lg bg-gray-50 p-3">
            <div class="text-gray-500">
              {{ t('baseline.wizard.selectedDuration') }}
            </div>
            <div class="mt-1 text-lg font-semibold">
              {{ formatDuration(summaryStats.durationSecond) }}
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <div v-if="activeStep === 2" class="space-y-4">
      <el-card>
        <div class="space-y-2 text-sm text-gray-700">
          <div>
            <span class="text-gray-500">{{ t('baseline.name') }}:</span> {{ formData.name }}
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.wizard.definition') }}:</span>
            {{ selectedDefinition?.definitionName || '--' }}
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.selectHeat') }}:</span>
            {{ selectedHeat?.heatNo || '--' }}
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.wizard.pointRange') }}:</span>
            {{ selectedStart ? dayjs(selectedStart).format('YYYY-MM-DD HH:mm:ss') : '--' }}
            ~
            {{ selectedEnd ? dayjs(selectedEnd).format('YYYY-MM-DD HH:mm:ss') : '--' }}
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.tolerance') }}:</span>
            {{ formData.tolerancePercent }}%
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.wizard.description') }}:</span>
            {{ formData.description || t('common.noDescription') }}
          </div>
          <div>
            <span class="text-gray-500">{{ t('baseline.wizard.bindingStatus') }}:</span>
            {{ metricBindingSummary.boundCount }}/{{ metricBindingSummary.total }}
            {{ t('baseline.wizard.metricBound') }}
          </div>
        </div>
      </el-card>

      <div class="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-700">
        {{ t('baseline.wizard.confirmHint') }}
      </div>
      <div
        v-if="metricBindingSummary.unboundCount > 0"
        class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700"
      >
        {{ t('baseline.wizard.confirmUnboundHint', { count: metricBindingSummary.unboundCount }) }}
      </div>
    </div>

    <div class="flex items-center justify-between">
      <el-button
        data-testid="baseline-wizard-secondary-action"
        :disabled="props.submitting"
        @click="activeStep === 0 ? emit('cancel') : prevStep()"
      >
        {{ activeStep === 0 ? t('common.cancel') : t('common.previousPage') }}
      </el-button>
      <div class="flex items-center gap-2">
        <el-button
          v-if="activeStep < 2"
          type="primary"
          data-testid="baseline-wizard-next"
          :disabled="nextStepDisabled"
          @click="nextStep"
        >
          {{ t('common.next') }}
        </el-button>
        <template v-else>
          <el-button
            :disabled="props.submitting"
            :loading="props.submitting"
            @click="submit('draft')"
          >
            {{ t('baseline.wizard.saveDraft') }}
          </el-button>
          <el-button
            type="primary"
            data-testid="baseline-wizard-publish"
            :disabled="props.submitting"
            :loading="props.submitting"
            @click="submit('publish')"
          >
            {{ t('baseline.publish') }}
          </el-button>
        </template>
      </div>
    </div>

    <el-dialog
      v-model="fullscreenVisible"
      :title="t('baseline.wizard.fullscreenTitle')"
      fullscreen
      data-testid="baseline-wizard-fullscreen-dialog"
    >
      <div class="flex h-[80vh] flex-col gap-6">
        <div class="min-h-0 flex-[1_1_0%]">
          <div
            class="h-full"
            data-testid="baseline-wizard-fullscreen-chart"
            :data-runtime-series-summary="chartRuntimeSeriesSummary"
            :data-definition-id="formData.definitionId"
            :data-heat-id="selectedHeatId"
          >
            <v-chart
              ref="fullscreenChartRef"
              :option="chartOption"
              autoresize
              class="h-full"
              @datazoom="handleChartDataZoom"
              @zr:mousedown="handleChartPointerDown('fullscreen', $event)"
              @zr:mousemove="handleChartPointerMove('fullscreen', $event)"
              @zr:click="handleChartPointerClick('fullscreen', $event)"
              @zr:globalout="clearPointerState('fullscreen')"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div
            class="space-y-4 rounded-2xl bg-slate-50 p-5"
            data-testid="baseline-wizard-fullscreen-point-range-panel"
          >
            <div>
              <div class="text-sm font-medium text-slate-600">
                {{ t('baseline.wizard.pointRange') }}
              </div>
              <p class="mt-2 text-sm text-slate-500">
                {{ t('baseline.wizard.pickHint') }}
              </p>
            </div>

            <div class="flex flex-wrap items-center gap-3">
              <el-button
                :type="selectingBoundary === 'start' ? 'primary' : 'default'"
                data-testid="baseline-wizard-fullscreen-pick-start"
                @click="selectingBoundary = 'start'"
              >
                {{ t('baseline.wizard.pickStart') }}
              </el-button>
              <el-button
                :type="selectingBoundary === 'end' ? 'primary' : 'default'"
                data-testid="baseline-wizard-fullscreen-pick-end"
                @click="selectingBoundary = 'end'"
              >
                {{ t('baseline.wizard.pickEnd') }}
              </el-button>
            </div>
          </div>

          <div class="space-y-4 rounded-2xl bg-slate-50 p-5">
            <div
              class="grid grid-cols-1 items-center gap-3 xl:grid-cols-[96px_minmax(0,1fr)_auto_auto]"
              data-testid="baseline-wizard-fullscreen-start-form-item"
            >
              <div class="text-sm font-medium text-slate-600">
                {{ t('baseline.wizard.rangeStart') }}
              </div>
              <el-date-picker
                v-model="selectedStart"
                type="datetime"
                value-format="x"
                format="YYYY-MM-DD HH:mm:ss"
                class="w-full"
                data-testid="baseline-wizard-fullscreen-range-start"
              />
              <el-button @click="adjustBoundary('start', -1)"> -1s </el-button>
              <el-button @click="adjustBoundary('start', 1)"> +1s </el-button>
            </div>

            <div
              class="grid grid-cols-1 items-center gap-3 xl:grid-cols-[96px_minmax(0,1fr)_auto_auto]"
              data-testid="baseline-wizard-fullscreen-end-form-item"
            >
              <div class="text-sm font-medium text-slate-600">
                {{ t('baseline.wizard.rangeEnd') }}
              </div>
              <el-date-picker
                v-model="selectedEnd"
                type="datetime"
                value-format="x"
                format="YYYY-MM-DD HH:mm:ss"
                class="w-full"
                data-testid="baseline-wizard-fullscreen-range-end"
              />
              <el-button @click="adjustBoundary('end', -1)"> -1s </el-button>
              <el-button @click="adjustBoundary('end', 1)"> +1s </el-button>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div class="rounded-2xl bg-slate-50 p-5">
            <div class="text-sm text-slate-500">
              {{ summaryStats.label }}
            </div>
            <div class="mt-3 text-3xl font-semibold text-slate-900">
              {{ summaryStats.avg }}
            </div>
          </div>
          <div class="rounded-2xl bg-slate-50 p-5">
            <div class="text-sm text-slate-500">
              {{ t('baseline.wizard.peakPower') }}
            </div>
            <div class="mt-3 text-3xl font-semibold text-slate-900">
              {{ summaryStats.peak }}{{ summaryStats.unit ? ` ${summaryStats.unit}` : '' }}
            </div>
          </div>
          <div class="rounded-2xl bg-slate-50 p-5">
            <div class="text-sm text-slate-500">
              {{ t('baseline.wizard.selectedDuration') }}
            </div>
            <div class="mt-3 text-3xl font-semibold text-slate-900">
              {{ formatDuration(summaryStats.durationSecond) }}
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="fullscreenVisible = false">
          {{ t('common.confirm') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
