<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElButton, ElCard, ElEmpty, ElMessage, ElTag } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'
import dayjs from 'dayjs'
import { useHeatStore } from '@/stores/heat'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const heatStore = useHeatStore()

const heatId = computed(() => String(route.params.id || ''))
const current = computed(() => heatStore.current)

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
        data: current.value.baselinePowerCurve.map(point => point.value)
      },
      {
        name: t('dashboard.chart.currentProduction'),
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#409EFF' },
        markArea: {
          itemStyle: { color: 'rgba(245, 108, 108, 0.18)' },
          data: current.value.deviationRanges.map(range => {
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

function handleBack() {
  router.push('/heats')
}

function handleCreateTask() {
  ElMessage.info(t('heat.createTaskHint'))
}

onMounted(() => {
  if (!heatId.value) return
  void heatStore.fetchDetail(heatId.value)
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between gap-4 flex-wrap">
      <div>
        <div class="text-sm text-gray-500">
          {{ t('heat.detailTitle') }}
        </div>
        <div class="mt-1 flex items-center gap-3">
          <h1 class="text-2xl font-bold text-gray-900">
            {{ current?.base.heatNo || '--' }}
          </h1>
          <el-tag :type="statusTagType">
            {{ statusText }}
          </el-tag>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <el-button @click="handleBack">
          {{ t('common.back') }}
        </el-button>
        <el-button
          type="primary"
          :icon="Plus"
          @click="handleCreateTask"
        >
          {{ t('heat.createTask') }}
        </el-button>
      </div>
    </div>

    <div
      v-if="current"
      class="grid grid-cols-1 gap-4 xl:grid-cols-3"
    >
      <el-card class="xl:col-span-2">
        <template #header>
          <span>{{ t('heat.compareWithBaseline') }}</span>
        </template>
        <v-chart
          :option="compareOption"
          autoresize
          class="h-80"
        />
      </el-card>

      <el-card>
        <template #header>
          <span>{{ t('heat.detailSummary') }}</span>
        </template>
        <div class="space-y-3 text-sm text-gray-700">
          <div>
            <span class="text-gray-500">{{ t('heat.startTime') }}:</span>
            <span class="ml-2 font-medium">{{ current.base.startTime }}</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.endTime') }}:</span>
            <span class="ml-2 font-medium">{{ current.base.endTime }}</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.deviation') }}:</span>
            <span class="ml-2 font-medium">{{ current.base.deviationPercent ?? '--' }}%</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.avgDeviation') }}:</span>
            <span class="ml-2 font-medium">{{ current.base.avgDeviationPercent ?? '--' }}%</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.maxDeviation') }}:</span>
            <span class="ml-2 font-medium">{{ current.maxDeviation ?? '--' }}%</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.temperature') }}:</span>
            <span class="ml-2 font-medium">{{ current.base.temperature ?? '--' }}</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.baselineName') }}:</span>
            <span class="ml-2 font-medium">{{ current.baselineName || '--' }}</span>
          </div>
        </div>
      </el-card>
    </div>

    <el-card v-if="current">
      <template #header>
        <span>{{ t('heat.abnormalRanges') }}</span>
      </template>
      <div
        v-if="current.deviationRanges.length > 0"
        class="space-y-2 text-sm"
      >
        <div
          v-for="(range, idx) in current.deviationRanges"
          :key="`${range.start}-${range.end}`"
          class="rounded-md border border-red-200 bg-red-50 p-3"
        >
          <span class="font-medium">{{ t('heat.range') }} {{ idx + 1 }}:</span>
          <span class="ml-2">
            {{ dayjs(range.start).format('HH:mm:ss') }} - {{ dayjs(range.end).format('HH:mm:ss') }}
          </span>
          <span class="ml-2 text-red-600">({{ range.deviation }}%)</span>
        </div>
      </div>
      <el-empty
        v-else
        :description="t('common.noData')"
      />
    </el-card>

    <el-empty
      v-else
      :description="t('common.loading')"
    />
  </div>
</template>
