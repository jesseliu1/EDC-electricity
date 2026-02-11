<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ElButton,
  ElCard,
  ElDatePicker,
  ElEmpty,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElTabPane,
  ElTabs,
  ElTag
} from 'element-plus'
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

const editingDescription = ref(false)
const descriptionDraft = ref('')
const editingTiming = ref(false)
const timingDraft = ref<[Date, Date] | null>(null)
const activeBaselineId = ref('')

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
        data: (selectedComparison.value?.baseline.power_curve || current.value.baselinePowerCurve).map(
          point => point.value
        )
      },
      {
        name: t('dashboard.chart.currentProduction'),
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#409EFF' },
        markArea: {
          itemStyle: { color: 'rgba(245, 108, 108, 0.18)' },
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

function handleBack() {
  router.push('/heats')
}

function handleCreateTask() {
  ElMessage.info(t('heat.createTaskHint'))
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
    await ElMessageBox.confirm(
      t('heat.adjustSubsequentConfirm'),
      t('common.confirm'),
      {
        distinguishCancelAndClose: true,
        confirmButtonText: t('heat.adjustSubsequentYes'),
        cancelButtonText: t('heat.adjustSubsequentNo'),
        type: 'warning'
      }
    )
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
        <el-button
          v-if="current?.base.cutStatus === 'major_issue' || current?.base.cutStatus === 'blocked'"
          type="warning"
          @click="handleResumeCutting"
        >
          {{ t('heat.resumeCutting') }}
        </el-button>
      </div>
    </div>

    <div
      v-if="current"
      class="grid grid-cols-1 gap-4 xl:grid-cols-3"
    >
      <el-card class="xl:col-span-2">
        <template #header>
          <div class="space-y-3">
            <span>{{ t('heat.compareWithBaseline') }}</span>
            <el-tabs v-model="activeBaselineId" type="border-card">
              <el-tab-pane
                v-for="item in current.baselineComparisons"
                :key="item.baseline.id"
                :name="item.baseline.id"
                :label="item.baseline.name"
              />
            </el-tabs>
          </div>
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
            <span class="text-gray-500">{{ t('heat.description') }}:</span>
            <template v-if="!editingDescription">
              <span class="ml-2 font-medium">{{ current.base.description || t('common.noDescription') }}</span>
              <el-button
                type="primary"
                link
                class="ml-2"
                @click="startEditDescription"
              >
                {{ t('common.edit') }}
              </el-button>
            </template>
            <template v-else>
              <el-input
                v-model="descriptionDraft"
                class="ml-2 inline-block w-64"
                size="small"
                @keyup.enter="saveDescription"
              />
              <el-button
                type="primary"
                link
                class="ml-1"
                @click="saveDescription"
              >
                {{ t('common.save') }}
              </el-button>
              <el-button
                link
                class="ml-1"
                @click="editingDescription = false"
              >
                {{ t('common.cancel') }}
              </el-button>
            </template>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.startTime') }}:</span>
            <template v-if="!editingTiming">
              <span class="ml-2 font-medium">{{ current.base.startTime }}</span>
            </template>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.endTime') }}:</span>
            <template v-if="!editingTiming">
              <span class="ml-2 font-medium">{{ current.base.endTime }}</span>
              <el-button type="primary" link class="ml-2" @click="startEditTiming">
                {{ t('heat.editTiming') }}
              </el-button>
            </template>
            <template v-else>
              <el-date-picker
                v-model="timingDraft"
                type="datetimerange"
                :range-separator="t('heat.to')"
                :start-placeholder="t('heat.startTime')"
                :end-placeholder="t('heat.endTime')"
              />
              <el-button type="primary" link class="ml-2" @click="saveTiming">
                {{ t('common.save') }}
              </el-button>
              <el-button link class="ml-1" @click="editingTiming = false">
                {{ t('common.cancel') }}
              </el-button>
            </template>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.cutStatus') }}:</span>
            <span class="ml-2 font-medium">{{ t(`heat.cutStatus${current.base.cutStatus}`) }}</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.timeOffsetPercent') }}:</span>
            <span class="ml-2 font-medium">
              {{ current.base.timeOffsetPercent === null ? '--' : `${current.base.timeOffsetPercent}%` }}
            </span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.temperature') }}:</span>
            <span class="ml-2 font-medium">{{ current.base.temperature ?? '--' }}</span>
          </div>
          <div>
            <span class="text-gray-500">{{ t('heat.baselineName') }}:</span>
            <span class="ml-2 font-medium">{{ selectedComparison?.baseline.name || '--' }}</span>
          </div>
        </div>
      </el-card>
    </div>

    <el-card v-if="current">
      <template #header>
        <span>{{ t('heat.abnormalRanges') }}</span>
      </template>
      <div
        v-if="(selectedComparison?.deviation_ranges || current.deviationRanges).length > 0"
        class="space-y-2 text-sm"
      >
        <div
          v-for="(range, idx) in selectedComparison?.deviation_ranges || current.deviationRanges"
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
