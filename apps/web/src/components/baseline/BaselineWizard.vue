<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
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
  ElSteps
} from 'element-plus'
import { FullScreen } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts, EChartsOption } from 'echarts'
import dayjs from 'dayjs'
import { useBaselineDefinitionStore } from '@/stores/baselineDefinition'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent, DataZoomComponent])

interface MetricCurvePoint {
  timestamp: number
  values: Record<string, number>
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

const props = withDefaults(defineProps<Props>(), {
  initialSourceHeatId: '',
  initialSelectedStartTime: '',
  initialSelectedEndTime: '',
  initialName: ''
})

const emit = defineEmits<Emits>()
const { t } = useI18n()
const baselineDefinitionStore = useBaselineDefinitionStore()

const activeStep = ref(0)
const selectedHeatId = ref('')
const selectingBoundary = ref<'start' | 'end'>('start')
const fullscreenVisible = ref(false)
const fullCurvePoints = ref<MetricCurvePoint[]>([])
const heatCandidates = ref<HeatCandidate[]>([])
const inlineChartRef = ref<InstanceType<typeof VChart> | null>(null)
const fullscreenChartRef = ref<InstanceType<typeof VChart> | null>(null)
const zoomWindow = ref({ start: 0, end: 100 })

const formData = ref({
  name: '',
  description: '',
  definitionId: '',
  tolerancePercent: 15
})

const selectedStart = ref<number | null>(null)
const selectedEnd = ref<number | null>(null)
const pointerStates: Partial<Record<ChartSurface, PointerState>> = {}
const pointerDragThreshold = 6

const selectedDefinition = computed(() =>
  baselineDefinitionStore.list.find(item => item.id === formData.value.definitionId) || null
)

const selectedHeat = computed(() =>
  heatCandidates.value.find(item => item.id === selectedHeatId.value) || null
)

const selectionProbe = computed(() => ({
  boundary: selectingBoundary.value,
  start: normalizedTimestamp(selectedStart.value),
  end: normalizedTimestamp(selectedEnd.value),
  zoomStart: zoomWindow.value.start,
  zoomEnd: zoomWindow.value.end,
  fullscreen: fullscreenVisible.value ? 'true' : 'false'
}))

function metricSeed(metricId: string) {
  return metricId.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
}

function getMetricBase(unit: string, seed: number) {
  if (unit === 'kW') return 420 + (seed % 20)
  if (unit === 'V') return 382 + (seed % 8)
  if (unit === '°C') return 1455 + (seed % 18)
  if (unit === 'MPa') return Number((0.85 + (seed % 10) * 0.02).toFixed(2))
  return 100 + (seed % 30)
}

function getMetricAmplitude(unit: string, seed: number) {
  if (unit === 'kW') return 28 + (seed % 6)
  if (unit === 'V') return 6 + (seed % 3)
  if (unit === '°C') return 18 + (seed % 5)
  if (unit === 'MPa') return Number((0.08 + (seed % 4) * 0.01).toFixed(2))
  return 12
}

function createCurvePoints() {
  const metrics = selectedDefinition.value?.metrics || []
  const rangeStart = dayjs().subtract(24, 'hour').startOf('hour')
  const totalPoints = 576

  fullCurvePoints.value = Array.from({ length: totalPoints + 1 }).map((_, index) => {
    const timestamp = rangeStart.add(index * 5, 'minute').valueOf()
    const values = metrics.reduce<Record<string, number>>((accumulator, metric) => {
      const seed = metricSeed(metric.id)
      const base = getMetricBase(metric.unit, seed)
      const amplitude = getMetricAmplitude(metric.unit, seed)
      const phase = seed / 17
      const periodic = Math.sin(index / (14 + (seed % 7)) + phase)
      const microFluctuation = Math.cos(index / (11 + (seed % 5)) + phase / 2)
      const rawValue = base + periodic * amplitude + microFluctuation * amplitude * 0.18

      accumulator[metric.id] = Number(rawValue.toFixed(metric.unit === 'MPa' ? 2 : 1))
      return accumulator
    }, {})

    return { timestamp, values }
  })
  zoomWindow.value = { start: 0, end: 100 }

  const candidateSeed = [
    { id: 'heat-101', heatNo: 'H20260312-101', offsetHours: 3, durationMinutes: 38 },
    { id: 'heat-102', heatNo: 'H20260312-102', offsetHours: 16, durationMinutes: 42 },
    { id: 'heat-103', heatNo: 'H20260313-103', offsetHours: 28, durationMinutes: 35 },
    { id: 'heat-104', heatNo: 'H20260313-104', offsetHours: 40, durationMinutes: 31 }
  ]

  heatCandidates.value = candidateSeed.map(item => {
    const start = rangeStart.add(item.offsetHours, 'hour')
    const end = start.add(item.durationMinutes, 'minute')
    return {
      id: item.id,
      heatNo: item.heatNo,
      date: start.format('YYYY-MM-DD HH:mm:ss'),
      startTime: start.valueOf(),
      endTime: end.valueOf()
    }
  })

  if (props.initialSourceHeatId) {
    const exists = heatCandidates.value.some(item => item.id === props.initialSourceHeatId)
    if (!exists) {
      const start = props.initialSelectedStartTime
        ? dayjs(props.initialSelectedStartTime)
        : rangeStart.add(20, 'hour')
      const end = props.initialSelectedEndTime
        ? dayjs(props.initialSelectedEndTime)
        : start.add(35, 'minute')

      heatCandidates.value.unshift({
        id: props.initialSourceHeatId,
        heatNo: props.initialName || `H-PREFILL-${props.initialSourceHeatId}`,
        date: start.format('YYYY-MM-DD HH:mm:ss'),
        startTime: start.valueOf(),
        endTime: end.valueOf()
      })
    }
  }
}

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

function selectNearestPoint(targetTimestamp: number) {
  const point = fullCurvePoints.value.reduce<MetricCurvePoint | null>((closestPoint, currentPoint) => {
    if (!closestPoint) return currentPoint
    return Math.abs(currentPoint.timestamp - targetTimestamp) < Math.abs(closestPoint.timestamp - targetTimestamp)
      ? currentPoint
      : closestPoint
  }, null)

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
  const chartRef = (surface === 'inline'
    ? inlineChartRef.value?.chart
    : fullscreenChartRef.value?.chart) as ExposedChart | undefined
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
    dragging: false
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
    end: latest.end ?? zoomWindow.value.end
  }
}

