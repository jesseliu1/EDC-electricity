<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElButton, ElTabPane, ElTabs } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import type { BaselineCompareItem, DeviationRange, MetricCompareSeries } from '@/api/heat'
import { formatTimestamp } from '@/utils/time'

use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  DataZoomComponent,
])

type TimeWindow = {
  start: number
  end: number
}

type ChartRuntimeSeriesSummary = {
  name: string
  type: string
  pointCount: number
}

interface Props {
  heatId: string
  baselineComparisons: BaselineCompareItem[]
  activeBaselineId: string
  heatCoreWindow: TimeWindow | null
  compareContextWindow: TimeWindow | null
  fallbackDeviationRanges: DeviationRange[]
  surface?: 'inline' | 'fullscreen'
  showFullscreenButton?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  surface: 'inline',
  showFullscreenButton: false,
})

const emit = defineEmits<{
  (e: 'update:activeBaselineId', value: string): void
  (e: 'openFullscreen'): void
}>()

const { t } = useI18n()

const isFullscreen = computed(() => props.surface === 'fullscreen')

const selectedComparison = computed(() => {
  if (props.baselineComparisons.length === 0) return null
  return (
    props.baselineComparisons.find((item) => item.baseline.id === props.activeBaselineId) ||
    props.baselineComparisons[0]
  )
})

const primaryComparisonMetric = computed<MetricCompareSeries | null>(() => {
  const metricCurves = selectedComparison.value?.metric_curves || []
  if (metricCurves.length === 0) return null
  return metricCurves.find((item) => item.metric_key === 'power') || metricCurves[0] || null
})

const compareMetricCurves = computed(() => {
  if (!selectedComparison.value) return [] as MetricCompareSeries[]
  const metricCurves = selectedComparison.value.metric_curves || []
  if (metricCurves.length > 0) return metricCurves
  return primaryComparisonMetric.value ? [primaryComparisonMetric.value] : []
})

const compareSeriesCount = computed(() => compareMetricCurves.value.length * 2)

const compareChartKey = computed(
  () =>
    `${props.heatId}-${props.surface}-${selectedComparison.value?.baseline.id || 'default'}`
)

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

