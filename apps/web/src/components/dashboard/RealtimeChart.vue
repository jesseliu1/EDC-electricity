<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'
import dayjs from 'dayjs'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

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
  { key: '24h' as TimeRange }
]

const xAxisLabels = computed(() =>
  props.power.map(item => dayjs(item.timestamp).format('HH:mm'))
)

const powerSeries = computed(() => props.power.map(item => item.value))
const baselineSeries = computed(() => props.baselinePower.map(item => item.value))

const option = computed<EChartsOption>(() => ({
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'cross',
      label: {
        backgroundColor: '#6a7985'
      }
    }
  },
  legend: {
    data: [t('dashboard.chart.goldenBaseline'), t('dashboard.chart.currentProduction')],
    top: 0
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: xAxisLabels.value
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
      lineStyle: {
        width: 2,
        type: 'dashed',
        color: '#67C23A' // Success color
      },
      showSymbol: false,
      areaStyle: {
        opacity: 0.1,
        color: '#67C23A'
      },
      emphasis: {
        focus: 'series'
      },
      data: baselineSeries.value
    },
    {
      name: t('dashboard.chart.currentProduction'),
      type: 'line',
      smooth: true,
      lineStyle: {
        width: 2,
        color: '#409EFF' // Primary color
      },
      showSymbol: false,
      areaStyle: {
        opacity: 0.1,
        color: '#409EFF'
      },
      emphasis: {
        focus: 'series'
      },
      data: powerSeries.value
    }
  ]
}))
</script>

<template>
  <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 h-full flex flex-col">
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-800">
        {{ t('dashboard.realtimeCurve') }}
      </h3>
      <div class="flex bg-gray-100 p-1 rounded-lg">
        <button
          v-for="range in timeRanges"
          :key="range.key"
          :class="[
            'px-3 py-1 text-xs font-medium rounded-md transition-all duration-200',
            selectedRange === range.key
              ? 'bg-white text-primary shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          ]"
          @click="emit('range-change', range.key)"
        >
          {{ t(`dashboard.timeRange.${range.key}`) }}
        </button>
      </div>
    </div>
    
    <div class="flex-1 min-h-[300px]">
      <v-chart
        class="chart"
        :option="option"
        autoresize
      />
    </div>
  </div>
</template>

<style scoped>
.chart {
  height: 100%;
  width: 100%;
}
.text-primary {
  color: var(--el-color-primary);
}
</style>