const chartOption = computed<EChartsOption>(() => {
  const definition = selectedDefinition.value
  if (!definition || fullCurvePoints.value.length === 0) return {}

  const rangeStart = normalizedTimestamp(selectedStart.value)
  const rangeEnd = normalizedTimestamp(selectedEnd.value)

  const metrics = [...definition.metrics].sort((left, right) => left.sortOrder - right.sortOrder)
  const units = Array.from(new Set(metrics.map(metric => metric.unit)))
  const yAxis = units.map((unit, index) => ({
    type: 'value' as const,
    name: unit,
    position: index % 2 === 0 ? 'left' as const : 'right' as const,
    offset: index > 1 ? Math.floor((index - 1) / 2) * 56 : 0,
    axisLabel: { color: '#64748b' },
    nameTextStyle: { color: '#64748b' },
    splitLine: index === 0 ? { lineStyle: { color: '#e2e8f0' } } : { show: false }
  }))

  return {
    animation: false,
    grid: { left: 56, right: 72, top: 48, bottom: 86 },
    tooltip: {
      trigger: 'axis',
      valueFormatter: value => (typeof value === 'number' ? value.toFixed(2).replace(/\.00$/, '') : `${value || ''}`)
    },
    legend: {
      top: 0,
      data: metrics.map(metric => metric.name)
    },
    dataZoom: [
      {
        type: 'inside',
        moveOnMouseMove: true,
        zoomOnMouseWheel: true,
        start: zoomWindow.value.start,
        end: zoomWindow.value.end
      },
      {
        type: 'slider',
        height: 28,
        bottom: 24,
        start: zoomWindow.value.start,
        end: zoomWindow.value.end
      }
    ],
    xAxis: {
      type: 'time',
      axisLabel: {
        color: '#64748b',
        formatter: (value: number) => dayjs(value).format('MM-DD HH:mm')
      }
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
              data: [[{ xAxis: rangeStart }, { xAxis: rangeEnd }]]
            }
          : undefined,
      data: fullCurvePoints.value.map(point => [point.timestamp, point.values[metric.id]])
    }))
  }
})

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
      unit: ''
    }
  }

  const selectedPoints = fullCurvePoints.value
    .filter(point => point.timestamp >= rangeStart && point.timestamp <= rangeEnd)
    .map(point => point.values[primaryMetric.id])
    .filter(value => value !== undefined)

  if (selectedPoints.length === 0) {
    return {
      label: `${primaryMetric.name} (${primaryMetric.unit})`,
      avg: 0,
      peak: 0,
      durationSecond: 0,
      unit: primaryMetric.unit
    }
  }

  const avg = selectedPoints.reduce((sum, value) => sum + value, 0) / selectedPoints.length

  return {
    label: `${primaryMetric.name} (${primaryMetric.unit})`,
    avg: Number(avg.toFixed(primaryMetric.unit === 'MPa' ? 2 : 1)),
    peak: Number(Math.max(...selectedPoints).toFixed(primaryMetric.unit === 'MPa' ? 2 : 1)),
    durationSecond: Math.floor((rangeEnd - rangeStart) / 1000),
    unit: primaryMetric.unit
  }
})