function normalizeHexColor(color: string) {
  const value = color.trim()
  if (/^#[0-9a-fA-F]{6}$/.test(value)) return value
  if (/^#[0-9a-fA-F]{3}$/.test(value)) {
    const [, r, g, b] = value
    return `#${r}${r}${g}${g}${b}${b}`
  }
  return '#409EFF'
}

function mixHexColor(color: string, target: string, ratio: number) {
  const source = normalizeHexColor(color)
  const destination = normalizeHexColor(target)
  const weight = Math.min(Math.max(ratio, 0), 1)
  const channels = [0, 2, 4].map((offset) => {
    const from = Number.parseInt(source.slice(offset + 1, offset + 3), 16)
    const to = Number.parseInt(destination.slice(offset + 1, offset + 3), 16)
    return Math.round(from + (to - from) * weight)
      .toString(16)
      .padStart(2, '0')
  })
  return `#${channels.join('')}`
}

function areCurvesFullyOverlapped(
  baselineCurve: Array<{ timestamp: number; value: number }>,
  currentCurve: Array<{ timestamp: number; value: number }>
) {
  if (baselineCurve.length === 0 || currentCurve.length === 0) return false
  if (baselineCurve.length !== currentCurve.length) return false

  return baselineCurve.every((point, index) => {
    const currentPoint = currentCurve[index]
    if (!currentPoint) return false
    return (
      point.timestamp === currentPoint.timestamp &&
      Math.abs(point.value - currentPoint.value) < 0.0001
    )
  })
}

function clipCurveToWindow(
  curve: Array<{ timestamp: number; value: number }>,
  start: number,
  end: number
) {
  return curve.filter((point) => point.timestamp >= start && point.timestamp <= end)
}

const selectedComparisonOverlap = computed(() => {
  if (!selectedComparison.value || !primaryComparisonMetric.value) return null
  const clippedCurrentCurve = props.heatCoreWindow
    ? clipCurveToWindow(
        primaryComparisonMetric.value.current_curve,
        props.heatCoreWindow.start,
        props.heatCoreWindow.end
      )
    : primaryComparisonMetric.value.current_curve
  if (
    !areCurvesFullyOverlapped(primaryComparisonMetric.value.baseline_curve, clippedCurrentCurve)
  ) {
    return null
  }

  return {
    metricName: primaryComparisonMetric.value.metric_name,
    baselineName: selectedComparison.value.baseline.name,
  }
})

const selectedComparisonMissingCurrentMetrics = computed(() =>
  (selectedComparison.value?.metric_curves || [])
    .filter((metric) => metric.current_curve.length === 0)
    .map((metric) => metric.metric_name)
)

const compareOption = computed<EChartsOption>(() => {
  const metricCurves = compareMetricCurves.value
  if (metricCurves.length === 0) return {}

  const units = Array.from(new Set(metricCurves.map((item) => item.unit)))
  const firstCurrentCurve = metricCurves[0]?.current_curve || []
  const deviationRanges = selectedComparison.value?.deviation_ranges || props.fallbackDeviationRanges
  const grid = isFullscreen.value
    ? { left: 72, right: 96, top: 64, bottom: 52 }
    : { left: 56, right: 72, top: 40, bottom: 32 }
  const axisFontSize = isFullscreen.value ? 14 : 12
  const legendFontSize = isFullscreen.value ? 14 : 12
  const unitFontSize = isFullscreen.value ? 13 : 12

  return {
    animation: false,
    grid,
    tooltip: { trigger: 'axis' },
    legend: {
      data: metricCurves.flatMap((item) => [
        `${item.metric_name}-${t('dashboard.chart.goldenBaseline')}`,
        `${item.metric_name}-${t('dashboard.chart.currentProduction')}`,
      ]),
      top: 0,
      textStyle: {
        fontSize: legendFontSize,
      },
    },
    xAxis: {
      type: 'time',
      min: props.compareContextWindow?.start,
      max: props.compareContextWindow?.end,
      axisLabel: {
        fontSize: axisFontSize,
        formatter: (value: number) => formatTimestamp(value, 'HH:mm'),
      },
    },
    yAxis: units.map((unit, index) => ({
      type: 'value',
      name: unit,
      nameTextStyle: {
        fontSize: unitFontSize,
      },
      axisLabel: {
        fontSize: axisFontSize,
      },
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
        lineStyle: {
          width: isFullscreen.value ? 3 : 2,
          type: 'dashed',
          color: mixHexColor(metric.color, '#ffffff', 0.42),
        },
        z: 2,
        data: metric.baseline_curve.map((point) => [point.timestamp, point.value]),
      },
      {
        name: `${metric.metric_name}-${t('dashboard.chart.currentProduction')}`,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: units.indexOf(metric.unit),
        lineStyle: {
          width: isFullscreen.value ? (index === 0 ? 4 : 3) : index === 0 ? 2.5 : 2,
          color: metric.color,
        },
        areaStyle: index === 0 ? { color: metric.color, opacity: 0.05 } : undefined,
        z: 4,
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
        markLine:
          index === 0 && props.heatCoreWindow
            ? {
                symbol: 'none',
                label: { show: false },
                lineStyle: {
                  color: 'rgba(15, 23, 42, 0.42)',
                  type: 'dashed',
                  width: isFullscreen.value ? 2 : 1.5,
                },
                data: [
                  { xAxis: props.heatCoreWindow.start },
                  { xAxis: props.heatCoreWindow.end },
                ],
              }
            : undefined,
        data: metric.current_curve.map((point) => [point.timestamp, point.value]),
      },
    ]),
    dataZoom: firstCurrentCurve.length > 120 ? [{ type: 'inside' }] : undefined,
  }
})

const compareRuntimeSeriesSummary = computed(() =>
  JSON.stringify(summarizeChartSeries(compareOption.value))
)

const compareChartWindowAttrs = computed(() => ({
  displayStart: props.compareContextWindow?.start ?? '',
  displayEnd: props.compareContextWindow?.end ?? '',
  coreStart: props.heatCoreWindow?.start ?? '',
  coreEnd: props.heatCoreWindow?.end ?? '',
}))

const chartClassName = computed(() => (isFullscreen.value ? 'h-[78vh] min-h-[560px]' : 'h-80'))
const chartTestId = computed(() =>
  isFullscreen.value ? 'heat-compare-fullscreen-chart' : 'heat-compare-chart'
)

function handleBaselineChange(value: string | number) {
  emit('update:activeBaselineId', String(value))
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <h3 class="text-sm font-bold text-slate-800 flex items-center gap-2">
        <span class="material-symbols-outlined text-primary text-[20px]">ssid_chart</span>
        {{ t('heat.compareWithBaseline') }}
      </h3>
      <div class="flex flex-wrap items-center gap-3">
        <el-tabs
          :model-value="selectedComparison?.baseline.id || activeBaselineId"
          class="-mb-[15px] mr-2"
          @update:model-value="handleBaselineChange"
        >
          <el-tab-pane
            v-for="item in baselineComparisons"
            :key="item.baseline.id"
            :name="item.baseline.id"
            :label="item.baseline.name"
          />
        </el-tabs>
        <el-button
          v-if="showFullscreenButton"
          data-testid="heat-compare-fullscreen-button"
          @click="emit('openFullscreen')"
        >
          {{ t('heat.compareFullscreen') }}
        </el-button>
      </div>
    </div>

    <div
      v-if="selectedComparisonOverlap"
      class="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800"
      data-testid="heat-compare-overlap-note"
    >
      {{
        t('heat.compareOverlapHint', {
          metric: selectedComparisonOverlap.metricName,
          baseline: selectedComparisonOverlap.baselineName,
        })
      }}
    </div>

    <div
      v-if="selectedComparisonMissingCurrentMetrics.length > 0"
      class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
      data-testid="heat-compare-missing-current-note"
    >
      {{
        t('heat.compareMissingCurrentHint', {
          metrics: selectedComparisonMissingCurrentMetrics.join(' / '),
        })
      }}
    </div>

    <v-chart
      :key="compareChartKey"
      :option="compareOption"
      autoresize
      :class="chartClassName"
      :data-testid="chartTestId"
      :data-series-count="compareSeriesCount"
      :data-runtime-series-summary="compareRuntimeSeriesSummary"
      :data-active-baseline-id="selectedComparison?.baseline.id || ''"
      :data-active-baseline-name="selectedComparison?.baseline.name || ''"
      :data-display-start="compareChartWindowAttrs.displayStart"
      :data-display-end="compareChartWindowAttrs.displayEnd"
      :data-core-start="compareChartWindowAttrs.coreStart"
      :data-core-end="compareChartWindowAttrs.coreEnd"
    />
  </div>
</template>
