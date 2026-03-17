<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import type { EChartsOption } from 'echarts'
import dayjs from 'dayjs'

use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
])

const { t } = useI18n()

type TimeRange = '5m' | '1h' | '6h' | '24h'

interface CurvePoint {
  timestamp: number
  value: number
}

interface Props {
  power: CurvePoint[]
  baselinePower: CurvePoint[]
  selectedRange: TimeRange
  baselineName?: string | null
  powerSourceLabel?: string | null
  voltageSourceLabel?: string | null
}

interface Emits {
  (e: 'range-change', value: TimeRange): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const timeRanges = [
  { key: '5m' as TimeRange },
  { key: '1h' as TimeRange },
  { key: '6h' as TimeRange },
  { key: '24h' as TimeRange },
]

const xAxisLabels = computed(() =>
  props.power.map((item) => dayjs(item.timestamp).format('HH:mm'))
)

const powerSeries = computed(() => props.power.map((item) => item.value))
const baselineSeries = computed(() =>
  props.baselinePower.map((item) => item.value)
)

const option = computed<EChartsOption>(() => ({
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true,
  },
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'cross',
      label: {
        backgroundColor: '#334155',
      },
    },
  },
  legend: {
    data: [
      t('dashboard.chart.goldenBaseline'),
      t('dashboard.chart.currentProduction'),
    ],
    top: 0,
    right: 0,
    icon: 'circle',
    itemWidth: 8,
    itemHeight: 8,
    textStyle: {
      fontSize: 12,
      color: '#64748b',
    },
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: xAxisLabels.value,
    axisLine: { lineStyle: { color: '#e2e8f0' } },
    axisLabel: {
      color: '#94a3b8',
      fontSize: 11,
      interval:
        props.selectedRange === '24h'
          ? Math.max(Math.floor(props.power.length / 10), 1)
          : props.selectedRange === '6h'
            ? Math.max(Math.floor(props.power.length / 8), 1)
            : 'auto',
    },
  },
  yAxis: {
    type: 'value',
    name: `${t('dashboard.chart.power')} (kW)`,
    nameTextStyle: { color: '#94a3b8', fontSize: 11 },
    axisLine: { show: false },
    splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    axisLabel: { color: '#94a3b8', fontSize: 11 },
  },
  series: [
    {
      name: t('dashboard.chart.goldenBaseline'),
      type: 'line',
      smooth: true,
      lineStyle: {
        width: 2,
        type: 'dashed',
        color: '#f59e0b',
      },
      showSymbol: false,
      areaStyle: {
        opacity: 0.05,
        color: '#f59e0b',
      },
      emphasis: {
        focus: 'series',
      },
      data: baselineSeries.value,
    },
    {
      name: t('dashboard.chart.currentProduction'),
      type: 'line',
      smooth: true,
      lineStyle: {
        width: 2.5,
        color: '#1152d4',
      },
      showSymbol: false,
      areaStyle: {
        opacity: 0.08,
        color: '#1152d4',
      },
      emphasis: {
        focus: 'series',
      },
      data: powerSeries.value,
    },
  ],
}))
</script>

<template>
  <div
    class="bg-white p-6 rounded-xl shadow-card border border-border-light h-full flex flex-col"
  >
    <div class="flex justify-between items-center mb-6">
      <div class="flex items-center gap-3">
        <span class="material-symbols-outlined text-primary text-[24px]">ssid_chart</span>
        <div>
          <h3 class="text-base font-bold text-slate-800">
            {{ t('dashboard.realtimeCurve') }}
          </h3>
          <p class="text-xs text-slate-400 mt-0.5">
            当前炉次 #H-20231025-08 vs {{ baselineName || '黄金基线 V3.2' }} · {{ t(`dashboard.timeRange.${selectedRange}`) }}
          </p>
        </div>
      </div>
      <div class="flex bg-slate-100 p-1 rounded-lg">
        <button
          v-for="range in timeRanges"
          :key="range.key"
          :data-testid="`dashboard-range-${range.key}`"
          :class="[
            'px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200',
            selectedRange === range.key
              ? 'bg-white text-primary shadow-sm font-bold'
              : 'text-slate-500 hover:text-slate-700',
          ]"
          @click="emit('range-change', range.key)"
        >
          {{ t(`dashboard.timeRange.${range.key}`) }}
        </button>
      </div>
    </div>

    <div class="flex-1 min-h-[300px]">
      <v-chart
        class="w-full h-full"
        :option="option"
        autoresize
      />
    </div>

    <div
      class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2"
      data-testid="dashboard-source-summary"
    >
      <div class="rounded-lg border border-border-light bg-slate-50 px-4 py-3">
        <div class="text-xs uppercase tracking-wider text-slate-400">
          功率来源
        </div>
        <div class="mt-1 text-sm font-medium text-slate-700">
          {{ powerSourceLabel || '未绑定宿主通道' }}
        </div>
      </div>
      <div class="rounded-lg border border-border-light bg-slate-50 px-4 py-3">
        <div class="text-xs uppercase tracking-wider text-slate-400">
          电压来源
        </div>
        <div class="mt-1 text-sm font-medium text-slate-700">
          {{ voltageSourceLabel || '未绑定宿主通道' }}
        </div>
      </div>
    </div>
  </div>
</template>