function nextStep() {
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
  if (activeStep.value === 1 && (!selectedStart.value || !selectedEnd.value)) {
    ElMessage.warning(t('baseline.wizard.pointRangeRequired'))
    return
  }

  if (activeStep.value < 2) {
    activeStep.value += 1
  }
}

function prevStep() {
  if (activeStep.value > 0) {
    activeStep.value -= 1
  }
}

function submit(mode: 'draft' | 'publish') {
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
    mode
  })
}

watch(
  () => formData.value.definitionId,
  () => {
    createCurvePoints()
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
  }
)

watch(selectedHeatId, () => {
  if (activeStep.value === 1) {
    resetRangeByHeat()
  }
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

  createCurvePoints()

  if (!selectedHeatId.value && heatCandidates.value[0]) {
    selectedHeatId.value = heatCandidates.value[0].id
  }

  if (props.initialSelectedStartTime && props.initialSelectedEndTime) {
    selectedStart.value = dayjs(props.initialSelectedStartTime).valueOf()
    selectedEnd.value = dayjs(props.initialSelectedEndTime).valueOf()
    normalizeRange()
  } else {
    resetRangeByHeat()
  }
})
</script>

<template>
  <div
    class="space-y-6"
    data-testid="baseline-wizard"
  >
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

    <el-steps
      :active="activeStep + 1"
      finish-status="success"
    >
      <el-step :title="t('baseline.wizard.step1')" />
      <el-step :title="t('baseline.wizard.step2')" />
      <el-step :title="t('baseline.wizard.step3')" />
    </el-steps>

    <div
      v-if="activeStep === 0"
      class="space-y-4"
    >
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
              {{ selectedDefinition.metrics.length }} 条曲线 · {{ selectedDefinition.expectedDurationMinutes }} 分钟
            </span>
          </div>
        </template>

        <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div
            v-for="metric in selectedDefinition.metrics"
            :key="metric.id"
            class="rounded-lg border border-border-light bg-slate-50 p-3"
          >
            <div class="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <span
                class="h-2.5 w-2.5 rounded-full"
                :style="{ backgroundColor: metric.color }"
              />
              {{ metric.name }}
            </div>
            <div class="mt-1 text-xs text-slate-500">
              {{ metric.unit }}
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <div
      v-if="activeStep === 1"
      class="space-y-4"
    >
      <el-card>
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
      </el-card>

      <el-card>
        <template #header>
          <div class="flex items-center justify-between">
            <div>
              <div>{{ t('baseline.wizard.chartPickTitle') }}</div>
              <div class="mt-1 text-xs text-slate-500">
                {{ selectedDefinition?.definitionName || '--' }} · {{ t('baseline.wizard.pickHint') }}
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

        <div
          v-if="selectedDefinition && fullCurvePoints.length > 0"
          class="space-y-4"
        >
          <div data-testid="baseline-wizard-chart">
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
          </div>

          <div class="grid grid-cols-1 gap-4 xl:grid-cols-[220px_1fr]">
            <div
              class="space-y-2"
              data-testid="baseline-wizard-point-range-panel"
            >
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
                  <el-button @click="adjustBoundary('start', -1)">
                    -1s
                  </el-button>
                  <el-button @click="adjustBoundary('start', 1)">
                    +1s
                  </el-button>
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
                  <el-button @click="adjustBoundary('end', -1)">
                    -1s
                  </el-button>
                  <el-button @click="adjustBoundary('end', 1)">
                    +1s
                  </el-button>
                </div>
              </el-form-item>
            </div>
          </div>
        </div>
        <el-empty
          v-else
          :description="t('common.noData')"
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

    <div
      v-if="activeStep === 2"
      class="space-y-4"
    >
      <el-card>
        <div class="space-y-2 text-sm text-gray-700">
          <div><span class="text-gray-500">{{ t('baseline.name') }}:</span> {{ formData.name }}</div>
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
        </div>
      </el-card>

      <div class="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-700">
        {{ t('baseline.wizard.confirmHint') }}
      </div>
    </div>

    <div class="flex items-center justify-between">
      <el-button @click="emit('cancel')">
        {{ t('common.cancel') }}
      </el-button>
      <div class="flex items-center gap-2">
        <el-button
          v-if="activeStep > 0"
          data-testid="baseline-wizard-back"
          @click="prevStep"
        >
          {{ t('common.back') }}
        </el-button>
        <el-button
          v-if="activeStep < 2"
          type="primary"
          data-testid="baseline-wizard-next"
          @click="nextStep"
        >
          {{ t('common.next') }}
        </el-button>
        <template v-else>
          <el-button @click="submit('draft')">
            {{ t('baseline.wizard.saveDraft') }}
          </el-button>
          <el-button
            type="primary"
            data-testid="baseline-wizard-publish"
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
      <div class="flex h-[78vh] flex-col gap-4">
        <div>
          <div class="text-lg font-semibold text-slate-900">
            {{ t('baseline.wizard.chartPickTitle') }}
          </div>
          <div class="mt-1 text-sm text-slate-500">
            {{ selectedDefinition?.definitionName || '--' }} · {{ t('baseline.wizard.pickHint') }}
          </div>
        </div>

        <div class="flex min-h-0 flex-1 flex-col gap-4">
          <div
            class="min-h-0 flex-1"
            data-testid="baseline-wizard-fullscreen-chart"
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

          <div class="grid grid-cols-1 gap-4 xl:grid-cols-[220px_1fr]">
            <div
              class="space-y-2"
              data-testid="baseline-wizard-fullscreen-point-range-panel"
            >
              <div class="text-sm text-gray-500">
                {{ t('baseline.wizard.pointRange') }}
              </div>
              <div class="flex flex-wrap items-center gap-2">
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

            <div class="grid grid-cols-1 gap-4">
              <el-form-item
                :label="t('baseline.wizard.rangeStart')"
                data-testid="baseline-wizard-fullscreen-start-form-item"
              >
                <div class="grid w-full grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto]">
                  <el-date-picker
                    v-model="selectedStart"
                    type="datetime"
                    value-format="x"
                    format="YYYY-MM-DD HH:mm:ss"
                    class="w-full"
                    data-testid="baseline-wizard-fullscreen-range-start"
                  />
                  <el-button @click="adjustBoundary('start', -1)">
                    -1s
                  </el-button>
                  <el-button @click="adjustBoundary('start', 1)">
                    +1s
                  </el-button>
                </div>
              </el-form-item>
              <el-form-item
                :label="t('baseline.wizard.rangeEnd')"
                data-testid="baseline-wizard-fullscreen-end-form-item"
              >
                <div class="grid w-full grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto]">
                  <el-date-picker
                    v-model="selectedEnd"
                    type="datetime"
                    value-format="x"
                    format="YYYY-MM-DD HH:mm:ss"
                    class="w-full"
                    data-testid="baseline-wizard-fullscreen-range-end"
                  />
                  <el-button @click="adjustBoundary('end', -1)">
                    -1s
                  </el-button>
                  <el-button @click="adjustBoundary('end', 1)">
                    +1s
                  </el-button>
                </div>
              </el-form-item>
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
